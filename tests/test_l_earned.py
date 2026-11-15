"""Earned benefits, part 1: what follows from what.

    public rule (on offer)  ->  personal achievement (eligible)  ->  personal entitlement (held)  ->  use (remaining)

Rules under test: an offer is not an achievement; an achievement is not an entitlement; nothing is
borrowed from another account, another person, another cycle or a later date; unknown stays unknown.
All data here is invented.
"""
import unittest

from util import H, codes, ent, ev, flag_codes, holding, make_store, metric, rule
from prices import discovery
from prices.cards import matrix
from prices.earned import (ACHIEVED, ACTIVATION_REQUIRED, ACTIVE, BELOW, CONFLICT, EARNED_NOT_CONFIRMED, EXHAUSTED, EXPIRED,
                           INCOMPLETE, LAPSED_UNCLAIMED, NOT_EARNED, NOT_OFFERED, NOT_QUALIFIED, NOT_RECORDED, NOT_STARTED,
                           NOT_YET_EFFECTIVE, UNCERTAIN, UNRESOLVED as E_UNRESOLVED, achievement, survey)
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.review import timeline

OWNER, ACCT, MEASURE, T = "Test Owner", "h-card", "card.spend", 75000
FEB = {"ends": "fixed", "year_offset": 2, "month": 2, "month_end": True}
DEC = {"ends": "fixed", "year_offset": 1, "month": 12, "day": 31}


def earn_rule(rid, output, term=DEC, activation="automatic", status="verified", **kw):
    earn = dict({"measure": MEASURE, "period": "calendar_year", "threshold": T, "unit": "units", "activation": activation, "term": term},
                **{k: kw.pop(k) for k in ("allowance", "activation_action") if k in kw})
    return rule(rid, "earns", output, kw.pop("when", H("card")), status=status, earn=earn, **kw)


def reading(rid, value, observed_on, state="confirmed", confirmed_on=None, **kw):
    r = dict({"id": rid, "value": value, "observed_on": observed_on, "state": state}, **kw)
    if state == "confirmed":
        r.update(confirmed_by=OWNER, confirmed_on=confirmed_on or (observed_on if observed_on != "unknown" else "2027-01-20"))
    return r


def qual(cycle, readings, account=ACCT):
    return {"id": "q-%s-%s" % (account, cycle), "account": account, "measure": MEASURE, "cycle": cycle, "readings": list(readings)}


def inst(eid, rule_id, entity, cycle, start, end, state="confirmed", confirmed_on="2026-11-10", account=ACCT, **kw):
    e = dict({"id": eid, "rule": rule_id, "entity": entity, "account": account, "cycle": cycle, "state": state,
              "effective_from": start, "expires_on": end}, **kw)
    if state == "confirmed":
        e.update(confirmed_by=OWNER, confirmed_on=confirmed_on)
    return e


def use(uid, amount, used_on, state="confirmed", confirmed_on=None):
    u = {"id": uid, "amount": amount, "used_on": used_on, "state": state}
    if state == "confirmed":
        u.update(confirmed_by=OWNER, confirmed_on=confirmed_on or used_on)
    return u


def world(quals=(), insts=(), rules=None, holdings=None, extra_entities=(), profile="t"):
    es = [ent("card", "card"), ent("status.x", "status"), ent("fare", "benefit"), ent("award", "benefit"), ent("credit", "benefit"),
          ent("perk", "benefit"), ent("act.enroll", "action", how="Enroll in the portal")] + list(extra_entities)
    rs = rules if rules is not None else [
        earn_rule("earn-status", "status.x", FEB), earn_rule("earn-fare", "fare"),
        earn_rule("earn-award", "award", activation="required", activation_action="act.enroll"),
        earn_rule("earn-credit", "credit", allowance={"amount": 300, "unit": "units"}),
        rule("perk-from-status", "grants", "perk", H("status.x"))]
    s = make_store(es, rs, holdings if holdings is not None else [holding(ACCT, "card", valid_from="2026-01-01")], profile=profile)
    for q in quals:
        s.files["profiles/%s/qualifications/%s.json" % (profile, q["id"])] = q
    for e in insts:
        s.files["profiles/%s/entitlements/%s.json" % (profile, e["id"])] = e
    return s


def row(store, entity, cycle, as_of, profile="t", account=ACCT):
    for a in survey(store, profile, as_of)["accounts"]:
        if a["account"] == account:
            for c in a["cycles"]:
                for b in c["benefits"]:
                    if c["cycle"] == cycle and b["entity"] == entity:
                        return b
    return None


ACHIEVED_2026 = [reading("r1", 38400, "2026-06-30"), reading("r2", 76900, "2026-10-31")]


class TestOfferAchievementEntitlement(unittest.TestCase):
    def test_an_offer_gives_the_cardholder_nothing(self):
        s = world()
        self.assertEqual(lint(s), [])
        r = evaluate(s, "t", "2026-11-01")
        for x in ("status.x", "fare", "award", "credit", "perk"):
            self.assertEqual(r.have(x), NOT_AVAILABLE, x)
        b = row(s, "status.x", "2026", "2026-11-01")
        self.assertEqual((b["achievement"]["state"], b["entitlement"]["state"]), (NOT_RECORDED, NOT_EARNED))
        self.assertTrue(b["public"]["offered_for_cycle"])

    def test_reaching_the_threshold_is_eligibility_never_possession(self):
        s = world([qual("2026", ACHIEVED_2026)])
        self.assertEqual(lint(s), [])
        r = evaluate(s, "t", "2026-11-05")
        for x in ("status.x", "fare", "credit"):
            self.assertEqual(r.status("can_get:" + x), ESTABLISHED, x)
            self.assertEqual(r.have(x), CONDITIONAL, x)                      # eligible, not held
            self.assertEqual(row(s, x, "2026", "2026-11-05")["entitlement"]["state"], EARNED_NOT_CONFIRMED)
        self.assertEqual(r.have("perk"), CONDITIONAL)                         # nothing downstream is established either
        rep = r.report()
        self.assertEqual(rep["derived_entitlements"], [])
        self.assertEqual(sorted(x["entity"] for x in rep["eligible_to_acquire"]), ["award", "credit", "fare", "status.x"])
        self.assertEqual(rep["earned_entitlements"], [])

    def test_activation_is_a_separate_personal_fact(self):
        s = world([qual("2026", ACHIEVED_2026)])
        b = row(s, "award", "2026", "2026-11-05")
        self.assertEqual((b["achievement"]["state"], b["entitlement"]["state"]), (ACHIEVED, ACTIVATION_REQUIRED))
        r = evaluate(s, "t", "2026-11-05")
        self.assertEqual(r.have("award"), CONDITIONAL)
        self.assertEqual(sorted((x["type"], x["entity"]) for x in r.tokens("have:award")["steps"]), [("acquire", "award"), ("action", "act.enroll")])
        done = world([qual("2026", ACHIEVED_2026)], [inst("e-award", "earn-award", "award", "2026", "2027-01-15", "2027-12-31", confirmed_on="2027-01-16")])
        self.assertEqual(evaluate(done, "t", "2027-01-14").have("award"), CONDITIONAL)     # still only eligible the day before
        self.assertEqual(row(done, "award", "2026", "2027-01-14")["entitlement"]["state"], ACTIVATION_REQUIRED)
        self.assertEqual(evaluate(done, "t", "2027-01-15").have("award"), ESTABLISHED)
        self.assertEqual(evaluate(done, "t", "2027-01-15").basis("have:award"), "personal")

    def test_holder_below_holder_achieving_and_holder_who_did_not_qualify(self):
        below = world([qual("2026", [reading("r1", 38400, "2026-06-30")])])
        self.assertEqual(row(below, "status.x", "2026", "2026-07-15")["achievement"]["state"], BELOW)
        self.assertEqual(evaluate(below, "t", "2026-07-15").have("status.x"), NOT_AVAILABLE)
        missed = world([qual("2026", [reading("r1", 41000, "2026-08-31"), reading("r9", 61300, "2026-12-31", final=True, confirmed_on="2027-01-04")])])
        b = row(missed, "status.x", "2026", "2027-02-01")
        self.assertEqual((b["achievement"]["state"], b["entitlement"]["state"]), (NOT_QUALIFIED, NOT_EARNED))
        r = evaluate(missed, "t", "2027-02-01")
        self.assertEqual((r.have("status.x"), r.status("can_get:status.x")), (NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertEqual(r.flags, [])

    def test_one_qualifying_event_two_benefits_two_expiries(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29"),
                                                  inst("e-fare", "earn-fare", "fare", "2026", "2026-11-08", "2027-12-31")])
        self.assertEqual(lint(s), [])
        for d, status, fare in (("2026-10-30", UNRESOLVED, UNRESOLVED),             # crossed some time after June 30: not known yet
                                ("2026-11-07", CONDITIONAL, CONDITIONAL),           # eligible since October 31; the account records start November 8
                                ("2026-11-08", ESTABLISHED, ESTABLISHED),
                                ("2027-12-31", ESTABLISHED, ESTABLISHED), ("2028-01-01", ESTABLISHED, NOT_AVAILABLE),
                                ("2028-02-29", ESTABLISHED, NOT_AVAILABLE), ("2028-03-01", NOT_AVAILABLE, NOT_AVAILABLE)):
            r = evaluate(s, "t", d)
            self.assertEqual((r.have("status.x"), r.have("fare")), (status, fare), d)
        self.assertEqual(evaluate(s, "t", "2027-06-01").have("perk"), ESTABLISHED)      # ordinary rules build on an earned status
        self.assertEqual(evaluate(s, "t", "2028-03-01").have("perk"), NOT_AVAILABLE)

    def test_progress_is_scoped_to_the_account_not_the_person(self):
        two = [holding(ACCT, "card", valid_from="2026-01-01"), holding("h-card-2", "card", valid_from="2026-01-01")]
        s = world([qual("2026", ACHIEVED_2026)], holdings=two)                           # all the spend is on the first account
        self.assertEqual(lint(s), [])
        self.assertEqual(row(s, "status.x", "2026", "2026-11-05")["achievement"]["state"], ACHIEVED)
        self.assertEqual(row(s, "status.x", "2026", "2026-11-05", account="h-card-2")["achievement"]["state"], NOT_RECORDED)
        split = world([qual("2026", [reading("r1", 40000, "2026-10-31")]), qual("2026", [reading("r1", 40000, "2026-10-31")], account="h-card-2")],
                      holdings=two)                                                      # 40,000 + 40,000 on two accounts is not 80,000 on one
        self.assertEqual(evaluate(split, "t", "2026-11-05").status("can_get:status.x"), NOT_AVAILABLE)

    def test_progress_is_scoped_to_the_person(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29")])
        s.files["profiles/u/profile.json"] = {"id": "u", "label": "second person", "synthetic": True, "owner": "Second Owner"}
        s.files["profiles/u/holdings/%s.json" % ACCT] = holding(ACCT, "card", valid_from="2026-01-01")   # same card, even the same holding id
        self.assertEqual(lint(s), [])
        other = evaluate(s, "u", "2027-01-01")
        self.assertEqual((other.have("card"), other.have("status.x"), other.status("can_get:status.x")), (ESTABLISHED, NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertNotIn("earned_entitlements", other.report())
        self.assertEqual(evaluate(s, "t", "2027-01-01").have("status.x"), ESTABLISHED)

    def test_progress_is_scoped_to_the_cycle(self):
        s = world([qual("2026", ACHIEVED_2026), qual("2027", [reading("r1", 12000, "2027-03-31")])])
        self.assertEqual(row(s, "fare", "2026", "2027-04-10")["achievement"]["state"], ACHIEVED)
        self.assertEqual(row(s, "fare", "2027", "2027-04-10")["achievement"]["state"], BELOW)    # 2026's spend does not carry over
        self.assertEqual(row(s, "fare", "2027", "2027-04-10")["achievement"]["progress"]["value"], 12000)


class TestTime(unittest.TestCase):
    def test_a_later_reading_never_reaches_back(self):
        s = world([qual("2026", [reading("r2", 76900, "2026-10-31")])])
        for d in ("2026-03-01", "2026-10-30"):
            r = evaluate(s, "t", d)
            self.assertEqual(row(s, "status.x", "2026", d)["achievement"]["state"], UNCERTAIN, d)
            self.assertEqual(r.status("can_get:status.x"), UNRESOLVED, d)        # never ESTABLISHED before the reading's date
            self.assertNotEqual(r.have("status.x"), ESTABLISHED, d)
        self.assertEqual(evaluate(s, "t", "2026-10-31").status("can_get:status.x"), ESTABLISHED)

    def test_a_dated_lower_reading_settles_the_dates_before_it(self):
        s = world([qual("2026", ACHIEVED_2026)])
        self.assertEqual(row(s, "status.x", "2026", "2026-05-01")["achievement"]["state"], BELOW)      # still below on June 30, so below on May 1
        self.assertEqual(evaluate(s, "t", "2026-05-01").status("can_get:status.x"), NOT_AVAILABLE)
        self.assertEqual(row(s, "status.x", "2026", "2026-08-15")["achievement"]["state"], UNCERTAIN)  # crossed some time in July-October
        a = row(s, "status.x", "2026", "2026-11-05")["achievement"]
        self.assertEqual((a["state"], a["by"]), (ACHIEVED, "2026-10-31"))
        self.assertIn("not recorded", a["detail"])                                                       # the crossing day is never invented

    def test_before_the_cycle_starts_nothing_counts(self):
        s = world([qual("2027", [reading("r1", 80000, "2027-03-31")])])
        self.assertEqual(row(s, "status.x", "2027", "2026-12-15")["achievement"]["state"], NOT_STARTED)
        self.assertEqual(evaluate(s, "t", "2026-12-15").status("can_get:status.x"), NOT_AVAILABLE)

    def test_year_only_attestation_keeps_its_date_unknown(self):
        said = reading("r-year", 75000, "unknown", value_kind="at_least", confirmed_on="2027-01-20")
        s = world([qual("2026", [said])])
        self.assertEqual(lint(s), [])
        for d in ("2026-02-01", "2026-12-31"):
            self.assertEqual(row(s, "status.x", "2026", d)["achievement"]["state"], UNCERTAIN if d < "2026-12-31" else ACHIEVED, d)
        self.assertEqual(evaluate(s, "t", "2026-09-01").status("can_get:status.x"), UNRESOLVED)
        a = row(s, "status.x", "2026", "2027-01-05")["achievement"]
        self.assertEqual(a["state"], ACHIEVED)                         # it happened during 2026, so it is settled once 2026 is over
        self.assertEqual(a["progress"]["as_of"], "unknown")            # ...but no date is attached to it
        self.assertIn("date unknown", a["detail"])
        early = world([qual("2026", [reading("r-year", 75000, "unknown", value_kind="at_least", confirmed_on="2026-11-20")])])
        self.assertEqual(row(early, "status.x", "2026", "2026-11-19")["achievement"]["state"], UNCERTAIN)
        self.assertEqual(row(early, "status.x", "2026", "2026-11-20")["achievement"]["state"], ACHIEVED)

    def test_unknown_start_date_is_unresolved_until_the_owner_saw_it_active(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-status", "earn-status", "status.x", "2026", "unknown", "2028-02-29", confirmed_on="2027-01-20")])
        self.assertEqual(lint(s), [])
        self.assertEqual(evaluate(s, "t", "2025-12-31").have("status.x"), NOT_AVAILABLE)   # cannot predate its own qualifying cycle
        mid = evaluate(s, "t", "2026-12-01")
        self.assertEqual(mid.have("status.x"), UNRESOLVED)
        self.assertIn("ENTITLEMENT_UNRESOLVED", flag_codes(mid))
        self.assertTrue(any("effective date not recorded" in u for u in mid.tokens("have:status.x")["unknowns"]))
        self.assertEqual(evaluate(s, "t", "2027-01-20").have("status.x"), ESTABLISHED)
        self.assertEqual(evaluate(s, "t", "2028-03-01").have("status.x"), NOT_AVAILABLE)

    def test_unknown_expiry_does_not_persist_silently(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-fare", "earn-fare", "fare", "2026", "2026-11-08", "unknown", confirmed_on="2026-11-10")])
        self.assertEqual(evaluate(s, "t", "2026-11-10").have("fare"), ESTABLISHED)          # the day the owner confirmed it
        later = evaluate(s, "t", "2027-06-01")
        self.assertEqual(later.have("fare"), UNRESOLVED)
        self.assertTrue(any("expiry not recorded" in u for u in later.tokens("have:fare")["unknowns"]))
        self.assertEqual(evaluate(s, "t", "2031-01-01").have("fare"), UNRESOLVED)           # never quietly established, never quietly dropped

    def test_personal_expiry_ends_it_and_says_so(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-fare", "earn-fare", "fare", "2026", "2026-11-08", "2027-12-31")])
        self.assertEqual(evaluate(s, "t", "2027-12-31").have("fare"), ESTABLISHED)
        after = evaluate(s, "t", "2028-01-01")
        self.assertEqual(after.have("fare"), NOT_AVAILABLE)
        self.assertIn("EXPIRED_ENTITLEMENT", flag_codes(after))
        self.assertEqual(row(s, "fare", "2026", "2028-01-01")["entitlement"]["state"], EXPIRED)
        events = {e["date"]: e for e in timeline(s, "t", "2026-11-01", "2028-06-01")}
        gone = {c["atom"]: (c["before"], c["after"]) for c in events["2028-01-01"]["changes"]}
        self.assertEqual(gone["have:fare"], (ESTABLISHED, NOT_AVAILABLE))        # the timeline shows the day it ends

    def test_the_end_of_the_qualifying_year_does_not_end_the_benefit(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29")])
        for d in ("2026-12-31", "2027-01-01", "2027-12-31", "2028-01-01"):
            self.assertEqual(evaluate(s, "t", d).have("status.x"), ESTABLISHED, d)

    def test_offer_validity_is_not_personal_expiry(self):
        rules = [earn_rule("earn-fare", "fare", valid_to="2026-12-31")]                      # the bank stops offering it after 2026
        s = world([qual("2026", ACHIEVED_2026), qual("2027", [reading("r1", 90000, "2027-06-30")])],
                  [inst("e-fare", "earn-fare", "fare", "2026", "2026-11-08", "2027-12-31")], rules=rules)
        self.assertEqual(lint(s), [])
        self.assertEqual(evaluate(s, "t", "2027-09-01").have("fare"), ESTABLISHED)           # the 2026 instance runs its own course
        b = row(s, "fare", "2027", "2027-09-01")
        self.assertEqual((b["achievement"]["state"], b["entitlement"]["state"]), (ACHIEVED, NOT_OFFERED))   # 2027 spend earns nothing: no offer
        self.assertEqual(evaluate(s, "t", "2028-01-01").have("fare"), NOT_AVAILABLE)
        for status in ("retired", "unverified"):                                             # nor does withdrawing or doubting the rule revoke it
            s.files["data/kb/rules/earn-fare.json"]["verification"]["status"] = status
            self.assertEqual(evaluate(s, "t", "2027-09-01").have("fare"), ESTABLISHED, status)

    def test_unclaimed_eligibility_lapses_with_the_rules_term(self):
        s = world([qual("2026", ACHIEVED_2026)])
        self.assertEqual(evaluate(s, "t", "2027-12-31").have("fare"), CONDITIONAL)
        self.assertEqual(evaluate(s, "t", "2028-01-01").have("fare"), NOT_AVAILABLE)
        self.assertEqual(row(s, "fare", "2026", "2028-01-01")["entitlement"]["state"], LAPSED_UNCLAIMED)

    def test_closed_account_is_flagged_not_assumed(self):
        closed = [holding(ACCT, "card", valid_from="2026-01-01", valid_to="2027-03-31")]
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29")], holdings=closed)
        r = evaluate(s, "t", "2027-06-01")
        self.assertEqual(r.have("status.x"), ESTABLISHED)            # the owner's record stands until the owner changes it
        self.assertIn("ACCOUNT_NOT_HELD", flag_codes(r))             # ...but the question is raised
        self.assertEqual(r.status("can_get:fare"), NOT_AVAILABLE)    # and nothing new can be claimed on a closed account

    def test_legacy_metric_no_longer_reaches_back(self):
        es, rs = [ent("gold")], [rule("r", "grants", "gold", {"metric": "nights", "gte": 50})]
        m = dict(metric("nights", 60), as_of="2026-06-30")
        s = make_store(es, rs, metrics=[m])
        self.assertEqual(evaluate(s, "t", "2026-06-29").have("gold"), UNRESOLVED)    # observed later: unknown on this date, not satisfied
        self.assertTrue(any("no observation on or before" in u for u in evaluate(s, "t", "2026-06-29").tokens("have:gold")["unknowns"]))
        self.assertEqual(evaluate(s, "t", "2026-06-30").have("gold"), ESTABLISHED)
        self.assertEqual(evaluate(s, "t", "2027-01-01").have("gold"), ESTABLISHED)   # unchanged for dates on or after the observation


class TestCycles(unittest.TestCase):
    def two_years(self):
        return world([qual("2026", ACHIEVED_2026), qual("2027", [reading("r1", 29000, "2027-04-30"), reading("r2", 78300, "2027-09-30")])],
                     [inst("e26-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29"),
                      inst("e27-status", "earn-status", "status.x", "2027", "2027-10-06", "2029-02-28", confirmed_on="2027-10-08"),
                      inst("e26-credit", "earn-credit", "credit", "2026", "2026-11-08", "2027-12-31", allowance={"amount": 300, "unit": "units"},
                           usage=[use("u1", 120, "2026-12-03"), use("u2", 80, "2027-02-10")]),
                      inst("e27-credit", "earn-credit", "credit", "2027", "2027-10-06", "2028-12-31", confirmed_on="2027-10-08",
                           allowance={"amount": 300, "unit": "units"})])

    def test_second_year_is_independent(self):
        s = self.two_years()
        self.assertEqual(lint(s), [])
        b26, b27 = row(s, "status.x", "2026", "2027-06-01"), row(s, "status.x", "2027", "2027-06-01")
        self.assertEqual((b26["achievement"]["state"], b26["entitlement"]["state"]), (ACHIEVED, ACTIVE))
        self.assertEqual((b27["achievement"]["state"], b27["entitlement"]["state"]), (UNCERTAIN, NOT_YET_EFFECTIVE))
        self.assertEqual(b26["achievement"]["progress"]["value"], 76900)        # each cycle keeps its own readings
        self.assertEqual(b27["achievement"]["progress"]["value"], 29000)

    def test_overlapping_instances_neither_gap_nor_double(self):
        s = self.two_years()
        for d, want in (("2027-10-05", ESTABLISHED), ("2027-10-06", ESTABLISHED), ("2028-02-29", ESTABLISHED),
                        ("2028-03-01", ESTABLISHED), ("2029-02-28", ESTABLISHED), ("2029-03-01", NOT_AVAILABLE)):
            self.assertEqual(evaluate(s, "t", d).have("status.x"), want, d)
        both = [x for x in evaluate(s, "t", "2027-12-01").report()["earned_entitlements"] if x["entity"] == "status.x"]
        self.assertEqual([(x["cycle"], x["state"]) for x in both], [("2026", ACTIVE), ("2027", ACTIVE)])   # two instances, listed apart
        r = evaluate(s, "t", "2028-03-01")
        self.assertNotIn("EXPIRED_ENTITLEMENT", flag_codes(r))                   # a newer instance took over: no alarm
        self.assertEqual(r.via["E"]["have:status.x"][0], "entitlement:e27-status")

    def test_credits_from_two_years_are_never_merged(self):
        s = self.two_years()
        c26, c27 = row(s, "credit", "2026", "2027-11-01")["instances"][0]["credit"], row(s, "credit", "2027", "2027-11-01")["instances"][0]["credit"]
        self.assertEqual((c26["allowance"], c26["used"], c26["remaining"]), (300, 200, 100))
        self.assertEqual((c27["allowance"], c27["used"], c27["remaining"]), (300, 0, 300))
        after = evaluate(s, "t", "2028-01-01")                                   # the first credit lapses with 100 left: said out loud
        self.assertEqual(after.have("credit"), ESTABLISHED)
        self.assertIn("CREDIT_LAPSED_UNUSED", flag_codes(after))
        self.assertEqual(row(s, "credit", "2027", "2028-01-01")["instances"][0]["credit"]["remaining"], 300)   # and is not added to the second


class TestCredit(unittest.TestCase):
    def credit_world(self, usage, start="2026-11-08", end="2027-12-31"):
        return world([qual("2026", ACHIEVED_2026)], [inst("e-credit", "earn-credit", "credit", "2026", start, end,
                                                          allowance={"amount": 300, "unit": "units"}, usage=usage)])

    def numbers(self, s, d):
        c = row(s, "credit", "2026", d)["instances"][0]["credit"]
        return c["allowance"], c["used"], c["possibly_used"], c["remaining"], c["remaining_at_least"]

    def test_allowance_used_and_remaining_are_three_numbers(self):
        s = self.credit_world([use("u1", 120, "2026-12-03"), use("u2", 80, "2027-02-10")])
        self.assertEqual(lint(s), [])
        self.assertEqual(self.numbers(s, "2026-12-02"), (300, 0, 0, 300, 300))        # use dated later is not counted earlier
        self.assertEqual(self.numbers(s, "2026-12-03"), (300, 120, 0, 180, 180))
        self.assertEqual(self.numbers(s, "2027-03-01"), (300, 200, 0, 100, 100))
        self.assertEqual(s.files["profiles/t/entitlements/e-credit.json"]["allowance"]["amount"], 300)   # the allowance itself is never reduced

    def test_unconfirmed_use_is_a_range_not_a_fact(self):
        s = self.credit_world([use("u1", 120, "2026-12-03"), use("u2", 60, "2027-03-02", state="unconfirmed")])
        self.assertEqual(self.numbers(s, "2027-03-10"), (300, 120, 60, 180, 120))
        r = evaluate(s, "t", "2027-03-10")
        self.assertEqual(r.have("credit"), ESTABLISHED)
        self.assertIn("CREDIT_USE_UNCONFIRMED", flag_codes(r))

    def test_exhausted_and_possibly_exhausted(self):
        gone = self.credit_world([use("u1", 300, "2026-12-03")])
        self.assertEqual(row(gone, "credit", "2026", "2027-01-01")["entitlement"]["state"], EXHAUSTED)
        self.assertEqual(evaluate(gone, "t", "2027-01-01").have("credit"), NOT_AVAILABLE)   # an empty credit is not a usable benefit
        self.assertEqual(evaluate(gone, "t", "2026-12-02").have("credit"), ESTABLISHED)
        maybe = self.credit_world([use("u1", 250, "2026-12-03"), use("u2", 50, "2027-01-05", state="unconfirmed")])
        r = evaluate(maybe, "t", "2027-02-01")
        self.assertEqual(r.have("credit"), UNRESOLVED)                                       # cannot be called available
        self.assertEqual(row(maybe, "credit", "2026", "2027-02-01")["entitlement"]["state"], E_UNRESOLVED)

    def test_undated_use_counts_only_from_its_confirmation(self):
        s = self.credit_world([use("u1", 100, "unknown", confirmed_on="2027-02-01")])
        self.assertEqual(lint(s), [])
        self.assertEqual(self.numbers(s, "2027-01-15"), (300, 0, 100, 300, 200))     # may already have been used: a range
        self.assertEqual(self.numbers(s, "2027-02-01"), (300, 100, 0, 200, 200))

    def test_recorded_overuse_is_an_error_and_never_available(self):
        s = self.credit_world([use("u1", 200, "2026-12-03"), use("u2", 200, "2026-12-20")])
        self.assertIn("OVER_CONSUMED", codes(lint(s)))
        self.assertEqual(evaluate(s, "t", "2027-01-01").have("credit"), UNRESOLVED)


class TestUnrecordedUnconfirmedConflicting(unittest.TestCase):
    def test_unconfirmed_progress_is_never_established(self):
        s = world([qual("2026", [reading("r1", 80000, "2026-10-31", state="unconfirmed")])])
        b = row(s, "status.x", "2026", "2026-11-05")
        self.assertEqual((b["achievement"]["state"], b["entitlement"]["state"]), (UNCERTAIN, E_UNRESOLVED))
        r = evaluate(s, "t", "2026-11-05")
        self.assertEqual((r.status("can_get:status.x"), r.have("status.x")), (UNRESOLVED, UNRESOLVED))
        self.assertEqual(r.report()["eligible_to_acquire"], [])

    def test_conflicting_progress_is_reported_not_resolved(self):
        s = world([qual("2026", [reading("r1", 76900, "2026-10-31"), reading("r2", 70100, "2026-11-30")])])
        b = row(s, "status.x", "2026", "2026-12-05")
        self.assertEqual(b["achievement"]["state"], CONFLICT)
        r = evaluate(s, "t", "2026-12-05")
        self.assertEqual(r.status("can_get:status.x"), UNRESOLVED)
        self.assertIn("CONFLICTING_PROGRESS", flag_codes(r))
        self.assertEqual(achievement(T, s.files["profiles/t/qualifications/q-h-card-2026.json"], evaluate(s, "t", "2026-11-05").as_of)["state"], CONFLICT)

    def test_cycle_over_with_no_final_figure(self):
        s = world([qual("2026", [reading("r1", 41000, "2026-08-31")])])
        self.assertEqual(row(s, "status.x", "2026", "2026-12-15")["achievement"]["state"], BELOW)
        self.assertIn("days before this query date", row(s, "status.x", "2026", "2026-12-15")["achievement"]["detail"])   # staleness is stated
        r = evaluate(s, "t", "2027-02-01")
        self.assertEqual(row(s, "status.x", "2026", "2027-02-01")["achievement"]["state"], INCOMPLETE)
        self.assertEqual(r.have("status.x"), NOT_AVAILABLE)
        self.assertIn("QUALIFICATION_OUTCOME_NOT_RECORDED", flag_codes(r))

    def test_unconfirmed_entitlement_is_unresolved(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29", state="unconfirmed")])
        self.assertEqual(lint(s), [])
        r = evaluate(s, "t", "2027-01-01")
        self.assertEqual((r.have("status.x"), r.have("perk")), (UNRESOLVED, UNRESOLVED))
        self.assertIn("UNCONFIRMED_ENTITLEMENT", flag_codes(r))

    def test_two_records_for_one_benefit_account_and_cycle(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-a", "earn-fare", "fare", "2026", "2026-11-08", "2027-12-31"),
                                                  inst("e-b", "earn-fare", "fare", "2026", "2026-11-08", "2027-06-30")])
        self.assertIn("CONFLICTING_ENTITLEMENTS", {i[1] for i in lint(s)})
        r = evaluate(s, "t", "2027-03-01")
        self.assertEqual(r.have("fare"), UNRESOLVED)                         # conflicting expiry: not promoted
        self.assertIn("CONFLICTING_ENTITLEMENTS", flag_codes(r))

    def test_entitlement_contradicted_by_a_final_shortfall(self):
        missed = [reading("r9", 61300, "2026-12-31", final=True, confirmed_on="2027-01-04")]
        s = world([qual("2026", missed)], [inst("e-status", "earn-status", "status.x", "2026", "2027-01-10", "2028-02-29", confirmed_on="2027-01-12")])
        r = evaluate(s, "t", "2027-02-01")
        self.assertEqual(r.have("status.x"), UNRESOLVED)
        self.assertIn("CONFLICTING_QUALIFICATION", flag_codes(r))

    def test_entitlement_without_progress_on_file_stands_but_is_flagged(self):
        s = world([], [inst("e-status", "earn-status", "status.x", "2026", "2026-11-08", "2028-02-29")])
        r = evaluate(s, "t", "2027-01-01")
        self.assertEqual(r.have("status.x"), ESTABLISHED)                    # the owner confirmed what the account shows...
        self.assertIn("QUALIFICATION_NOT_RECORDED", flag_codes(r))           # ...and the missing link in the chain is not hidden
        self.assertEqual(row(s, "status.x", "2026", "2027-01-01")["achievement"]["state"], NOT_RECORDED)

    def test_unverified_rule_gives_only_unresolved_eligibility(self):
        s = world([qual("2026", ACHIEVED_2026)], rules=[earn_rule("earn-fare", "fare", status="unverified")])
        r = evaluate(s, "t", "2026-11-05")
        self.assertEqual((r.status("can_get:fare"), r.have("fare")), (UNRESOLVED, UNRESOLVED))

    def test_term_and_allowance_differences_are_shown_personal_value_used(self):
        s = world([qual("2026", ACHIEVED_2026)], [inst("e-credit", "earn-credit", "credit", "2026", "2026-11-08", "2027-10-31",
                                                       allowance={"amount": 250, "unit": "units"})])
        r = evaluate(s, "t", "2027-01-01")
        self.assertLessEqual({"TERM_DIFFERS_FROM_RULE", "ALLOWANCE_DIFFERS_FROM_RULE"}, flag_codes(r))
        self.assertEqual(evaluate(s, "t", "2027-11-01").have("credit"), NOT_AVAILABLE)      # the personal date governs, not the rule's
        self.assertEqual(row(s, "credit", "2026", "2027-01-01")["instances"][0]["credit"]["allowance"], 250)


class TestStructure(unittest.TestCase):
    def test_earn_rule_shapes(self):
        tier = [ent("org.net", "organization"), ent("tier.t", "network_tier", network="org.net")]
        cases = [(earn_rule("x", "fare", when={"all": [H("card"), H("status.x")]}), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "card"), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "fare", {"ends": "fixed", "year_offset": 1, "month": 2, "day": 30}), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "fare", {"ends": "fixed", "year_offset": 1, "month": 13, "day": 1}), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "fare", {"ends": "not_stated", "month": 2}), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "fare", activation_action="act.enroll"), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "fare", activation="required", activation_action="perk"), "BAD_EARN_SHAPE"),
                 (earn_rule("x", "tier.t"), "BAD_EARN_SHAPE"),
                 (rule("x", "grants", "fare", H("card"), earn={"measure": MEASURE, "period": "calendar_year", "threshold": 1,
                                                               "activation": "automatic", "term": DEC}), "UNEXPECTED_FIELD"),
                 (rule("x", "earns", "fare", H("card")), "BAD_EARN_SHAPE")]
        for r, code in cases:
            self.assertIn(code, codes(lint(world(rules=[r], extra_entities=tier))), r["id"] + " " + code)
        zero = earn_rule("x", "fare")
        zero["earn"]["threshold"] = 0
        self.assertIn("BAD_EARN_SHAPE", codes(lint(world(rules=[zero]))))

    def test_personal_records_are_checked(self):
        ok_q, ok_e = qual("2026", ACHIEVED_2026), inst("e-credit", "earn-credit", "credit", "2026", "2026-11-08", "2027-12-31",
                                                       allowance={"amount": 300, "unit": "units"})

        def broken(q=None, e=None):
            return codes(lint(world([q or ok_q], [e or ok_e])))
        self.assertEqual(broken(), set())
        self.assertIn("UNKNOWN_ACCOUNT", broken(q=dict(ok_q, account="h-someone-elses")))
        self.assertIn("UNKNOWN_MEASURE", broken(q=dict(ok_q, measure="other.measure")))
        self.assertIn("BAD_READING", broken(q=qual("2026", [reading("r", 75000, "unknown")])))                 # undated and "exact"
        self.assertIn("OUT_OF_CYCLE", broken(q=qual("2026", [reading("r", 75000, "2027-01-02")])))
        self.assertIn("BAD_READING", broken(q=qual("2026", [reading("r", 75000, "2026-11-30", final=True)])))  # final must be year end
        self.assertIn("UNATTESTED_CONFIRMATION", broken(q=qual("2026", [dict(reading("r", 1, "2026-02-01"), confirmed_by="A maintainer")])))
        self.assertIn("BAD_DATES", broken(q=qual("2026", [reading("r", 1, "2026-02-30", confirmed_on="2026-03-01")])))
        self.assertIn("SCHEMA", broken(q=qual("26", [])))
        self.assertIn("ENTITY_MISMATCH", broken(e=dict(ok_e, entity="fare")))
        self.assertIn("UNKNOWN_REFERENCE", broken(e=dict(ok_e, rule="perk-from-status")))                      # not an earns rule
        self.assertIn("UNKNOWN_ACCOUNT", broken(e=dict(ok_e, account="h-someone-elses")))
        self.assertIn("BAD_DATES", broken(e=dict(ok_e, effective_from="2025-12-31")))                          # before its own cycle
        self.assertIn("BAD_DATES", broken(e=dict(ok_e, expires_on="2026-11-01")))
        self.assertIn("MISSING_ALLOWANCE", broken(e={k: v for k, v in ok_e.items() if k != "allowance"}))
        self.assertIn("BAD_ALLOWANCE", broken(e=dict(ok_e, allowance={"amount": 300, "unit": "miles"})))
        self.assertIn("OUT_OF_TERM", broken(e=dict(ok_e, usage=[use("u", 10, "2028-01-05")])))
        self.assertIn("UNATTESTED_CONFIRMATION", broken(e=dict(ok_e, confirmed_by="A maintainer")))
        self.assertIn("SCHEMA", broken(e=dict(ok_e, expires_on="sometime in 2027")))                           # a date or the word unknown
        self.assertIn("BAD_ALLOWANCE", codes(lint(world([ok_q], [inst("e-fare", "earn-fare", "fare", "2026", "2026-11-08", "2027-12-31",
                                                                       allowance={"amount": 1, "unit": "units"})]))))

    def test_account_must_be_the_right_card(self):
        other = [holding(ACCT, "card", valid_from="2026-01-01"), holding("h-other", "card.b", valid_from="2026-01-01")]
        s = world([], [inst("e-fare", "earn-fare", "fare", "2026", "2026-11-08", "2027-12-31", account="h-other")],
                  holdings=other, extra_entities=[ent("card.b", "card")])
        self.assertIn("ACCOUNT_MISMATCH", codes(lint(s)))

    def test_network_tier_guarantee_still_holds_for_earned_benefits(self):
        tier = [ent("org.net", "organization"), ent("tier.t", "network_tier", network="org.net")]
        rules = [rule("base.fare", "baseline", "fare", H("tier.t")), earn_rule("earn-fare", "fare")]      # evidence ev1 names no card
        s = world([qual("2026", ACHIEVED_2026)], rules=rules, extra_entities=tier)
        self.assertIn("CARD_SPECIFIC_EVIDENCE_REQUIRED", codes(lint(s)))
        s.files["data/kb/evidence/ev1.json"] = dict(ev(), applies_to=["card"])
        self.assertEqual(codes(lint(s)), set())
        self.assertEqual(evaluate(s, "t", "2026-11-05").have("fare"), CONDITIONAL)                         # still only eligibility
        self.assertEqual([m["standing"] for m in matrix(s, "2026-11-05")], [])                             # card has no tier: matrix untouched

    def test_discovery_sees_the_route_but_tables_and_matrix_do_not_treat_it_as_a_card_benefit(self):
        s = world()
        back = discovery.plan_backward(s, "t", "fare", "2026-11-05")
        self.assertEqual([r["rule"] for r in back["tree"]["routes"]], ["earn-fare"])
        from prices.tables import rows_from_store
        rows, _c = rows_from_store(s)
        self.assertEqual(rows["card_benefits"], {})                         # earn rules are not card_benefits rows
        self.assertNotIn("entitlement", " ".join(c for cols in __import__("prices.tables", fromlist=["COLUMNS"]).COLUMNS.values() for c in cols))


class TestNoPersonalFactsNoChange(unittest.TestCase):
    def test_profile_without_earned_records_is_untouched(self):
        s = world()
        r = evaluate(s, "t", "2026-11-05")
        self.assertFalse(hasattr(r, "earned"))                       # the earned module was not even consulted
        self.assertNotIn("earned_entitlements", r.report())

    def test_adding_earn_rules_changes_nothing_for_people_with_no_records(self):
        plain_rules = [rule("perk-from-status", "grants", "perk", H("status.x"))]
        before = evaluate(world(rules=plain_rules), "t", "2026-11-05").report()
        after = evaluate(world(), "t", "2026-11-05").report()
        for key in before:
            if key != "sourced_rules":
                self.assertEqual(before[key], after[key], key)
        self.assertEqual(set(before), set(after))


if __name__ == "__main__":
    unittest.main()
