"""The first capabilities built for the foundation viability experiment, on invented data only.

    unchecked   a condition on WHO has a benefit that the rule's `when` does not check. Prose is not enforcement:
                nothing is ever established through such a rule. (CHANGED 2026-11-17, safety correction: this was a
                list field on the rule. It is now a class a reviewer records for the restriction, prices/conditions.py;
                the expectations below are the same, and tests/test_t_safety.py goes further.)
    earnings    points for a purchase from published per-dollar rates (prices/calc.py)
    convert     points after a transfer from a recorded ratio

Every card, rate, ratio and person below is invented.
"""
import copy
import unittest

from util import H, TEST_VOCAB, ent, ev, holding, make_store, review, rule
from prices.calc import convert_quote, earn_quote, lineage, narrower, parse_ratio
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint

DAY = "2026-06-01"
VOCAB = dict(copy.deepcopy(TEST_VOCAB), spend_categories={
    "other": {"name": "everything else"}, "dining": {"name": "dining"}, "travel": {"name": "travel"},
    "portal": {"name": "issuer portal", "parent": "travel"}, "portal-hotels": {"name": "hotels in the portal", "parent": "portal"},
    "portal-flights": {"name": "flights in the portal", "parent": "portal"}, "fuel": {"name": "fuel"}})
ENTS = [ent("card.a", "card"), ent("card.b", "card"), ent("pts.a", "currency"), ent("pts.b", "currency"), ent("miles.x", "currency"),
        ent("miles.y", "currency"), ent("b.earn", "benefit"), ent("b.promo", "benefit"), ent("b.earn-b", "benefit"), ent("b.offer", "benefit"),
        ent("b.plain", "benefit"), ent("st.gold", "status"), ent("act.enrol", "action", how="enrol online")]


def earning(*rates, currency="pts.a"):
    return {"currency": currency, "rates": [{"category": c, "per_usd": n} for c, n in rates]}


def world(rules, holdings, **kw):
    return make_store(ENTS, rules, holdings, vocab=VOCAB, **kw)


def codes(issues, level="ERROR"):
    return {i[1] for i in issues if i[0] == level}


class TestUncheckedConditions(unittest.TestCase):
    RULE = dict(restrictions=["Book through the portal", "New applicants only"],
                condition_review=review(("Book through the portal", "usage"), ("New applicants only", "unchecked")))

    def test_prose_condition_blocks_establishment(self):
        s = world([rule("r.offer", "grants", "b.offer", H("card.a"), **self.RULE),
                   rule("r.plain", "grants", "b.plain", H("card.a"), restrictions=["Book through the portal"])], [holding("h1", "card.a")])
        r = evaluate(s, "t", DAY)
        self.assertEqual(r.have("b.offer"), UNRESOLVED)
        self.assertEqual(r.have("b.plain"), ESTABLISHED)                    # usage terms alone never block
        self.assertTrue(any("New applicants only" in u for u in r.tokens("have:b.offer")["unknowns"]))
        self.assertNotIn("b.offer", [x["entity"] for x in r.report()["derived_entitlements"]])
        self.assertIn("b.offer", [x["entity"] for x in r.report()["unresolved"]])

    def test_it_does_not_leak_downstream(self):
        s = world([rule("r.offer", "grants", "b.offer", H("card.a"), **self.RULE), rule("r.gold", "grants", "st.gold", H("b.offer"))],
                  [holding("h1", "card.a")])
        self.assertEqual(evaluate(s, "t", DAY).have("st.gold"), UNRESOLVED)

    def test_another_checked_route_can_still_establish(self):
        s = world([rule("r.offer", "grants", "b.offer", H("card.a"), **self.RULE), rule("r.other", "grants", "b.offer", H("card.b"))],
                  [holding("h1", "card.a"), holding("h2", "card.b")])
        self.assertEqual(evaluate(s, "t", DAY).have("b.offer"), ESTABLISHED)

    def test_an_action_does_not_satisfy_it(self):
        acq = rule("r.gold", "acquire", "st.gold", {"all": [H("card.a"), H("act.enrol")]}, restrictions=["Primary cardholder only"],
                   condition_review=review(("Primary cardholder only", "unchecked")), retention={"mode": "unknown"})
        s = world([acq], [holding("h1", "card.a")])
        self.assertEqual(evaluate(s, "t", DAY).have("st.gold"), UNRESOLVED)   # classed as a usage term this would be CONDITIONAL
        acq2 = dict(acq, condition_review=review(("Primary cardholder only", "usage")))
        self.assertEqual(evaluate(world([acq2], [holding("h1", "card.a")]), "t", DAY).have("st.gold"), CONDITIONAL)

    def test_not_holding_the_card_is_still_not_available(self):
        s = world([rule("r.offer", "grants", "b.offer", H("card.a"), **self.RULE)], [])
        self.assertEqual(evaluate(s, "t", DAY).have("b.offer"), NOT_AVAILABLE)

    def test_a_class_that_claims_a_check_the_rule_does_not_have_is_an_error(self):
        s = world([rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=["New applicants only"],
                        condition_review=review(("New applicants only", "enforced", [{"holds": "act.enrol"}])))], [])
        self.assertIn("BAD_CLASSIFICATION", codes(lint(s)))


class TestEarnings(unittest.TestCase):
    BASE = rule("r.earn", "grants", "b.earn", H("card.a"), restrictions=["Excludes fees"],
                earning=earning(("portal", 5), ("dining", 3), ("other", 1)))

    def one(self, s, category, amount=100, day=DAY, **kw):
        out = earn_quote(s, "t", day, category, amount, **kw)["answers"]
        self.assertEqual(len(out), 1, out)
        return out[0]

    def test_exact_broader_and_catch_all(self):
        s = world([self.BASE], [holding("h1", "card.a")])
        a = self.one(s, "dining", 250)
        self.assertEqual((a["result"], a["points"], a["currency"], a["arithmetic"]), ("CALCULATED", 750, "pts.a", "250 x 3"))
        self.assertEqual(a["terms_not_evaluated"], ["Excludes fees"])
        self.assertEqual(a["basis"]["rule"], "r.earn")
        b = self.one(s, "portal-hotels")                                       # the portal rate covers hotels booked in it
        self.assertEqual((b["points"], b["category_used"]), (500, "portal"))
        c = self.one(s, "fuel")                                                # nothing published for fuel: the catch-all, and it says so
        self.assertEqual((c["points"], c["category_used"]), (100, "other"))
        self.assertIn("catch-all", c["assumptions"][0])

    def test_too_broad_a_question_is_not_answered_with_the_catch_all(self):
        s = world([self.BASE], [holding("h1", "card.a")])
        a = self.one(s, "travel")                                              # the card has 5 for the portal and 1 otherwise
        self.assertEqual(a["result"], "NOT_CALCULATED")
        self.assertIn("too broad", a["reason"])

    def test_no_rate_at_all_is_not_calculated(self):
        r = rule("r.earn", "grants", "b.earn", H("card.a"), earning=earning(("dining", 3)))
        a = self.one(world([r], [holding("h1", "card.a")]), "fuel")
        self.assertEqual(a["result"], "NOT_CALCULATED")
        self.assertIn("no published rate", a["reason"])

    def test_rates_are_never_added(self):
        promo = rule("r.promo", "grants", "b.promo", H("card.a"), valid_to="2026-12-31", earning=earning(("dining", 5)))
        s = world([self.BASE, promo], [holding("h1", "card.a")])
        a = self.one(s, "dining")
        self.assertEqual(a["points"], 500)                                     # the higher published total, not 3 + 5
        self.assertTrue(any("not added" in n for n in a["assumptions"]))
        self.assertEqual(self.one(s, "dining", day="2027-01-01")["points"], 300)   # the promotion has ended

    def test_only_what_is_established_for_the_person_is_used(self):
        unconfirmed = world([self.BASE], [holding("h1", "card.a", "unconfirmed")])
        self.assertEqual(self.one(unconfirmed, "dining")["result"], "NOT_CALCULATED")
        self.assertEqual(earn_quote(world([self.BASE], []), "t", DAY, "dining", 100)["answers"], [])       # no card, no answer
        unverified = dict(self.BASE, verification={"status": "unverified"})
        a = self.one(world([unverified], [holding("h1", "card.a")]), "dining")
        self.assertEqual(a["result"], "NOT_CALCULATED")
        gated = dict(self.BASE, restrictions=["Excludes fees", "Enrolment required"],
                     condition_review=review(("Excludes fees", "usage"), ("Enrolment required", "unchecked")))
        a = self.one(world([gated], [holding("h1", "card.a")]), "dining")
        self.assertEqual(a["result"], "NOT_CALCULATED")
        self.assertIn("Enrolment required", a["reason"])

    def test_one_answer_per_card_and_a_stale_rule_says_so(self):
        b = rule("r.earn-b", "grants", "b.earn-b", H("card.b"), review_by="2026-03-01", earning=earning(("dining", 4), currency="pts.b"))
        s = world([self.BASE, b], [holding("h1", "card.a"), holding("h2", "card.b")])
        out = {a["card"]: a for a in earn_quote(s, "t", DAY, "dining", 100)["answers"]}
        self.assertEqual((out["card.a"]["points"], out["card.b"]["points"], out["card.b"]["currency"]), (300, 400, "pts.b"))
        self.assertTrue(out["card.b"]["stale"] and not out["card.a"]["stale"])
        self.assertEqual([a["card"] for a in earn_quote(s, "t", DAY, "dining", 100, card="card.b")["answers"]], ["card.b"])

    def test_bad_questions_are_refused(self):
        s = world([self.BASE], [holding("h1", "card.a")])
        for category, amount in (("groceries", 100), ("dining", 0), ("dining", -5)):
            with self.assertRaises(KeyError):
                earn_quote(s, "t", DAY, category, amount)

    def test_definition_checks(self):
        ok = world([self.BASE], [])
        self.assertEqual(codes(lint(ok)), set())
        bad = lambda **kw: codes(lint(world([dict(self.BASE, **kw)], [])))        # noqa: E731
        self.assertIn("UNKNOWN_CATEGORY", bad(earning=earning(("groceries", 2))))
        self.assertIn("BAD_EARNING_SHAPE", bad(earning=earning(("dining", 0))))
        self.assertIn("BAD_EARNING_SHAPE", bad(earning=earning(("dining", 3), ("dining", 4))))
        self.assertIn("BAD_EARNING_SHAPE", bad(earning=earning(("dining", 3), currency="st.gold")))
        self.assertIn("BAD_EARNING_SHAPE", bad(when=H("pts.a")))                                   # not a rule about one card
        self.assertIn("BAD_EARNING_SHAPE", bad(kind="transfer", transfer={"from": "pts.a"}, output="miles.x"))

    def test_category_tree(self):
        cats = VOCAB["spend_categories"]
        self.assertEqual(lineage("portal-hotels", cats), ["portal-hotels", "portal", "travel"])
        self.assertEqual(narrower("travel", cats), ["portal", "portal-flights", "portal-hotels"])


class TestConvert(unittest.TestCase):
    def rules(self, **kw):
        return [rule("t.x", "transfer", "miles.x", H("pts.a"), transfer={"from": "pts.a", "ratio": "2:1.5", "note": "Minimum 1,000"},
                     restrictions=["Names must match"], open_questions=["Increment not verified"], **kw),
                rule("t.y", "transfer", "miles.y", {"all": [H("card.a"), H("pts.a")]}, transfer={"from": "pts.a"})]

    def test_ratio_arithmetic_and_its_caveats(self):
        s = world(self.rules(), [holding("h1", "pts.a", quantity=40000)])
        out = {a["to"]: a for a in convert_quote(s, "t", DAY, "pts.a", 10000)["answers"]}
        x = out["miles.x"]
        self.assertEqual((x["result"], x["amount"], x["arithmetic"]), ("CALCULATED", 7500, "10,000 x 1.5 / 2"))
        self.assertEqual(x["terms_not_evaluated"], ["Names must match", "Minimum 1,000"])
        self.assertEqual(x["open_questions"], ["Increment not verified"])
        self.assertTrue(any("balance on record 40,000" in n for n in x["assumptions"]))
        self.assertEqual(out["miles.y"]["result"], "NOT_CALCULATED")              # the person does not hold card.a
        self.assertIn("card.a", out["miles.y"]["reason"])

    def test_no_ratio_no_number(self):
        s = world(self.rules(), [holding("h1", "pts.a"), holding("h2", "card.a")])
        y = convert_quote(s, "t", DAY, "pts.a", 10000, to="miles.y")["answers"][0]
        self.assertEqual((y["result"], y["reason"]), ("NOT_CALCULATED", "no transfer ratio is recorded"))
        x = convert_quote(s, "t", DAY, "pts.a", 10000, to="miles.x")["answers"][0]
        self.assertTrue(any("balance not recorded" in n for n in x["assumptions"]))

    def test_asking_about_more_than_the_balance_is_said(self):
        s = world(self.rules(), [holding("h1", "pts.a", quantity=4000)])
        x = convert_quote(s, "t", DAY, "pts.a", 10000, to="miles.x")["answers"][0]
        self.assertTrue(any("LESS than the amount" in n for n in x["assumptions"]))

    def test_unverified_gated_ended_and_malformed(self):
        hold = [holding("h1", "pts.a")]
        for kw, word in ((dict(status="unverified"), "unverified"), (dict(condition_review=review(("Names must match", "unchecked"), ("Increment not verified", "informational"))), "Names must match"),
                         (dict(valid_to="2026-01-31"), "not in effect")):
            a = convert_quote(world(self.rules(**kw), hold), "t", DAY, "pts.a", 1000, to="miles.x")["answers"][0]
            self.assertEqual(a["result"], "NOT_CALCULATED", kw)
            self.assertIn(word, a["reason"])
        self.assertIsNone(parse_ratio("about 1 to 1"))
        self.assertIsNone(parse_ratio("0:1"))
        self.assertEqual(parse_ratio("1:2"), (1.0, 2.0))
        with self.assertRaises(KeyError):
            convert_quote(world(self.rules(), hold), "t", DAY, "card.a", 1000)


class TestPipeline(unittest.TestCase):
    def test_adding_a_restriction_needs_evidence_and_blocks_until_it_is_classified(self):
        import os
        import shutil
        import tempfile
        from prices import changes
        from util import write_store
        tmp = tempfile.mkdtemp(prefix="prices-r-")
        try:
            s = world([rule("r.offer", "grants", "b.offer", H("card.a"))], [holding("h1", "card.a")])
            write_store(s, tmp)
            cs = {"id": "cs-20260601-r-01-revise-rule", "op": "revise_rule", "target": "r.offer", "author": "test", "date": DAY,
                  "reason": "invented", "data": {"set": {"restrictions": ["New applicants only"]}}}
            self.assertFalse(changes.apply(tmp, cs)["ok"])
            # CHANGED 2026-11-17 (repair): the rule has applied since before today, so a new restriction on it is a declared
            # correction (or a successor rule); without the declaration it is refused as a history rewrite
            refused = changes.apply(tmp, dict(cs, evidence=[ev("ev2", retrieved_on=DAY)]))
            self.assertTrue(any(e.startswith("HISTORY_REWRITE") for e in refused["errors"]), refused["errors"])
            cs["data"]["correction"] = "the new-applicant condition was in the source and was left out"
            out = changes.apply(tmp, dict(cs, evidence=[ev("ev2", retrieved_on=DAY)]))
            self.assertTrue(out["ok"], out.get("errors"))
            from prices.store import Store
            self.assertEqual(evaluate(Store.load(tmp), "t", DAY).have("b.offer"), UNRESOLVED)
            self.assertTrue(os.path.exists(os.path.join(tmp, "data", "audit", "previous", cs["id"] + ".json")))   # the rule as it was
        finally:
            shutil.rmtree(tmp)


class TestSuccessorRules(unittest.TestCase):
    """Published terms change. The same relationship with new terms from a later date is a successor, not a duplicate."""

    def setUp(self):
        import shutil
        import tempfile
        from util import write_store
        self.tmp = tempfile.mkdtemp(prefix="prices-r-")
        self.addCleanup(shutil.rmtree, self.tmp)
        old = rule("r.earn", "grants", "b.earn", H("card.a"), earning=earning(("dining", 3)))
        write_store(world([old], [holding("h1", "card.a")]), self.tmp)

    def candidate(self, **kw):
        new = dict({"id": "r.earn-2", "kind": "grants", "output": "b.earn", "when": H("card.a"), "summary": "new terms",
                    "earning": earning(("dining", 2))}, **kw)
        return {"id": "cs-20260601-r-%s" % len(kw), "op": "add_candidate", "author": "test", "date": DAY, "reason": "invented",
                "data": {"candidate": {"id": "c-r.earn-2", "status": "proposed", "created_on": DAY, "proposed_rule": new, "evidence": [ev("ev2")],
                                       "search_path": ["test"], "open_questions": []}}}

    def test_overlapping_dates_are_still_a_duplicate(self):
        from prices import changes
        for kw in ({}, {"valid_from": "2027-01-01"}):                          # the old rule has no end date: every date overlaps
            out = changes.apply(self.tmp, self.candidate(**kw))
            self.assertFalse(out["ok"])
            self.assertIn("DUPLICATE_RELATIONSHIP", out["errors"][0])
            self.assertIn("valid_to", out["errors"][0])                        # the message says how to supersede

    def test_end_the_old_rule_then_the_successor_is_accepted_and_each_date_gets_its_own_terms(self):
        from prices import changes
        from prices.store import Store
        end = {"id": "cs-20260601-r-end", "op": "revise_rule", "target": "r.earn", "author": "test", "date": DAY, "reason": "invented",
               "data": {"set": {"valid_to": "2026-12-31"}}, "evidence": [ev("ev3", retrieved_on=DAY)]}
        self.assertTrue(changes.apply(self.tmp, end)["ok"])
        self.assertFalse(changes.apply(self.tmp, self.candidate(valid_from="2026-12-31"))["ok"])       # one shared day is an overlap
        self.assertTrue(changes.apply(self.tmp, self.candidate(valid_from="2027-01-01", valid_to="2027-12-31"))["ok"])
        promote = {"id": "cs-20260601-r-promote", "op": "promote_candidate", "target": "c-r.earn-2", "author": "test", "date": DAY,
                   "reason": "invented", "data": {"review_by": "2027-05-01"},
                   "attestation": {"by": "Synthetic Reviewer", "on": DAY, "statement": "invented"}}
        s = Store.load(self.tmp)
        s.files["data/kb/vocab.json"]["promotion_reviewers"] = ["Synthetic Reviewer"]
        from util import write_store
        write_store(s, self.tmp)
        out = changes.apply(self.tmp, promote)
        self.assertTrue(out["ok"], out.get("errors"))
        s = Store.load(self.tmp)
        self.assertEqual(codes(lint(s)), set())
        pts = lambda day: [a.get("points") for a in earn_quote(s, "t", day, "dining", 100)["answers"]]      # noqa: E731
        self.assertEqual((pts("2026-12-31"), pts("2027-01-01"), pts("2028-01-01")), ([300], [200], [None]))
        self.assertEqual(sorted(s.rules), ["r.earn", "r.earn-2"])               # both kept: history is not rewritten

    def test_two_rules_in_force_for_the_same_relationship_is_a_lint_error(self):
        a = rule("r.one", "grants", "b.earn", H("card.a"), valid_to="2026-12-31")
        b = rule("r.two", "grants", "b.earn", H("card.a"), valid_from="2026-12-01")
        self.assertIn("DUPLICATE_RELATIONSHIP", codes(lint(world([a, b], []))))
        b2 = dict(b, valid_from="2027-01-01")
        self.assertNotIn("DUPLICATE_RELATIONSHIP", codes(lint(world([a, b2], []))))


if __name__ == "__main__":
    unittest.main()
