"""Cardholder elections (ENG-02): mutually exclusive options on one card.

Part 1 (TestSemantics ... TestStructure) uses small invented stores built in memory.
Part 2 (TestLiveBiltDefinitions) applies the real Bilt Palladium election definitions to a scratch copy of the
live store, promotes Argon's five governed candidates THERE ONLY (the committed store keeps them proposed), and adds
an invented cardholder. Nothing in part 2 is written back.

The rules under test:
  * no election recorded            -> every option that could apply is UNRESOLVED, none established
  * one election, owner-confirmed   -> that option only, subject to the other conditions
  * contradictory elections         -> detected, flagged, none applied
  * the 2027 transition             -> at the cardholder's own first anniversary on or after 2027-01-01
  * nothing is inferred from the absence of an election
"""
import json
import os
import shutil
import tempfile
import unittest

from util import H, TEST_VOCAB, ent, flag_codes, holding, make_store, rule
from condition_classes import scratch_real
from prices import changes
from prices.elections import anniversary_window, before_anniversary
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.review import timeline
from prices.store import Store
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = "card.x"
D27 = "2027-01-01"


def codes(issues):
    """Every lint code, errors and warnings alike."""
    return {i[1] for i in issues}


def option(oid, group, governs, **terms):
    e = ent(oid, "election", name=oid)
    e["election"] = dict({"group": group, "card": CARD, "governs": list(governs)}, **terms)
    return e


def options():
    return [option("el.tiered", "housing", ["r.tiered"]),
            option("el.flex", "housing", ["r.flex"], opened_before=D27, elect_before_anniversary=D27),
            option("el.legacy", "credits", ["r.c200", "r.h400"], opened_before=D27, default_before_anniversary=D27, elect_before_anniversary=D27),
            option("el.600", "credits", ["r.c600"], starts_at_anniversary=D27)]


def world(card=None, picks=(), extra_rules=(), extra_entities=(), opts=None, rule_status="verified"):
    es = [ent(CARD, "card"), ent("tiered", "benefit"), ent("flex", "benefit"), ent("c200", "benefit"), ent("h400", "benefit"),
          ent("c600", "benefit"), ent("lounge", "benefit"), ent("perk", "benefit")] + (opts if opts is not None else options()) + list(extra_entities)
    rs = [rule("r.tiered", "grants", "tiered", H(CARD), status=rule_status), rule("r.flex", "grants", "flex", H(CARD), status=rule_status),
          rule("r.c200", "grants", "c200", H(CARD), status=rule_status), rule("r.h400", "grants", "h400", H(CARD), status=rule_status),
          rule("r.c600", "grants", "c600", H(CARD), status=rule_status, valid_from=D27),
          rule("r.lounge", "grants", "lounge", H(CARD))] + list(extra_rules)    # r.lounge is not part of any election
    hs = ([card] if card else []) + list(picks)
    return make_store(es, rs, hs)


def card(opened="2025-06-01", **kw):
    h = holding("h-card", CARD, valid_from=kw.pop("valid_from", opened), **kw)
    if opened:
        h["opened_on"] = opened
    return h


def pick(hid, oid, valid_from=None, valid_to=None, **kw):
    h = holding(hid, oid, **kw)
    if valid_from:
        h["valid_from"] = valid_from
    if valid_to:
        h["valid_to"] = valid_to
    return h


def have(s, day, *names):
    r = evaluate(s, "t", day)
    return tuple(r.have(n) for n in names)


def elections_of(s, day):
    return {e["group"]: (e["established"], tuple(sorted(e["unresolved"])), e["reason"]) for e in evaluate(s, "t", day).report().get("elections", [])}


class TestAnniversary(unittest.TestCase):
    def test_first_anniversary_on_or_after(self):
        d = datetime.date
        self.assertEqual(anniversary_window(d(2025, 6, 1), d(2027, 1, 1)), (d(2027, 6, 1), d(2027, 6, 1)))
        self.assertEqual(anniversary_window(d(2026, 1, 1), d(2027, 1, 1)), (d(2027, 1, 1), d(2027, 1, 1)))   # falls on the date itself
        self.assertEqual(anniversary_window(d(2026, 12, 31), d(2027, 1, 1)), (d(2027, 12, 31), d(2027, 12, 31)))
        self.assertEqual(anniversary_window(d(2027, 3, 1), d(2027, 1, 1)), (d(2028, 3, 1), d(2028, 3, 1)))    # opened after: its own first anniversary
        self.assertEqual(anniversary_window(d(2024, 2, 29), d(2027, 1, 1)), (d(2027, 2, 28), d(2027, 3, 1)))  # no Feb 29 in 2027: a window

    def test_before_the_anniversary(self):
        d = datetime.date
        h = {"opened_on": "2025-06-01"}
        self.assertEqual([before_anniversary(h, d(2027, 1, 1), x) for x in (d(2026, 12, 31), d(2027, 5, 31), d(2027, 6, 1))], [True, True, False])
        self.assertEqual(before_anniversary({}, d(2027, 1, 1), d(2026, 7, 1)), True)       # unknown anniversary, but it cannot be before 2027
        self.assertEqual(before_anniversary({}, d(2027, 1, 1), d(2027, 7, 1)), None)
        leap = {"opened_on": "2024-02-29"}
        self.assertEqual([before_anniversary(leap, d(2027, 1, 1), x) for x in (d(2027, 2, 27), d(2027, 2, 28), d(2027, 3, 1))], [True, None, False])


class TestUnknownElection(unittest.TestCase):
    def test_no_election_recorded_establishes_neither_side(self):
        s = world(card())
        self.assertEqual(lint(s), [])
        r = evaluate(s, "t", "2026-11-15")
        self.assertEqual((r.have("tiered"), r.have("flex")), (UNRESOLVED, UNRESOLVED))       # might be either; established as neither
        self.assertEqual(r.have("lounge"), ESTABLISHED)                                      # rules outside any election are untouched
        self.assertIn("ELECTION_NOT_RECORDED", flag_codes(r))
        self.assertTrue(any("no election recorded" in u for u in r.tokens("have:tiered")["unknowns"]))
        rep = r.report()
        # legacy credits apply by default in 2026 (see TestTransition2027); neither housing option is derived
        self.assertEqual([x["entity"] for x in rep["derived_entitlements"]], ["c200", "h400", "lounge"])
        self.assertNotIn("el.tiered", [x["entity"] for x in rep["unresolved"] + rep["conditional"]])   # options are reported per group

    def test_nothing_is_inferred_from_the_absence_of_an_election(self):
        # an account opened in 2027 cannot take the Flex option, so tiered is the only possibility - still not assumed
        s = world(card("2027-03-01"))
        self.assertEqual(have(s, "2027-06-01", "tiered", "flex"), (UNRESOLVED, NOT_AVAILABLE))
        self.assertEqual(elections_of(s, "2027-06-01")["housing"][:2], (None, ("el.tiered",)))
        # after the 2027 transition, $600 is what applies "unless legacy was retained" - not recording legacy is not a $600 election
        s = world(card("2025-06-01"))
        self.assertEqual(have(s, "2027-07-01", "c200", "h400", "c600"), (UNRESOLVED, UNRESOLVED, UNRESOLVED))

    def test_no_card_no_decision(self):
        s = world()
        r = evaluate(s, "t", "2026-11-15")
        self.assertEqual((r.have("tiered"), r.have("c200")), (NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertNotIn("elections", r.report())
        self.assertEqual(flag_codes(r) & {"ELECTION_NOT_RECORDED"}, set())

    def test_only_candidates_governed_means_no_review_flag(self):
        s = world(card(), rule_status="unverified")
        s.files["data/kb/rules/r.lounge.json"]["verification"]["status"] = "verified"
        for rid in ("r.tiered", "r.flex", "r.c200", "r.h400", "r.c600"):
            s.files["data/kb/rules/%s.json" % rid]["verification"]["status"] = "retired"
        self.assertNotIn("ELECTION_NOT_RECORDED", flag_codes(evaluate(s, "t", "2026-11-15")))


class TestConfirmedElection(unittest.TestCase):
    def test_an_election_activates_its_pathway_only(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01")])
        self.assertEqual(lint(s), [])
        self.assertEqual(have(s, "2026-11-15", "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE))
        r = evaluate(s, "t", "2026-11-15")
        self.assertEqual(r.basis("have:el.tiered"), "personal")
        self.assertEqual(r.via["E"]["have:tiered"][0], "r.tiered")
        s = world(card(), [pick("e1", "el.flex", "2025-06-01")])
        self.assertEqual(have(s, "2026-11-15", "tiered", "flex"), (NOT_AVAILABLE, ESTABLISHED))

    def test_subject_to_the_other_conditions(self):
        s = world(None, [pick("e1", "el.tiered", "2025-06-01")])                              # election but no card
        self.assertEqual(have(s, "2026-11-15", "tiered"), (NOT_AVAILABLE,))
        self.assertIn("ELECTION_WITHOUT_CARD", codes(lint(s)) | flag_codes(evaluate(s, "t", "2026-11-15")))
        s = world(card(state="unconfirmed"), [pick("e1", "el.tiered", "2025-06-01")])          # card unconfirmed
        self.assertEqual(have(s, "2026-11-15", "tiered"), (UNRESOLVED,))
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01")], rule_status="unverified")   # rule unverified
        self.assertEqual(have(s, "2026-11-15", "tiered"), (UNRESOLVED,))
        ended = card(valid_to="2026-12-31")                                                    # card ended: election irrelevant
        self.assertEqual(have(world(ended, [pick("e1", "el.tiered", "2025-06-01")]), "2027-02-01", "tiered"), (NOT_AVAILABLE,))

    def test_unconfirmed_election_is_unresolved(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01", state="unconfirmed")])
        self.assertEqual(have(s, "2026-11-15", "tiered", "flex"), (UNRESOLVED, UNRESOLVED))
        self.assertIn("UNCONFIRMED_ELECTION", flag_codes(evaluate(s, "t", "2026-11-15")))

    def test_election_with_no_start_date(self):
        e = pick("e1", "el.tiered")
        e["confirmed_on"] = "2026-09-01"
        s = world(card(), [e])
        self.assertEqual(have(s, "2026-08-31", "tiered", "flex"), (UNRESOLVED, UNRESOLVED))    # before the owner confirmed it: unknown
        self.assertEqual(have(s, "2026-09-01", "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE))
        self.assertIn("ELECTION_START_NOT_RECORDED", codes(lint(s)))

    def test_downstream_rules_follow_the_election(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01")], extra_rules=[rule("r.perk", "grants", "perk", H("tiered"))])
        self.assertEqual(have(s, "2026-11-15", "perk"), (ESTABLISHED,))
        s = world(card(), [], extra_rules=[rule("r.perk", "grants", "perk", H("tiered"))])
        self.assertEqual(have(s, "2026-11-15", "perk"), (UNRESOLVED,))


class TestConflicts(unittest.TestCase):
    def test_two_options_in_effect_are_reported_and_neither_applied(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01"), pick("e2", "el.flex", "2026-03-01")])
        self.assertIn("CONFLICTING_ELECTIONS", codes(lint(s)))
        self.assertEqual(have(s, "2026-02-01", "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE))   # before the overlap: fine
        r = evaluate(s, "t", "2026-11-15")
        self.assertEqual((r.have("tiered"), r.have("flex")), (UNRESOLVED, UNRESOLVED))
        self.assertIn("CONFLICTING_ELECTIONS", flag_codes(r))
        self.assertEqual(elections_of(s, "2026-11-15")["housing"][2], "conflicting elections recorded")

    def test_a_confirmed_and_an_unconfirmed_option_still_conflict(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01"), pick("e2", "el.flex", "2026-03-01", state="unconfirmed")])
        self.assertEqual(have(s, "2026-11-15", "tiered", "flex"), (UNRESOLVED, UNRESOLVED))

    def test_the_same_option_twice_is_not_a_conflict(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01"), pick("e2", "el.tiered", "2026-03-01")])
        self.assertNotIn("CONFLICTING_ELECTIONS", codes(lint(s)))
        self.assertEqual(have(s, "2026-11-15", "tiered"), (ESTABLISHED,))

    def test_two_accounts_of_the_card(self):
        s = world(card(), [holding("h-card-2", CARD, valid_from="2026-01-01"), pick("e1", "el.tiered", "2025-06-01")])
        r = evaluate(s, "t", "2026-11-15")
        self.assertEqual(r.have("tiered"), UNRESOLVED)
        self.assertIn("MULTIPLE_CARD_ACCOUNTS", flag_codes(r))

    def test_election_the_published_terms_do_not_allow(self):
        s = world(card("2027-02-01"), [pick("e1", "el.flex", "2027-02-01")])       # Flex is only for accounts opened before 2027
        r = evaluate(s, "t", "2027-06-01")
        self.assertEqual((r.have("flex"), r.have("tiered")), (UNRESOLVED, UNRESOLVED))   # neither granted nor silently dropped
        self.assertIn("ELECTION_NOT_PERMITTED", flag_codes(r))
        self.assertTrue(any("opened before 2027-01-01" in f["detail"] for f in r.flags))


class TestChangingElections(unittest.TestCase):
    def switch(self, ended_with_state=True):
        old = pick("e1", "el.tiered", "2025-06-01", valid_to="2026-08-31")
        if ended_with_state:
            old["state"] = "ended"
        return world(card(), [old, pick("e2", "el.flex", "2026-09-01")])

    def test_switching_options_keeps_history(self):
        for ended in (True, False):          # closed with end_holding, or with set_holding and a valid_to
            s = self.switch(ended)
            self.assertEqual(lint(s), [])
            self.assertEqual(have(s, "2026-08-31", "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE), ended)
            self.assertEqual(have(s, "2026-09-01", "tiered", "flex"), (NOT_AVAILABLE, ESTABLISHED), ended)
            self.assertEqual(have(s, "2025-05-31", "tiered", "flex"), (NOT_AVAILABLE, NOT_AVAILABLE), ended)   # before the account

    def test_timeline_shows_the_switch(self):
        events = {e["date"]: {c["atom"]: (c["before"], c["after"]) for c in e["changes"]} for e in timeline(self.switch(), "t", "2026-01-01", "2026-12-31")}
        self.assertEqual(events["2026-09-01"]["have:tiered"], (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(events["2026-09-01"]["have:flex"], (NOT_AVAILABLE, ESTABLISHED))

    def test_gap_between_elections_is_unknown(self):
        s = world(card(), [pick("e1", "el.tiered", "2025-06-01", valid_to="2026-08-31"), pick("e2", "el.flex", "2026-10-01")])
        self.assertEqual(have(s, "2026-09-15", "tiered", "flex"), (UNRESOLVED, UNRESOLVED))


class TestTransition2027(unittest.TestCase):
    def test_legacy_by_default_until_the_cardholders_own_anniversary(self):
        s = world(card("2025-06-01"))
        steps = [("2026-11-15", (ESTABLISHED, ESTABLISHED, NOT_AVAILABLE)),
                 ("2027-01-01", (ESTABLISHED, ESTABLISHED, NOT_AVAILABLE)),     # 2027 has begun, but this account's anniversary has not
                 ("2027-05-31", (ESTABLISHED, ESTABLISHED, NOT_AVAILABLE)),
                 ("2027-06-01", (UNRESOLVED, UNRESOLVED, UNRESOLVED)),          # anniversary: retained legacy or $600 - not recorded
                 ("2028-01-01", (UNRESOLVED, UNRESOLVED, UNRESOLVED))]
        for day, want in steps:
            self.assertEqual(have(s, day, "c200", "h400", "c600"), want, day)
        self.assertEqual(elections_of(s, "2026-11-15")["credits"][0], "el.legacy")
        self.assertEqual(evaluate(s, "t", "2026-11-15").via["E"]["have:el.legacy"][0], "election-default:credits")

    def test_two_cardholders_two_transition_dates(self):
        jan, oct_ = world(card("2025-01-20")), world(card("2024-10-05"))
        self.assertEqual(have(jan, "2027-01-20", "c200", "c600"), (UNRESOLVED, UNRESOLVED))
        self.assertEqual(have(oct_, "2027-01-20", "c200", "c600"), (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(have(oct_, "2027-10-05", "c200", "c600"), (UNRESOLVED, UNRESOLVED))

    def test_recorded_choice_at_the_transition(self):
        keep = world(card("2025-06-01"), [pick("e1", "el.legacy", "2026-12-01")])
        self.assertEqual(have(keep, "2027-06-01", "c200", "h400", "c600"), (ESTABLISHED, ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(have(keep, "2028-06-01", "c200", "c600"), (ESTABLISHED, NOT_AVAILABLE))
        move = world(card("2025-06-01"), [pick("e1", "el.600", "2027-06-01")])
        self.assertEqual(have(move, "2027-05-31", "c200", "c600"), (ESTABLISHED, NOT_AVAILABLE))     # legacy default until the anniversary
        self.assertEqual(have(move, "2027-06-01", "c200", "c600"), (NOT_AVAILABLE, ESTABLISHED))
        self.assertEqual(lint(keep), [])
        self.assertEqual(lint(move), [])

    def test_choices_that_do_not_respect_the_anniversary(self):
        early = world(card("2025-06-01"), [pick("e1", "el.600", "2027-02-01")])       # $600 recorded before this account's anniversary
        r = evaluate(early, "t", "2027-03-01")
        self.assertEqual((r.have("c600"), r.have("c200")), (UNRESOLVED, UNRESOLVED))
        self.assertIn("ELECTION_NOT_PERMITTED", flag_codes(r))
        late = world(card("2025-06-01"), [pick("e1", "el.legacy", "2027-07-01")])     # legacy "retained" only after the anniversary passed
        r = evaluate(late, "t", "2027-08-01")
        self.assertEqual(r.have("c200"), UNRESOLVED)
        self.assertIn("ELECTION_NOT_PERMITTED", flag_codes(r))
        self.assertEqual(have(late, "2027-06-15", "c200", "c600"), (UNRESOLVED, UNRESOLVED))          # between anniversary and record: unknown

    def test_unknown_anniversary(self):
        s = world(card(None, valid_from="2025-06-01"))                                # held since 2025; opening date not recorded
        self.assertEqual(have(s, "2026-11-15", "c200", "c600"), (ESTABLISHED, NOT_AVAILABLE))  # 2026: before any 2027 anniversary for sure
        r = evaluate(s, "t", "2027-03-01")
        self.assertEqual((r.have("c200"), r.have("c600")), (UNRESOLVED, UNRESOLVED))
        self.assertIn("ANNIVERSARY_NOT_RECORDED", flag_codes(r))
        kept = world(card(None, valid_from="2025-06-01"), [pick("e1", "el.600", "2027-03-01")])
        r = evaluate(kept, "t", "2027-03-01")
        # CHANGED 2026-11-20 (Step 04B): was ESTABLISHED on the owner's word with an info flag. A recorded election whose
        # published terms cannot be checked (here: the anniversary is unknown) no longer establishes spendable value
        self.assertEqual(r.have("c600"), UNRESOLVED)
        self.assertIn("ELECTION_TERMS_UNVERIFIED", flag_codes(r))

    def test_february_29_account(self):
        s = world(card("2024-02-29"))
        self.assertEqual(have(s, "2027-02-27", "c200", "c600"), (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(have(s, "2027-02-28", "c200", "c600"), (UNRESOLVED, UNRESOLVED))   # anniversary is Feb 28 or Mar 1: not decided by convention
        self.assertEqual(have(s, "2027-03-01", "c200", "c600"), (UNRESOLVED, UNRESOLVED))
        self.assertEqual(elections_of(s, "2027-03-01")["credits"][2], "no election recorded")

    def test_account_opened_after_the_cutoff(self):
        s = world(card("2027-03-01"))
        self.assertEqual(have(s, "2027-06-01", "c200", "c600"), (NOT_AVAILABLE, NOT_AVAILABLE))   # legacy closed to it; $600 not until its anniversary
        self.assertEqual(elections_of(s, "2027-06-01")["credits"][2], "no option of this group applies on this date under its published terms")
        self.assertEqual([f["subject"] for f in evaluate(s, "t", "2027-06-01").flags if f["code"] == "ELECTION_NOT_RECORDED"], ["housing"])
        self.assertEqual(have(s, "2028-03-01", "c600"), (UNRESOLVED,))
        self.assertEqual(have(world(card("2027-03-01"), [pick("e1", "el.600", "2028-03-01")]), "2028-03-01", "c600"), (ESTABLISHED,))

    def test_transition_dates_appear_on_the_timeline(self):
        events = {e["date"]: {c["atom"]: (c["before"], c["after"]) for c in e["changes"]} for e in timeline(world(card("2025-06-01")), "t", "2026-11-01", "2027-12-31")}
        self.assertEqual(events["2027-06-01"]["have:c200"], (ESTABLISHED, UNRESOLVED))
        self.assertEqual(events["2027-06-01"]["have:c600"], (NOT_AVAILABLE, UNRESOLVED))


class TestStructure(unittest.TestCase):
    def test_definition_checks(self):
        def lint_with(opts):
            return codes(lint(world(card(), opts=opts)))
        self.assertIn("UNKNOWN_REFERENCE", lint_with([option("a", "g", ["r.nope"]), option("b", "g", ["r.flex"])]))
        self.assertIn("ELECTION_OVERLAP", lint_with([option("a", "g", ["r.flex"]), option("b", "g", ["r.flex"])]))
        bad_card = option("a", "g", ["r.tiered"])
        bad_card["election"]["card"] = "tiered"
        self.assertIn("BAD_ELECTION_SHAPE", lint_with([bad_card, option("b", "g", ["r.flex"])]))
        self.assertIn("INCOMPLETE_ELECTION_GROUP", lint_with([option("a", "g", ["r.flex"])]))
        two_defaults = [option("a", "g", ["r.flex"], default_before_anniversary=D27), option("b", "g", ["r.tiered"], default_before_anniversary=D27)]
        self.assertIn("BAD_ELECTION_SHAPE", lint_with(two_defaults))
        no_block = ent("a", "election")
        self.assertIn("BAD_ELECTION_SHAPE", lint_with([no_block]))
        stray = ent("tiered2", "benefit")
        stray["election"] = {"group": "g", "card": CARD, "governs": ["r.flex"]}
        self.assertIn("UNEXPECTED_FIELD", lint_with(options() + [stray]))
        s = world(card(), extra_rules=[rule("r.other", "grants", "perk", H("lounge"))], opts=options() + [option("el.x", "g2", ["r.other"]), option("el.y", "g2", ["r.lounge"])])
        self.assertIn("BAD_ELECTION_SHAPE", codes(lint(s)))                    # r.other does not require holding the card
        s = world(card(), extra_rules=[rule("r.make", "grants", "el.tiered", H(CARD))])
        self.assertIn("BAD_ELECTION_SHAPE", codes(lint(s)))                    # an election is never derived

    def test_holding_checks(self):
        h = holding("h-x", "lounge", valid_from="2026-01-01")
        h["opened_on"] = "2026-01-01"
        self.assertIn("UNEXPECTED_FIELD", codes(lint(world(card(), [h]))))
        self.assertIn("BAD_DATES", codes(lint(world(card("2026-01-01", valid_from="2025-12-01")))))

    def test_no_election_entities_no_change(self):
        s = world(card(), opts=[])
        r = evaluate(s, "t", "2026-11-15")
        self.assertEqual((r.have("tiered"), r.have("flex"), r.have("c200")), (ESTABLISHED, ESTABLISHED, ESTABLISHED))   # the hazard, ungated
        self.assertNotIn("elections", r.report())
        self.assertFalse(hasattr(r, "elections"))


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prices-elections-")
        from util import write_store
        s = world(card())
        # "Test Reviewer" stamps the invented definitions' approval (tests/util.approve, Step 04B)
        s.files["data/kb/vocab.json"] = dict(TEST_VOCAB, promotion_reviewers=["Reviewer", "Test Reviewer"])
        write_store(s, self.tmp)
        self.n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def cs(self, op, by="Test Owner", **kw):
        self.n += 1
        c = dict({"id": "cs-test-%02d" % self.n, "op": op, "author": "maintainer", "date": "2026-11-15", "reason": "test", "profile": "t"}, **kw)
        if by:
            c["attestation"] = {"by": by, "on": "2026-11-15", "statement": "invented"}
        return c

    def test_recording_and_changing_an_election(self):
        maint = self.cs("set_holding", by="maintainer", data={"holding": {"id": "e1", "entity": "el.tiered", "state": "confirmed", "valid_from": "2025-06-01"}})
        out = changes.apply(self.tmp, maint)
        self.assertFalse(out["ok"])                                             # only the owner confirms an election
        self.assertTrue(any("OWNER_ATTESTATION_REQUIRED" in e for e in out["errors"]))
        out = changes.apply(self.tmp, self.cs("set_holding", data={"holding": {"id": "e1", "entity": "el.tiered", "state": "confirmed", "valid_from": "2025-06-01"}}))
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(have(Store.load(self.tmp), "2026-11-15", "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE))
        out = changes.apply(self.tmp, self.cs("end_holding", target="e1", data={"ended_on": "2026-11-30"}))
        self.assertTrue(out["ok"], out["errors"])
        out = changes.apply(self.tmp, self.cs("set_holding", data={"holding": {"id": "e2", "entity": "el.flex", "state": "confirmed", "valid_from": "2026-12-01"}}))
        self.assertTrue(out["ok"], out["errors"])
        s = Store.load(self.tmp)
        self.assertEqual(have(s, "2026-11-30", "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(have(s, "2026-12-01", "tiered", "flex"), (NOT_AVAILABLE, ESTABLISHED))

    def test_conflicting_election_is_accepted_with_a_warning_and_applied_as_neither(self):
        changes.apply(self.tmp, self.cs("set_holding", data={"holding": {"id": "e1", "entity": "el.tiered", "state": "confirmed", "valid_from": "2025-06-01"}}))
        out = changes.apply(self.tmp, self.cs("set_holding", data={"holding": {"id": "e2", "entity": "el.flex", "state": "unconfirmed", "valid_from": "2026-10-01"}}))
        self.assertTrue(out["ok"], out["errors"])
        self.assertTrue(out["review_needed"])
        self.assertEqual(have(Store.load(self.tmp), "2026-11-15", "tiered", "flex"), (UNRESOLVED, UNRESOLVED))

    def test_withdrawing_a_mistaken_election(self):
        changes.apply(self.tmp, self.cs("set_holding", data={"holding": {"id": "e1", "entity": "el.tiered", "state": "confirmed", "valid_from": "2025-06-01"}}))
        changes.apply(self.tmp, self.cs("set_holding", by=None, data={"holding": {"id": "e2", "entity": "el.flex", "state": "unconfirmed", "valid_from": "2026-10-01"}}))
        self.assertEqual(have(Store.load(self.tmp), "2026-11-15", "tiered", "flex"), (UNRESOLVED, UNRESOLVED))
        out = changes.apply(self.tmp, self.cs("end_holding", by=None, target="e2", data={"withdrawn": True}))   # nobody confirmed it: a maintainer may withdraw
        self.assertTrue(out["ok"], out["errors"])
        s = Store.load(self.tmp)
        self.assertEqual(s.profile("t").holdings["e2"]["state"], "withdrawn")                                    # kept on file
        for day in ("2026-10-01", "2026-11-15", "2027-06-01"):
            self.assertEqual(have(s, day, "tiered", "flex"), (ESTABLISHED, NOT_AVAILABLE), day)                 # never in effect on any date
        self.assertNotIn("CONFLICTING_ELECTIONS", codes(lint(s)))
        out = changes.apply(self.tmp, self.cs("end_holding", by="maintainer", target="e1", data={"withdrawn": True}))
        self.assertFalse(out["ok"])                                                                             # a confirmed election: only its owner
        self.assertTrue(any("OWNER_ATTESTATION_REQUIRED" in e for e in out["errors"]))
        out = changes.apply(self.tmp, self.cs("end_holding", target="e2", data={"withdrawn": True}))
        self.assertTrue(any("BAD_STATE" in e for e in out["errors"]))

    def test_revising_an_election_definition_needs_a_reviewer(self):
        out = changes.apply(self.tmp, self.cs("revise_entity", by="maintainer", target="el.flex",
                                              data={"set": {"election": {"group": "housing", "card": CARD, "governs": ["r.flex"]}}}))
        self.assertFalse(out["ok"])
        self.assertTrue(any("REVIEWER_NOT_AUTHORIZED" in e for e in out["errors"]), out["errors"])
        out = changes.apply(self.tmp, self.cs("revise_entity", by="maintainer", target="el.flex", data={"set": {"notes": "wording only"}}))
        self.assertTrue(out["ok"], out["errors"])                               # descriptive fields as before


class TestLiveBiltDefinitions(unittest.TestCase):
    FIVE = {"housing-tiered-points": "housing", "housing-flex-bilt-cash-legacy": "housing", "annual-bilt-cash-200-legacy": "credits",
            "annual-bilt-cash-600-post2027": "credits", "hotel-credit-400-semiannual-legacy": "credits"}

    def test_committed_store_keeps_the_candidates_proposed_and_gated(self):
        s = Store.load(ROOT)
        gov = {o["id"]: o["election"]["governs"] for o in s.entities.values() if o["kind"] == "election"}
        self.assertEqual(sorted(r for rs in gov.values() for r in rs), sorted("cb.bilt-palladium." + k for k in self.FIVE))
        for k in self.FIVE:
            self.assertEqual(s.candidates["c-cb.bilt-palladium." + k]["status"], "proposed")
            self.assertNotIn("cb.bilt-palladium." + k, s.rules)
        for name in s.profile_names():
            self.assertFalse([h for h in s.profile(name).holdings.values() if s.entities.get(h["entity"], {}).get("kind") == "election"], name)

    def test_after_promotion_the_real_rules_never_grant_both_sides(self):
        tmp = tempfile.mkdtemp(prefix="prices-bilt-")
        try:
            for d in ("data", "profiles", "tables"):
                shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d))
            reviewer = Store.load(tmp).vocab["promotion_reviewers"][0]
            from util import approve_elections_on_disk
            approve_elections_on_disk(tmp)                     # scratch only: the committed definitions await a real reviewer
            for i, k in enumerate(self.FIVE):
                out = changes.apply(tmp, {"id": "cs-20261115-scratch-%d" % i, "op": "promote_candidate", "target": "c-cb.bilt-palladium." + k,
                                          "author": "test", "date": "2026-11-15", "reason": "scratch copy only",
                                          "data": {"review_by": "2027-11-15", "conditions": scratch_real(
                                              Store.load(tmp).candidates["c-cb.bilt-palladium." + k], governed=True)},
                                          "attestation": {"by": reviewer, "on": "2026-11-15", "statement": "scratch copy only"}})
                self.assertTrue(out["ok"], out["errors"])
            os.makedirs(os.path.join(tmp, "profiles", "synthetic-bilt", "holdings"))
            with open(os.path.join(tmp, "profiles", "synthetic-bilt", "profile.json"), "w") as f:
                json.dump({"id": "synthetic-bilt", "label": "invented", "synthetic": True, "owner": "Bilt Holder (synthetic)"}, f)
            with open(os.path.join(tmp, "profiles", "synthetic-bilt", "holdings", "h-bilt.json"), "w") as f:
                json.dump({"id": "h-bilt", "entity": "card.bilt-palladium", "state": "confirmed", "valid_from": "2025-06-01", "opened_on": "2025-06-01",
                           "confirmed_by": "Bilt Holder (synthetic)", "confirmed_on": "2026-11-15"}, f)
            s = Store.load(tmp)
            self.assertEqual([i for i in lint(s) if i[0] == "ERROR"], [])
            B = "benefit.bilt-palladium."
            got = lambda day: {k: evaluate(s, "synthetic-bilt", day).have(B + k) for k in self.FIVE}     # noqa: E731
            self.assertEqual(got("2026-11-15"), {"housing-tiered-points": UNRESOLVED, "housing-flex-bilt-cash-legacy": UNRESOLVED,
                                                 "annual-bilt-cash-200-legacy": ESTABLISHED, "hotel-credit-400-semiannual-legacy": ESTABLISHED,
                                                 "annual-bilt-cash-600-post2027": NOT_AVAILABLE})
            # ENG-02B: the published Card Anniversary Date is counted from the first billing cycle after opening, so for an
            # account opened 2025-06-01 it falls between 2027-06-02 and 2027-08-02 (it is not 2027-06-01, as ENG-02 assumed).
            self.assertEqual(set(got("2027-08-02").values()), {UNRESOLVED})          # this cardholder's 2027 anniversary has come, nothing recorded
            self.assertEqual(evaluate(s, "synthetic-bilt", "2026-11-15").have(B + "base-2x-everyday"), NOT_AVAILABLE)   # still a candidate there
            for day in ("2026-11-15", "2027-06-01", "2028-01-01"):
                for group in (("housing-tiered-points", "housing-flex-bilt-cash-legacy"), ("annual-bilt-cash-200-legacy", "annual-bilt-cash-600-post2027")):
                    both = [got(day)[k] for k in group]
                    self.assertNotEqual(both, [ESTABLISHED, ESTABLISHED], (day, group))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
