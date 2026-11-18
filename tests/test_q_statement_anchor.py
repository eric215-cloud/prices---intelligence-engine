"""DEP-01: the statement-cycle anniversary anchor (cycle `anniversary_statement_year`). All data here is invented.

Rule under test, from the issuer's published wording for the Sapphire Reserve travel credit: an anniversary year runs
from the account open date through the first statement date after the account-open anniversary, and each 12 monthly
billing cycles thereafter. The statement closing date is a profile fact. Without it the period is UNRESOLVED: no
closing date is inferred, and a missing date never yields an allowance. The calendar `anniversary_year` is unchanged.
"""
import datetime
import json
import os
import unittest

from test_o_credits import ACCT, CARD, OWNER, TRAVEL, card, credit_rule, rec, row, world
from prices import credits
from prices.credits import BEFORE_ACCOUNT, KNOWN, NOT_RECORDED, UNRESOLVED, period, statement_year
from prices.lint import lint

D = datetime.date
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BILLING = {"amount": 300, "unit": "USD", "cycle": "anniversary_statement_year"}


def acct(opened="2025-03-10", **facts):
    return dict({"id": "h", "opened_on": opened}, **facts)


def span(p):
    return (p["state"], p.get("label"), p.get("start"), p.get("end"))


# ================================================================================== (a) computed from a known closing date
class TestAnchorFromAKnownClosingDate(unittest.TestCase):
    def test_first_year_runs_to_the_first_closing_after_the_anniversary(self):
        h = acct(statement_closing_day=22)                   # opened Mar 10; anniversary Mar 10, 2026; closes on the 22nd
        self.assertEqual(span(period(BILLING, D(2025, 3, 10), h)), (KNOWN, "2025", D(2025, 3, 10), D(2026, 3, 22)))
        self.assertEqual(span(period(BILLING, D(2026, 3, 22), h)), (KNOWN, "2025", D(2025, 3, 10), D(2026, 3, 22)))   # 12 days past the anniversary
        self.assertEqual(span(period(BILLING, D(2026, 3, 23), h)), (KNOWN, "2026", D(2026, 3, 23), D(2027, 3, 22)))
        self.assertEqual(span(period(BILLING, D(2028, 1, 5), h)), (KNOWN, "2027", D(2027, 3, 23), D(2028, 3, 22)))
        self.assertEqual(period(BILLING, D(2025, 3, 9), h)["state"], BEFORE_ACCOUNT)

    def test_a_closing_before_the_anniversary_in_that_month_moves_to_the_next_month(self):
        h = acct(opened="2025-03-25", statement_closing_day=22)
        self.assertEqual(span(period(BILLING, D(2026, 4, 1), h)), (KNOWN, "2025", D(2025, 3, 25), D(2026, 4, 22)))
        self.assertEqual(span(period(BILLING, D(2026, 4, 23), h)), (KNOWN, "2026", D(2026, 4, 23), D(2027, 4, 22)))

    def test_years_follow_each_other_without_gap_or_overlap(self):
        h = acct(statement_closing_day=5)
        prev = None
        d = D(2025, 3, 10)
        while d < D(2031, 1, 1):
            p = period(BILLING, d, h)
            self.assertEqual(p["state"], KNOWN, d)
            if prev and p["label"] != prev["label"]:
                self.assertEqual(p["start"], prev["end"] + datetime.timedelta(days=1))
                self.assertEqual(int(p["label"]), int(prev["label"]) + 1)
            prev = p
            d += datetime.timedelta(days=11)

    def test_recorded_statement_dates_win_over_the_closing_day(self):
        h = acct(statement_closing_day=22, statement_closings=["2026-03-21", "2027-03-23"])    # the issuer moved two closings
        self.assertEqual(span(period(BILLING, D(2026, 3, 22), h)), (KNOWN, "2026", D(2026, 3, 22), D(2027, 3, 23)))
        self.assertNotIn("note", period(BILLING, D(2026, 3, 22), h))                           # both ends recorded
        self.assertIn("computed from the recorded closing day", period(BILLING, D(2027, 6, 1), h)["note"])  # 2028 end is derived, and says so

    def test_recorded_statement_dates_alone_are_enough_where_they_reach(self):
        h = acct(statement_closings=["2026-03-22", "2027-03-22"])
        self.assertEqual(span(period(BILLING, D(2026, 6, 1), h)), (KNOWN, "2026", D(2026, 3, 23), D(2027, 3, 22)))
        self.assertEqual(period(BILLING, D(2027, 6, 1), h)["state"], UNRESOLVED)               # March 2028 not recorded: not extrapolated

    def test_survey_reports_the_billing_year_and_never_a_balance_from_the_terms(self):
        s = world([card(opened="2025-03-10", statement_closing_day=22)], rules=[credit_rule("r.travel", "travel", BILLING)])
        c = row(s, "travel", "2026-03-15")
        self.assertEqual((c["period"]["state"], c["period"]["label"], c["period"]["end"]), (KNOWN, "2025", "2026-03-22"))
        self.assertEqual(c["personal"]["state"], NOT_RECORDED)                                 # no record: not "unused"
        s2 = world([card(opened="2025-03-10", statement_closing_day=22)], rules=[credit_rule("r.travel", "travel", BILLING)],
                   records=[rec("e1", "r.travel", "2025", "2025-03-10", "2026-03-22", 300)])
        self.assertEqual(row(s2, "travel", "2026-03-15")["personal"]["allowance"], 300)        # only from the owner's record


# ======================================================================================== (b) unknown closing -> unresolved
class TestUnknownClosingDateIsUnresolved(unittest.TestCase):
    def test_no_closing_date_recorded(self):
        p = period(BILLING, D(2026, 6, 1), acct())
        self.assertEqual(p["state"], UNRESOLVED)
        self.assertIn("statement closing date of account h is not recorded", p["reason"])
        self.assertNotIn("start", p)
        self.assertEqual(period(BILLING, D(2026, 6, 1))["state"], UNRESOLVED)                  # no person: depends on the account

    def test_no_opening_date(self):
        p = period(BILLING, D(2026, 6, 1), {"id": "h", "statement_closing_day": 22, "valid_from": "2025-03-10"})
        self.assertEqual(p["state"], UNRESOLVED)
        self.assertIn("opening date", p["reason"])

    def test_a_closing_day_the_month_lacks_is_not_guessed(self):
        h = acct(opened="2025-02-10", statement_closing_day=30)                                # anniversary in February: no 30th
        p = period(BILLING, D(2025, 6, 1), h)
        self.assertEqual(p["state"], UNRESOLVED)
        self.assertIn("does not exist in February 2026", p["reason"])
        h["statement_closings"] = ["2026-02-28"]                                               # the actual statement settles it
        self.assertEqual(span(period(BILLING, D(2025, 6, 1), h)), (KNOWN, "2025", D(2025, 2, 10), D(2026, 2, 28)))

    def test_a_closing_on_the_anniversary_itself_is_not_settled(self):
        p = period(BILLING, D(2025, 5, 1), acct(opened="2025-03-22", statement_closing_day=22))
        self.assertEqual(p["state"], UNRESOLVED)
        self.assertIn("the opening anniversary itself", p["reason"])

    def test_a_february_29_opening(self):
        h = acct(opened="2024-02-29", statement_closing_day=28)                                # 2025 anniversary: Feb 28 or Mar 1
        self.assertEqual(period(BILLING, D(2024, 6, 1), h)["state"], UNRESOLVED)
        h2 = acct(opened="2024-02-29", statement_closing_day=10)
        self.assertEqual(span(period(BILLING, D(2024, 6, 1), h2)), (KNOWN, "2024", D(2024, 2, 29), D(2025, 3, 10)))

    def test_two_recorded_closings_in_one_month(self):
        h = acct(statement_closings=["2026-03-20", "2026-03-22"])
        self.assertEqual(period(BILLING, D(2025, 6, 1), h)["state"], UNRESOLVED)
        self.assertIn("BAD_DATA", {i[1] for i in lint(world([card(opened="2025-03-10", statement_closings=["2026-03-20", "2026-03-22"])]))})

    def test_missing_closing_date_never_yields_spendable_value(self):
        s = world([card(opened="2025-03-10")], rules=[credit_rule("r.travel", "travel", BILLING)])
        c = row(s, "travel", "2026-03-15")
        self.assertEqual(c["period"]["state"], UNRESOLVED)
        self.assertEqual(c["personal"]["state"], NOT_RECORDED)
        self.assertNotIn("allowance", c["personal"])
        self.assertIn("CREDIT_PERIOD_UNRESOLVED", {f["code"] for f in credits.survey(s, "t", "2026-03-15")["flags"]})
        self.assertEqual([e for e in credits.events(s, "t", "2026-01-01", "2027-12-31") if e["benefit"] == "travel"], [])


class TestClosingFactsAreChecked(unittest.TestCase):
    def test_lint(self):
        self.assertEqual({i[1] for i in lint(world([card(statement_closing_day=22)])) if i[0] == "ERROR"}, set())
        for bad, code in ((dict(statement_closing_day=0), "BAD_DATA"), (dict(statement_closing_day=32), "BAD_DATA"),
                          (dict(statement_closings=["2024-01-05"]), "BAD_DATES"), (dict(statement_closing_day="22"), "SCHEMA")):
            with self.subTest(bad):
                self.assertIn(code, {i[1] for i in lint(world([card(**bad)]))})


# ================================================================================ (c) the calendar anniversary is unchanged
class TestCalendarAnniversaryUnchanged(unittest.TestCase):
    def test_anniversary_year_ignores_statement_facts(self):
        for h in ({"id": "h", "opened_on": "2025-03-15"}, {"id": "h", "opened_on": "2025-03-15", "statement_closing_day": 22,
                                                           "statement_closings": ["2026-03-21"]}):
            for day, want in ((D(2025, 3, 15), ("2025", D(2025, 3, 15), D(2026, 3, 14))), (D(2026, 3, 15), ("2026", D(2026, 3, 15), D(2027, 3, 14)))):
                self.assertEqual(span(period(TRAVEL, day, h)), (KNOWN,) + want)
        self.assertEqual(period(TRAVEL, D(2027, 2, 28), {"id": "h", "opened_on": "2024-02-29"})["state"], UNRESOLVED)

    def test_the_two_cycles_differ_and_say_so(self):
        h = {"id": "h", "opened_on": "2025-03-10", "statement_closing_day": 22}
        self.assertNotEqual(period(TRAVEL, D(2026, 3, 15), h)["label"], period(BILLING, D(2026, 3, 15), h)["label"])
        self.assertIn("card-anniversary year", credits.cycle_text(TRAVEL))
        self.assertIn("billing", credits.cycle_text(BILLING))
        self.assertEqual(statement_year(h, D(2026, 3, 15))["end"], D(2026, 3, 22))


# ============================================================================ (d) the $300 Sapphire Reserve credit stays deferred
class TestSapphireReserveTravelCreditStaysDeferred(unittest.TestCase):
    def test_no_structured_credit_block_is_attached(self):
        with open(os.path.join(ROOT, "data", "candidates", "c-cb.csr.annual-travel-credit-300.json"), encoding="utf-8") as f:
            cand = json.load(f)
        self.assertEqual(cand["status"], "proposed")
        self.assertNotIn("credit", cand["proposed_rule"])
        rules_dir = os.path.join(ROOT, "data", "kb", "rules")
        for name in os.listdir(rules_dir):
            with open(os.path.join(rules_dir, name), encoding="utf-8") as f:
                r = json.load(f)
            self.assertFalse(r.get("output") == "benefit.csr.annual-travel-credit-300" and "credit" in r, name)
        with open(os.path.join(ROOT, "tables", "credits.csv"), encoding="utf-8") as f:
            self.assertNotIn("annual-travel-credit-300", f.read())


if __name__ == "__main__":
    unittest.main()
