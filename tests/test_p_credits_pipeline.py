"""Recurring card credits (ENG-01), part 2: the invented acceptance scenarios, and how terms and personal records
get in, get corrected and stay auditable.

Every test works on a private copy of the synthetic recurring-credit fixture (built once, through the tables and the
ordinary changeset pipeline) and changes it only the way a maintainer would. All data here is invented.
"""
import contextlib
import filecmp
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

import util  # noqa: F401  (sets sys.path)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "fixtures"))

import synthetic_credits  # noqa: E402
from synthetic_credits import edit_table  # noqa: E402
from prices import changes, credits, tables  # noqa: E402
from prices.cli import main  # noqa: E402
from prices.engine import ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate  # noqa: E402
from prices.lint import lint  # noqa: E402
from prices.store import Store, read_audit  # noqa: E402

D = "2027-07-10"                                   # "today" for new changesets: after everything in the fixture
ALEX, BLAKE, ERIN, FINN = "synthetic-alex", "synthetic-blake", "synthetic-erin", "synthetic-finn"
OWNER = dict(synthetic_credits.OWNERS, **{BLAKE: "Blake (synthetic)"})
CARD, ACCT = synthetic_credits.CARD, synthetic_credits.ACCOUNT
REVIEW = {"by": "Synthetic Reviewer", "on": D, "statement": "Synthetic review."}
B = "benefit.voyager."
HOTEL, DINING, RIDE, TRAVEL, FEE, STREAM, LIFE, WELL = (B + x for x in (
    "curated-hotel-credit", "dining-credit", "ride-credit", "travel-credit", "traveler-fee-credit", "streaming-credit", "lifestyle-credit", "wellness-credit"))
HOTEL_TERMS = {"amount": 500, "unit": "USD", "cycle": "calendar_year", "max_per_transaction": 250, "min_stay_nights": 2, "rollover": "none"}


def source(sid, **kw):
    return dict({"id": sid, "url": "https://example.invalid/northwind/" + sid, "title": "Northwind Voyager credit terms, re-read",
                 "publisher": "Northwind Bank (synthetic)", "source_type": "synthetic", "retrieved_on": D, "applies_to": [CARD],
                 "summary": "Invented source for a test."}, **kw)


def tree(base):
    return sorted(os.path.relpath(os.path.join(d, n), base) for d, _s, names in os.walk(base) for n in names)


def cli(root, *argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = main(["--root", root] + list(argv))
    return code, out.getvalue()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.class_tmp = tempfile.mkdtemp(prefix="prices-credits-")
        cls.built = synthetic_credits.build(os.path.join(cls.class_tmp, "fx"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.class_tmp)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prices-credits-")
        self.root = shutil.copytree(self.built, os.path.join(self.tmp, "fx"))
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def store(self):
        return Store.load(self.root)

    def cs(self, op, person=None, by="owner", date=D, **kw):
        self.n += 1
        c = dict({"id": "cs-test-%03d-%s" % (self.n, op.replace("_", "-")), "op": op, "author": "test maintainer", "date": date, "reason": "test"}, **kw)
        if person:
            c["profile"] = person
        if by is not None and "attestation" not in c and person:
            c["attestation"] = {"by": OWNER.get(person, by) if by == "owner" else by, "on": date, "statement": "Invented statement for a test."}
        return c

    def ok(self, c):
        out = changes.apply(self.root, c)
        self.assertTrue(out["ok"], out["errors"])
        return out

    def no(self, c, code):
        """Rejected with this code, and nothing but the audit log changed."""
        before, files, log = self.store().digest(), tree(self.root), read_audit(self.root)
        out = changes.apply(self.root, c)
        self.assertFalse(out["ok"], "%s should have been rejected" % c["id"])
        self.assertTrue(any(e.startswith(code) or (": " + code) in e or (" " + code + " ") in e for e in out["errors"]), "expected %s, got %s" % (code, out["errors"]))
        self.assertEqual(self.store().digest(), before, "a rejected changeset must not change any record")
        self.assertEqual(tree(self.root), files)
        self.assertEqual((len(read_audit(self.root)), read_audit(self.root)[-1]["result"]), (len(log) + 1, "rejected"))
        return out

    def terms(self, target, block=None, evidence=None, **kw):
        c = self.cs("set_credit_terms", target=target, data={"remove": True} if block is None else {"credit": block}, **kw)
        if evidence:
            c["evidence"] = evidence
        return c

    def period(self, person, eid, rule, cycle, start, end, amount, state="confirmed", by="owner", **extra):
        return self.cs("record_entitlement", person, by, data={"entitlement": dict(
            {"id": eid, "rule": rule, "account": ACCT, "cycle": cycle, "state": state, "effective_from": start, "expires_on": end,
             "allowance": {"amount": amount, "unit": "USD"}}, **extra)})

    def use(self, person, target, uid, amount, used_on, state="confirmed", by="owner", **extra):
        return self.cs("record_usage", person, by, target=target, data={"usage": dict({"id": uid, "amount": amount, "used_on": used_on, "state": state}, **extra)})

    def row(self, person, benefit, day, **kw):
        for a in credits.survey(self.store(), person, day, **kw)["accounts"]:
            for c in a["credits"]:
                if c["benefit"] == benefit:
                    return c
        return None

    def picture(self, person, day):
        """{benefit: (applies, period label, start, end, published allowance, personal state, remaining)}"""
        out = {}
        for a in credits.survey(self.store(), person, day)["accounts"]:
            for c in a["credits"]:
                p, me = c["period"], c["personal"]
                out[c["benefit"]] = (c["applies"]["status"], p.get("label"), p.get("start"), p.get("end"),
                                     c.get("allowance", {}).get("amount"), me["state"], me.get("remaining"))
        return out

    def imported(self, **kw):
        return tables.import_tables(self.root, "tables", "test maintainer", D, **kw)


class TestFixture(Base):
    def test_committed_fixture_is_exactly_what_the_builder_produces(self):
        committed = os.path.join(ROOT, "fixtures", "synthetic-credits")
        self.assertEqual(tree(committed), tree(self.root))
        _same, diff, errs = filecmp.cmpfiles(committed, self.root, tree(committed), shallow=False)
        self.assertEqual((diff, errs), ([], []))

    def test_fixture_is_valid_and_every_term_came_through_the_tables_and_the_pipeline(self):
        s = self.store()
        self.assertEqual(lint(s), [])
        self.assertEqual(tables.status(self.root), {"exists": True, "stale": [], "edited": []})
        log = [e for e in read_audit(self.root) if e["result"] == "applied"]
        ops = [e["op"] for e in log if "-tbl-" in e["changeset"] and "credit" not in e["changeset"][:11]]
        self.assertEqual((ops.count("add_candidate"), ops.count("set_credit_terms"), ops.count("revise_rule")), (15, 1, 1))   # 8 from the card fixture + 7
        self.assertEqual(len([r for r in s.rules.values() if "credit" in r]), 8)
        self.assertEqual([c["id"] for c in s.candidates.values() if c["status"] == "proposed"], [])
        self.assertTrue(all(s.profile(p).meta["synthetic"] for p in s.profile_names()))

    def test_before_and_after_for_the_credit_that_was_prose_only(self):
        before = Store.load(os.path.join(ROOT, "fixtures", "synthetic-cards")).rules["voyager.travel-credit"]
        after = self.store().rules["voyager.travel-credit"]
        self.assertNotIn("credit", before)
        self.assertEqual(before["summary"], "200 annual travel credit per cardmember year.")
        self.assertEqual(after["credit"], {"amount": 300, "unit": "USD", "cycle": "anniversary_year"})
        self.assertEqual((after["summary"], after["evidence"]), ("300 annual travel credit per cardmember year.", ["ev-syn-voyager-guide", "ev-syn-voyager-credit-terms"]))
        self.assertEqual({k: after[k] for k in ("id", "kind", "output", "when")}, {k: before[k] for k in ("id", "kind", "output", "when")})   # stable identity
        cs_id = next(e["changeset"] for e in read_audit(self.root) if e["op"] == "set_credit_terms")
        with open(os.path.join(self.root, "data/audit/previous", cs_id + ".json"), encoding="utf-8") as f:
            snap = json.load(f)["records"]["data/kb/rules/voyager.travel-credit.json"]["before"]
        self.assertNotIn("credit", snap)                                             # the record as it was is preserved

    def test_people_without_credit_terms_on_their_card_are_unaffected(self):
        s, cards = self.store(), Store.load(os.path.join(ROOT, "fixtures", "synthetic-cards"))
        new = {r["id"] for r in s.rules.values()} - {r["id"] for r in cards.rules.values()}
        for day in ("2026-11-14", "2027-06-01", "2028-03-01"):
            a, b = evaluate(cards, BLAKE, day).report(), evaluate(s, BLAKE, day).report()
            b["flags"] = [f for f in b["flags"] if f["subject"] not in new]          # new rules go stale after their review date, like any rule
            self.assertEqual([k for k in a if a[k] != b[k]], ["sourced_rules"], day)
        self.assertEqual(credits.survey(s, BLAKE, "2027-06-01")["accounts"], [])
        code, text = cli(self.root, "credits", "--profile", BLAKE, "--as-of", "2027-06-01")
        self.assertIn("No card this person holds on this date has structured credit terms in force.", text)

    def test_the_live_data_has_no_credit_terms_and_no_personal_credit_records(self):
        live = Store.load(ROOT)
        self.assertEqual([r["id"] for r in live.rules.values() if "credit" in r], [])
        self.assertEqual([c["id"] for c in live.candidates.values() if "credit" in c["proposed_rule"]], [])      # Argon's candidates are untouched
        self.assertEqual(sum(c["status"] == "proposed" for c in live.candidates.values()), 113)
        self.assertEqual(len(live.rules), 10)
        for name in live.profile_names():
            self.assertEqual(live.profile(name).entitlements, {}, name)
            self.assertEqual(credits.survey(live, name, "2026-11-15")["accounts"], [], name)
        with open(os.path.join(ROOT, "tables", "credits.csv"), encoding="utf-8") as f:
            self.assertEqual(len(f.read().splitlines()), 1)                           # header only


class TestAcceptanceScenarios(Base):
    def test_alex_published_periods_and_personal_records(self):
        got = self.picture(ALEX, "2027-03-10")
        self.assertEqual(got, {
            TRAVEL: (ESTABLISHED, "2026", "2026-03-15", "2027-03-14", 300, "NOT_RECORDED", None),            # A  anniversary 15 March
            HOTEL: (ESTABLISHED, "2027", "2027-01-01", "2027-12-31", 500, "ACTIVE", 250),                    # B  250 of 500 used
            DINING: (ESTABLISHED, "2027-H1", "2027-01-01", "2027-06-30", 150, "EXHAUSTED", 0),               # C
            RIDE: (ESTABLISHED, "2027-03", "2027-03-01", "2027-03-31", 10, "NOT_RECORDED", None),            # D
            STREAM: (ESTABLISHED, "2027-Q1", "2027-01-01", "2027-03-31", 20, "NOT_RECORDED", None),
            FEE: (ESTABLISHED, "2025", "2025-09-10", "2029-09-09", 120, "EXHAUSTED", 0),
            LIFE: (ESTABLISHED, "2027", "2027-01-01", "2027-12-31", 200, "NOT_RECORDED", None),              # G  elected
            WELL: (NOT_AVAILABLE, "2027-03", "2027-03-01", "2027-03-31", None, "NOT_RECORDED", None)})       # G  the other option
        hotel = self.row(ALEX, HOTEL, "2027-03-10")
        self.assertEqual((hotel["terms"]["max_per_transaction"], hotel["terms"]["min_stay_nights"]), (250, 2))
        self.assertTrue(hotel["personal"]["established"])

    def test_alex_boundaries_resets_and_expiration(self):
        steps = [("2027-03-14", TRAVEL, "2026", 300), ("2027-03-15", TRAVEL, "2027", 300),                   # anniversary reset
                 ("2027-06-30", DINING, "2027-H1", 150), ("2027-07-01", DINING, "2027-H2", 150),             # half-year reset
                 ("2027-03-31", RIDE, "2027-03", 10), ("2027-04-01", RIDE, "2027-04", 10),                   # monthly reset
                 ("2027-09-30", RIDE, "2027-09", 10), ("2027-10-01", RIDE, None, None),                      # the offer has ended
                 ("2027-12-31", HOTEL, "2027", 500), ("2028-01-01", HOTEL, "2028", 500),                     # calendar-year reset
                 ("2029-09-09", FEE, "2025", 120), ("2029-09-10", FEE, None, 120)]                           # four years after the last use
        for day, benefit, label, amount in steps:
            got = self.picture(ALEX, day)[benefit]
            self.assertEqual((got[1], got[4]), (label, amount), (day, benefit))
        self.assertEqual(self.picture(ALEX, "2027-06-30")[DINING][5:], ("EXHAUSTED", 0))
        self.assertEqual(self.picture(ALEX, "2027-07-01")[DINING][5:], ("NOT_RECORDED", None))               # no rollover, and nothing assumed for H2
        self.assertEqual(self.picture(ALEX, "2028-01-01")[HOTEL][5:], ("NOT_RECORDED", None))                # 2027's record is not 2028's
        self.assertEqual(self.picture(ALEX, "2027-10-01")[RIDE][0], NOT_AVAILABLE)
        july = self.row(ALEX, HOTEL, "2027-07-01")["personal"]
        self.assertEqual((july["used"], july["possibly_used"], july["remaining"], july["remaining_at_least"], july["established"]), (250, 180, 250, 70, False))

    def test_erin_has_a_different_anniversary_and_no_election(self):
        got = self.picture(ERIN, "2027-03-10")
        self.assertEqual(got[TRAVEL], (ESTABLISHED, "2026", "2026-11-02", "2027-11-01", 300, "ACTIVE", 180))  # E
        self.assertEqual((got[LIFE][0], got[WELL][0]), (UNRESOLVED, UNRESOLVED))                              # G  no election: neither established
        self.assertEqual(got[FEE][:2], (ESTABLISHED, None))                                                   # no use recorded: period unresolved
        self.assertEqual(self.picture(ERIN, "2027-11-01")[TRAVEL][1], "2026")
        self.assertEqual(self.picture(ERIN, "2027-11-02")[TRAVEL][1:], ("2027", "2027-11-02", "2028-11-01", 300, "NOT_RECORDED", None))
        self.assertEqual(self.picture(ERIN, "2027-03-10")[HOTEL], self.picture(FINN, "2027-03-10")[HOTEL])    # calendar credits agree for everyone

    def test_finn_has_no_opening_date_on_file(self):
        c = self.row(FINN, TRAVEL, "2027-03-10")
        self.assertEqual((c["applies"]["status"], c["period"]["state"]), (ESTABLISHED, "UNRESOLVED"))         # F
        self.assertIn("opening date of account h-card-northwind-voyager is not recorded", c["period"]["reason"])
        self.assertNotIn("allowance", c)
        self.assertNotIn("opened_on", self.store().profile(FINN).holdings[ACCT])                              # nothing was filled in
        got = self.picture(FINN, "2027-03-10")
        self.assertEqual((got[WELL][0], got[LIFE][0]), (ESTABLISHED, NOT_AVAILABLE))
        # once the owner gives the date, the period resolves
        self.ok(self.cs("set_holding", FINN, data={"holding": {"id": ACCT, "entity": CARD, "state": "confirmed", "valid_from": "2026-05-01",
                                                                "opened_on": "2026-05-01"}}))
        self.assertEqual(self.picture(FINN, "2027-03-10")[TRAVEL][:5], (ESTABLISHED, "2026", "2026-05-01", "2027-04-30", 300))

    def test_election_safeguards_still_hold_for_credits(self):
        s = self.store()
        for person in (ALEX, ERIN, FINN):
            for day in ("2026-06-01", "2027-03-10", "2028-01-01"):
                r = evaluate(s, person, day)
                self.assertNotEqual((r.have(LIFE), r.have(WELL)), (ESTABLISHED, ESTABLISHED), (person, day))
        self.ok(self.cs("set_holding", ERIN, data={"holding": {"id": "el-annual-perk", "entity": "election.voyager.wellness-credit",
                                                                "state": "confirmed", "valid_from": "2027-01-01"}}))
        got = self.picture(ERIN, "2027-03-10")
        self.assertEqual((got[WELL][0], got[WELL][4], got[LIFE][0], got[LIFE][4]), (ESTABLISHED, 25, NOT_AVAILABLE, None))
        self.ok(self.cs("set_holding", ERIN, by=None, data={"holding": {"id": "el-2", "entity": "election.voyager.lifestyle-credit",
                                                                         "state": "unconfirmed", "valid_from": "2027-02-01"}}))
        got = self.picture(ERIN, "2027-03-10")
        self.assertEqual((got[WELL][0], got[LIFE][0]), (UNRESOLVED, UNRESOLVED))                              # contradictory: neither


class TestTermsOperation(Base):
    def test_correcting_terms_of_a_rule_in_force_needs_evidence_and_keeps_history(self):
        fixed = dict(HOTEL_TERMS, max_per_transaction=200)
        self.no(self.terms("voyager.curated-hotel-credit", fixed), "EVIDENCE_REQUIRED")
        weak = source("ev-test-blog", source_type="reputable_secondary")
        self.no(self.terms("voyager.curated-hotel-credit", fixed, [weak]), "INSUFFICIENT_EVIDENCE")
        c = self.terms("voyager.curated-hotel-credit", fixed, [source("ev-test-reread")])
        self.ok(c)
        r = self.store().rules["voyager.curated-hotel-credit"]
        self.assertEqual((r["credit"], r["evidence"]), (fixed, ["ev-syn-voyager-credit-terms", "ev-test-reread"]))
        self.assertEqual(r["verification"], Store.load(self.built).rules["voyager.curated-hotel-credit"]["verification"])   # not a re-verification
        self.assertEqual(self.row(ALEX, HOTEL, "2027-03-10")["terms"]["max_per_transaction"], 200)
        with open(os.path.join(self.root, "data/audit/previous", c["id"] + ".json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["records"]["data/kb/rules/voyager.curated-hotel-credit.json"]["before"]["credit"], HOTEL_TERMS)
        last = read_audit(self.root)[-1]
        self.assertEqual((last["op"], last["result"], sorted(last["changed"])),
                         ("set_credit_terms", "applied", ["data/kb/evidence/ev-test-reread.json", "data/kb/rules/voyager.curated-hotel-credit.json"]))
        self.no(c, "DUPLICATE_CHANGESET")                                             # the same changeset twice
        self.no(self.terms("voyager.curated-hotel-credit", fixed, [source("ev-test-reread")]), "NO_CHANGE")   # the same terms under a new id
        self.ok(self.cs("revert_changeset", data={"changeset": c["id"]}, attestation=REVIEW))
        self.assertEqual(self.store().files["data/kb/rules/voyager.curated-hotel-credit.json"],
                         Store.load(self.built).files["data/kb/rules/voyager.curated-hotel-credit.json"])

    def test_a_term_the_source_stops_stating_goes_back_to_not_stated(self):
        looser = {k: v for k, v in HOTEL_TERMS.items() if k != "min_stay_nights"}     # the complete block replaces the old one
        self.ok(self.terms("voyager.curated-hotel-credit", looser, [source("ev-test-reread")]))
        t = self.row(ALEX, HOTEL, "2027-03-10")["terms"]
        self.assertIsNone(t["min_stay_nights"])                                        # not 0, not "no minimum": not stated
        code, text = cli(self.root, "credits", "--profile", ALEX, "--as-of", "2027-03-10")
        self.assertIn("per transaction: maximum 250 USD; minimum stay not stated by the source; minimum transaction not stated by the source", text)

    def test_invalid_terms_are_refused(self):
        ev = [source("ev-test-reread")]
        t = "voyager.curated-hotel-credit"
        self.no(self.terms(t, dict(HOTEL_TERMS, amount=0), ev), "BAD_CREDIT_SHAPE")
        self.no(self.terms(t, dict(HOTEL_TERMS, cycle="weekly"), ev), "SCHEMA")
        self.no(self.terms(t, dict(HOTEL_TERMS, max_per_transaction="unlimited"), ev), "SCHEMA")
        self.no(self.terms(t, dict(HOTEL_TERMS, years=4), ev), "BAD_CREDIT_SHAPE")
        self.no(self.terms(t, {"amount": 120, "unit": "USD", "cycle": "multi_year"}, ev), "BAD_CREDIT_SHAPE")
        self.no(self.terms(t, dict(HOTEL_TERMS, rollover_max=50), ev), "BAD_CREDIT_SHAPE")
        self.no(self.terms(t, dict(HOTEL_TERMS, unlimited=True), ev), "SCHEMA")
        self.no(self.terms("voyager.no-such-credit", HOTEL_TERMS, ev), "UNKNOWN_TARGET")
        self.no(self.terms("baseline.orbit-summit.phone-protection", HOTEL_TERMS, ev), "UNEXPECTED_FIELD")     # a tier baseline is not a card benefit
        self.no(self.terms("voyager.rental-cover-superseded", HOTEL_TERMS, ev), "UNEXPECTED_FIELD")            # nor is an exclusion
        self.no(self.cs("set_credit_terms", target=t, data={"credit": HOTEL_TERMS, "remove": True}, evidence=ev), "BAD_DATA")
        self.no(self.cs("set_credit_terms", target=t, data={}, evidence=ev), "BAD_DATA")
        self.no(self.cs("set_credit_terms", data={"credit": HOTEL_TERMS}, evidence=ev), "MISSING_TARGET")
        self.no(self.terms("voyager.phone-protection", None, ev), "BAD_STATE")                                 # nothing to remove
        late = source("ev-test-late", retrieved_on="2027-08-01")
        self.no(self.terms(t, dict(HOTEL_TERMS, amount=600), [late]), "BAD_DATES")

    def test_removing_terms(self):
        self.ok(self.terms("voyager.streaming-credit", None, [source("ev-test-reread")]))
        self.assertIsNone(self.row(ALEX, STREAM, "2027-03-10"))                        # prose only again: no longer a structured credit
        self.assertEqual(evaluate(self.store(), ALEX, "2027-03-10").have(STREAM), ESTABLISHED)   # the benefit itself is untouched
        self.no(self.terms("voyager.curated-hotel-credit", None, [source("ev-test-2")]), "UNKNOWN_REFERENCE")   # a personal record depends on it

    def test_retired_rule_is_history(self):
        self.ok(self.cs("retire_rule", target="voyager.streaming-credit", data={"ended_on": "2027-06-30"}, evidence=[source("ev-test-end")]))
        self.no(self.terms("voyager.streaming-credit", dict(amount=25, unit="USD", cycle="calendar_quarter"), [source("ev-test-2")]), "RETIRED")
        gone = self.row(ALEX, STREAM, "2027-07-05")                                    # still listed, as ended: an expiration is reported, not hidden
        self.assertEqual((gone["offer"]["state"], gone["offer"]["text"], gone["period"]["state"], gone["applies"]["status"]),
                         ("ENDED", "the rule is retired (ended 2027-06-30)", "NO_OFFER", NOT_AVAILABLE))
        self.assertNotIn("allowance", gone)
        self.assertEqual(evaluate(self.store(), ALEX, "2027-07-05").have(STREAM), NOT_AVAILABLE)
        # existing engine behaviour, unchanged: once retired, a rule is treated as ended on every date, earlier ones included
        self.assertEqual(self.picture(ALEX, "2027-06-30")[STREAM][:5], (NOT_AVAILABLE, None, None, None, None))

    def test_a_candidate_gets_terms_in_place_and_stays_a_candidate(self):
        cand = {"id": "c-voyager.spa-credit", "status": "proposed", "created_on": D, "search_path": ["test"], "open_questions": [],
                "proposed_entities": [{"id": B + "spa-credit", "kind": "benefit", "name": "Northwind Voyager spa credit (synthetic)"}],
                "evidence": [source("ev-test-spa")],
                "proposed_rule": {"id": "voyager.spa-credit", "kind": "grants", "output": B + "spa-credit", "when": {"holds": CARD},
                                  "summary": "100 spa credit each calendar year."}}
        self.ok(self.cs("add_candidate", data={"candidate": cand}))
        spa = {"amount": 100, "unit": "USD", "cycle": "calendar_year"}
        self.ok(self.terms("voyager.spa-credit", spa))                                 # no reviewer, no new evidence: it is still only a proposal
        s = self.store()
        c = s.candidates["c-voyager.spa-credit"]
        self.assertEqual((c["status"], c["proposed_rule"]["id"], c["proposed_rule"]["credit"]), ("proposed", "voyager.spa-credit", spa))
        self.assertNotIn("voyager.spa-credit", s.rules)
        self.assertIsNone(self.row(ALEX, B + "spa-credit", "2027-07-10"))              # quarantined: not reported
        shown = self.row(ALEX, B + "spa-credit", "2027-07-10", include_candidates=True)
        self.assertEqual((shown["rule_state"], shown["applies"]["status"]), ("candidate", UNRESOLVED))
        self.assertEqual(evaluate(s, ALEX, "2027-07-10").have(B + "spa-credit"), NOT_AVAILABLE)
        self.no(self.period(ALEX, "e-spa", "voyager.spa-credit", "2027", "2027-01-01", "2027-12-31", 100), "UNKNOWN_RULE")   # no balance on a proposal
        self.ok(self.terms("voyager.spa-credit", dict(spa, amount=120), [source("ev-test-spa-2")]))            # corrected, with one more source
        self.assertEqual([e["id"] for e in self.store().candidates["c-voyager.spa-credit"]["evidence"]], ["ev-test-spa", "ev-test-spa-2"])
        self.ok(self.cs("promote_candidate", target="c-voyager.spa-credit", data={"review_by": "2028-07-10"}, attestation=REVIEW))
        self.assertEqual(self.store().rules["voyager.spa-credit"]["credit"], dict(spa, amount=120))            # promotion carries the terms
        self.assertEqual(self.picture(ALEX, "2027-07-10")[B + "spa-credit"][:5], (ESTABLISHED, "2027", "2027-01-01", "2027-12-31", 120))

    def test_terms_never_touch_the_election_gate(self):
        self.ok(self.terms("voyager.wellness-credit", {"amount": 30, "unit": "USD", "cycle": "calendar_month", "rollover": "none"}, [source("ev-test-reread")]))
        s = self.store()
        self.assertEqual(s.entities["election.voyager.wellness-credit"]["election"]["governs"], ["voyager.wellness-credit"])
        self.assertEqual((evaluate(s, ALEX, "2027-07-10").have(WELL), evaluate(s, FINN, "2027-07-10").have(WELL)), (NOT_AVAILABLE, ESTABLISHED))
        self.assertEqual(self.picture(FINN, "2027-07-10")[WELL][4], 30)


class TestTables(Base):
    def test_round_trip_is_deterministic(self):
        before = {n: open(os.path.join(self.root, "tables", n), "rb").read() for n in os.listdir(os.path.join(self.root, "tables"))}
        out = self.imported()
        self.assertEqual((out["ok"], out["changesets"]), (True, []))                   # untouched tables: nothing to do
        tables.export(self.root)
        self.assertEqual({n: open(os.path.join(self.root, "tables", n), "rb").read() for n in before}, before)
        with open(os.path.join(self.root, "tables", "credits.csv"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("voyager.curated-hotel-credit,card.northwind-voyager,benefit.voyager.curated-hotel-credit,Northwind Voyager curated hotel credit (synthetic),"
                      "verified,500,USD,calendar_year,,,250,2,,none,,,,\n", text)
        self.assertIn("voyager.travel-credit,card.northwind-voyager,benefit.voyager.travel-credit,Northwind Voyager annual travel credit,"
                      "verified,300,USD,anniversary_year,,,,,,,,,,\n", text)             # empty cells: the source does not say

    def test_correcting_a_cell_needs_a_source_and_becomes_one_changeset(self):
        edit_table(self.root, "credits", change={"voyager.curated-hotel-credit": {"max_per_transaction": "200"}})
        out = self.imported()
        self.assertFalse(out["ok"])
        self.assertTrue(out["errors"][0].startswith("EVIDENCE_REQUIRED: credits row voyager.curated-hotel-credit"), out["errors"])
        self.assertEqual(self.store().rules["voyager.curated-hotel-credit"]["credit"], HOTEL_TERMS)
        edit_table(self.root, "credits", change={"voyager.curated-hotel-credit": {"_evidence": "ev-test-reread"}})
        edit_table(self.root, "sources", add=[dict(source("ev-test-reread"), applies_to=CARD)])
        out = self.imported()
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual([(c["op"], c["target"], c["data"]) for c in out["changesets"]],
                         [("set_credit_terms", "voyager.curated-hotel-credit", {"credit": dict(HOTEL_TERMS, max_per_transaction=200)})])
        self.assertEqual(tables.status(self.root), {"exists": True, "stale": [], "edited": []})
        with open(os.path.join(self.root, "tables", "credits.csv"), encoding="utf-8") as f:
            self.assertIn("verified,500,USD,calendar_year,,,200,2,,none,,,,\n", f.read())   # refreshed; _evidence is empty again
        self.assertEqual(self.imported()["changesets"], [])

    def test_new_benefit_with_terms_enters_as_one_quarantined_candidate(self):
        edit_table(self.root, "benefits", add=[{"id": B + "spa-credit", "name": "Northwind Voyager spa credit (synthetic)"}])
        edit_table(self.root, "sources", add=[dict(source("ev-test-spa"), applies_to=CARD)])
        edit_table(self.root, "card_benefits", add=[{"id": "voyager.spa-credit", "card": CARD, "benefit": B + "spa-credit", "applicability": "confirmed",
                                                      "summary": "50 spa credit each calendar quarter.", "evidence": "ev-test-spa"}])
        edit_table(self.root, "credits", add=[{"id": "voyager.spa-credit", "amount": "50", "unit": "USD", "cycle": "calendar_quarter", "rollover": "none"}])
        out = self.imported()
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual([c["op"] for c in out["changesets"]], ["add_entity", "add_candidate"])
        s = self.store()
        c = s.candidates["c-voyager.spa-credit"]
        self.assertEqual((c["status"], c["proposed_rule"]["credit"]), ("proposed", {"amount": 50, "unit": "USD", "cycle": "calendar_quarter", "rollover": "none"}))
        self.assertIsNone(self.row(ALEX, B + "spa-credit", D))
        self.assertEqual(evaluate(s, ALEX, D).have(B + "spa-credit"), NOT_AVAILABLE)
        # the candidate's terms can be corrected in the credits table; its card_benefits row stays read-only until reviewed
        edit_table(self.root, "credits", change={"voyager.spa-credit": {"amount": "60"}})
        out = self.imported()
        self.assertEqual([(c["op"], c["target"]) for c in out["changesets"]], [("set_credit_terms", "voyager.spa-credit")])
        self.assertEqual(self.store().candidates["c-voyager.spa-credit"]["status"], "proposed")
        edit_table(self.root, "card_benefits", change={"voyager.spa-credit": {"summary": "60 spa credit each calendar quarter."}})
        self.assertTrue(self.imported()["errors"][0].startswith("CANDIDATE_READ_ONLY"))

    def test_adding_terms_to_an_existing_prose_row_and_removing_them(self):
        edit_table(self.root, "sources", add=[dict(source("ev-test-reread"), applies_to=CARD)])
        edit_table(self.root, "credits", add=[{"id": "voyager.phone-protection", "amount": "800", "unit": "USD", "cycle": "calendar_year",
                                                "max_per_transaction": "none", "_evidence": "ev-test-reread"}])
        out = self.imported()
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(self.store().rules["voyager.phone-protection"]["credit"], {"amount": 800, "unit": "USD", "cycle": "calendar_year", "max_per_transaction": "none"})
        edit_table(self.root, "sources", add=[dict(source("ev-test-reread-2"), applies_to=CARD)])
        edit_table(self.root, "credits", change={"voyager.phone-protection": {"_action": "remove", "_evidence": "ev-test-reread-2"}})
        out = self.imported()
        self.assertEqual([(c["op"], c["data"]) for c in out["changesets"]], [("set_credit_terms", {"remove": True})])
        self.assertNotIn("credit", self.store().rules["voyager.phone-protection"])

    def test_invalid_table_edits_change_nothing(self):
        def refused(code, table="credits", **kw):
            work = shutil.copytree(self.root, os.path.join(self.tmp, "w%d" % len(os.listdir(self.tmp))))
            edit_table(work, table, **kw)
            before = Store.load(work).digest()
            out = tables.import_tables(work, "tables", "test maintainer", D)
            self.assertFalse(out["ok"], (code, kw))
            self.assertTrue(any(code in e for e in out["errors"]), (code, out["errors"]))
            self.assertEqual(Store.load(work).digest(), before)
        hotel, ev = "voyager.curated-hotel-credit", {"_evidence": "ev-syn-voyager-credit-terms"}
        refused("BAD_VALUE", change={hotel: dict(ev, amount="lots")})
        refused("MISSING_VALUE", change={hotel: dict(ev, amount="")})
        refused("SCHEMA", change={hotel: dict(ev, cycle="weekly")})
        refused("BAD_VALUE", change={hotel: dict(ev, max_per_transaction="unlimited")})
        refused("BAD_VALUE", change={hotel: dict(ev, min_stay_nights="1.5")})
        refused("BAD_CREDIT_SHAPE", change={hotel: dict(ev, amount="0")})
        refused("BAD_CREDIT_SHAPE", change={hotel: dict(ev, years="4")})
        refused("BAD_VALUE", change={hotel: ev})                                       # a source named, nothing changed
        refused("BAD_VALUE", change={hotel: dict(ev, _action="delete")})
        refused("BAD_VALUE", change={hotel: dict(ev, _action="remove", amount="1")})
        refused("READ_ONLY_COLUMN", change={hotel: {"=state": "candidate"}})
        refused("READ_ONLY_COLUMN", change={hotel: {"=card": "card.halcyon-kestrel"}})
        refused("UNKNOWN_RULE", add=[{"id": "voyager.no-such", "amount": "5", "unit": "USD", "cycle": "calendar_year", "_evidence": "ev-syn-voyager-credit-terms"}])
        refused("UNKNOWN_RULE", add=[{"id": "baseline.orbit-summit.phone-protection", "amount": "5", "unit": "USD", "cycle": "calendar_year",
                                      "_evidence": "ev-syn-voyager-credit-terms"}])
        refused("UNKNOWN_SOURCE", change={hotel: {"amount": "600", "_evidence": "ev-no-such"}})
        refused("DUPLICATE_ROW", add=[{"id": hotel, "amount": "5", "unit": "USD", "cycle": "calendar_year"}])
        work = shutil.copytree(self.root, os.path.join(self.tmp, "deleted"))
        path = os.path.join(work, "tables", "credits.csv")
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines(True)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(line for line in lines if not line.startswith("voyager.dining-credit,"))
        out = tables.import_tables(work, "tables", "test maintainer", D)
        self.assertTrue(out["errors"][0].startswith("ROW_DELETED: credits row voyager.dining-credit"), out["errors"])

    def test_one_bad_credit_row_blocks_a_good_edit_in_the_same_import(self):
        before = self.store().digest()
        edit_table(self.root, "sources", add=[dict(source("ev-test-reread"), applies_to=CARD)])
        edit_table(self.root, "card_benefits", change={"voyager.dining-credit": {"summary": "Up to 150 per half year at restaurants.",
                                                                                 "evidence": "ev-syn-voyager-credit-terms;ev-test-reread"}})
        edit_table(self.root, "credits", change={"voyager.ride-credit": {"cycle": "fortnightly", "_evidence": "ev-test-reread"}})
        out = self.imported()
        self.assertFalse(out["ok"])
        self.assertEqual(self.store().digest(), before)

    def test_tables_carry_no_personal_balance(self):
        for name in sorted(os.listdir(os.path.join(self.root, "tables"))):
            if name == "view_holdings.csv":
                continue
            with open(os.path.join(self.root, "tables", name), encoding="utf-8") as f:
                text = f.read()
            for needle in ("e-hotel-2027", "u-2027-02-10", "remaining", "e-dining"):
                self.assertFalse(needle in text, "%s appears in tables/%s" % (needle, name))
        self.assertFalse([c for c in tables.COLUMNS["credits"] if "used" in c or "remaining" in c or "balance" in c])
        edit_table(self.root, "sources", add=[dict(source("ev-test-reread"), applies_to=CARD)])
        edit_table(self.root, "credits", change={"voyager.dining-credit": {"amount": "175", "_evidence": "ev-test-reread"}})
        before = {p: json.dumps(v, sort_keys=True) for p, v in self.store().files.items() if p.startswith("profiles/")}
        self.assertTrue(self.imported()["ok"])
        self.assertEqual({p: json.dumps(v, sort_keys=True) for p, v in self.store().files.items() if p.startswith("profiles/")}, before)
        self.assertIn("ALLOWANCE_DIFFERS_FROM_RULE", {f["code"] for f in credits.survey(self.store(), ALEX, "2027-03-10")["flags"]})   # shown, not overwritten


class TestPersonalRecords(Base):
    def test_a_period_record_needs_the_owner_and_the_right_period(self):
        new = lambda **kw: self.period(ALEX, "e-dining-2027-h2", "voyager.dining-credit", "2027-H2", "2027-07-01", "2027-12-31", 150, **kw)   # noqa: E731
        self.no(new(by=None), "ATTESTATION_REQUIRED")
        self.no(new(by="test maintainer"), "OWNER_ATTESTATION_REQUIRED")
        self.no(self.period(ALEX, "e-x", "voyager.dining-credit", "2027", "2027-07-01", "2027-12-31", 150), "BAD_PERIOD")
        self.no(self.period(ALEX, "e-x", "voyager.dining-credit", "2027-H3", "2027-07-01", "2027-12-31", 150), "BAD_PERIOD")
        self.no(self.period(ALEX, "e-x", "voyager.dining-credit", "2027-H2", "2027-01-01", "2027-06-30", 150), "BAD_DATES")     # the dates of H1
        self.no(self.period(ALEX, "e-x", "voyager.dining-credit", "2027-H1", "2027-01-01", "2027-06-30", 150), "DUPLICATE_INSTANCE")
        self.no(self.period(ALEX, "e-x", "voyager.phone-protection", "2027", "2027-01-01", "2027-12-31", 150), "UNKNOWN_RULE")  # no credit terms
        self.no(self.period(ALEX, "e-x", "voyager.no-such", "2027", "2027-01-01", "2027-12-31", 150), "UNKNOWN_RULE")
        self.no(self.period(BLAKE, "e-x", "voyager.dining-credit", "2027-H2", "2027-07-01", "2027-12-31", 150), "UNKNOWN_ACCOUNT")
        missing = new()
        del missing["data"]["entitlement"]["allowance"]
        self.no(missing, "MISSING_ALLOWANCE")
        nodate = new()
        del nodate["data"]["entitlement"]["expires_on"]
        self.no(nodate, "MISSING_DATA")
        self.no(self.cs("record_entitlement", ALEX, data={"entitlement": {
            "id": "e-x", "rule": "voyager.dining-credit", "account": ACCT, "cycle": "2027-H2", "state": "confirmed", "effective_from": "2027-07-01",
            "expires_on": "2027-12-31", "allowance": {"amount": 150, "unit": "points"}}}), "BAD_ALLOWANCE")
        self.no(self.period(ALEX, "e-x", "voyager.travel-credit", "2026", "2027-03-15", "2028-03-14", 300), "BAD_DATES")        # that period starts in 2027
        self.ok(new())
        self.assertEqual(self.picture(ALEX, "2027-07-10")[DINING][5:], ("ACTIVE", 150))
        self.assertEqual(self.picture(ALEX, "2027-06-30")[DINING][5:], ("EXHAUSTED", 0))                 # H1 is its own record; nothing merged

    def test_use_caps_and_limits(self):
        hotel = "e-hotel-2027"
        self.no(self.use(ALEX, hotel, "u-x", 300, "2027-07-01"), "USE_EXCEEDS_TRANSACTION_CAP")          # 250 per booking
        self.no(self.use(ALEX, hotel, "u-x", 250.01, "2027-07-01"), "USE_EXCEEDS_TRANSACTION_CAP")
        self.no(self.use(ALEX, hotel, "u-x", 250, "2027-02-10", basis="Two nights, first booking"), "DUPLICATE_USAGE")
        self.no(self.use(ALEX, hotel, "u-x", 100, "2026-12-31"), "OUT_OF_TERM")                          # before this period
        self.no(self.use(ALEX, hotel, "u-x", 100, "2027-08-01"), "FUTURE_DATE")
        self.no(self.use(ALEX, hotel, "u-x", 100, "2027-07-01", by="test maintainer"), "OWNER_ATTESTATION_REQUIRED")
        self.no(self.use(ERIN, hotel, "u-x", 100, "2027-07-01"), "UNKNOWN_TARGET")                       # Alex's record is not Erin's
        self.ok(self.use(ALEX, hotel, "u-2027-07-01", 250, "2027-07-01", basis="Two nights, second booking"))   # exactly the cap: fine
        p = self.row(ALEX, HOTEL, D)["personal"]
        self.assertEqual((p["state"], p["used"], p["possibly_used"], p["remaining"]), ("EXHAUSTED", 500, 180, 0))
        self.no(self.use(ALEX, hotel, "u-y", 1, "2027-07-02"), "USAGE_EXCEEDS_ALLOWANCE")
        self.assertEqual(evaluate(self.store(), ALEX, D).have(HOTEL), ESTABLISHED)                       # still a benefit of the card; this year's is spent
        self.ok(self.use(ERIN, "e-travel-2026", "u-2027-01-10", 180, "2027-01-10"))                       # no cap is stated on this credit: none is imposed
        self.assertEqual(self.picture(ERIN, D)[TRAVEL][5:], ("EXHAUSTED", 0))

    def test_corrections_keep_the_old_entry(self):
        hotel = "e-hotel-2027"
        self.ok(self.cs("correct_entry", ALEX, data={"record": "entitlement", "id": hotel, "entry": "u-2027-02-10", "replacement": {
            "id": "u-2027-02-10b", "amount": 220, "used_on": "2027-02-10", "state": "confirmed", "basis": "Two nights, first booking (corrected amount)"}}))
        self.ok(self.cs("correct_entry", ALEX, data={"record": "entitlement", "id": hotel, "entry": "u-2027-06-20", "replacement": {
            "id": "u-2027-06-20b", "amount": 180, "used_on": "2027-06-20", "state": "confirmed", "basis": "Confirmed by the owner"}}))
        p = self.row(ALEX, HOTEL, D)["personal"]
        self.assertEqual((p["used"], p["possibly_used"], p["remaining"], p["established"]), (400, 0, 100, True))
        self.assertEqual(self.row(ALEX, HOTEL, "2027-03-10")["personal"]["remaining"], 280)              # earlier dates follow the correction
        usage = self.store().profile(ALEX).entitlements[hotel]["usage"]
        self.assertEqual([(u["id"], u["state"]) for u in usage], [("u-2027-02-10", "superseded"), ("u-2027-06-20", "superseded"),
                                                                  ("u-2027-02-10b", "confirmed"), ("u-2027-06-20b", "confirmed")])
        self.no(self.cs("correct_entry", ALEX, data={"record": "entitlement", "id": hotel, "entry": "u-2027-06-20b", "replacement": {
            "id": "u-big", "amount": 260, "used_on": "2027-06-20", "state": "confirmed"}}), "USE_EXCEEDS_TRANSACTION_CAP")
        self.ok(self.cs("revise_entitlement", ALEX, target=hotel, data={"set": {"allowance": {"amount": 450, "unit": "USD"}}}))
        self.assertEqual(self.row(ALEX, HOTEL, D)["personal"]["remaining"], 50)
        self.assertIn("ALLOWANCE_DIFFERS_FROM_RULE", {f["code"] for f in credits.survey(self.store(), ALEX, D)["flags"]})
        self.assertEqual(self.row(ALEX, HOTEL, D)["allowance"]["amount"], 500)                           # the published figure is not edited by it

    def test_personal_records_are_not_earned_benefits_and_grant_nothing(self):
        r = evaluate(self.store(), ALEX, "2027-03-10")
        self.assertNotIn("earned_entitlements", r.report())
        code, text = cli(self.root, "earned", "--profile", ALEX, "--as-of", "2027-03-10")
        self.assertIn("No account of this person has an earned-benefit rule or record.", text)
        self.ok(self.period(ALEX, "e-well", "voyager.wellness-credit", "2027-07", "2027-07-01", "2027-07-31", 25))   # a record for the option not elected
        self.assertEqual(evaluate(self.store(), ALEX, D).have(WELL), NOT_AVAILABLE)
        self.assertNotIn("allowance", self.row(ALEX, WELL, D))


class TestReportCommand(Base):
    def test_person_report(self):
        code, text = cli(self.root, "credits", "--profile", ALEX, "--as-of", "2027-07-01")
        self.assertEqual(code, 0)
        for needle in ("RECURRING CREDITS  profile=synthetic-alex  owner=Alex (synthetic)  as-of=2027-07-01  [SYNTHETIC DATA]",
                       "ACCOUNT h-card-northwind-voyager  Northwind Voyager (synthetic)  [confirmed; opened 2025-03-15]",
                       "PUBLISHED   voyager.curated-hotel-credit (verified): 500 USD each calendar year (January 1 to December 31)",
                       "per transaction: maximum 250 USD; minimum stay 2 night(s); minimum transaction not stated by the source",
                       "rollover: none; unused allowance expires with the period",
                       "PERIOD      2027-H2  2027-07-01 to 2027-12-31",
                       "2028-01-01: new period, allowance resets; unused allowance does not roll over",
                       "ALLOWANCE   150 USD - published allowance for this period; not a personal balance",
                       "PERSONAL    NOT RECORDED - nothing is recorded for this account and period; the personal balance is not known",
                       "PERSONAL    record e-hotel-2027: ACTIVE  2027-01-01 to 2027-12-31  (confirmed by Alex (synthetic) on 2027-02-11)",
                       "allowance 500 USD; used 250 (confirmed); remaining 250 (at least 70; 180 more may have been used, unconfirmed)",
                       "only under election election.voyager.lifestyle-credit (voyager.annual-perk): in effect",
                       "APPLIES     NOT_AVAILABLE for this person on this date",
                       "ALLOWANCE   none for this person: the benefit does not apply to them on this date",
                       "PERIOD      2025  2025-09-10 to 2029-09-09",
                       "[review] CREDIT_USE_UNCONFIRMED e-hotel-2027",
                       "Only PERSONAL says anything about this person's own balance"):
            self.assertIn(needle, text)
        code, text = cli(self.root, "credits", "--profile", FINN, "--as-of", "2027-03-10", "--card", CARD)
        self.assertIn("[confirmed; opened not recorded]", text)
        self.assertIn("PERIOD      UNRESOLVED - the opening date of account h-card-northwind-voyager is not recorded (opened_on), so its anniversary is not known", text)
        self.assertIn("ALLOWANCE   not determined: the allowance period is not known", text)
        self.assertEqual(cli(self.root, "credits", "--profile", "synthetic-nobody")[0], 2)

    def test_published_report_and_json(self):
        code, text = cli(self.root, "credits", "--as-of", "2027-03-10")
        for needle in ("These are the card's published terms. Nothing here is anyone's balance.",
                       "RULE        voyager.ride-credit (verified); offer in effect through 2027-09-30; evidence: ev-syn-voyager-credit-terms",
                       "TERMS       10 USD each calendar month, separately (at most 120 USD in a calendar year)",
                       "PERIOD NOW  2027-03  2027-03-01 to 2027-03-31",
                       "PERIOD NOW  UNRESOLVED - depends on the opening date of each cardholder's own account",
                       "TERMS       120 USD once every 4 years, counted from the date the credit was last used"):
            self.assertIn(needle, text)
        self.assertNotIn("remaining", text)
        code, text = cli(self.root, "--json", "credits", "--profile", ERIN, "--as-of", "2027-03-10", "--until", "2027-06-30")
        o = json.loads(text)
        travel = next(c for c in o["accounts"][0]["credits"] if c["benefit"] == TRAVEL)
        self.assertEqual((travel["rule"], travel["evidence"], travel["terms"]["amount"], travel["period"]["start"], travel["period"]["end"]),
                         ("voyager.travel-credit", ["ev-syn-voyager-guide", "ev-syn-voyager-credit-terms"], 300, "2026-11-02", "2027-11-01"))
        self.assertEqual((travel["personal"]["record"], travel["personal"]["confirmed_by"], travel["personal"]["remaining"]), ("e-travel-2026", "Erin (synthetic)", 180))
        self.assertEqual(travel["terms"]["rollover"], None)
        ending = [(e["date"], e["benefit"], e["applies"]) for e in o["periods_ending"]]
        self.assertIn(("2027-06-30", DINING, ESTABLISHED), ending)
        self.assertIn(("2027-03-31", WELL, UNRESOLVED), ending)                         # might apply: listed, and marked unresolved

    def test_review_and_timeline_show_period_ends(self):
        code, text = cli(self.root, "review", "--profile", ALEX, "--from", "2027-06-15", "--to", "2027-07-01")
        self.assertIn("credit periods ending in this window (published allowance; not a personal balance):", text)
        self.assertIn("2027-06-30  benefit.voyager.dining-credit  period 2027-H1 ends (150 USD published, account h-card-northwind-voyager, applies: ESTABLISHED); "
                      "unused allowance does not roll over; a new period starts on 2027-07-01", text)
        self.assertNotIn("wellness", text)                                             # not Alex's election
        code, text = cli(self.root, "timeline", "--profile", ALEX, "--as-of", "2027-09-01", "--until", "2027-10-05")
        self.assertIn("credit period ends: benefit.voyager.ride-credit  period 2027-09 ends (10 USD published, account h-card-northwind-voyager, applies: ESTABLISHED); "
                      "unused allowance does not roll over; the offer ends", text)
        self.assertIn("have:benefit.voyager.ride-credit: ESTABLISHED -> NOT_AVAILABLE", text)   # and the next day the benefit itself is gone
        code, text = cli(self.root, "review", "--profile", BLAKE, "--from", "2027-06-15", "--to", "2027-07-01")
        self.assertNotIn("credit periods", text)


if __name__ == "__main__":
    unittest.main()
