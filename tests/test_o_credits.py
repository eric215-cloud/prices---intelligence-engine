"""Recurring card credits (ENG-01), part 1: periods, published terms, and what is and is not known about a person.

    published terms (rule)  ->  applies to this person? (engine)  ->  allowance period for a date  ->  personal record, if any

Rules under test: a published allowance is never a personal balance; a period that depends on a date nobody recorded
is unresolved, not guessed; a term the source does not state is reported as not stated, never as zero or unlimited;
elections (ENG-02) still decide which of two exclusive credits applies. All data here is invented.
"""
import datetime
import unittest

from util import H, ent, flag_codes, holding, make_store, rule
from prices import credits
from prices.credits import BEFORE_ACCOUNT, KNOWN, NOT_RECORDED, UNRESOLVED as P_UNRESOLVED, calendar_period, clip, label_bounds, label_ok, offer, period
from prices.engine import ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.review import review, timeline

D = datetime.date
CARD, ACCT, OWNER = "card.x", "h-card", "Test Owner"
TRAVEL = {"amount": 300, "unit": "USD", "cycle": "anniversary_year"}                                              # A
HOTEL = {"amount": 500, "unit": "USD", "cycle": "calendar_year", "max_per_transaction": 250, "min_stay_nights": 2, "rollover": "none"}   # B
DINING = {"amount": 150, "unit": "USD", "cycle": "calendar_half", "rollover": "none"}                              # C
RIDE = {"amount": 10, "unit": "USD", "cycle": "calendar_month", "rollover": "none"}                                # D
FEE = {"amount": 120, "unit": "USD", "cycle": "multi_year", "years": 4, "anchor": "last_use"}


def codes(issues):
    return {i[1] for i in issues}


def credit_rule(rid, output, block, **kw):
    return rule(rid, "grants", output, H(CARD), credit=dict(block), **kw)


def card(opened="2025-03-15", hid=ACCT, **kw):
    h = holding(hid, CARD, valid_from=kw.pop("valid_from", opened or "2025-01-01"), **kw)
    if opened:
        h["opened_on"] = opened
    return h


def option(oid, governs, **terms):
    e = ent(oid, "election", name=oid)
    e["election"] = dict({"group": "perk", "card": CARD, "governs": [governs]}, **terms)
    return e


def rec(eid, rule_id, cycle, start, end, amount, state="confirmed", usage=(), account=ACCT, **kw):
    e = dict({"id": eid, "rule": rule_id, "entity": {"r.travel": "travel", "r.hotel": "hotel", "r.dining": "dining", "r.ride": "ride",
                                                      "r.fee": "fee", "r.a": "perk.a", "r.b": "perk.b"}[rule_id],
              "account": account, "cycle": cycle, "state": state, "effective_from": start, "expires_on": end,
              "allowance": {"amount": amount, "unit": "USD"}}, **kw)
    if state == "confirmed":
        e.update(confirmed_by=OWNER, confirmed_on=kw.get("confirmed_on", start if start != "unknown" else "2027-01-05"))
    if usage:
        e["usage"] = list(usage)
    return e


def use(uid, amount, used_on, state="confirmed"):
    u = {"id": uid, "amount": amount, "used_on": used_on, "state": state}
    if state == "confirmed":
        u.update(confirmed_by=OWNER, confirmed_on=used_on)
    return u


def world(holdings=None, records=(), rules=None, options=(), profile="t"):
    es = [ent(CARD, "card"), ent("card.y", "card")] + [ent(b, "benefit") for b in ("travel", "hotel", "dining", "ride", "fee", "perk.a", "perk.b", "plain")]
    rs = rules if rules is not None else [
        credit_rule("r.travel", "travel", TRAVEL), credit_rule("r.hotel", "hotel", HOTEL), credit_rule("r.dining", "dining", DINING),
        credit_rule("r.ride", "ride", RIDE, valid_to="2027-09-30"), credit_rule("r.fee", "fee", FEE),
        rule("r.plain", "grants", "plain", H(CARD))]
    s = make_store(es + list(options), rs, holdings if holdings is not None else [card()], profile=profile, owner=OWNER)
    for h in s.profile(profile).holdings.values():
        if h["state"] == "confirmed":
            h["confirmed_by"] = OWNER
    for e in records:
        s.files["profiles/%s/entitlements/%s.json" % (profile, e["id"])] = e
    return s


def row(s, benefit, as_of, profile="t", account=ACCT, **kw):
    for a in credits.survey(s, profile, as_of, **kw)["accounts"]:
        for c in a["credits"]:
            if a["account"] == account and c["benefit"] == benefit:
                return c
    return None


def span(c):
    p = c["period"]
    return (p["state"], p.get("label"), p.get("start"), p.get("end"))


class TestCalendarPeriods(unittest.TestCase):
    def test_year_half_quarter_month(self):
        self.assertEqual(calendar_period("calendar_year", D(2027, 12, 31)), ("2027", D(2027, 1, 1), D(2027, 12, 31)))
        self.assertEqual(calendar_period("calendar_year", D(2028, 1, 1))[0], "2028")
        self.assertEqual(calendar_period("calendar_half", D(2027, 6, 30)), ("2027-H1", D(2027, 1, 1), D(2027, 6, 30)))
        self.assertEqual(calendar_period("calendar_half", D(2027, 7, 1)), ("2027-H2", D(2027, 7, 1), D(2027, 12, 31)))
        self.assertEqual(calendar_period("calendar_quarter", D(2027, 9, 30)), ("2027-Q3", D(2027, 7, 1), D(2027, 9, 30)))
        self.assertEqual(calendar_period("calendar_quarter", D(2027, 10, 1)), ("2027-Q4", D(2027, 10, 1), D(2027, 12, 31)))
        self.assertEqual(calendar_period("calendar_month", D(2028, 2, 29)), ("2028-02", D(2028, 2, 1), D(2028, 2, 29)))    # leap year
        self.assertEqual(calendar_period("calendar_month", D(2027, 2, 28)), ("2027-02", D(2027, 2, 1), D(2027, 2, 28)))
        self.assertEqual(calendar_period("calendar_month", D(2027, 12, 31)), ("2027-12", D(2027, 12, 1), D(2027, 12, 31)))

    def test_period_labels(self):
        for block, good, bad in ((HOTEL, ["2027"], ["2027-H1", "27", "2027-13"]), (DINING, ["2027-H1", "2027-H2"], ["2027", "2027-H3", "2027-Q1"]),
                                 (RIDE, ["2027-01", "2027-12"], ["2027", "2027-00", "2027-13", "2027-H1"]), (TRAVEL, ["2026"], ["2026-03"]),
                                 ({"cycle": "calendar_quarter"}, ["2027-Q4"], ["2027-Q5", "2027-04"])):
            for label in good:
                self.assertTrue(label_ok(block, label), label)
            for label in bad:
                self.assertFalse(label_ok(block, label), label)
        self.assertEqual(label_bounds(DINING, "2027-H2"), (D(2027, 7, 1), D(2027, 12, 31)))
        self.assertEqual(label_bounds(RIDE, "2027-02"), (D(2027, 2, 1), D(2027, 2, 28)))
        self.assertIsNone(label_bounds(TRAVEL, "2026"))                       # depends on the account, not on the calendar


class TestAccountPeriods(unittest.TestCase):
    def test_anniversary_year_boundaries(self):
        h = {"id": "h", "opened_on": "2025-03-15"}
        for day, want in ((D(2025, 3, 15), ("2025", D(2025, 3, 15), D(2026, 3, 14))), (D(2026, 3, 14), ("2025", D(2025, 3, 15), D(2026, 3, 14))),
                          (D(2026, 3, 15), ("2026", D(2026, 3, 15), D(2027, 3, 14))), (D(2027, 12, 31), ("2027", D(2027, 3, 15), D(2028, 3, 14)))):
            p = period(TRAVEL, day, h)
            self.assertEqual((p["state"], p["label"], p["start"], p["end"]), (KNOWN,) + want, day)
        self.assertEqual(period(TRAVEL, D(2025, 3, 14), h)["state"], BEFORE_ACCOUNT)

    def test_missing_opening_date_is_unresolved_never_invented(self):
        p = period(TRAVEL, D(2027, 3, 10), {"id": "h", "valid_from": "2025-03-15"})       # valid_from is NOT the opening date
        self.assertEqual(p["state"], P_UNRESOLVED)
        self.assertIn("opening date of account h is not recorded", p["reason"])
        self.assertNotIn("start", p)
        self.assertEqual(period(TRAVEL, D(2027, 3, 10))["state"], P_UNRESOLVED)           # no person at all: depends on each account

    def test_february_29_account(self):
        h = {"id": "h", "opened_on": "2024-02-29"}
        self.assertEqual(period(TRAVEL, D(2027, 2, 27), h)["end"], D(2027, 2, 27))        # certain part of the period only
        self.assertEqual(period(TRAVEL, D(2027, 2, 28), h)["state"], P_UNRESOLVED)        # Feb 28 or Mar 1: not decided by convention
        p = period(TRAVEL, D(2027, 3, 1), h)
        self.assertEqual((p["state"], p["label"], p["start"], p["end"]), (KNOWN, "2027", D(2027, 3, 1), D(2028, 2, 28)))
        self.assertIn("February 29", p["note"])
        self.assertEqual(period(TRAVEL, D(2028, 2, 29), h)["start"], D(2028, 2, 29))      # a real anniversary day in a leap year

    def test_multi_year_from_account_opening(self):
        four = {"amount": 120, "unit": "USD", "cycle": "multi_year", "years": 4, "anchor": "account_opening"}
        h = {"id": "h", "opened_on": "2022-06-01"}
        self.assertEqual(period(four, D(2026, 5, 31), h)["end"], D(2026, 5, 31))
        p = period(four, D(2026, 6, 1), h)
        self.assertEqual((p["label"], p["start"], p["end"]), ("2026", D(2026, 6, 1), D(2030, 5, 31)))
        self.assertEqual(period(four, D(2026, 6, 1), {"id": "h"})["state"], P_UNRESOLVED)

    def test_multi_year_with_no_stated_starting_point(self):
        p = period({"amount": 120, "unit": "USD", "cycle": "multi_year", "years": 4}, D(2027, 1, 1), {"id": "h", "opened_on": "2022-06-01"})
        self.assertEqual(p["state"], P_UNRESOLVED)
        self.assertIn("source does not say", p["reason"])

    def test_multi_year_from_last_use(self):
        h = {"id": "h", "opened_on": "2022-06-01"}
        used = rec("e1", "r.fee", "2025", "2025-09-10", "2029-09-09", 120)
        self.assertEqual(period(FEE, D(2027, 1, 1), h)["state"], P_UNRESOLVED)            # no use recorded: unknown, not "available"
        self.assertIn("no use is recorded", period(FEE, D(2027, 1, 1), h)["reason"])
        p = period(FEE, D(2029, 9, 9), h, [used])
        self.assertEqual((p["state"], p["label"], p["start"], p["end"], p["record"]), (KNOWN, "2025", D(2025, 9, 10), D(2029, 9, 9), "e1"))
        p = period(FEE, D(2029, 9, 10), h, [used])
        self.assertEqual((p["state"], p["label"], p["start"], p["end"]), (KNOWN, None, D(2029, 9, 10), None))   # open until the next use
        self.assertEqual(period(FEE, D(2025, 9, 9), h, [used])["state"], P_UNRESOLVED)    # before the only recorded use: unknown
        self.assertEqual(period(FEE, D(2027, 1, 1), h, [dict(used, state="unconfirmed")])["state"], P_UNRESOLVED)
        self.assertEqual(period(FEE, D(2027, 1, 1), h, [dict(used, effective_from="unknown")])["state"], P_UNRESOLVED)
        self.assertEqual(period(FEE, D(2027, 1, 1), h, [dict(used, state="superseded")])["state"], P_UNRESOLVED)


class TestOfferDates(unittest.TestCase):
    def test_effective_and_expiration_dates_come_from_the_rule(self):
        r = {"valid_from": "2026-04-01", "valid_to": "2027-09-30", "verification": {"status": "verified"}}
        self.assertEqual([offer(r, d)[0] for d in (D(2026, 3, 31), D(2026, 4, 1), D(2027, 9, 30), D(2027, 10, 1))],
                         ["NOT_YET_EFFECTIVE", "IN_EFFECT", "IN_EFFECT", "ENDED"])
        self.assertEqual(offer({"verification": {"status": "retired"}}, D(2027, 1, 1))[0], "ENDED")
        self.assertEqual(offer({"verification": {"status": "verified"}}, D(2027, 1, 1)), ("IN_EFFECT", "in effect"))

    def test_a_period_is_cut_to_the_offer_and_not_pro_rated(self):
        r = {"valid_from": "2027-02-10", "valid_to": "2027-09-30"}
        p = clip(period(HOTEL, D(2027, 3, 1)), r)
        self.assertEqual((p["start"], p["end"], p["last"]), (D(2027, 2, 10), D(2027, 9, 30), True))
        self.assertIn("2027-09-30", p["cut"])
        sep = clip(period(RIDE, D(2027, 9, 12)), r)                              # the offer ends exactly at a period end
        self.assertEqual((sep["end"], sep["last"], "cut" in sep), (D(2027, 9, 30), True, False))
        self.assertNotIn("last", clip(period(RIDE, D(2027, 8, 12)), r))


class TestPublishedIsNotPersonal(unittest.TestCase):
    def test_scenarios_a_to_d_for_a_cardholder_with_nothing_recorded(self):
        s = world()
        self.assertEqual(lint(s), [])
        want = {"travel": (KNOWN, "2026", "2026-03-15", "2027-03-14"), "hotel": (KNOWN, "2027", "2027-01-01", "2027-12-31"),
                "dining": (KNOWN, "2027-H1", "2027-01-01", "2027-06-30"), "ride": (KNOWN, "2027-03", "2027-03-01", "2027-03-31")}
        for benefit, period_ in want.items():
            c = row(s, benefit, "2027-03-10")
            self.assertEqual(span(c), period_, benefit)
            self.assertEqual(c["applies"]["status"], ESTABLISHED, benefit)
            self.assertEqual(c["personal"]["state"], NOT_RECORDED, benefit)          # the card offers it; nothing says it is unused
            self.assertFalse({"remaining", "used"} & set(c["personal"]), benefit)
        hotel = row(s, "hotel", "2027-03-10")
        self.assertEqual((hotel["allowance"]["amount"], hotel["allowance"]["unit"]), (500, "USD"))
        self.assertIn("not a personal balance", hotel["allowance"]["note"])
        self.assertEqual((hotel["terms"]["max_per_transaction"], hotel["terms"]["min_stay_nights"], hotel["terms"]["rollover"]), (250, 2, "none"))
        self.assertEqual(hotel["next"], {"date": "2028-01-01", "what": "new period, allowance resets", "unused": "unused allowance does not roll over"})
        self.assertEqual(row(s, "dining", "2027-03-10")["terms"]["per_calendar_year_at_most"], 300)      # two separate 150 periods
        self.assertIsNone(row(s, "plain", "2027-03-10"))                             # a benefit without credit terms is not a credit

    def test_resets_at_each_boundary(self):
        s = world()
        self.assertEqual(span(row(s, "travel", "2027-03-14"))[1:], ("2026", "2026-03-15", "2027-03-14"))
        self.assertEqual(span(row(s, "travel", "2027-03-15"))[1:], ("2027", "2027-03-15", "2028-03-14"))
        self.assertEqual(span(row(s, "dining", "2027-06-30"))[1], "2027-H1")
        self.assertEqual(span(row(s, "dining", "2027-07-01"))[1:], ("2027-H2", "2027-07-01", "2027-12-31"))
        self.assertEqual(span(row(s, "ride", "2027-03-31"))[1], "2027-03")
        self.assertEqual(span(row(s, "ride", "2027-04-01"))[1:], ("2027-04", "2027-04-01", "2027-04-30"))
        self.assertEqual(span(row(s, "hotel", "2027-12-31"))[1], "2027")
        self.assertEqual(span(row(s, "hotel", "2028-01-01"))[1], "2028")

    def test_expiration_of_the_offer(self):
        s = world()
        sep = row(s, "ride", "2027-09-15")
        self.assertEqual(span(sep), (KNOWN, "2027-09", "2027-09-01", "2027-09-30"))
        self.assertEqual(sep["next"]["what"], "offer ends")
        gone = row(s, "ride", "2027-10-01")
        self.assertEqual((gone["offer"]["state"], gone["period"]["state"], gone["applies"]["status"]), ("ENDED", "NO_OFFER", NOT_AVAILABLE))
        self.assertNotIn("allowance", gone)
        self.assertEqual(evaluate(s, "t", "2027-10-01").have("ride"), NOT_AVAILABLE)
        mid = world(rules=[credit_rule("r.hotel", "hotel", HOTEL, valid_to="2027-08-15")])       # a yearly credit withdrawn in mid-year
        cut = row(mid, "hotel", "2027-03-10")
        self.assertEqual((span(cut), cut["next"]["date"], cut["next"]["what"]), ((KNOWN, "2027", "2027-01-01", "2027-08-15"), "2027-08-16", "offer ends"))
        self.assertEqual(cut["allowance"]["amount"], 500)                                         # the published amount, not a pro-rated guess
        self.assertIn("not pro-rated", cut["allowance"]["note"])
        self.assertEqual([(e["date"], e["then"]) for e in credits.events(mid, "t", "2027-03-10", "2028-12-31")], [("2027-08-15", "the offer ends")])

    def test_two_cardholders_two_anniversaries(self):
        s = world([card("2025-03-15")])
        s.files["profiles/u/profile.json"] = {"id": "u", "label": "second person", "synthetic": True, "owner": "Second Owner"}
        s.files["profiles/u/holdings/%s.json" % ACCT] = dict(card("2024-11-02"), confirmed_by="Second Owner")
        self.assertEqual(lint(s), [])
        self.assertEqual(span(row(s, "travel", "2027-03-10"))[1:], ("2026", "2026-03-15", "2027-03-14"))
        self.assertEqual(span(row(s, "travel", "2027-03-10", profile="u"))[1:], ("2026", "2026-11-02", "2027-11-01"))
        self.assertEqual(span(row(s, "hotel", "2027-03-10")), span(row(s, "hotel", "2027-03-10", profile="u")))     # calendar credits agree

    def test_two_accounts_of_one_person_keep_their_own_periods_and_records(self):
        s = world([card("2025-03-15"), card("2024-11-02", hid="h-card-2")],
                  [rec("e1", "r.hotel", "2027", "2027-01-01", "2027-12-31", 500, usage=[use("u1", 200, "2027-02-01")])])
        self.assertEqual(span(row(s, "travel", "2027-03-10"))[2], "2026-03-15")
        self.assertEqual(span(row(s, "travel", "2027-03-10", account="h-card-2"))[2], "2026-11-02")
        self.assertEqual(row(s, "hotel", "2027-03-10")["personal"]["remaining"], 300)
        self.assertEqual(row(s, "hotel", "2027-03-10", account="h-card-2")["personal"]["state"], NOT_RECORDED)     # not shared between accounts

    def test_missing_opening_date_leaves_the_anniversary_unresolved(self):
        s = world([card(None, valid_from="2025-03-15")])
        c = row(s, "travel", "2027-03-10")
        self.assertEqual((c["period"]["state"], c["applies"]["status"]), (P_UNRESOLVED, ESTABLISHED))      # the benefit applies; the period is unknown
        self.assertNotIn("allowance", c)
        self.assertNotIn("next", c)
        self.assertEqual({f["code"] for f in credits.survey(s, "t", "2027-03-10")["flags"]}, {"CREDIT_PERIOD_UNRESOLVED"})   # fee credit: no use recorded
        self.assertEqual(span(row(s, "hotel", "2027-03-10"))[0], KNOWN)                                    # calendar credits do not need it

    def test_what_the_source_does_not_state_stays_unstated(self):
        s = world(rules=[credit_rule("r.travel", "travel", TRAVEL),
                         credit_rule("r.hotel", "hotel", dict(HOTEL, max_per_transaction="none", rollover="allowed", rollover_max="none"))])
        t = row(s, "travel", "2027-03-10")["terms"]
        for key in ("max_per_transaction", "min_stay_nights", "min_transaction", "rollover", "rollover_max"):
            self.assertIsNone(t[key], key)                                           # not 0, not "none", not unlimited
        self.assertEqual(row(s, "travel", "2027-03-10")["next"]["unused"], "the source does not say whether unused allowance rolls over")
        h = row(s, "hotel", "2027-03-10")["terms"]
        self.assertEqual((h["max_per_transaction"], h["rollover"], h["rollover_max"]), ("none", "allowed", "none"))   # stated as none: kept apart
        self.assertEqual(credits.unused_text({"rollover": "allowed", "unit": "USD"}), "unused allowance rolls over (the source does not state a maximum)")
        self.assertEqual(credits.unused_text({"rollover": "allowed", "rollover_max": 20, "unit": "USD"}), "unused allowance rolls over, up to 20 USD")

    def test_applies_follows_the_ordinary_conditions(self):
        self.assertEqual(credits.survey(world([]), "t", "2027-03-10")["accounts"], [])                     # no card: nothing
        other = world([holding("h-y", "card.y", valid_from="2025-01-01")])
        self.assertEqual(credits.survey(other, "t", "2027-03-10")["accounts"], [])                         # another card: nothing
        unconfirmed = world([card(state="unconfirmed")])
        c = row(unconfirmed, "hotel", "2027-03-10")
        self.assertEqual(c["applies"]["status"], UNRESOLVED)
        self.assertIn("whether it applies to this person is not established", c["allowance"]["note"])
        unverified = world(rules=[credit_rule("r.hotel", "hotel", HOTEL, status="unverified")])
        self.assertEqual(row(unverified, "hotel", "2027-03-10")["applies"]["status"], UNRESOLVED)
        ended = world([card(valid_to="2026-12-31")])
        self.assertEqual(credits.survey(ended, "t", "2027-03-10")["accounts"], [])

    def test_candidate_terms_are_shown_only_on_request_and_never_established(self):
        s = world(rules=[credit_rule("r.travel", "travel", TRAVEL)])
        s.files["data/candidates/c1.json"] = {"id": "c1", "status": "proposed", "created_on": "2026-11-15", "search_path": ["test"], "open_questions": [],
                                              "evidence": [{"id": "ev9", "url": "https://example.invalid/x", "title": "t", "publisher": "p",
                                                            "source_type": "synthetic", "retrieved_on": "2026-11-15", "summary": "s"}],
                                              "proposed_rule": {"id": "r.hotel", "kind": "grants", "output": "hotel", "when": H(CARD),
                                                                "summary": "proposed", "credit": dict(HOTEL)}}
        self.assertEqual(lint(s), [])
        self.assertIsNone(row(s, "hotel", "2027-03-10"))
        self.assertEqual([c["rule"] for c in credits.published(s, "2027-03-10")["credits"]], ["r.travel"])
        c = row(s, "hotel", "2027-03-10", include_candidates=True)
        self.assertEqual((c["rule_state"], c["candidate"], c["applies"]["status"]), ("candidate", "c1", UNRESOLVED))
        self.assertTrue(any("not promoted" in n for n in c["applies"]["needs"]))
        self.assertEqual([c["rule"] for c in credits.published(s, "2027-03-10", include_candidates=True)["credits"]], ["r.hotel", "r.travel"])

    def test_published_report_without_a_person(self):
        pub = {c["benefit"]: c for c in credits.published(world(), "2027-03-10")["credits"]}
        self.assertEqual(pub["hotel"]["period"]["label"], "2027")
        self.assertEqual(pub["travel"]["period"]["state"], P_UNRESOLVED)             # depends on each cardholder's account
        self.assertNotIn("personal", pub["hotel"])
        self.assertIsNone({c["benefit"]: c for c in credits.published(world(), "2027-10-05")["credits"]}["ride"]["period"])
        self.assertEqual(credits.published(world(), "2027-03-10", card="card.y")["credits"], [])


class TestElections(unittest.TestCase):
    """G: a credit subject to a cardholder election. ENG-02 still decides; credits never grant both sides."""
    RULES = [credit_rule("r.a", "perk.a", {"amount": 200, "unit": "USD", "cycle": "calendar_year"}),
             credit_rule("r.b", "perk.b", {"amount": 25, "unit": "USD", "cycle": "calendar_month", "rollover": "none"})]
    OPTS = [option("el.a", "r.a"), option("el.b", "r.b")]

    def statuses(self, s, day):
        return tuple(row(s, b, day)["applies"]["status"] for b in ("perk.a", "perk.b"))

    def test_no_election_no_credit_established(self):
        s = world(rules=self.RULES, options=self.OPTS)
        self.assertEqual(lint(s), [])
        self.assertEqual(self.statuses(s, "2027-03-10"), (UNRESOLVED, UNRESOLVED))
        a = row(s, "perk.a", "2027-03-10")
        self.assertEqual(a["applies"]["election"], {"group": "perk", "option": "el.a", "in_effect": False, "reason": "no election recorded"})
        self.assertTrue(any("no election recorded" in n for n in a["applies"]["needs"]))
        self.assertIn("not established", a["allowance"]["note"])

    def test_recorded_election_gives_one_credit_only(self):
        s = world([card(), holding("el", "el.a", valid_from="2026-01-01")], rules=self.RULES, options=self.OPTS)
        self.assertEqual(self.statuses(s, "2027-03-10"), (ESTABLISHED, NOT_AVAILABLE))
        b = row(s, "perk.b", "2027-03-10")
        self.assertNotIn("allowance", b)                                             # no allowance is published FOR THIS PERSON
        self.assertNotIn("next", b)
        self.assertFalse(b["applies"]["election"]["in_effect"])
        self.assertTrue(row(s, "perk.a", "2027-03-10")["applies"]["election"]["in_effect"])

    def test_conflicting_elections_establish_neither(self):
        s = world([card(), holding("e1", "el.a", valid_from="2026-01-01"), holding("e2", "el.b", valid_from="2026-06-01")],
                  rules=self.RULES, options=self.OPTS)
        self.assertEqual(self.statuses(s, "2027-03-10"), (UNRESOLVED, UNRESOLVED))
        for day in ("2026-03-01", "2026-12-01", "2027-03-10"):
            self.assertNotEqual(self.statuses(s, day), (ESTABLISHED, ESTABLISHED), day)

    def test_a_period_that_outlasts_the_election_is_called_out(self):
        opts = [option("el.a", "r.a", opened_before="2027-01-01", default_before_anniversary="2027-01-01", elect_before_anniversary="2027-01-01"),
                option("el.b", "r.b", starts_at_anniversary="2027-01-01")]
        s = world([card("2025-06-01")], rules=self.RULES, options=opts)              # legacy credit by default until 2027-06-01
        a = row(s, "perk.a", "2027-03-10")
        self.assertEqual((a["applies"]["status"], span(a)[3]), (ESTABLISHED, "2027-12-31"))
        self.assertTrue(any("2027-12-31" in n and "may be cut short" in n for n in a["applies"]["needs"]))
        self.assertEqual(self.statuses(s, "2027-06-01"), (UNRESOLVED, UNRESOLVED))


class TestPersonalRecords(unittest.TestCase):
    def hotel(self, usage=(), **kw):
        return world(records=[rec("e-hotel", "r.hotel", "2027", "2027-01-01", "2027-12-31", 500, usage=usage, **kw)])

    def numbers(self, s, day, benefit="hotel"):
        p = row(s, benefit, day)["personal"]
        return p["state"], p["allowance"], p["used"], p["possibly_used"], p["remaining"], p["remaining_at_least"], p["established"]

    def test_allowance_used_and_remaining_come_only_from_the_owners_record(self):
        s = self.hotel([use("u1", 250, "2027-02-10"), use("u2", 120, "2027-05-04")])
        self.assertEqual(lint(s), [])
        self.assertEqual(self.numbers(s, "2027-02-09"), ("ACTIVE", 500, 0, 0, 500, 500, True))       # a later use is not counted earlier
        self.assertEqual(self.numbers(s, "2027-02-10"), ("ACTIVE", 500, 250, 0, 250, 250, True))
        self.assertEqual(self.numbers(s, "2027-12-31"), ("ACTIVE", 500, 370, 0, 130, 130, True))
        self.assertEqual(credits.survey(s, "t", "2027-03-10")["flags"], [f for f in credits.survey(s, "t", "2027-03-10")["flags"]
                                                                        if f["code"] == "CREDIT_PERIOD_UNRESOLVED"])

    def test_a_record_for_one_period_says_nothing_about_the_next(self):
        s = world(records=[rec("e-h1", "r.dining", "2027-H1", "2027-01-01", "2027-06-30", 150, usage=[use("u1", 150, "2027-03-05")])])
        self.assertEqual(self.numbers(s, "2027-06-30", "dining")[:5], ("EXHAUSTED", 150, 150, 0, 0))
        self.assertEqual(row(s, "dining", "2027-07-01")["personal"]["state"], NOT_RECORDED)           # reset: published 150, personal unknown
        self.assertEqual(row(s, "dining", "2027-07-01")["allowance"]["amount"], 150)
        self.assertEqual(row(s, "hotel", "2027-03-10")["personal"]["state"], NOT_RECORDED)            # nor about another credit
        self.assertEqual(evaluate(s, "t", "2027-06-30").have("dining"), ESTABLISHED)                  # the benefit is held; this period is used up

    def test_unconfirmed_use_is_a_range_and_not_established(self):
        s = self.hotel([use("u1", 250, "2027-02-10"), use("u2", 180, "2027-06-20", state="unconfirmed")])
        self.assertEqual(self.numbers(s, "2027-07-01"), ("ACTIVE", 500, 250, 180, 250, 70, False))
        self.assertIn("CREDIT_USE_UNCONFIRMED", {f["code"] for f in credits.survey(s, "t", "2027-07-01")["flags"]})

    def test_unconfirmed_record_is_not_a_balance(self):
        s = self.hotel(state="unconfirmed")
        p = row(s, "hotel", "2027-03-10")["personal"]
        self.assertEqual((p["state"], p["established"]), ("UNRESOLVED", False))
        self.assertIn("UNCONFIRMED_ENTITLEMENT", {f["code"] for f in credits.survey(s, "t", "2027-03-10")["flags"]})

    def test_two_records_for_one_period_report_no_balance(self):
        s = world(records=[rec("e1", "r.hotel", "2027", "2027-01-01", "2027-12-31", 500), rec("e2", "r.hotel", "2027", "2027-01-01", "2027-12-31", 400)])
        self.assertIn("CONFLICTING_ENTITLEMENTS", codes(lint(s)))
        p = row(s, "hotel", "2027-03-10")["personal"]
        self.assertEqual(p["state"], "UNRESOLVED")
        self.assertNotIn("remaining", p)
        self.assertIn("CONFLICTING_ENTITLEMENTS", {f["code"] for f in credits.survey(s, "t", "2027-03-10")["flags"]})

    def test_account_figures_that_differ_from_the_published_terms_are_shown(self):
        s = world(records=[rec("e1", "r.hotel", "2027", "2027-01-05", "2027-12-31", 450)])
        got = {f["code"] for f in credits.survey(s, "t", "2027-03-10")["flags"]}
        self.assertLessEqual({"ALLOWANCE_DIFFERS_FROM_RULE", "PERIOD_DIFFERS_FROM_RULE"}, got)
        self.assertEqual(row(s, "hotel", "2027-03-10")["personal"]["remaining"], 450)                 # the account's figure is the personal one
        self.assertEqual(row(s, "hotel", "2027-03-10")["allowance"]["amount"], 500)                   # the published one is untouched

    def test_use_above_the_per_transaction_cap_is_flagged(self):
        s = self.hotel([use("u1", 300, "2027-02-10")])
        self.assertIn("USE_OVER_TRANSACTION_CAP", codes(lint(s)))
        self.assertIn("USE_OVER_TRANSACTION_CAP", {f["code"] for f in credits.survey(s, "t", "2027-03-10")["flags"]})

    def test_personal_records_never_grant_the_benefit(self):
        s = world([card(), holding("el", "el.a", valid_from="2026-01-01")], rules=TestElections.RULES, options=TestElections.OPTS,
                  records=[rec("e1", "r.b", "2027-03", "2027-03-01", "2027-03-31", 25)])                 # a record for the option NOT elected
        r = evaluate(s, "t", "2027-03-10")
        self.assertEqual((r.have("perk.a"), r.have("perk.b")), (ESTABLISHED, NOT_AVAILABLE))          # the election decides, not the record
        self.assertNotIn("earned_entitlements", r.report())                                            # and it is not an earned benefit

    def test_period_counted_from_the_last_use(self):
        s = world(records=[rec("e-fee", "r.fee", "2025", "2025-09-10", "2029-09-09", 120, usage=[use("u1", 120, "2025-09-10")])])
        self.assertEqual(lint(s), [])
        c = row(s, "fee", "2027-03-10")
        self.assertEqual(span(c), (KNOWN, "2025", "2025-09-10", "2029-09-09"))
        self.assertEqual((c["personal"]["state"], c["personal"]["remaining"]), ("EXHAUSTED", 0))
        again = row(s, "fee", "2029-09-10")
        self.assertEqual((again["period"]["start"], again["period"]["end"], again["personal"]["state"]), ("2029-09-10", None, NOT_RECORDED))
        self.assertEqual(again["allowance"]["amount"], 120)
        self.assertEqual(row(world(), "fee", "2027-03-10")["period"]["state"], P_UNRESOLVED)

    def test_record_found_by_its_own_dates_when_the_period_cannot_be_computed(self):
        s = world([card(None, valid_from="2025-03-15")], [rec("e1", "r.travel", "2026", "2026-03-15", "2027-03-14", 300, usage=[use("u1", 100, "2026-08-01")])])
        c = row(s, "travel", "2027-03-10")
        self.assertEqual((c["period"]["state"], c["personal"]["record"], c["personal"]["remaining"]), (P_UNRESOLVED, "e1", 200))
        self.assertEqual(row(s, "travel", "2027-03-15")["personal"]["state"], NOT_RECORDED)


class TestCalendarAhead(unittest.TestCase):
    def test_period_ends_are_listed_on_their_last_day(self):
        s = world()
        ev = credits.events(s, "t", "2027-03-10", "2027-07-31")
        got = [(e["date"], e["benefit"], e["period"]) for e in ev]
        self.assertEqual(got, [("2027-03-14", "travel", "2026"), ("2027-03-31", "ride", "2027-03"), ("2027-04-30", "ride", "2027-04"),
                               ("2027-05-31", "ride", "2027-05"), ("2027-06-30", "dining", "2027-H1"), ("2027-06-30", "ride", "2027-06"),
                               ("2027-07-31", "ride", "2027-07")])
        h1 = next(e for e in ev if e["benefit"] == "dining")
        self.assertEqual((h1["amount"], h1["unused"], h1["then"]), (150, "unused allowance does not roll over", "a new period starts on 2027-07-01"))
        last = credits.events(s, "t", "2027-09-01", "2027-12-31")
        self.assertEqual([(e["date"], e["then"]) for e in last if e["benefit"] == "ride"], [("2027-09-30", "the offer ends")])
        self.assertEqual([e["date"] for e in last if e["benefit"] == "hotel"], ["2027-12-31"])

    def test_only_credits_that_apply_and_only_computable_periods(self):
        s = world([card(None, valid_from="2025-03-15"), holding("el", "el.a", valid_from="2026-01-01")],
                  rules=TestElections.RULES + [credit_rule("r.travel", "travel", TRAVEL)], options=TestElections.OPTS)
        got = {e["benefit"] for e in credits.events(s, "t", "2027-01-01", "2027-12-31")}
        self.assertEqual(got, {"perk.a"})                        # not the unelected monthly credit; not the undatable anniversary credit

    def test_review_and_timeline_surface_them_only_when_there_are_any(self):
        s = world()
        r = review(s, "t", "2027-06-01", "2027-07-01")
        self.assertEqual([(c["date"], c["benefit"]) for c in r["credit_periods"]], [("2027-06-30", "dining"), ("2027-06-30", "ride")])
        days = {e["date"]: e for e in timeline(s, "t", "2027-06-01", "2027-07-01")}
        self.assertEqual([c["benefit"] for c in days["2027-06-30"]["credit_periods"]], ["dining", "ride"])
        plain = world(rules=[rule("r.plain", "grants", "plain", H(CARD))])
        self.assertNotIn("credit_periods", review(plain, "t", "2027-06-01", "2027-07-01"))
        self.assertEqual(timeline(plain, "t", "2027-06-01", "2027-07-01"), [])


class TestStructure(unittest.TestCase):
    def issues(self, **kw):
        return codes(lint(world(**kw)))

    def test_credit_block_shape(self):
        bad = [dict(HOTEL, amount=0), dict(HOTEL, amount=-5), dict(HOTEL, years=4), dict(HOTEL, anchor="last_use"),
               {"amount": 120, "unit": "USD", "cycle": "multi_year"}, {"amount": 120, "unit": "USD", "cycle": "multi_year", "years": 1},
               dict(HOTEL, max_per_transaction=0), dict(HOTEL, min_stay_nights=0), dict(HOTEL, min_transaction=-1),
               dict(HOTEL, rollover_max=50), dict(HOTEL, rollover="none", rollover_max="none")]
        for block in bad:
            self.assertIn("BAD_CREDIT_SHAPE", self.issues(rules=[credit_rule("r.hotel", "hotel", block)]), block)
        for block in (dict(HOTEL, cycle="weekly"), dict(HOTEL, rollover="maybe"), dict(HOTEL, max_per_transaction="unlimited"),
                      dict(HOTEL, amount="500"), dict(HOTEL, surprise=1), {"unit": "USD", "cycle": "calendar_year"}, dict(HOTEL, anchor="calendar")):
            self.assertIn("SCHEMA", self.issues(rules=[credit_rule("r.hotel", "hotel", block)]), block)
        for block in (HOTEL, DINING, RIDE, TRAVEL, FEE, dict(HOTEL, max_per_transaction="none"), dict(HOTEL, rollover="allowed", rollover_max="none")):
            self.assertEqual(self.issues(rules=[credit_rule("r.hotel", "hotel", block)]), set(), block)

    def test_credit_terms_belong_on_a_card_benefit_rule(self):
        self.assertIn("UNEXPECTED_FIELD", self.issues(rules=[rule("r.x", "excludes", "hotel", H(CARD), credit=dict(HOTEL))]))
        two = rule("r.x", "grants", "hotel", {"all": [H(CARD), H("plain")]}, credit=dict(HOTEL))
        self.assertIn("BAD_CREDIT_SHAPE", self.issues(rules=[two, rule("r.plain", "grants", "plain", H(CARD))]))
        self.assertIn("BAD_CREDIT_SHAPE", self.issues(rules=[rule("r.x", "grants", "hotel", H("plain"), credit=dict(HOTEL)),
                                                             rule("r.plain", "grants", "plain", H(CARD))]))

    def test_personal_period_records_are_checked(self):
        ok = rec("e1", "r.dining", "2027-H1", "2027-01-01", "2027-06-30", 150)

        def broken(**change):
            return codes(lint(world(records=[dict(ok, **change)])))
        self.assertEqual(broken(), set())
        self.assertIn("BAD_PERIOD", broken(cycle="2027"))                                   # a half-year credit has half-year periods
        self.assertIn("BAD_PERIOD", broken(cycle="2027-07"))
        self.assertIn("BAD_DATES", broken(effective_from="2027-07-01", expires_on="2027-12-31"))   # does not overlap 2027-H1
        self.assertIn("MISSING_ALLOWANCE", codes(lint(world(records=[{k: v for k, v in ok.items() if k != "allowance"}]))))
        self.assertIn("BAD_ALLOWANCE", broken(allowance={"amount": 150, "unit": "points"}))
        self.assertIn("UNATTESTED_CONFIRMATION", broken(confirmed_by="A maintainer"))
        self.assertIn("UNKNOWN_ACCOUNT", broken(account="h-someone-elses"))
        self.assertIn("UNKNOWN_REFERENCE", broken(rule="r.plain"))                          # no credit terms: nothing to keep a balance of
        self.assertIn("OUT_OF_TERM", broken(usage=[use("u1", 10, "2027-07-02")]))
        self.assertIn("OVER_CONSUMED", broken(usage=[use("u1", 100, "2027-02-01"), use("u2", 100, "2027-03-01")]))
        year = rec("e2", "r.travel", "2027", "2026-03-15", "2027-03-14", 300)               # labelled with the wrong starting year
        self.assertIn("BAD_DATES", codes(lint(world(records=[year]))))
        other = world([card(), holding("h-y", "card.y", valid_from="2025-01-01")], [dict(ok, account="h-y")])
        self.assertIn("ACCOUNT_MISMATCH", codes(lint(other)))


class TestNoCreditTermsNoChange(unittest.TestCase):
    def test_a_store_without_credit_terms_behaves_as_before(self):
        plain = [rule("r.travel", "grants", "travel", H(CARD)), rule("r.plain", "grants", "plain", H(CARD))]
        s = world(rules=plain)
        self.assertEqual(credits.survey(s, "t", "2027-03-10")["accounts"], [])
        self.assertEqual(credits.published(s, "2027-03-10")["credits"], [])
        self.assertEqual(credits.events(s, "t", "2027-01-01", "2028-01-01"), [])
        self.assertEqual(set(review(s, "t", "2027-01-01", "2028-01-01")), {"profile", "from", "to", "changes", "new_flags", "downstream_review"})

    def test_adding_terms_changes_no_engine_answer(self):
        before = evaluate(world(rules=[rule("r.hotel", "grants", "hotel", H(CARD)), rule("r.travel", "grants", "travel", H(CARD))]), "t", "2027-03-10").report()
        after = evaluate(world(rules=[credit_rule("r.hotel", "hotel", HOTEL), credit_rule("r.travel", "travel", TRAVEL)]), "t", "2027-03-10").report()
        self.assertEqual(before, after)                           # terms describe the credit; they grant and withhold nothing


if __name__ == "__main__":
    unittest.main()
