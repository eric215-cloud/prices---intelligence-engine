"""Earned benefits, part 2: the invented acceptance scenario, and how personal facts get in, get corrected and stay auditable.

Every test works on a private copy of the synthetic earned-benefit fixture (built once through the normal
changeset pipeline) and changes it only through changesets, the way a maintainer would.
All data here is invented.
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

import synthetic_earned  # noqa: E402
from prices import changes, tables  # noqa: E402
from prices.cli import main  # noqa: E402
from prices.earned import survey  # noqa: E402
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate  # noqa: E402
from prices.lint import lint  # noqa: E402
from prices.review import timeline  # noqa: E402
from prices.store import Store, read_audit  # noqa: E402

D = "2027-11-20"                                   # "today" for new changesets: after everything in the fixture
ALEX, BLAKE, CASEY, DEVON = "synthetic-alex", "synthetic-blake", "synthetic-casey", "synthetic-devon"
OWNER = dict(synthetic_earned.OWNERS, **{"synthetic-blake": "Blake (synthetic)"})
ACCT, MEASURE = synthetic_earned.ACCOUNT, synthetic_earned.MEASURE
STATUS, FARE = "status.orbit-concierge", "benefit.voyager.companion-fare"
AWARD, CREDIT, LINE = "benefit.voyager.suite-award", "benefit.voyager.milestone-credit", "benefit.orbit-concierge.priority-line"
SHORT = {STATUS: "status", FARE: "fare", AWARD: "award", CREDIT: "credit"}
REVIEW = {"by": "Synthetic Reviewer", "on": D, "statement": "Synthetic review."}


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
        cls.class_tmp = tempfile.mkdtemp(prefix="prices-earned-")
        cls.built = synthetic_earned.build(os.path.join(cls.class_tmp, "fx"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.class_tmp)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prices-earned-")
        self.root = shutil.copytree(self.built, os.path.join(self.tmp, "fx"))
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def store(self):
        return Store.load(self.root)

    def cs(self, op, person=None, by="owner", date=D, **kw):
        """A changeset. by: 'owner' (the person's own attestation), None (no attestation), or any other name."""
        self.n += 1
        c = dict({"id": "cs-test-%03d-%s" % (self.n, op.replace("_", "-")), "op": op, "author": "test maintainer", "date": date,
                  "reason": "test"}, **kw)
        if person:
            c["profile"] = person
        if by is not None and "attestation" not in c:
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
        self.assertTrue(any(e.startswith(code) or (": " + code) in e or e.startswith("SCHEMA") and code == "SCHEMA" for e in out["errors"]),
                        "expected %s, got %s" % (code, out["errors"]))
        self.assertEqual(self.store().digest(), before, "a rejected changeset must not change any record")
        self.assertEqual(tree(self.root), files, "a rejected changeset must not create any file")
        after = read_audit(self.root)
        self.assertEqual((len(after), after[-1]["result"], after[-1]["changeset"]), (len(log) + 1, "rejected", c["id"]))
        return out

    def progress(self, person, cycle, rid, value, observed_on, state="confirmed", by="owner", date=D, account=ACCT, measure=MEASURE, **extra):
        return self.cs("record_progress", person, by, date, data={"account": account, "measure": measure, "cycle": cycle,
                       "reading": dict({"id": rid, "value": value, "observed_on": observed_on, "state": state}, **extra)})

    def instance(self, person, cycle, eid, rule, start, end, state="confirmed", by="owner", date=D, account=ACCT, **extra):
        return self.cs("record_entitlement", person, by, date, data={"entitlement": dict(
            {"id": eid, "rule": rule, "account": account, "cycle": cycle, "state": state, "effective_from": start, "expires_on": end}, **extra)})

    def usage(self, person, target, uid, amount, used_on, state="confirmed", by="owner", date=D, **extra):
        return self.cs("record_usage", person, by, date, target=target,
                       data={"usage": dict({"id": uid, "amount": amount, "used_on": used_on, "state": state}, **extra)})

    def picture(self, person, day, cycle):
        """{benefit: (achievement, entitlement)} for one qualifying year, plus the engine's person-level answers."""
        s = self.store()
        res, out = evaluate(s, person, day), {}
        for a in survey(s, person, day)["accounts"]:
            for c in a["cycles"]:
                if c["cycle"] == cycle:
                    for b in c["benefits"]:
                        out[SHORT[b["entity"]]] = (b["achievement"]["state"], b["entitlement"]["state"])
        return out, {SHORT[e]: res.have(e) for e in SHORT}, {f["code"] for f in res.flags if f["code"] != "STALE_RULE"}

    def credit(self, person, day, eid):
        for a in survey(self.store(), person, day)["accounts"]:
            for c in a["cycles"]:
                for b in c["benefits"]:
                    for i in b["instances"]:
                        if i["id"] == eid:
                            cr = i["credit"]
                            return cr["allowance"], cr["used"], cr["possibly_used"], cr["remaining"], cr["remaining_at_least"]


class TestFixture(Base):
    def test_committed_fixture_is_exactly_what_the_builder_produces(self):
        committed = os.path.join(ROOT, "fixtures", "synthetic-earned")
        self.assertEqual(tree(committed), tree(self.root))
        _same, diff, errs = filecmp.cmpfiles(committed, self.root, tree(committed), shallow=False)
        self.assertEqual((diff, errs), ([], []))

    def test_fixture_is_valid_and_every_personal_fact_came_through_the_pipeline(self):
        s = self.store()
        self.assertEqual(lint(s), [])
        ops = [e["op"] for e in read_audit(self.root) if e["result"] == "applied"]
        self.assertEqual((ops.count("record_progress"), ops.count("record_entitlement"), ops.count("record_usage")), (8, 7, 3))
        for person in (ALEX, CASEY, DEVON):
            p = s.profile(person)
            for q in p.qualifications.values():
                for r in q["readings"]:
                    self.assertTrue(os.path.exists(os.path.join(self.root, "data/audit/changesets", r["changeset"] + ".json")), r["id"])
                    self.assertEqual(r["confirmed_by"], OWNER[person])               # every confirmation is the owner's own
            for e in p.entitlements.values():
                self.assertEqual(e["confirmed_by"], OWNER[person])
        self.assertTrue(all(s.profile(p).meta["synthetic"] for p in s.profile_names()))

    def test_people_without_earned_records_are_unaffected(self):
        s, cards = self.store(), Store.load(os.path.join(ROOT, "fixtures", "synthetic-cards"))
        for day in ("2026-11-14", "2027-06-01", "2028-03-01"):
            a, b = evaluate(cards, BLAKE, day).report(), evaluate(s, BLAKE, day).report()
            self.assertEqual(set(a), set(b))
            new_rules = {r["id"] for r in synthetic_earned.RULES}                        # more public rules exist...
            stale = [f for f in b["flags"] if f["subject"] in new_rules]                 # ...which, like any rule, go stale after their review date
            self.assertEqual({f["code"] for f in stale}, {"STALE_RULE"} if day > "2027-11-14" else set(), day)
            b["flags"] = [f for f in b["flags"] if f not in stale]
            self.assertEqual([k for k in a if a[k] != b[k]], ["sourced_rules"], day)     # nothing personal moved
            self.assertNotIn("earned_entitlements", b)
        code, text = cli(self.root, "earned", "--profile", BLAKE, "--as-of", "2027-06-01")
        self.assertEqual(code, 0)
        self.assertIn("No account of this person has an earned-benefit rule or record.", text)
        code, text = cli(self.root, "status", "--profile", BLAKE, "--as-of", "2027-06-01")
        self.assertNotIn("Earned benefits on record", text)

    def test_no_earned_facts_or_earn_rules_exist_in_the_live_data(self):
        live = Store.load(ROOT)
        self.assertEqual([r["id"] for r in live.rules.values() if r["kind"] == "earns"], [])
        for name in live.profile_names():
            p = live.profile(name)
            self.assertEqual((p.qualifications, p.entitlements), ({}, {}), name)
            self.assertNotIn("earned_entitlements", evaluate(live, name, "2026-11-14").report())
            self.assertFalse(os.path.exists(os.path.join(ROOT, "profiles", name, "qualifications")))
            self.assertFalse(os.path.exists(os.path.join(ROOT, "profiles", name, "entitlements")))


class TestAcceptanceScenario(Base):
    """The commission's scenario, read off the fixture at a series of dates."""

    def test_holder_who_achieves_it_alex_2026(self):
        A, N, AR, NE = "ACHIEVED", "NOT_YET_EFFECTIVE", "ACTIVATION_REQUIRED", "ACTIVE"
        steps = [
            # day          status          fare           award          credit          have: status, fare, award, credit
            ("2026-06-15", ("BELOW", N), ("BELOW", N), ("BELOW", N), ("BELOW", N), (NOT_AVAILABLE,) * 4),
            ("2026-07-15", ("UNCERTAIN", N), ("UNCERTAIN", N), ("UNCERTAIN", N), ("UNCERTAIN", N), (NOT_AVAILABLE,) * 4),
            # threshold reached by October 31: eligible. Nothing is held until the account record says so (November 8).
            ("2026-11-05", (A, N), (A, N), (A, AR), (A, N), (NOT_AVAILABLE, NOT_AVAILABLE, CONDITIONAL, NOT_AVAILABLE)),
            ("2026-11-08", (A, NE), (A, NE), (A, AR), (A, NE), (ESTABLISHED, ESTABLISHED, CONDITIONAL, ESTABLISHED)),
            # the award needed its own step; it is held only from the day that step is recorded as done
            ("2027-01-14", (A, NE), (A, NE), (A, AR), (A, NE), (ESTABLISHED, ESTABLISHED, CONDITIONAL, ESTABLISHED)),
            ("2027-01-15", (A, NE), (A, NE), (A, NE), (A, NE), (ESTABLISHED,) * 4),
            ("2027-12-31", (A, NE), (A, NE), (A, NE), (A, NE), (ESTABLISHED,) * 4),
            # one qualifying event, two expiries: fare (and award, credit) end December 31; the status runs to the end of February
            ("2028-01-01", (A, NE), (A, "EXPIRED"), (A, "EXPIRED"), (A, "EXPIRED"), (ESTABLISHED, NOT_AVAILABLE, CONDITIONAL, ESTABLISHED)),
            ("2028-02-29", (A, NE), (A, "EXPIRED"), (A, "EXPIRED"), (A, "EXPIRED"), (ESTABLISHED, NOT_AVAILABLE, CONDITIONAL, ESTABLISHED)),
            ("2028-03-01", (A, "EXPIRED"), (A, "EXPIRED"), (A, "EXPIRED"), (A, "EXPIRED"), (ESTABLISHED, NOT_AVAILABLE, CONDITIONAL, ESTABLISHED)),
        ]
        for day, status, fare, award, credit, have in steps:
            pic, got, _flags = self.picture(ALEX, day, "2026")
            self.assertEqual((pic["status"], pic["fare"], pic["award"], pic["credit"]), (status, fare, award, credit), day)
            self.assertEqual((got["status"], got["fare"], got["award"], got["credit"]), have, day)

    def test_second_year_is_independent_and_overlaps_alex_2027(self):
        pic, have, _f = self.picture(ALEX, "2027-06-01", "2027")
        self.assertEqual(pic["status"][0], "UNCERTAIN")                 # 29,000 in April; whether 75,000 is reached yet is not known
        pic, have, _f = self.picture(ALEX, "2027-04-15", "2027")
        self.assertEqual(pic["status"][0], "BELOW")                     # 2026's 91,250 does not count toward 2027
        pic, have, flags = self.picture(ALEX, "2027-12-01", "2027")
        self.assertEqual(pic, {"status": ("ACHIEVED", "ACTIVE"), "credit": ("ACHIEVED", "ACTIVE"),
                               "fare": ("ACHIEVED", "NOT_OFFERED"),      # the fare offer ended with qualifying year 2026
                               "award": ("ACHIEVED", "ACTIVATION_REQUIRED")})   # 2026's activation does not activate 2027's award
        both = [x for x in evaluate(self.store(), ALEX, "2027-12-01").report()["earned_entitlements"] if x["entity"] == STATUS]
        self.assertEqual([(x["cycle"], x["state"], x["expires_on"]) for x in both],
                         [("2026", "ACTIVE", "2028-02-29"), ("2027", "ACTIVE", "2029-02-28")])     # overlapping, kept apart
        self.assertEqual(self.credit(ALEX, "2027-12-01", "e-2026-milestone-credit"), (300, 200, 60, 100, 40))
        self.assertEqual(self.credit(ALEX, "2027-12-01", "e-2027-milestone-credit"), (300, 0, 0, 300, 300))  # not 400, not 600
        s = self.store()
        self.assertEqual(evaluate(s, ALEX, "2028-03-01").have(STATUS), ESTABLISHED)       # carried by the 2027 instance alone
        self.assertEqual(evaluate(s, ALEX, "2029-02-28").have(LINE), ESTABLISHED)
        self.assertEqual(evaluate(s, ALEX, "2029-03-01").have(STATUS), NOT_AVAILABLE)
        late = evaluate(s, ALEX, "2028-01-05")
        self.assertEqual(late.have(CREDIT), ESTABLISHED)                                   # the 2027 credit, on its own terms
        self.assertLessEqual({"EXPIRED_ENTITLEMENT", "CREDIT_LAPSED_UNUSED"}, {f["code"] for f in late.flags})

    def test_credit_allowance_used_and_remaining(self):
        for day, want in (("2026-11-08", (300, 0, 0, 300, 300)), ("2026-12-02", (300, 0, 0, 300, 300)), ("2026-12-03", (300, 120, 0, 180, 180)),
                          ("2027-02-10", (300, 200, 0, 100, 100)), ("2027-03-02", (300, 200, 60, 100, 40))):
            self.assertEqual(self.credit(ALEX, day, "e-2026-milestone-credit"), want, day)
        self.assertIn("CREDIT_USE_UNCONFIRMED", self.picture(ALEX, "2027-03-10", "2026")[2])
        self.assertEqual(self.store().profile(ALEX).entitlements["e-2026-milestone-credit"]["allowance"], {"amount": 300, "unit": "units"})

    def test_holder_who_did_not_qualify_casey(self):
        for day, ach in (("2026-09-15", "BELOW"), ("2026-12-20", "BELOW"), ("2027-02-01", "NOT_QUALIFIED"), ("2028-06-01", "NOT_QUALIFIED")):
            pic, have, flags = self.picture(CASEY, day, "2026")
            self.assertEqual(set(pic.values()), {(ach, "NOT_EARNED")}, day)
            self.assertEqual(set(have.values()), {NOT_AVAILABLE}, day)
            self.assertEqual(flags, set(), day)
        r = evaluate(self.store(), CASEY, "2027-02-01")                       # same card, same year as Alex; nothing rubs off
        self.assertEqual((r.have("card.northwind-voyager"), r.status("can_get:" + STATUS), r.have(LINE)), (ESTABLISHED, NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertEqual(r.report()["earned_entitlements"], [])

    def test_year_only_attestation_and_unknown_start_date_devon(self):
        pic, have, flags = self.picture(DEVON, "2026-09-01", "2026")
        self.assertEqual(pic["fare"], ("UNCERTAIN", "UNRESOLVED"))
        self.assertEqual(have, {"status": UNRESOLVED, "fare": UNRESOLVED, "award": UNRESOLVED, "credit": UNRESOLVED})
        pic, have, flags = self.picture(DEVON, "2027-01-05", "2026")            # 2026 is over: reached, but the day is not known
        self.assertEqual(pic, {"status": ("ACHIEVED", "UNRESOLVED"), "fare": ("ACHIEVED", "EARNED_NOT_CONFIRMED"),
                               "credit": ("ACHIEVED", "EARNED_NOT_CONFIRMED"), "award": ("ACHIEVED", "ACTIVATION_REQUIRED")})
        self.assertEqual(have, {"status": UNRESOLVED, "fare": CONDITIONAL, "award": CONDITIONAL, "credit": CONDITIONAL})
        self.assertIn("ENTITLEMENT_UNRESOLVED", flags)
        pic, have, flags = self.picture(DEVON, "2027-01-20", "2026")            # the day the owner saw the status on the account
        self.assertEqual((pic["status"], have["status"], flags), (("ACHIEVED", "ACTIVE"), ESTABLISHED, set()))
        s = self.store()
        q = s.profile(DEVON).qualifications["q-%s-%s-2026" % (ACCT, MEASURE)]
        self.assertEqual((q["readings"][0]["observed_on"], s.profile(DEVON).entitlements["e-2026-concierge-status"]["effective_from"]),
                         ("unknown", "unknown"))                                 # nothing was filled in for the owner
        code, text = cli(self.root, "earned", "--profile", DEVON, "--as-of", "2027-03-01")
        self.assertIn("at least 75,000 units on a date that is not recorded", text)
        self.assertIn("unknown to 2028-02-29", text)

    def test_timeline_shows_each_personal_boundary(self):
        events = {e["date"]: e for e in timeline(self.store(), ALEX, "2026-06-01", "2029-06-01")}
        moved = lambda day: {c["atom"]: (c["before"], c["after"]) for c in events[day]["changes"]}      # noqa: E731
        self.assertEqual(moved("2026-11-08")["have:" + STATUS], (NOT_AVAILABLE, ESTABLISHED))
        self.assertEqual(moved("2027-01-15")["have:" + AWARD], (CONDITIONAL, ESTABLISHED))
        self.assertEqual(moved("2028-01-01")["have:" + FARE], (ESTABLISHED, NOT_AVAILABLE))
        self.assertNotIn("have:" + STATUS, moved("2028-01-01"))
        self.assertNotIn("2028-03-01", events)                                   # the 2027 status instance covers the handover: no change
        self.assertEqual(moved("2029-03-01")["have:" + STATUS], (ESTABLISHED, NOT_AVAILABLE))


class TestAttestation(Base):
    def test_only_the_owner_can_confirm_a_personal_fact(self):
        new = lambda by, **kw: self.progress(ALEX, "2027", "r-2027-10", 84000, "2027-10-31", by=by, **kw)     # noqa: E731
        self.no(new(None), "ATTESTATION_REQUIRED")
        self.no(new("test maintainer"), "OWNER_ATTESTATION_REQUIRED")
        self.no(new(OWNER[CASEY]), "OWNER_ATTESTATION_REQUIRED")                 # another person cannot confirm Alex's spending
        late = new("owner")
        late["attestation"]["on"] = "2027-11-25"
        self.no(late, "BAD_DATES")                                               # an attestation cannot be dated after the change it supports
        self.ok(new("owner"))
        r = self.store().profile(ALEX).qualifications["q-%s-%s-2027" % (ACCT, MEASURE)]["readings"][-1]
        self.assertEqual((r["confirmed_by"], r["confirmed_on"], r["changeset"][:8]), (OWNER[ALEX], D, "cs-test-"))

    def test_a_maintainer_can_record_but_never_confirm(self):
        self.ok(self.progress(CASEY, "2027", "r-2027-10", 80000, "2027-10-31", state="unconfirmed", by=None))
        pic, have, _f = self.picture(CASEY, D, "2027")
        self.assertEqual(pic["status"], ("UNCERTAIN", "UNRESOLVED"))             # on file, and not relied on
        self.assertEqual(have["status"], UNRESOLVED)
        self.ok(self.instance(CASEY, "2027", "e-2027-status", "voyager.earn-concierge-status", "2027-11-01", "2029-02-28", state="unconfirmed", by=None))
        r = evaluate(self.store(), CASEY, D)
        self.assertEqual((r.have(STATUS), r.have(LINE)), (UNRESOLVED, UNRESOLVED))
        self.assertIn("UNCONFIRMED_ENTITLEMENT", {f["code"] for f in r.flags})
        sneaky = self.progress(CASEY, "2027", "r-2027-11", 81000, "2027-11-15", state="unconfirmed", by=None, confirmed_by=OWNER[CASEY])
        self.ok(sneaky)                                                          # a typed-in confirmed_by is discarded, not trusted
        self.assertNotIn("confirmed_by", self.store().profile(CASEY).qualifications["q-%s-%s-2027" % (ACCT, MEASURE)]["readings"][-1])

    def test_the_owners_word_is_recorded_but_contradictions_are_not_hidden(self):
        # Casey's final 2026 figure is 61,300. Casey now says the status is on the account anyway.
        out = self.ok(self.instance(CASEY, "2026", "e-2026-status", "voyager.earn-concierge-status", "2027-01-10", "2028-02-29"))
        self.assertTrue(out["review_needed"])
        r = evaluate(self.store(), CASEY, D)
        self.assertEqual(r.have(STATUS), UNRESOLVED)                             # neither granted nor refused: a conflict to resolve
        self.assertIn("CONFLICTING_QUALIFICATION", {f["code"] for f in r.flags})


class TestInvalidInput(Base):
    def test_progress(self):
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "2027-10-31", account="h-no-such-account"), "UNKNOWN_ACCOUNT")
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "2027-10-31", account="h-card-halcyon-kestrel"), "UNKNOWN_ACCOUNT")   # Blake's card, not Alex's
        self.no(self.progress(BLAKE, "2027", "r-x", 84000, "2027-10-31", account="h-card-halcyon-kestrel"), "UNKNOWN_MEASURE")  # no such rule on that card
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "2027-10-31", measure="voyager.lifetime-spend"), "UNKNOWN_MEASURE")
        self.no(self.progress("synthetic-nobody", "2027", "r-x", 84000, "2027-10-31", by="Nobody"), "UNKNOWN_PROFILE")
        self.no(self.progress(ALEX, "27", "r-x", 84000, "2027-10-31"), "BAD_DATA")
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "2027-11-25"), "FUTURE_DATE")
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "2026-12-31"), "OUT_OF_CYCLE")           # last year's figure in this year's cycle
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "last October"), "BAD_DATES")
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "unknown"), "BAD_READING")               # no date: can only say "at least"
        self.no(self.progress(ALEX, "2027", "r-x", -5, "2027-10-31"), "BAD_VALUE")
        self.no(self.progress(ALEX, "2027", "r-x", "84,000", "2027-10-31"), "BAD_VALUE")
        self.no(self.progress(ALEX, "2027", "r-x", 84000, "2027-12-31", final=True), "FINAL_BEFORE_PERIOD_END")   # the year is not over
        self.no(self.progress(ALEX, "2026", "r-x", 91000, "2026-11-30", final=True), "BAD_READING")              # a final figure is the year-end figure
        self.no(self.cs("record_progress", ALEX, data={"account": ACCT, "measure": MEASURE, "cycle": "2027",
                                                       "reading": {"id": "r-x", "value": 84000, "final": True, "state": "confirmed"}}),
                "FINAL_BEFORE_PERIOD_END")                                                          # the year is not over
        self.no(self.cs("record_progress", ALEX, data={"account": ACCT, "measure": MEASURE, "cycle": "2027",
                                                       "reading": {"id": "r-x", "value": 84000, "state": "confirmed"}}), "MISSING_DATA")
        self.no(self.progress(ALEX, "2027", "r-2027-09", 99999, "2027-10-31"), "ID_EXISTS")
        self.no(self.progress(ALEX, "2027", "r-again", 78300, "2027-09-30"), "DUPLICATE_READING")  # the same fact typed in twice
        self.no(self.cs("record_progress", ALEX, data={"account": ACCT, "measure": MEASURE, "cycle": "2027"}), "MISSING_DATA")

    def test_entitlement(self):
        rule = "voyager.earn-suite-award"
        self.no(self.instance(ALEX, "2026", "e-again", "voyager.earn-companion-fare", "2026-11-08", "2027-12-31"), "DUPLICATE_INSTANCE")
        self.no(self.instance(ALEX, "2027", "e-2026-companion-fare", rule, "2027-11-01", "2028-12-31"), "ID_EXISTS")
        self.no(self.instance(ALEX, "2027", "e-x", "concierge.priority-line", "2027-11-01", "2028-12-31"), "UNKNOWN_RULE")   # not an earn rule
        self.no(self.instance(ALEX, "2027", "e-x", "no.such.rule", "2027-11-01", "2028-12-31"), "UNKNOWN_RULE")
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "2028-12-31", account="h-no-such-account"), "UNKNOWN_ACCOUNT")
        self.no(self.instance(BLAKE, "2027", "e-x", rule, "2027-11-01", "2028-12-31", account="h-card-halcyon-kestrel"), "ACCOUNT_MISMATCH")
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "2028-12-31", entity=FARE), "ENTITY_MISMATCH")
        self.no(self.instance(ALEX, "27", "e-x", rule, "2027-11-01", "2028-12-31"), "BAD_DATA")
        missing = self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "2028-12-31")
        del missing["data"]["entitlement"]["expires_on"]
        out = self.no(missing, "MISSING_DATA")
        self.assertIn("write the word unknown", out["errors"][0])                 # the message says what to do instead of guessing
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "some time in 2028"), "SCHEMA")
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "2027-10-01"), "BAD_DATES")          # ends before it starts
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2026-12-01", "2028-12-31"), "BAD_DATES")          # starts before its own qualifying year
        self.no(self.instance(DEVON, "2026", "e-credit", "voyager.earn-milestone-credit", "2027-01-20", "2027-12-31"), "MISSING_ALLOWANCE")
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "2028-12-31", allowance={"amount": 2, "unit": "units"}), "BAD_ALLOWANCE")
        self.no(self.instance(ALEX, "2027", "e-x", rule, "2027-11-01", "2028-12-31",
                              usage=[{"id": "u1", "amount": 1, "used_on": "2027-11-02", "state": "unconfirmed"}]), "BAD_DATA")

    def test_usage(self):
        credit, status = "e-2026-milestone-credit", "e-2026-concierge-status"
        self.no(self.usage(ALEX, credit, "u-x", 150, "2027-11-01"), "USAGE_EXCEEDS_ALLOWANCE")       # 200 confirmed + 150 > 300
        self.no(self.usage(ALEX, status, "u-x", 10, "2027-11-01"), "NO_ALLOWANCE")                   # a status is not a balance
        self.no(self.usage(ALEX, credit, "u-x", 120, "2026-12-03", basis="Airfare"), "DUPLICATE_USAGE")
        self.no(self.usage(ALEX, credit, "u-2026-12-03", 5, "2027-11-01"), "ID_EXISTS")
        self.no(self.usage(ALEX, credit, "u-x", 0, "2027-11-01"), "BAD_VALUE")
        self.no(self.usage(ALEX, credit, "u-x", 10, "2027-11-25"), "FUTURE_DATE")
        self.no(self.usage(ALEX, credit, "u-x", 10, "2026-10-01"), "OUT_OF_TERM")                    # before the credit existed
        self.no(self.usage(ALEX, "e-no-such", "u-x", 10, "2027-11-01"), "UNKNOWN_TARGET")
        self.no(self.usage(CASEY, credit, "u-x", 10, "2027-11-01"), "UNKNOWN_TARGET")                # Alex's credit is not Casey's to spend
        self.no(self.usage(ALEX, credit, "u-x", 10, "2027-11-01", by="test maintainer"), "OWNER_ATTESTATION_REQUIRED")
        self.no(self.usage(ALEX, credit, "u-x", 10, "2028-01-05", date="2028-01-10"), "OUT_OF_TERM")  # after the credit expired
        self.ok(self.usage(ALEX, credit, "u-ok", 30, "2027-11-01", basis="Train"))
        self.assertEqual(self.credit(ALEX, D, credit), (300, 230, 60, 70, 10))

    def test_revision_and_correction(self):
        fare = "e-2026-companion-fare"
        rev = lambda person=ALEX, by="owner", **s: self.cs("revise_entitlement", person, by, target=fare, data={"set": s})   # noqa: E731
        self.no(rev(cycle="2027"), "FIELD_NOT_REVISABLE")
        self.no(rev(rule="voyager.earn-suite-award"), "FIELD_NOT_REVISABLE")
        self.no(rev(account="h-other"), "FIELD_NOT_REVISABLE")
        self.no(rev(confirmed_by="Somebody"), "FIELD_NOT_REVISABLE")
        self.no(rev(by=None, expires_on="2028-06-30"), "ATTESTATION_REQUIRED")                        # a maintainer cannot extend it alone
        self.no(rev(by="test maintainer", expires_on="2028-06-30"), "OWNER_ATTESTATION_REQUIRED")
        self.no(rev(person=CASEY, expires_on="2028-06-30"), "UNKNOWN_TARGET")
        self.no(rev(expires_on="2026-01-01"), "BAD_DATES")
        self.no(self.cs("revise_entitlement", ALEX, target=fare, data={"set": {}}), "MISSING_DATA")
        fix = lambda by="owner", **d: self.cs("correct_entry", ALEX, by, data=d)                       # noqa: E731
        q = "q-%s-%s-2026" % (ACCT, MEASURE)
        self.no(fix(by=None, record="qualification", id=q, entry="r-2026-10"), "ATTESTATION_REQUIRED")
        self.no(fix(record="qualification", id=q, entry="r-no-such"), "UNKNOWN_TARGET")
        self.no(fix(record="holding", id=ACCT, entry="x"), "BAD_DATA")
        self.no(fix(record="qualification", id=q, entry="r-2026-10",
                    replacement={"id": "r-2026-06", "value": 74900, "observed_on": "2026-10-31", "state": "confirmed"}), "ID_EXISTS")

    def test_personal_ops_are_the_only_way_in(self):
        s = self.store()
        self.assertEqual(lint(s), [])
        # a hand-edited "confirmed" record with nobody's attestation behind it does not pass lint
        path = "profiles/%s/entitlements/e-forged.json" % CASEY
        s.files[path] = {"id": "e-forged", "rule": "voyager.earn-concierge-status", "entity": STATUS, "account": ACCT, "cycle": "2027",
                         "state": "confirmed", "effective_from": "2027-11-01", "expires_on": "2029-02-28"}
        self.assertEqual({i[1] for i in lint(s)}, {"UNATTESTED_CONFIRMATION"})
        s.files[path].update(confirmed_by="test maintainer", confirmed_on=D)
        self.assertEqual({i[1] for i in lint(s)}, {"UNATTESTED_CONFIRMATION"})
        # holding the card through set_holding creates no progress, no achievement and no entitlement
        self.ok(self.cs("set_holding", BLAKE, data={"holding": {"id": ACCT, "entity": "card.northwind-voyager", "state": "confirmed", "valid_from": "2027-11-01"}}))
        p = self.store().profile(BLAKE)
        self.assertEqual((p.qualifications, p.entitlements), ({}, {}))
        r = evaluate(self.store(), BLAKE, D)
        self.assertEqual([r.have(e) for e in SHORT], [NOT_AVAILABLE] * 4)
        code, text = cli(self.root, "earned", "--profile", BLAKE, "--as-of", D)
        self.assertEqual(text.count("NOT_RECORDED - no progress recorded for this cycle"), 4)        # on offer; nothing assumed

    def test_tables_carry_no_personal_earned_facts_and_import_creates_none(self):
        for name in sorted(os.listdir(os.path.join(self.root, "tables"))):
            with open(os.path.join(self.root, "tables", name), encoding="utf-8") as f:
                text = f.read()
            for needle in ("r-2026", "e-2026", "e-2027", "91250", "61300", "qualifying-spend", "entitlement", "voyager.earn-", "u-2026"):
                self.assertFalse(needle in text, "%s appears in tables/%s" % (needle, name))
        self.assertFalse([c for cols in tables.COLUMNS.values() for c in cols if "progress" in c or "entitle" in c or "achiev" in c])
        out = tables.import_tables(self.root, "tables", "test maintainer", D)
        self.assertTrue(out["ok"], out.get("errors"))
        self.assertEqual((out["changesets"], out["applied"]), ([], []))                              # untouched tables: nothing to do
        with open(os.path.join(self.root, "tables", "benefits.csv"), encoding="utf-8") as f:
            edited = f.read().replace("Northwind Voyager companion fare (synthetic)", "Northwind Voyager companion fare (synthetic) renamed")
        with open(os.path.join(self.root, "tables", "benefits.csv"), "w", encoding="utf-8") as f:
            f.write(edited)
        before = {p: json.dumps(v, sort_keys=True) for p, v in self.store().files.items() if "/qualifications/" in p or "/entitlements/" in p
                  or p.startswith("data/kb/rules/voyager.earn-")}
        out = tables.import_tables(self.root, "tables", "test maintainer", D)
        self.assertTrue(out["ok"], out.get("errors"))
        self.assertEqual({c["op"] for c in out["changesets"]}, {"revise_entity"})
        after = self.store().files
        self.assertEqual({p: json.dumps(after[p], sort_keys=True) for p in before}, before)          # earn rules and personal records untouched


class TestIdempotency(Base):
    def test_the_same_changeset_twice_changes_nothing(self):
        c = self.progress(ALEX, "2027", "r-2027-10", 84000, "2027-10-31")
        self.ok(c)
        self.no(c, "DUPLICATE_CHANGESET")
        q = self.store().profile(ALEX).qualifications["q-%s-%s-2027" % (ACCT, MEASURE)]
        self.assertEqual([r["id"] for r in q["readings"]], ["r-2027-04", "r-2027-09", "r-2027-10"])

    def test_the_same_fact_under_a_new_id_is_refused_not_double_counted(self):
        self.no(self.progress(ALEX, "2026", "r-copy", 91250, "2026-12-31", final=True), "DUPLICATE_READING")
        self.no(self.usage(ALEX, "e-2026-milestone-credit", "u-copy", 80, "2027-02-10", basis="Hotel"), "DUPLICATE_USAGE")
        self.no(self.instance(ALEX, "2027", "e-copy", "voyager.earn-concierge-status", "2027-10-06", "2029-02-28"), "DUPLICATE_INSTANCE")
        self.assertEqual(self.credit(ALEX, D, "e-2026-milestone-credit"), (300, 200, 60, 100, 40))
        second = self.usage(ALEX, "e-2026-milestone-credit", "u-second", 80, "2027-02-10", basis="Hotel, second night (separate charge)")
        self.ok(second)                                                          # a real second use is recordable once it is described as one
        self.assertEqual(self.credit(ALEX, D, "e-2026-milestone-credit")[1], 280)

    def test_a_batch_is_all_or_nothing(self):
        before, log = self.store().digest(), len(read_audit(self.root))
        out = changes.apply_many(self.root, [self.progress(ALEX, "2027", "r-2027-10", 84000, "2027-10-31"),
                                             self.usage(ALEX, "e-2026-milestone-credit", "u-x", 500, "2027-11-01")])
        self.assertFalse(out["ok"])
        self.assertEqual((out["failed_index"], self.store().digest(), len(read_audit(self.root))), (1, before, log + 1))


class TestCorrectionsAndHistory(Base):
    def snapshot(self, cs_id):
        with open(os.path.join(self.root, "data/audit/previous", cs_id + ".json"), encoding="utf-8") as f:
            return json.load(f)["records"]

    def test_correcting_a_reading_keeps_the_old_one_and_reopens_the_question(self):
        q = "q-%s-%s-2026" % (ACCT, MEASURE)
        self.assertEqual(self.picture(ALEX, "2026-11-05", "2026")[0]["award"], ("ACHIEVED", "ACTIVATION_REQUIRED"))
        c = self.cs("correct_entry", ALEX, data={"record": "qualification", "id": q, "entry": "r-2026-10", "replacement": {
            "id": "r-2026-10b", "value": 74900, "observed_on": "2026-10-31", "state": "confirmed", "basis": "Misread the statement; corrected"}})
        self.ok(c)
        readings = {r["id"]: r for r in self.store().profile(ALEX).qualifications[q]["readings"]}
        self.assertEqual((readings["r-2026-10"]["state"], readings["r-2026-10"]["superseded_by"], readings["r-2026-10"]["value"]),
                         ("superseded", "r-2026-10b", 76900))                     # still on file, no longer counted
        pic, have, flags = self.picture(ALEX, "2026-11-05", "2026")
        self.assertEqual(pic["award"][0], "UNCERTAIN")                           # 74,900 in October, 91,250 at year end: crossed some time between
        self.assertEqual(have["award"], NOT_AVAILABLE)                           # so the award is no longer shown as ready to activate
        pic, have, flags = self.picture(ALEX, "2026-12-20", "2026")
        self.assertEqual((pic["status"], have["status"]), (("UNCERTAIN", "ACTIVE"), ESTABLISHED))   # the account record stands on the owner's word...
        self.assertIn("QUALIFICATION_NOT_RECORDED", flags)                       # ...and the gap behind it is shown
        self.assertEqual(self.picture(ALEX, "2027-01-05", "2026")[0]["status"], ("ACHIEVED", "ACTIVE"))   # the final figure settles it
        before = self.snapshot(c["id"])["profiles/%s/qualifications/%s.json" % (ALEX, q)]["before"]
        self.assertEqual([r["state"] for r in before["readings"]], ["confirmed"] * 3)                 # the earlier version is preserved
        code, text = cli(self.root, "earned", "--profile", ALEX, "--as-of", "2027-03-10", "--cycle", "2026", "--detail")
        self.assertIn("-> r-2026-10b", text)

    def test_correcting_and_withdrawing_use(self):
        credit = "e-2026-milestone-credit"
        self.ok(self.cs("correct_entry", ALEX, data={"record": "entitlement", "id": credit, "entry": "u-2027-02-10", "replacement": {
            "id": "u-2027-02-10b", "amount": 95, "used_on": "2027-02-10", "state": "confirmed", "basis": "Hotel (corrected amount)"}}))
        self.assertEqual(self.credit(ALEX, D, credit), (300, 215, 60, 85, 25))
        self.assertEqual(self.credit(ALEX, "2027-01-01", credit), (300, 120, 0, 180, 180))           # earlier dates are untouched
        self.ok(self.cs("correct_entry", ALEX, by=None, data={"record": "entitlement", "id": credit, "entry": "u-2027-03-02"}))   # never confirmed: a maintainer may withdraw it
        self.assertEqual(self.credit(ALEX, D, credit), (300, 215, 0, 85, 85))
        self.assertNotIn("CREDIT_USE_UNCONFIRMED", self.picture(ALEX, D, "2026")[2])
        self.no(self.cs("correct_entry", ALEX, data={"record": "entitlement", "id": credit, "entry": "u-2027-03-02"}), "BAD_STATE")
        usage = self.store().profile(ALEX).entitlements[credit]["usage"]
        self.assertEqual([(u["id"], u["state"]) for u in usage], [("u-2026-12-03", "confirmed"), ("u-2027-02-10", "superseded"),
                                                                  ("u-2027-03-02", "superseded"), ("u-2027-02-10b", "confirmed")])

    def test_revising_dates_ending_and_withdrawing_an_entitlement(self):
        fare, path = "e-2026-companion-fare", "profiles/%s/entitlements/e-2026-companion-fare.json" % ALEX
        c = self.cs("revise_entitlement", ALEX, target=fare, data={"set": {"expires_on": "2027-11-30", "basis": "Certificate shows November 30"}})
        self.ok(c)
        s = self.store()
        self.assertEqual((evaluate(s, ALEX, "2027-11-30").have(FARE), evaluate(s, ALEX, "2027-12-01").have(FARE)), (ESTABLISHED, NOT_AVAILABLE))
        self.assertIn("TERM_DIFFERS_FROM_RULE", {f["code"] for f in evaluate(s, ALEX, "2027-06-01").flags})   # the personal date is used, and the difference is shown
        self.assertEqual(self.snapshot(c["id"])[path]["before"]["expires_on"], "2027-12-31")
        # undo that correction exactly (reviewer-attested revert): the earlier record comes back byte for byte
        self.ok(self.cs("revert_changeset", data={"changeset": c["id"]}, attestation=REVIEW))
        self.assertEqual(self.store().files[path], Store.load(self.built).files[path])
        # the status is ended early on the account
        status = "e-2027-concierge-status"
        self.ok(self.cs("revise_entitlement", ALEX, target=status, data={"set": {"ended_on": "2028-06-30", "end_reason": "Account closed (invented)"}}))
        s = self.store()
        self.assertEqual((evaluate(s, ALEX, "2028-06-30").have(STATUS), evaluate(s, ALEX, "2028-07-01").have(STATUS)), (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(self.picture(ALEX, "2028-07-01", "2027")[0]["status"], ("ACHIEVED", "ENDED"))
        self.assertEqual(evaluate(s, ALEX, "2028-07-01").have(LINE), NOT_AVAILABLE)                  # what depended on it goes too
        # a record entered by mistake is withdrawn: kept on file, counted for nothing, and the slot is free again
        self.ok(self.cs("revise_entitlement", ALEX, target="e-2027-milestone-credit", data={"set": {"state": "superseded"}}))
        self.assertEqual(self.picture(ALEX, D, "2027")[0]["credit"], ("ACHIEVED", "EARNED_NOT_CONFIRMED"))
        self.assertTrue(os.path.exists(os.path.join(self.root, "profiles", ALEX, "entitlements", "e-2027-milestone-credit.json")))
        self.ok(self.instance(ALEX, "2027", "e-2027-milestone-credit-b", "voyager.earn-milestone-credit", "2027-10-10", "2028-12-31",
                              allowance={"amount": 300, "unit": "units"}))
        self.assertEqual(self.picture(ALEX, D, "2027")[0]["credit"], ("ACHIEVED", "ACTIVE"))

    def test_every_change_leaves_a_log_line_a_copy_and_a_before_snapshot(self):
        c = self.usage(ALEX, "e-2026-milestone-credit", "u-new", 25, "2027-11-01", basis="Taxi")
        self.ok(c)
        last = read_audit(self.root)[-1]
        path = "profiles/%s/entitlements/e-2026-milestone-credit.json" % ALEX
        self.assertEqual((last["changeset"], last["op"], last["result"], last["changed"]), (c["id"], "record_usage", "applied", [path]))
        with open(os.path.join(self.root, "data/audit/changesets", c["id"] + ".json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["attestation"]["by"], OWNER[ALEX])                          # who said so is kept with the change
        self.assertEqual(len(self.snapshot(c["id"])[path]["before"]["usage"]), 3)
        self.assertEqual(len(self.store().files[path]["usage"]), 4)
        self.assertEqual(self.store().files[path]["usage"][-1]["changeset"], c["id"])                 # and each entry names its changeset


class TestReportCommand(Base):
    def test_text_report_keeps_the_three_layers_apart(self):
        code, text = cli(self.root, "earned", "--profile", ALEX, "--as-of", "2026-12-20", "--cycle", "2026")
        self.assertEqual(code, 0)
        for needle in ("profile=synthetic-alex  owner=Alex (synthetic)  as-of=2026-12-20  [SYNTHETIC DATA]",
                       "ACCOUNT h-card-northwind-voyager  Northwind Voyager (synthetic)  [confirmed, held on this date]",
                       "QUALIFYING YEAR 2026  (2026-01-01 to 2026-12-31)   measure voyager.qualifying-spend",
                       "progress on file  76,900 units as of 2026-10-31",
                       "PUBLIC RULE   voyager.earn-suite-award (verified): 75,000 units",
                       "ACHIEVEMENT   ACHIEVED - at or above the threshold on 2026-10-31 (reading r-2026-10). The day the threshold was crossed is not recorded",
                       "ENTITLEMENT   ACTIVATION_REQUIRED - eligible; the separate activation step had not been done on this date",
                       "record e-2026-concierge-status: ACTIVE  2026-11-08 to 2028-02-29  (confirmed by Alex (synthetic) on 2026-11-14)",
                       "credit: allowance 300 units; used 120 (confirmed); remaining 180",
                       "WHOLE PERSON  CONDITIONAL on this date across all of this person's accounts and qualifying years (from rule voyager.earn-suite-award)",
                       "Only ENTITLEMENT = ACTIVE means the benefit can be used on this date. ACHIEVED means eligible, not held."):
            self.assertIn(needle, text)
        self.assertNotIn("QUALIFYING YEAR 2027", text)
        self.assertNotIn("91,250", text)                                         # the year-end figure is dated later than this query

    def test_json_report_carries_the_whole_chain(self):
        code, text = cli(self.root, "--json", "earned", "--profile", ALEX, "--as-of", "2027-03-10", "--account", ACCT, "--cycle", "2026")
        o = json.loads(text)
        self.assertEqual((code, o["profile"], o["as_of"], o["synthetic"], [c["cycle"] for c in o["accounts"][0]["cycles"]]),
                         (0, ALEX, "2027-03-10", True, ["2026"]))
        b = {x["entity"]: x for x in o["accounts"][0]["cycles"][0]["benefits"]}[CREDIT]
        self.assertEqual(b["public"]["rule"], "voyager.earn-milestone-credit")                        # source rule...
        self.assertEqual(b["chain"]["rule_evidence"][0]["id"], "ev-syn-voyager-milestones")           # ...its evidence...
        self.assertEqual([(r["id"], r["confirmed_by"], r["changeset"][:12]) for r in b["chain"]["readings"]],
                         [("r-2026-10", "Alex (synthetic)", "cs-20261114-")])                        # ...the owner's qualifying reading and its changeset...
        i = b["instances"][0]
        self.assertEqual((i["id"], i["state"], i["confirmed_by"], i["effective_from"], i["expires_on"]),
                         ("e-2026-milestone-credit", "ACTIVE", "Alex (synthetic)", "2026-11-08", "2027-12-31"))   # ...the account record...
        self.assertEqual((i["credit"]["allowance"], i["credit"]["used"], i["credit"]["possibly_used"], i["credit"]["remaining"]), (300, 200, 60, 100))
        self.assertEqual((b["engine_status"], b["engine_source"]), (ESTABLISHED, "entitlement:e-2026-milestone-credit"))   # ...and the result
        self.assertEqual([f["code"] for f in o["flags"]], ["CREDIT_USE_UNCONFIRMED"])
        code, text = cli(self.root, "earned", "--profile", ALEX, "--as-of", "2027-03-10", "--account", "h-some-other-account")
        self.assertIn("No account of this person has an earned-benefit rule or record.", text)

    def test_detail_view_explain_and_status(self):
        code, text = cli(self.root, "earned", "--profile", ALEX, "--as-of", "2027-03-10", "--cycle", "2026", "--detail")
        for needle in ("reading r-2026-06", "[June statement]", "source ev-syn-voyager-milestones: Northwind Voyager milestone benefit terms",
                       "basis: Credit shown on the account page", "use u-2027-03-02", "unconfirmed"):
            self.assertIn(needle, text)
        code, text = cli(self.root, "explain", "--profile", ALEX, "--as-of", "2027-03-10", LINE)
        self.assertIn("have:status.orbit-concierge  <- entitlement:e-2026-concierge-status", text)
        code, text = cli(self.root, "explain", "--profile", DEVON, "--as-of", "2027-01-05", AWARD)
        self.assertIn("qualification:q-h-card-northwind-voyager-voyager.qualifying-spend-2026", text)
        self.assertIn("DO Activate the suite night award", text)
        code, text = cli(self.root, "status", "--profile", ALEX, "--as-of", "2027-12-01")
        self.assertIn("Earned benefits on record (6)", text)
        self.assertIn("cycle 2027  2027-10-06 to 2028-12-31  remaining 300", text)
        code, text = cli(self.root, "earned", "--profile", "synthetic-nobody")
        self.assertEqual(code, 2)

    def test_changeset_files_through_the_command_line(self):
        path = os.path.join(self.tmp, "cs.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.progress(CASEY, "2027", "r-2027-10", 80500, "2027-10-31", basis="October statement"), f)
        code, text = cli(self.root, "apply", path, "--dry-run")
        self.assertEqual((code, "VALID (dry run, nothing written)" in text), (0, True))
        self.assertEqual(self.store().profile(CASEY).qualifications.get("q-%s-%s-2027" % (ACCT, MEASURE)), None)
        code, text = cli(self.root, "apply", path)
        self.assertEqual(code, 0)
        self.assertIn("can_get:status.orbit-concierge: NOT_AVAILABLE -> ESTABLISHED", text)           # eligibility appears...
        self.assertNotIn("have:status.orbit-concierge: NOT_AVAILABLE -> ESTABLISHED", text)           # ...possession does not
        self.assertEqual(evaluate(self.store(), CASEY, D).have(STATUS), CONDITIONAL)
        code, text = cli(self.root, "tables", "status")
        self.assertIn("out of date with the store: no", text)


if __name__ == "__main__":
    unittest.main()
