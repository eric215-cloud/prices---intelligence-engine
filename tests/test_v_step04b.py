"""Step 04B: adversarial tests for the Bilt election repair (A1, A2, A3, A8) and for the contained findings (A4, A6, A7).

Every cardholder here is INVENTED, with invented account dates. The committed Bilt definitions run on a scratch copy of
the live store; nothing is written back. Part 1 approves the definitions in the scratch copy (as a reviewer would) so
the other safeguards can be seen on their own; part 2 checks the approval gate itself, on scratch copies.

The column order of `at` is (tiered points, Flexible Bilt Cash, $200 Bilt Cash, $400 hotel credit, $600 Bilt Cash).
"""
import datetime
import json
import os
import shutil
import tempfile
import unittest

from util import approve_elections_on_disk, flag_codes
from condition_classes import scratch_real
from prices import changes
from prices.elections import next_cycle_start, presence, terms_digest
from prices.engine import ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.store import Store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = "election.bilt-palladium."
B = "benefit.bilt-palladium."
FIVE = ("housing-tiered-points", "housing-flex-bilt-cash-legacy", "annual-bilt-cash-200-legacy",
        "hotel-credit-400-semiannual-legacy", "annual-bilt-cash-600-post2027")
EST, NO, UNR = ESTABLISHED, NOT_AVAILABLE, UNRESOLVED
SIX = ("housing-tiered-points", "housing-flex-bilt-cash", "legacy-election", "refreshed-arrangement",
       "annual-credits-legacy", "annual-credits-600")
d = datetime.date


def acct(opened="2026-03-10", shown="2027-04-05", **extra):
    h = {"id": "h-card", "entity": "card.bilt-palladium", "state": "confirmed", "valid_from": opened, "opened_on": opened}
    if shown:
        h["anniversary_on"] = shown
    h.update(extra)
    return h


def el(hid, option, start=None, end=None, state="confirmed", **extra):
    h = {"id": hid, "entity": E + option, "state": "ended" if end else state}
    if start:
        h["valid_from"] = start
    if end:
        h["valid_to"] = end
    h.update(extra)
    return h


FLEX = el("f1", "housing-flex-bilt-cash", "2026-05-05")
FLEX15 = el("f1", "housing-flex-bilt-cash", "2026-05-15")        # on a card whose cycle starts on the 15th

PEOPLE = {
    # ---- A2: the Legacy Election needs Flexible Bilt Cash to be the active Rewards Option when it is made
    "a2-positive": [acct(), FLEX, el("e1", "legacy-election", "2026-11-20")],
    "a2-missing": [acct(), el("e1", "legacy-election", "2026-11-20")],
    "a2-tiered": [acct(), el("t1", "housing-tiered-points", "2026-03-10"), el("e1", "legacy-election", "2026-11-20")],
    "a2-too-late": [acct(), el("e1", "legacy-election", "2026-11-20"), el("f1", "housing-flex-bilt-cash", "2026-12-05")],
    "a2-ended-before": [acct(), el("f1", "housing-flex-bilt-cash", "2026-05-05", "2026-10-31"), el("e1", "legacy-election", "2026-11-20")],
    "a2-unconfirmed": [acct(), el("f1", "housing-flex-bilt-cash", "2026-05-05", state="unconfirmed"), el("e1", "legacy-election", "2026-11-20")],
    # ---- A3 (Q note 2): a switch requested inside a billing cycle takes effect on the first day of the next one
    "a3-request": [acct(billing_cycle_day=15), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-14"),
                   el("f1", "housing-flex-bilt-cash", "2026-06-15", requested_on="2026-06-10")],
    # the request date entered as the start: the issuer says the 15th
    "a3-request-as-start": [acct(billing_cycle_day=15), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-09"),
                            el("f1", "housing-flex-bilt-cash", "2026-06-10", requested_on="2026-06-10")],
    # no request date, but the cycle day contradicts the start
    "a3-off-cycle": [acct(billing_cycle_day=15), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-09"),
                     el("f1", "housing-flex-bilt-cash", "2026-06-10")],
    # a request with no effective date and no cycle day: when it took effect is not known
    "a3-request-only": [acct(), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-09"),
                        el("f1", "housing-flex-bilt-cash", requested_on="2026-06-10")],
    # the same, but the cycle day is known: the effective date follows from it
    "a3-request-cycle": [acct(billing_cycle_day=15), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-14"),
                         el("f1", "housing-flex-bilt-cash", requested_on="2026-06-10")],
    # leaving the Legacy arrangement: requested 2027-08-20, effective the next cycle (2027-09-15)
    "a3-exit": [acct(billing_cycle_day=15), FLEX15, el("e1", "legacy-election", "2026-11-20", "2027-09-14", exit_requested_on="2027-08-20"),
                el("r1", "refreshed-arrangement", "2027-09-15")],
    "a3-exit-on-request-day": [acct(billing_cycle_day=15), FLEX15,
                               el("e1", "legacy-election", "2026-11-20", "2027-08-19", exit_requested_on="2027-08-20"),
                               el("r1", "refreshed-arrangement", "2027-08-20")],
    # ---- A7: nothing but an election on file; no Bilt Cash lot, balance or conversion can be inferred
    "a7-nothing": [acct()],
    # A3: a Flexible Bilt Cash start that is not a cycle start makes the prerequisite unproven too
    "a3-prereq-off-cycle": [acct(billing_cycle_day=15), FLEX, el("e1", "legacy-election", "2026-11-20")],
}


def build(tmp, people, approve=True):
    for sub in ("data", "profiles", "tables"):
        shutil.copytree(os.path.join(ROOT, sub), os.path.join(tmp, sub))
    reviewer = Store.load(tmp).vocab["promotion_reviewers"][0]
    out = changes.apply_many(tmp, [
        {"id": "cs-20261115-scratch-v%d" % i, "op": "promote_candidate", "target": "c-cb.bilt-palladium." + k, "author": "test",
         "date": "2026-11-15", "reason": "scratch copy only",
         "data": {"review_by": "2027-12-15", "conditions": scratch_real(Store.load(tmp).candidates["c-cb.bilt-palladium." + k], governed=True)},
         "attestation": {"by": reviewer, "on": "2026-11-15", "statement": "scratch copy only"}} for i, k in enumerate(FIVE)])
    assert out["ok"], out["errors"]
    if approve:
        approve_elections_on_disk(tmp)
    for name, hs in people.items():
        owner = "Invented cardholder %s" % name
        os.makedirs(os.path.join(tmp, "profiles", "syn-" + name, "holdings"))
        with open(os.path.join(tmp, "profiles", "syn-" + name, "profile.json"), "w") as f:
            json.dump({"id": "syn-" + name, "label": "invented", "synthetic": True, "owner": owner}, f)
        for h in hs:
            h = dict(h)
            if h["state"] in ("confirmed", "ended"):
                h["confirmed_by"], h["confirmed_on"] = owner, "2026-11-15"
            with open(os.path.join(tmp, "profiles", "syn-" + name, "holdings", h["id"] + ".json"), "w") as f:
                json.dump(h, f)
    return Store.load(tmp)


class Base(unittest.TestCase):
    APPROVE = True

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="prices-step04b-")
        cls.s = build(cls.tmp, PEOPLE, cls.APPROVE)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def at(self, who, day):
        r = evaluate(self.s, "syn-" + who, day)
        return tuple(r.have(B + k) for k in FIVE)

    def flags(self, who, day):
        return flag_codes(evaluate(self.s, "syn-" + who, day))

    def reason(self, who, day):
        return " | ".join(f["detail"] for f in evaluate(self.s, "syn-" + who, day).flags)


class TestA2Prerequisite(Base):
    def test_positive_the_whole_legacy_arrangement_is_established(self):
        for day in ("2026-11-20", "2027-05-01", "2028-06-01"):
            self.assertEqual(self.at("a2-positive", day), (NO, EST, EST, EST, NO), day)

    def test_missing_history_never_establishes_spendable_value(self):
        for who in ("a2-missing", "a2-too-late", "a2-ended-before", "a2-unconfirmed"):
            for day in ("2027-05-01", "2028-06-01"):
                got = self.at(who, day)
                self.assertNotIn(EST, got, (who, day))                       # no Bilt Cash, no hotel credit, no $600
                self.assertIn("ELECTION_TERMS_UNVERIFIED", self.flags(who, day), (who, day))
                self.assertIn("no confirmed record shows that", self.reason(who, day), (who, day))

    def test_a_contradicting_record_rules_the_election_out(self):
        got = self.at("a2-tiered", "2027-05-01")
        self.assertNotIn(EST, got[1:3])
        self.assertIn("ELECTION_NOT_PERMITTED", self.flags("a2-tiered", "2027-05-01"))
        self.assertIn("housing-tiered-points", self.reason("a2-tiered", "2027-05-01"))

    def test_before_the_transition_the_automatic_credits_do_not_depend_on_it(self):
        # the $200 and $400 apply to every pre-2027 account until its transition anniversary, election or not
        self.assertEqual(self.at("a2-missing", "2026-12-01")[2:], (EST, EST, NO))


class TestA3EffectiveDates(Base):
    def test_a_request_inside_a_cycle_takes_effect_at_the_next_cycle(self):
        self.assertEqual(next_cycle_start({"billing_cycle_day": 15}, d(2026, 6, 10)), d(2026, 6, 15))
        self.assertEqual(next_cycle_start({"billing_cycle_day": 15}, d(2026, 6, 15)), d(2026, 7, 15))   # a request on the 15th: next month
        self.assertEqual(next_cycle_start({"billing_cycle_day": 15}, d(2026, 12, 20)), d(2027, 1, 15))
        self.assertIsNone(next_cycle_start({}, d(2026, 6, 10)))
        for day in ("2026-06-10", "2026-06-14"):
            self.assertEqual(self.at("a3-request", day)[:2], (EST, NO), day)     # still tiered: the request is not the switch
        self.assertEqual(self.at("a3-request", "2026-06-15")[:2], (NO, EST))

    def test_the_request_date_as_the_start_is_refused(self):
        for who in ("a3-request-as-start", "a3-off-cycle"):
            got = self.at(who, "2026-06-12")
            self.assertEqual(got[:2], (UNR, UNR), who)
            self.assertIn("ELECTION_EFFECTIVE_DATE_INVALID", self.flags(who, "2026-06-12"), who)

    def test_a_request_without_an_effective_date(self):
        self.assertEqual(self.at("a3-request-only", "2026-06-05")[:2], (EST, NO))           # before the request: as it was
        self.assertEqual(self.at("a3-request-only", "2026-06-10")[:2], (UNR, UNR))
        for day in ("2026-06-11", "2026-07-01"):
            self.assertEqual(self.at("a3-request-only", day)[:2], (UNR, UNR), day)
            self.assertIn("ELECTION_EFFECTIVE_DATE_NOT_RECORDED", self.flags("a3-request-only", day), day)
        # with the cycle day the effective date follows
        self.assertEqual(self.at("a3-request-cycle", "2026-06-12")[:2], (EST, NO))
        self.assertEqual(self.at("a3-request-cycle", "2026-06-15")[:2], (NO, EST))

    def test_leaving_takes_effect_at_the_next_cycle(self):
        self.assertEqual(self.at("a3-exit", "2027-09-14"), (NO, EST, EST, EST, NO))
        self.assertEqual(self.at("a3-exit", "2027-09-15")[:4], (EST, NO, NO, NO))
        # an exit recorded as taking effect on the request day: the record's own dates are in doubt, so neither the Legacy
        # benefits nor their loss is concluded (before this repair the conflict path answered NOT_AVAILABLE for them)
        for day in ("2027-08-25", "2027-09-20"):
            self.assertEqual(self.at("a3-exit-on-request-day", day), (UNR,) * 5, day)
            self.assertIn("ELECTION_EFFECTIVE_DATE_INVALID", self.flags("a3-exit-on-request-day", day), day)

    def test_an_off_cycle_prerequisite_does_not_count(self):
        self.assertIn("ELECTION_EFFECTIVE_DATE_INVALID", self.flags("a3-prereq-off-cycle", "2026-06-01"))
        self.assertEqual(self.at("a3-prereq-off-cycle", "2026-06-01")[:2], (UNR, UNR))
        self.assertNotIn(EST, self.at("a3-prereq-off-cycle", "2027-05-01")[:2] + self.at("a3-prereq-off-cycle", "2027-05-01")[4:])
        self.assertIn("ELECTION_TERMS_UNVERIFIED", self.flags("a3-prereq-off-cycle", "2027-05-01"))

    def test_presence_is_three_valued(self):
        card = {"billing_cycle_day": 15}
        opt = {"election": {"takes_effect": "next_billing_cycle"}}
        h = {"valid_from": "2026-06-15", "requested_on": "2026-06-10", "state": "confirmed"}
        self.assertEqual([presence(h, d(2026, 6, x), opt, card) for x in (9, 12, 15)], [None, None, "in"])
        h = {"requested_on": "2026-06-10", "state": "confirmed"}
        self.assertEqual(presence(h, d(2026, 6, 12), opt, {}), "maybe")
        h = {"valid_from": "2026-06-10", "requested_on": "2026-06-10", "state": "confirmed"}
        self.assertEqual(presence(h, d(2026, 6, 12), opt, card), "invalid")


class TestA7Contained(Base):
    def test_no_value_from_an_empty_history(self):
        # there is no lot, balance, expiry or conversion logic: nothing about Bilt Cash is established from absence
        for day in ("2027-05-01", "2028-06-01"):
            self.assertNotIn(EST, self.at("a7-nothing", day), day)


class TestA8ApprovalGate(Base):
    APPROVE = False

    def test_unapproved_definitions_establish_nothing(self):
        for day in ("2026-12-01", "2027-05-01"):
            got = self.at("a2-positive", day)
            self.assertNotIn(EST, got[:2] + got[4:], day)
            self.assertIn("ELECTION_DEFINITION_NOT_APPROVED", self.flags("a2-positive", day), day)

    def test_lint_reports_every_unapproved_definition(self):
        warned = {i[2] for i in lint(self.s) if i[1] == "ELECTION_DEFINITION_NOT_APPROVED"}
        self.assertEqual(len([p for p in warned if "election.bilt-palladium." in p]), 6)

    def approve(self, tmp, target, by, author="reviewer", terms=None):
        s = Store.load(tmp)
        return changes.apply(tmp, {
            "id": "cs-20261120-v-approve-%s-%s" % (target.split(".")[-1], by.replace(" ", "-").lower()), "op": "approve_election",
            "target": target, "author": author, "date": "2026-11-20", "reason": "test",
            "data": {"terms": terms if terms is not None else terms_digest(s.entities[target])},
            "attestation": {"by": by, "on": "2026-11-20", "statement": "test"}})

    def scratch(self):
        tmp = tempfile.mkdtemp(prefix="prices-step04b-gate-")
        self.addCleanup(shutil.rmtree, tmp)
        build(tmp, {}, approve=False)
        return tmp

    def test_the_builder_and_the_author_cannot_approve(self):
        tmp = self.scratch()
        t = E + "legacy-election"
        by = Store.load(tmp).entities[t]["election"]["terms_by"]
        self.assertEqual(by["attested_by"], "Commissioning build")
        out = self.approve(tmp, t, "Commissioning build")
        self.assertFalse(out["ok"])
        self.assertIn("NOT_INDEPENDENT", " ".join(out["errors"]))
        out = self.approve(tmp, t, "Bradley", author=by["author"])
        self.assertIn("NOT_INDEPENDENT", " ".join(out["errors"]))

    def test_an_approval_covers_exactly_the_terms_read(self):
        tmp = self.scratch()
        t = E + "legacy-election"
        out = self.approve(tmp, t, "Bradley", terms="0" * 16)
        self.assertIn("TERMS_CHANGED", " ".join(out["errors"]))
        self.assertTrue(self.approve(tmp, t, "Bradley")["ok"])
        s = Store.load(tmp)
        self.assertEqual(s.entities[t]["election"]["approval"]["by"], "Bradley")
        # revising the terms drops the approval with them
        block = dict(s.entities[t]["election"])
        block.pop("approval")
        block["source_note"] = block.get("source_note", "") + " (revised)"
        out = changes.apply(tmp, {"id": "cs-20261120-v-revise", "op": "revise_entity", "target": t, "author": "Claude (test)",
                                  "date": "2026-11-20", "reason": "test", "data": {"set": {"election": block}},
                                  "attestation": {"by": "Commissioning build", "on": "2026-11-20", "statement": "test"}})
        self.assertTrue(out["ok"], out.get("errors"))
        self.assertNotIn("approval", Store.load(tmp).entities[t]["election"])

    def test_an_approval_cannot_be_written_in_with_the_terms(self):
        tmp = self.scratch()
        t = E + "legacy-election"
        block = dict(Store.load(tmp).entities[t]["election"], approval={"by": "Bradley", "on": "2026-11-20"})
        out = changes.apply(tmp, {"id": "cs-20261120-v-sneak", "op": "revise_entity", "target": t, "author": "Claude (test)",
                                  "date": "2026-11-20", "reason": "test", "data": {"set": {"election": block}},
                                  "attestation": {"by": "Commissioning build", "on": "2026-11-20", "statement": "test"}})
        self.assertFalse(out["ok"])

    def test_the_committed_store_is_not_approved_by_engineering(self):
        s = Store.load(ROOT)
        for k in SIX:
            e = s.entities[E + k]["election"]
            self.assertNotIn("approval", e, k)
            self.assertEqual(e["terms_by"]["attested_by"], "Commissioning build", k)
            self.assertNotIn("anniversary_cycle_days", e, k)


class TestContainment(unittest.TestCase):
    def test_a6_links_are_one_level_deep(self):
        tmp = tempfile.mkdtemp(prefix="prices-step04b-a6-")
        self.addCleanup(shutil.rmtree, tmp)
        s = build(tmp, {}, approve=False)
        # make the $600 group's option follow an option whose own group has linked options (a chain)
        s.entities[E + "annual-credits-600"]["election"]["follows"] = E + "refreshed-arrangement"
        s.entities[E + "refreshed-arrangement"]["election"]["follows"] = E + "housing-tiered-points"
        errs = {i[1] for i in lint(s) if i[0] == "ERROR"}
        self.assertIn("BAD_ELECTION_SHAPE", errs)

    def test_a4_product_change_is_documented_not_modelled(self):
        with open(os.path.join(ROOT, "docs", "ELECTIONS.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("even if you opted out on your current card", text)
        self.assertIn("DISC-03-04", text)
        with open(os.path.join(ROOT, "docs", "operating", "OP-12-elections.md"), encoding="utf-8") as f:
            self.assertIn("product change", f.read().lower())


if __name__ == "__main__":
    unittest.main()
