"""ENG-02B: the corrected Bilt Palladium election model.

Every cardholder here is INVENTED, with invented account dates. Part 1 runs the committed Bilt definitions on a
scratch copy of the live store in which Argon's five governed candidates are promoted (there only; the committed
store keeps them proposed). Part 2 checks the general machinery (linked options, anniversary windows, definition
checks) on small stores built in memory. Nothing is written back.

What the published terms say (Bilt Rewards Card Offer Terms, last updated 2026-10-27), as modelled:
  A  account opened before 2027, before its first Card Anniversary Date on or after 2027-01-01:
     the housing Rewards Option is the cardholder's choice; the $200 Bilt Cash and $400 hotel credit apply whatever it is.
  B  Legacy Election (made before that anniversary): ONE linked arrangement - Flexible Bilt Cash, $200, $400.
  C  otherwise the refreshed arrangement from that anniversary - Housing-only, $600; and from account OPENING for
     accounts opened on or after 2027-01-01.
  D  leaving the Legacy Election is permanent; the $600 then starts at the next Card Anniversary Date.
The invented standard account: opened 2026-03-10, card anniversary shown as April 5, so the transition is 2027-04-05.
"""
import datetime
import json
import os
import shutil
import tempfile
import unittest

from util import H, ent, flag_codes, holding, make_store, rule
from prices import changes
from prices.elections import anniversary_window, before_anniversary, card_window
from prices.engine import ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.review import timeline
from prices.store import Store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = "election.bilt-palladium."
B = "benefit.bilt-palladium."
FIVE = ("housing-tiered-points", "housing-flex-bilt-cash-legacy", "annual-bilt-cash-200-legacy",
        "hotel-credit-400-semiannual-legacy", "annual-bilt-cash-600-post2027")
EST, NO, UNR = ESTABLISHED, NOT_AVAILABLE, UNRESOLVED
d = datetime.date


def acct(opened="2026-03-10", shown="2027-04-05", valid_from=None):
    h = {"id": "h-card", "entity": "card.bilt-palladium", "state": "confirmed", "confirmed_on": "2026-11-15"}
    if opened:
        h["opened_on"] = opened
    if shown:
        h["anniversary_on"] = shown
    h["valid_from"] = valid_from or opened
    return h


def el(hid, option, start=None, end=None, state="confirmed", confirmed_on="2026-11-15"):
    h = {"id": hid, "entity": E + option, "state": "ended" if end else state}
    if start:
        h["valid_from"] = start
    if end:
        h["valid_to"] = end
    if state == "confirmed":
        h["confirmed_on"] = confirmed_on
    return h


# every invented cardholder: name -> holdings
PEOPLE = {
    # 1: switches the housing option before the transition, never records an arrangement
    "switch": [acct(), el("e1", "housing-tiered-points", "2026-03-10", "2026-08-04"), el("e2", "housing-flex-bilt-cash", "2026-08-05")],
    # 2: keeps the linked legacy arrangement
    "legacy": [acct(), el("e1", "housing-flex-bilt-cash", "2026-05-05"), el("e2", "legacy-election", "2026-11-20")],
    "legacy-only": [acct(), el("e1", "legacy-election", "2026-11-20")],
    # 3: no Legacy Election; the owner records the refreshed arrangement from the transition anniversary
    "refreshed": [acct(), el("e1", "housing-tiered-points", "2026-03-10"), el("e2", "refreshed-arrangement", "2027-04-05")],
    "refreshed-early": [acct(), el("e1", "refreshed-arrangement", "2027-02-01")],
    # 4: account opened in 2027 - nothing recorded at all
    "new": [acct("2027-02-10", None)],
    "new-legacy": [acct("2027-02-10", None), el("e1", "housing-flex-bilt-cash", "2027-02-15"), el("e2", "legacy-election", "2027-02-15")],
    # 5: tries to hold both sides
    "double": [acct(), el("e1", "legacy-election", "2026-11-20"), el("e2", "annual-credits-600", "2027-04-05")],
    "both-arrangements": [acct(), el("e1", "legacy-election", "2026-11-20"), el("e2", "refreshed-arrangement", "2027-04-05")],
    # 6: leaves the legacy arrangement for good on 2027-09-05 (first day of a billing cycle)
    "exit": [acct(), el("e1", "legacy-election", "2026-11-20", "2027-09-04"), el("e2", "refreshed-arrangement", "2027-09-05")],
    "return": [acct(), el("e1", "legacy-election", "2026-11-20", "2027-09-04"), el("e2", "refreshed-arrangement", "2027-09-05", "2027-11-30"),
               el("e3", "legacy-election", "2027-12-01")],
    "return-early": [acct(), el("e1", "legacy-election", "2026-10-01", "2026-11-30"), el("e2", "legacy-election", "2026-12-15")],
    # 7: facts missing
    "no-dates": [acct(None, None, valid_from="2026-05-01")],
    "window": [acct("2026-03-10", None)],
    "unconfirmed": [acct(), el("e1", "legacy-election", "2026-11-20", state="unconfirmed")],
    "undated": [acct(), el("e1", "legacy-election", confirmed_on="2027-06-01")],
    # 8: boundaries
    "late": [acct(), el("e1", "legacy-election", "2027-04-05")],
    "last-day": [acct(), el("e1", "legacy-election", "2027-04-04")],
    "locked": [acct(), el("e1", "legacy-election", "2026-11-20"), el("e2", "housing-tiered-points", "2026-12-05")],
    "stale": [acct(), el("e1", "housing-tiered-points", "2026-03-10"), el("e2", "legacy-election", "2027-01-20")],
}


class Live(unittest.TestCase):
    """The committed Bilt definitions, on a scratch copy with the five candidates promoted there."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="prices-eng02b-")
        for sub in ("data", "profiles", "tables"):
            shutil.copytree(os.path.join(ROOT, sub), os.path.join(cls.tmp, sub))
        reviewer = Store.load(cls.tmp).vocab["promotion_reviewers"][0]
        out = changes.apply_many(cls.tmp, [
            {"id": "cs-20261115-scratch-q%d" % i, "op": "promote_candidate", "target": "c-cb.bilt-palladium." + k, "author": "test",
             "date": "2026-11-15", "reason": "scratch copy only", "data": {"review_by": "2027-12-15"},
             "attestation": {"by": reviewer, "on": "2026-11-15", "statement": "scratch copy only"}} for i, k in enumerate(FIVE)])
        assert out["ok"], out["errors"]
        for name, hs in PEOPLE.items():
            owner = "Invented cardholder %s" % name
            os.makedirs(os.path.join(cls.tmp, "profiles", "syn-" + name, "holdings"))
            with open(os.path.join(cls.tmp, "profiles", "syn-" + name, "profile.json"), "w") as f:
                json.dump({"id": "syn-" + name, "label": "invented", "synthetic": True, "owner": owner}, f)
            for h in hs:
                h = dict(h)
                if h["state"] in ("confirmed", "ended"):
                    h["confirmed_by"] = owner
                    h.setdefault("confirmed_on", "2026-11-15")
                with open(os.path.join(cls.tmp, "profiles", "syn-" + name, "holdings", h["id"] + ".json"), "w") as f:
                    json.dump(h, f)
        cls.s = Store.load(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def at(self, who, day):
        """(tiered, flex, $200, $400, $600) for one invented cardholder on one day."""
        r = evaluate(self.s, "syn-" + who, day)
        return tuple(r.have(B + k) for k in FIVE)

    def flags(self, who, day):
        return flag_codes(evaluate(self.s, "syn-" + who, day))

    def arrangement(self, who, day):
        rep = evaluate(self.s, "syn-" + who, day).report()["elections"]
        return next((x["established"], sorted(x["unresolved"])) for x in rep if x["group"] == "bilt-palladium.arrangement")

    def test_scratch_store_is_sound(self):
        self.assertEqual([i for i in lint(self.s) if i[0] == "ERROR"], [])

    # ---- 1
    def test_1_housing_option_switches_before_the_transition_and_the_legacy_benefits_stay(self):
        self.assertEqual(self.at("switch", "2026-06-01"), (EST, NO, EST, EST, NO))
        self.assertEqual(self.at("switch", "2026-08-04"), (EST, NO, EST, EST, NO))      # last day of the billing cycle
        self.assertEqual(self.at("switch", "2026-08-05"), (NO, EST, EST, EST, NO))      # the change takes effect with the next cycle
        self.assertEqual(self.at("switch", "2027-04-04"), (NO, EST, EST, EST, NO))      # the day before the transition anniversary
        for day in ("2026-06-01", "2026-08-05", "2027-04-04"):                          # the annual benefits are no election in this phase
            self.assertFalse(self.flags("switch", day) & {"ELECTION_NOT_RECORDED", "ELECTION_NOT_SELECTABLE", "ANNIVERSARY_NOT_RECORDED"}, day)
        self.assertEqual(self.arrangement("switch", "2026-06-01"), (None, [E + "legacy-election"]))   # may still be made; nothing assumed

    def test_1_a_housing_choice_does_not_outlive_the_transition(self):
        # Flexible Bilt Cash was selected, but whether a Legacy Election was made is not recorded: nothing is assumed either way
        self.assertEqual(self.at("switch", "2027-04-05"), (UNR,) * 5)
        self.assertIn("ELECTION_NOT_RECORDED", self.flags("switch", "2027-04-05"))
        self.assertEqual(self.arrangement("switch", "2027-04-05"), (None, [E + "legacy-election", E + "refreshed-arrangement"]))

    # ---- 2
    def test_2_legacy_election_keeps_the_whole_linked_arrangement(self):
        for day in ("2026-12-01", "2027-04-04", "2027-04-05", "2028-04-05", "2029-01-01"):
            self.assertEqual(self.at("legacy", day), (NO, EST, EST, EST, NO), day)
            self.assertFalse(self.flags("legacy", day) & {"ELECTION_NOT_RECORDED", "CONFLICTING_ELECTIONS"}, day)
        self.assertEqual(self.arrangement("legacy", "2027-06-01"), (E + "legacy-election", []))

    def test_2_the_legacy_election_alone_carries_flexible_bilt_cash(self):
        # no separate housing record: the published election itself keeps the Flexible option
        self.assertEqual(self.at("legacy-only", "2026-11-19"), (UNR, UNR, EST, EST, NO))     # before the election: housing not recorded
        self.assertEqual(self.at("legacy-only", "2026-11-20"), (NO, EST, EST, EST, NO))
        self.assertEqual(self.at("legacy-only", "2027-05-01"), (NO, EST, EST, EST, NO))

    # ---- 3
    def test_3_without_a_legacy_election_the_account_moves_at_its_anniversary(self):
        self.assertEqual(self.at("refreshed", "2027-04-04"), (EST, NO, EST, EST, NO))
        self.assertEqual(self.at("refreshed", "2027-04-05"), (EST, NO, NO, NO, EST))
        self.assertEqual(self.at("refreshed", "2028-07-01"), (EST, NO, NO, NO, EST))
        self.assertEqual(self.arrangement("refreshed", "2027-04-05"), (E + "refreshed-arrangement", []))

    def test_3_the_refreshed_arrangement_cannot_be_recorded_before_the_anniversary(self):
        # whether an earlier account can move early is not in the published terms: flagged, and the legacy benefits still apply
        self.assertIn("ELECTION_NOT_PERMITTED", self.flags("refreshed-early", "2027-03-01"))
        got = self.at("refreshed-early", "2027-03-01")
        self.assertEqual(got[2:], (EST, EST, NO))
        self.assertNotIn(EST, got[:2])

    # ---- 4
    def test_4_an_account_opened_in_2027_is_refreshed_from_the_day_it_opens(self):
        for day in ("2027-02-10", "2027-06-01", "2028-02-09", "2028-06-01"):          # 2028-02-09: still before any first anniversary
            self.assertEqual(self.at("new", day), (EST, NO, NO, NO, EST), day)
            self.assertFalse(self.flags("new", day) & {"ELECTION_NOT_RECORDED", "ANNIVERSARY_NOT_RECORDED"}, day)
        self.assertEqual(self.arrangement("new", "2027-02-10"), (E + "refreshed-arrangement", []))

    def test_4_a_2027_account_cannot_hold_the_legacy_arrangement(self):
        self.assertIn("ELECTION_NOT_PERMITTED", self.flags("new-legacy", "2027-03-01"))
        got = self.at("new-legacy", "2027-03-01")
        self.assertEqual((got[1], got[2], got[3]) .count(EST), 0)

    # ---- 5
    def test_5_incompatible_benefits_are_never_granted_together(self):
        days = ["%d-%02d-%02d" % (y, m, dd) for y in (2026, 2027, 2028, 2029) for m in range(1, 13) for dd in (4, 5, 20)]
        for who in PEOPLE:
            for day in days:
                t, fx, c200, h400, c600 = self.at(who, day)
                self.assertFalse(t == EST and fx == EST, (who, day))
                self.assertFalse(c600 == EST and EST in (c200, h400, fx), (who, day))    # $600 never with any legacy piece
                self.assertEqual(c200, h400, (who, day))                                 # the two legacy benefits move together

    def test_5_the_600_cannot_be_recorded_alongside_a_legacy_election(self):
        self.assertEqual(self.at("double", "2027-06-01"), (NO, EST, EST, EST, NO))
        self.assertIn("ELECTION_NOT_SELECTABLE", self.flags("double", "2027-06-01"))
        self.assertEqual(self.at("both-arrangements", "2027-06-01"), (UNR,) * 5)          # contradictory records: neither is applied
        self.assertIn("CONFLICTING_ELECTIONS", self.flags("both-arrangements", "2027-06-01"))

    # ---- 6
    def test_6_leaving_the_legacy_arrangement(self):
        self.assertEqual(self.at("exit", "2027-09-04"), (NO, EST, EST, EST, NO))
        self.assertEqual(self.at("exit", "2027-09-05"), (EST, NO, NO, NO, NO))     # first day of the next billing cycle: legacy benefits stop
        self.assertEqual(self.at("exit", "2028-04-04"), (EST, NO, NO, NO, NO))     # the $600 waits for the next card anniversary
        self.assertEqual(self.at("exit", "2028-04-05"), (EST, NO, NO, NO, EST))

    def test_6_a_permanent_exit_cannot_be_reversed(self):
        for who, day in (("return", "2028-01-15"), ("return", "2029-01-15"), ("return-early", "2027-01-15"), ("return-early", "2027-05-01")):
            got = self.at(who, day)
            self.assertNotIn(EST, (got[1],), (who, day))                              # Flexible Bilt Cash is not re-established
            self.assertIn("ELECTION_NOT_PERMITTED", self.flags(who, day), (who, day))
            self.assertEqual(self.arrangement(who, day)[0], None, (who, day))
        self.assertNotIn(EST, self.at("return", "2028-01-15")[2:4])                  # nor the legacy benefits

    # ---- 7
    def test_7_missing_dates_are_unresolved_not_guessed(self):
        self.assertEqual(self.at("no-dates", "2026-12-01"), (UNR, UNR, EST, EST, NO))    # 2026: no anniversary can matter yet
        self.assertEqual(self.at("no-dates", "2027-06-01"), (UNR,) * 5)
        self.assertIn("ANNIVERSARY_NOT_RECORDED", self.flags("no-dates", "2027-06-01"))

    def test_7_opening_date_alone_does_not_place_the_anniversary(self):
        # opened 2026-03-10; the first billing cycle after opening began 1 to 62 days later: anniversary 2027-03-11 .. 2027-05-11
        self.assertEqual(self.at("window", "2027-03-10")[2:], (EST, EST, NO))
        for day in ("2027-03-11", "2027-04-05", "2027-05-10"):
            self.assertEqual(self.at("window", day), (UNR,) * 5, day)
            self.assertIn("ANNIVERSARY_NOT_RECORDED", self.flags("window", day), day)
        self.assertEqual(self.at("window", "2027-05-11"), (UNR,) * 5)                    # certainly past it; no arrangement recorded
        self.assertNotIn("ANNIVERSARY_NOT_RECORDED", self.flags("window", "2027-05-11"))
        self.assertIn("ELECTION_NOT_RECORDED", self.flags("window", "2027-05-11"))

    def test_7_an_unverified_election_establishes_nothing(self):
        self.assertEqual(self.at("unconfirmed", "2027-05-01"), (UNR,) * 5)
        self.assertIn("UNCONFIRMED_ELECTION", self.flags("unconfirmed", "2027-05-01"))
        self.assertEqual(self.at("unconfirmed", "2026-12-01")[2:], (EST, EST, NO))       # before the transition the benefits are automatic
        self.assertEqual(self.at("undated", "2027-05-01"), (UNR,) * 5)                   # confirmed only on 2027-06-01, start unknown
        self.assertIn("ELECTION_START_NOT_RECORDED", self.flags("undated", "2027-05-01"))
        self.assertEqual(self.at("undated", "2027-07-01"), (NO, EST, EST, EST, NO))      # stands on the owner's word, and says so
        self.assertIn("ELECTION_TERMS_UNVERIFIED", self.flags("undated", "2027-07-01"))

    # ---- 8
    def test_8_election_deadline_is_the_day_before_the_anniversary(self):
        self.assertEqual(self.at("last-day", "2027-04-05"), (NO, EST, EST, EST, NO))
        self.assertIn("ELECTION_NOT_PERMITTED", self.flags("late", "2027-04-05"))
        self.assertNotIn(EST, self.at("late", "2027-05-01")[1:4])

    def test_8_a_legacy_election_locks_the_housing_option(self):
        self.assertEqual(self.at("locked", "2026-12-04"), (NO, EST, EST, EST, NO))
        got = self.at("locked", "2027-01-10")                                             # Housing-only recorded on top of a Legacy Election
        self.assertEqual(got[:2], (UNR, UNR))
        self.assertEqual(got[2:], (EST, EST, NO))
        self.assertIn("CONFLICTING_ELECTIONS", self.flags("locked", "2027-01-10"))

    def test_8_a_choice_left_on_file_after_the_transition_is_reported_not_applied(self):
        self.assertEqual(self.at("stale", "2027-05-01"), (NO, EST, EST, EST, NO))
        self.assertIn("ELECTION_SUPERSEDED", self.flags("stale", "2027-05-01"))

    def test_8_the_transition_dates_are_on_the_timeline(self):
        days = {x["date"] for x in timeline(self.s, "syn-exit", "2026-11-01", "2028-12-31")}
        self.assertTrue({"2027-09-05", "2028-04-05"} <= days, sorted(days))      # the exit, then the first $600 anniversary
        self.assertNotIn("2027-04-05", days)                                     # nothing changed for a Legacy Election holder
        self.assertIn("2027-04-05", {x["date"] for x in timeline(self.s, "syn-refreshed", "2026-11-01", "2028-12-31")})

    def test_committed_store_is_untouched_by_all_this(self):
        s = Store.load(ROOT)
        for k in FIVE:
            self.assertEqual(s.candidates["c-cb.bilt-palladium." + k]["status"], "proposed")
        for name in s.profile_names():
            self.assertFalse(name.startswith("syn-"))
            for h in s.profile(name).holdings.values():
                self.assertNotEqual(s.entities.get(h["entity"], {}).get("kind"), "election", name)
                self.assertNotIn("anniversary_on", h, name)

    def test_committed_definitions_are_one_linked_arrangement(self):
        t = {o["id"][len(E):]: o["election"] for o in Store.load(ROOT).entities.values() if o["kind"] == "election"}
        self.assertEqual({k: v.get("follows", "")[len(E):] for k, v in t.items()},
                         {"legacy-election": "", "refreshed-arrangement": "", "housing-flex-bilt-cash": "legacy-election",
                          "annual-credits-legacy": "legacy-election", "housing-tiered-points": "refreshed-arrangement",
                          "annual-credits-600": "refreshed-arrangement"})
        self.assertEqual(t["legacy-election"]["group"], t["refreshed-arrangement"]["group"])
        self.assertTrue(t["legacy-election"]["permanent_exit"])
        self.assertEqual(t["refreshed-arrangement"]["default_opened_on_or_after"], "2027-01-01")
        for k in ("annual-credits-legacy", "annual-credits-600"):                       # the annual benefits are not separately electable
            self.assertNotIn("choose_before_anniversary", t[k])
            self.assertNotIn("elect_before_anniversary", t[k])


# ---------------------------------------------------------------------------------------------- part 2: in memory
class TestAnniversaryFromTheFirstBillingCycle(unittest.TestCase):
    D0 = d(2027, 1, 1)

    def test_window_when_only_the_opening_date_is_known(self):
        self.assertEqual(anniversary_window(d(2026, 3, 10), self.D0, 62), (d(2027, 3, 11), d(2027, 5, 11)))
        self.assertEqual(anniversary_window(d(2026, 3, 10), self.D0), (d(2027, 3, 10), d(2027, 3, 10)))       # unchanged without the term
        # opened late December: the cycle may have begun before or after New Year, so the anniversary may be a year apart
        self.assertEqual(anniversary_window(d(2025, 12, 20), self.D0, 62), (d(2027, 1, 1), d(2027, 12, 31)))
        self.assertEqual(anniversary_window(d(2027, 2, 10), self.D0, 62), (d(2028, 2, 11), d(2028, 4, 13)))   # opened after: its first

    def test_the_issuers_date_removes_the_window(self):
        self.assertEqual(anniversary_window(d(2026, 3, 10), self.D0, 62, d(2027, 4, 5)), (d(2027, 4, 5), d(2027, 4, 5)))
        self.assertEqual(anniversary_window(d(2026, 3, 10), self.D0, 62, d(2030, 4, 5)), (d(2027, 4, 5), d(2027, 4, 5)))   # any year's date
        self.assertEqual(anniversary_window(d(2025, 12, 20), self.D0, 62, d(2027, 1, 15)), (d(2027, 1, 15), d(2027, 1, 15)))
        self.assertEqual(anniversary_window(d(2026, 12, 20), self.D0, 62, d(2028, 1, 15)), (d(2028, 1, 15), d(2028, 1, 15)))  # not 2027-01-15
        self.assertEqual(card_window({"anniversary_on": "2027-04-05"}, self.D0, 62), (d(2027, 4, 5), d(2027, 4, 5)))
        self.assertIsNone(card_window({"anniversary_on": "2028-04-05"}, self.D0, 62))      # was 2027-04-05 one too? not known
        self.assertIsNone(card_window({}, self.D0, 62))

    def test_inside_the_window_is_unknown(self):
        h = {"opened_on": "2026-03-10"}
        got = [before_anniversary(h, self.D0, x, 62) for x in (d(2027, 3, 10), d(2027, 3, 11), d(2027, 5, 10), d(2027, 5, 11))]
        self.assertEqual(got, [True, None, None, False])


CARD = "card.x"


def option(oid, group, governs, **terms):
    e = ent(oid, "election", name=oid)
    e["election"] = dict({"group": group, "card": CARD, "governs": list(governs)}, **terms)
    return e


def linked_options(**change):
    opts = {"el.keep": option("el.keep", "plan", [], opened_before="2027-01-01", elect_before_anniversary="2027-01-01", permanent_exit=True),
            "el.new": option("el.new", "plan", [], default_opened_on_or_after="2027-01-01", starts_at_anniversary="2027-01-01"),
            "el.a": option("el.a", "mode", ["r.a"], choose_before_anniversary="2027-01-01", follows="el.new"),
            "el.b": option("el.b", "mode", ["r.b"], opened_before="2027-01-01", choose_before_anniversary="2027-01-01", follows="el.keep"),
            "el.old": option("el.old", "perk", ["r.old"], opened_before="2027-01-01", default_before_anniversary="2027-01-01", follows="el.keep"),
            "el.big": option("el.big", "perk", ["r.big"], follows="el.new", after_exit_from_anniversary=True)}
    for oid, terms in change.items():
        if terms is None:
            del opts[oid]
        else:
            opts[oid]["election"].update(terms)
            for k in [k for k, v in terms.items() if v is None]:
                del opts[oid]["election"][k]
    return list(opts.values())


def world(holdings, opts=None, status="verified"):
    es = [ent(CARD, "card")] + [ent(x, "benefit") for x in ("a", "b", "old", "big")] + (opts if opts is not None else linked_options())
    rs = [rule("r." + x, "grants", x, H(CARD), status=status) for x in ("a", "b", "old", "big")]
    return make_store(es, rs, holdings)


def card(opened="2025-06-01", **kw):
    return holding("h-card", CARD, valid_from=opened, opened_on=opened, **kw)


def codes(issues):
    return {i[1] for i in issues}


class TestLinkedOptionsInGeneral(unittest.TestCase):
    """The same behaviour with invented options: nothing in the engine is specific to one card."""

    def have(self, s, day):
        r = evaluate(s, "t", day)
        return tuple(r.have(x) for x in ("a", "b", "old", "big"))

    def test_choice_period_then_linked(self):
        s = world([card(), holding("p1", "el.a", valid_from="2025-06-01")])
        self.assertEqual(self.have(s, "2027-05-31"), (EST, NO, EST, NO))
        self.assertEqual(self.have(s, "2027-06-01"), (UNR, UNR, UNR, UNR))               # the anniversary: the plan is not recorded
        s = world([card(), holding("p1", "el.a", valid_from="2025-06-01"), holding("p2", "el.new", valid_from="2027-06-01")])
        self.assertEqual(self.have(s, "2027-06-01"), (EST, NO, NO, EST))
        s = world([card(), holding("p2", "el.keep", valid_from="2026-09-01")])
        self.assertEqual(self.have(s, "2026-08-31"), (UNR, UNR, EST, NO))
        self.assertEqual(self.have(s, "2027-06-01"), (NO, EST, EST, NO))

    def test_account_opened_after_the_date_follows_from_opening(self):
        s = world([card("2027-03-01")])
        self.assertEqual(self.have(s, "2027-03-01"), (EST, NO, NO, EST))
        self.assertEqual(flag_codes(evaluate(s, "t", "2027-03-01")) & {"ELECTION_NOT_RECORDED", "ANNIVERSARY_NOT_RECORDED"}, set())

    def test_unrecorded_plan_is_flagged_only_once_a_rule_waits_on_it(self):
        s = world([card()])
        self.assertNotIn("ELECTION_NOT_RECORDED", {f["code"] for f in evaluate(s, "t", "2026-06-01").flags if f["subject"] == "plan"})
        self.assertIn("ELECTION_NOT_RECORDED", {f["code"] for f in evaluate(s, "t", "2027-06-01").flags if f["subject"] == "plan"})
        cand_only = world([card()], status="unverified")
        self.assertEqual(self.have(cand_only, "2027-06-01"), (UNR, UNR, UNR, UNR))

    def test_exit_then_next_anniversary(self):
        s = world([card(), holding("p1", "el.keep", "ended", valid_from="2026-09-01", valid_to="2027-08-14", confirmed_on="2026-09-01",
                                   confirmed_by="synthetic"), holding("p2", "el.new", valid_from="2027-08-15")])
        self.assertEqual(self.have(s, "2027-08-14"), (NO, EST, EST, NO))
        self.assertEqual(self.have(s, "2027-08-15"), (EST, NO, NO, NO))
        self.assertEqual(self.have(s, "2028-05-31"), (EST, NO, NO, NO))
        self.assertEqual(self.have(s, "2028-06-01"), (EST, NO, NO, EST))

    def test_definition_checks(self):
        ok = world([card()])
        self.assertEqual([i for i in lint(ok) if i[0] == "ERROR"], [])
        self.assertFalse(codes(lint(ok)) & {"ELECTION_GOVERNS_NOTHING", "ANNIVERSARY_RULE_DIFFERS"})
        bad = lambda **change: codes(lint(world([card()], linked_options(**change))))       # noqa: E731
        self.assertIn("UNKNOWN_REFERENCE", bad(**{"el.a": {"follows": "el.nobody"}}))
        self.assertIn("BAD_ELECTION_SHAPE", bad(**{"el.a": {"follows": "el.b"}}))            # its own group
        self.assertIn("BAD_ELECTION_SHAPE", bad(**{"el.new": {"follows": "el.a"}}))          # links are one level deep
        self.assertIn("BAD_ELECTION_SHAPE", bad(**{"el.a": {"follows": None}}))              # choose_before_anniversary needs follows
        self.assertIn("BAD_ELECTION_SHAPE", bad(**{"el.b": {"choose_before_anniversary": "2028-01-01"}}))   # one choice period per group
        self.assertIn("ELECTION_GOVERNS_NOTHING", bad(**{"el.a": None, "el.big": None}))     # nothing follows el.new any more
        self.assertIn("ANNIVERSARY_RULE_DIFFERS", bad(**{"el.a": {"anniversary_cycle_days": 62}}))
        self.assertIn("BAD_ELECTION_SHAPE", bad(**{"el.a": {"anniversary_cycle_days": 0}}))

    def test_holding_checks(self):
        s = world([card(), holding("p1", "el.big", valid_from="2027-06-01"), holding("p2", "el.a", valid_from="2025-06-01", anniversary_on="2027-06-20")])
        self.assertIn("ELECTION_NOT_SELECTABLE", codes(lint(s)))
        self.assertIn("UNEXPECTED_FIELD", codes(lint(s)))                                   # anniversary_on belongs on the card holding
        self.assertIn("ELECTION_NOT_SELECTABLE", flag_codes(evaluate(s, "t", "2027-06-20")))


if __name__ == "__main__":
    unittest.main()
