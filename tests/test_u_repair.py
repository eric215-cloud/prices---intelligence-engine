"""Adversarial tests of the consolidated foundation safety repair (2026-11-17). Every card, programme and person is invented.

One class per defect reproduced by Bradley and Astra:

    1  "enforced" must be enforced on every path, by the exact predicate the reviewer claims
    2  a missing fact is unknown; only a recorded absence makes "not held" true
    3  every calculator asks the engine the same question about the SPECIFIC rule it uses
    4  a date window opens an opportunity; it never shows that an action (activation, registration...) was taken
    5  ending a holding keeps what was true while it was held
    6  adding, removing or rewording a restriction on a rule that already answered is a declared correction, a successor,
       or waits for a fresh review; it never silently changes past answers or leaves a stale review in charge

Each pair asserts both sides: what is unsettled is never ESTABLISHED, and what is settled and unaffected still is.
"""
import copy
import random
import shutil
import tempfile
import unittest

from util import H, TEST_VOCAB, ent, ev, holding, make_store, metric, review, write_store
from util import rule as fixture_rule
from prices import changes
from prices.calc import convert_quote, earn_quote
from prices.conditions import blockers, context, implies, item_issues, review_issues
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.store import Store

DAY = "2026-06-01"
REVIEWER = "Synthetic Reviewer"
OWNER = "Test Owner"
VOCAB = dict(copy.deepcopy(TEST_VOCAB), promotion_reviewers=[REVIEWER],
             spend_categories={"other": {"name": "everything else"}, "dining": {"name": "dining"}})
ENTS = [ent("card.a", "card"), ent("card.b", "card"), ent("pts.a", "currency"), ent("miles.x", "currency"), ent("b.perk", "benefit"),
        ent("b.earn", "benefit"), ent("b.lounge", "benefit"), ent("b.act", "benefit"), ent("st.silver"), ent("prog.member"),
        ent("club.member"), ent("st.top"), ent("act.activate", "action", how="activate in the app"), ent("act.enrol", "action", how="enrol online")]
GATE, USAGE = "New applicants only", "Book through the portal"
NIGHTS = "At least 1,000 qualifying nights"


def rule(*args, **kw):
    r = fixture_rule(*args, **kw)
    if r.get("condition_review", {}).get("by") == "Test Owner":
        r["condition_review"]["by"] = REVIEWER
    return r


def world(rules, holdings=(), absences=(), **kw):
    s = make_store(ENTS, rules, list(holdings), vocab=VOCAB, **kw)
    for a in absences:
        s.files["profiles/t/absences/%s.json" % a["id"]] = a
    return s


def absence(aid, entity, **kw):
    return dict({"id": aid, "entity": entity, "confirmed_by": OWNER, "confirmed_on": "2026-01-02"}, **kw)


def enforced(text, *claims):
    return {"text": text, "class": "enforced", "enforced_by": list(claims)}


def reviewed(*items):
    return {"by": REVIEWER, "on": "2026-01-01", "items": list(items)}


def have(store, entity, day=DAY):
    return evaluate(store, "t", day).have(entity)


def errors(store):
    return {i[1] for i in lint(store) if i[0] == "ERROR"}


# ================================================================================================= 1. enforced means enforced
class TestEnforcedMeansEnforcedOnEveryPath(unittest.TestCase):
    CTX = context(world([]))

    def test_a_restriction_on_A_is_not_enforced_by_a_rule_that_also_accepts_B(self):
        r = rule("r.perk", "grants", "b.perk", {"any": [H("card.a"), H("card.b")]}, restrictions=["Card A holders only"])
        item = enforced("Card A holders only", {"holds": "card.a"})
        self.assertTrue(review_issues(r, [item], self.CTX))                          # refused at the door
        forged = dict(r, condition_review=reviewed(item))                            # and if it is written in by hand
        self.assertEqual(have(world([forged], [holding("h", "card.b")]), "b.perk"), UNRESOLVED)       # A: B alone does not establish it
        self.assertIn("BAD_CLASSIFICATION", errors(world([forged])))
        good = rule("r.perk", "grants", "b.perk", {"all": [H("card.b"), H("card.a")]}, restrictions=["Card A holders only"],
                    condition_review=reviewed(item))
        self.assertEqual(review_issues(good, [item], self.CTX), [])
        self.assertEqual(have(world([good], [holding("h1", "card.a"), holding("h2", "card.b")]), "b.perk"), ESTABLISHED)   # B
        self.assertEqual(have(world([good], [holding("h2", "card.b")]), "b.perk"), NOT_AVAILABLE)

    def test_nested_conditions(self):
        A, B, C, D = (H(x) for x in ("card.a", "card.b", "pts.a", "prog.member"))
        self.assertTrue(implies({"all": [{"any": [A, {"all": [A, C]}]}, D]}, {"holds": "card.a"}))      # every alternative has A
        self.assertFalse(implies({"any": [{"all": [A, C]}, {"all": [B, C]}]}, {"holds": "card.a"}))       # one alternative lacks A
        self.assertTrue(implies({"any": [{"all": [A, C]}, {"all": [B, C]}]}, {"holds": "pts.a"}))
        self.assertFalse(implies({"any": []}, {"holds": "card.a"}))
        self.assertFalse(implies({"not": A}, {"holds": "card.a"}))                   # "not A" never enforces A
        self.assertFalse(implies({"all": [{"not": {"not": A}}]}, {"holds": "card.a"}))

    def test_a_threshold_claim_must_be_the_threshold_the_rule_checks(self):
        low = rule("r.silver", "grants", "st.silver", {"all": [H("prog.member"), {"metric": "prog.nights", "gte": 1}]}, restrictions=[NIGHTS])
        self.assertTrue(review_issues(low, [enforced(NIGHTS, {"metric": "prog.nights", "gte": 1000})], self.CTX))   # the rule checks 1
        self.assertTrue(review_issues(low, [enforced(NIGHTS, {"metric": "prog.nights", "gte": 1})], self.CTX))      # the text says 1,000
        self.assertTrue(review_issues(low, [enforced(NIGHTS, {"metric": "prog.nights"})], self.CTX))                # a bare id is presence
        forged = dict(low, condition_review=reviewed(enforced(NIGHTS, {"metric": "prog.nights", "gte": 1000})))
        s = world([forged], [holding("h", "prog.member")], metrics=[metric("prog.nights", 5)])
        self.assertEqual(have(s, "st.silver"), UNRESOLVED)                           # A: five nights is not "established"
        right = rule("r.silver", "grants", "st.silver", {"all": [H("prog.member"), {"metric": "prog.nights", "gte": 1000}]}, restrictions=[NIGHTS],
                     condition_review=reviewed(enforced(NIGHTS, {"metric": "prog.nights", "gte": 1000})))
        for nights, want in ((1200, ESTABLISHED), (900, NOT_AVAILABLE)):                # B, and a clear no
            self.assertEqual(have(world([right], [holding("h", "prog.member")], metrics=[metric("prog.nights", nights)]), "st.silver"), want)
        stricter = dict(right, when={"all": [H("prog.member"), {"metric": "prog.nights", "gte": 1500}]})
        self.assertEqual(item_issues(stricter, stricter["condition_review"]["items"][0], self.CTX), [])   # a stricter check still enforces it

    def test_another_leaf_on_the_same_figure_is_not_the_claimed_predicate(self):
        r = rule("r.silver", "grants", "st.silver", {"all": [{"metric": "prog.nights", "gte": 1}, {"any": [{"metric": "prog.nights", "gte": 1000}, H("card.a")]}]},
                 restrictions=[NIGHTS])
        self.assertTrue(review_issues(r, [enforced(NIGHTS, {"metric": "prog.nights", "gte": 1000})], self.CTX))
        forged = dict(r, condition_review=reviewed(enforced(NIGHTS, {"metric": "prog.nights", "gte": 1000})))
        self.assertEqual(have(world([forged], [holding("h", "card.a")], metrics=[metric("prog.nights", 3)]), "st.silver"), UNRESOLVED)

    def test_old_presence_forms_and_misplaced_claims_never_count(self):
        r = rule("r.perk", "grants", "b.perk", H("card.a"), restrictions=["Card A holders only"])
        for by in ("when:card.a", "dates", "earn", "election", None, [], [{"holds": "card.a", "gte": 3}], [{"acquire": True}], [{"election": True}],
                   [{"valid_to": "2026-12-31"}], [{"earn_threshold": 1}], [{"earn_activation": True}], [{"holds": "no.such"}]):
            with self.subTest(by=by):
                item = {"text": "Card A holders only", "class": "enforced", "enforced_by": by}
                self.assertTrue(item_issues(r, item, self.CTX))
                self.assertEqual(have(world([dict(r, condition_review=reviewed(item))], [holding("h", "card.a")]), "b.perk"), UNRESOLVED)
        ok = dict(r, condition_review=reviewed(enforced("Card A holders only", {"holds": "card.a"})))
        self.assertEqual(have(world([ok], [holding("h", "card.a")]), "b.perk"), ESTABLISHED)

    def test_explain_shows_each_claim_and_why_it_is_not_demonstrated(self):
        import os
        import subprocess
        import sys
        from prices.conditions import describe
        item = enforced("Card A holders only", {"holds": "card.a"})
        forged = rule("r.perk", "grants", "b.perk", {"any": [H("card.a"), H("card.b")]}, restrictions=["Card A holders only"], condition_review=reviewed(item))
        d = describe(forged, self.CTX)[0]
        self.assertTrue(d["blocks"])
        self.assertIn("not every way this rule applies requires holding card.a", d["unproven"])
        root = tempfile.mkdtemp(prefix="prices-u-")
        self.addCleanup(shutil.rmtree, root)
        write_store(world([forged], [holding("h", "card.b")]), root)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run([sys.executable, "-m", "prices", "--root", root, "explain", "--profile", "t", "--as-of", DAY, "b.perk"],
                             cwd=here, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('enforced by [{"holds": "card.a"}]: BLOCKS', out.stdout)
        self.assertIn("not demonstrated: not every way this rule applies requires holding card.a", out.stdout)

    def test_enforcement_is_checked_again_whenever_the_rule_is_read(self):
        r = rule("r.perk", "grants", "b.perk", H("card.a"), valid_to="2026-12-31", restrictions=["Offer ends December 31, 2026"],
                 condition_review=reviewed(enforced("Offer ends December 31, 2026", {"valid_to": "2026-12-31"})))
        self.assertEqual(have(world([r], [holding("h", "card.a")]), "b.perk"), ESTABLISHED)
        moved = dict(r, valid_to=None)                                               # the end date is lost in a later edit
        self.assertEqual(have(world([moved], [holding("h", "card.a")]), "b.perk"), UNRESOLVED)
        self.assertEqual([c for c, _t in blockers(moved, self.CTX)], ["unproven"])


# ============================================================================================ 2. unknown is not absent
class TestMissingIsNotNegative(unittest.TestCase):
    RULE = rule("r.top", "grants", "st.top", {"all": [H("card.a"), {"not": H("club.member")}]})
    CARD = holding("h", "card.a")

    def test_unknown_membership_does_not_satisfy_not_a_member(self):
        r = evaluate(world([self.RULE], [self.CARD]), "t", DAY)
        self.assertEqual(r.have("st.top"), UNRESOLVED)                               # neither ESTABLISHED nor NOT_AVAILABLE
        self.assertTrue(any("not proof of absence" in u for u in r.tokens("have:st.top")["unknowns"]))

    def test_a_recorded_absence_satisfies_it(self):
        s = world([self.RULE], [self.CARD], [absence("a1", "club.member")])
        self.assertEqual(errors(s), set())
        self.assertEqual(have(s, "st.top"), ESTABLISHED)
        self.assertEqual(evaluate(s, "t", DAY).report()["recorded_absences"], ["club.member"])
        later = world([self.RULE], [self.CARD], [absence("a1", "club.member", valid_to="2026-03-31")])
        self.assertEqual(have(later, "st.top"), UNRESOLVED)                         # an absence ends like any record

    def test_known_membership_and_contradictions(self):
        self.assertEqual(have(world([self.RULE], [self.CARD, holding("m", "club.member")]), "st.top"), NOT_AVAILABLE)
        both = world([self.RULE], [self.CARD, holding("m", "club.member")], [absence("a1", "club.member")])
        self.assertNotEqual(have(both, "st.top"), ESTABLISHED)                       # the owner said both: neither is relied on
        self.assertIn("CONFLICTING_HOLDINGS", {f["code"] for f in evaluate(both, "t", DAY).flags})
        self.assertIn("CONFLICTING_HOLDINGS", {i[1] for i in lint(both)})
        maybe = world([self.RULE], [self.CARD, holding("m", "club.member", state="unconfirmed")], [absence("a1", "club.member")])
        self.assertEqual(have(maybe, "st.top"), UNRESOLVED)

    def test_a_derived_negative_needs_absence_of_every_route(self):
        derive = rule("r.club", "grants", "club.member", H("prog.member"))
        s = world([self.RULE, derive], [self.CARD, holding("p", "prog.member", state="unconfirmed")], [absence("a1", "club.member")])
        self.assertEqual(have(s, "st.top"), UNRESOLVED)                              # recorded absent, but a rule says it may be held
        s2 = world([self.RULE, derive], [self.CARD], [absence("a1", "club.member")])
        self.assertEqual(have(s2, "st.top"), ESTABLISHED)

    def test_an_action_plus_a_recorded_absence_is_conditional_not_established(self):
        r = rule("r.top", "acquire", "st.top", {"all": [H("act.enrol"), {"not": H("club.member")}]}, retention={"mode": "unknown"})
        self.assertEqual(have(world([r], [], [absence("a1", "club.member")]), "st.top"), CONDITIONAL)
        self.assertEqual(have(world([r], []), "st.top"), UNRESOLVED)

    def test_an_unattested_absence_is_not_relied_on(self):
        x = absence("a1", "club.member")
        del x["confirmed_by"]
        s = world([self.RULE], [self.CARD], [x])
        self.assertEqual(have(s, "st.top"), UNRESOLVED)
        self.assertTrue({"UNATTESTED_CONFIRMATION", "SCHEMA"} & errors(s), errors(s))

    def test_a_missing_required_figure_is_unresolved_not_unavailable(self):
        r = rule("r.silver", "grants", "st.silver", {"all": [H("prog.member"), {"metric": "prog.nights", "gte": 10}]})
        self.assertEqual(have(world([r], [holding("h", "prog.member")]), "st.silver"), UNRESOLVED)


class TestAbsencesThroughThePipeline(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prices-u-")
        self.addCleanup(shutil.rmtree, self.root)
        write_store(world([TestMissingIsNotNegative.RULE], [TestMissingIsNotNegative.CARD]), self.root)

    def cs(self, by=OWNER, **x):
        return {"id": "cs-20260601-u-01-set-absence", "op": "set_absence", "author": "t", "date": DAY, "reason": "invented", "profile": "t",
                "data": {"absence": dict({"id": "a1", "entity": "club.member"}, **x)}, "attestation": {"by": by, "on": DAY, "statement": "not a member"}}

    def test_only_the_owner_can_record_an_absence(self):
        self.assertFalse(changes.apply(self.root, self.cs(by="Somebody Else"))["ok"])
        self.assertFalse(changes.apply(self.root, self.cs(entity="no.such"))["ok"])
        self.assertEqual(have(Store.load(self.root), "st.top"), UNRESOLVED)
        out = changes.apply(self.root, self.cs())
        self.assertTrue(out["ok"], out.get("errors"))
        self.assertEqual(have(Store.load(self.root), "st.top"), ESTABLISHED)
        self.assertEqual(errors(Store.load(self.root)), set())


# ======================================================================================== 3. one question about one rule
class TestEveryCalculatorAsksAboutTheRuleItUses(unittest.TestCase):
    def transfer(self, extra):
        return rule("t.x", "transfer", "miles.x", {"all": [H("pts.a"), extra]}, transfer={"from": "pts.a", "ratio": "2:1"})

    def answer(self, r, holdings, **kw):
        a = convert_quote(world([r], holdings, **kw), "t", DAY, "pts.a", 10000)["answers"][0]
        return a["result"], a["eligibility"]["status"]

    def test_an_alternative_route_is_honoured(self):
        r = self.transfer({"any": [H("card.a"), H("card.b")]})
        self.assertEqual(self.answer(r, [holding("p", "pts.a", quantity=20000), holding("b", "card.b")]), ("CALCULATED", ESTABLISHED))
        self.assertEqual(self.answer(r, [holding("p", "pts.a", quantity=20000)]), ("NOT_CALCULATED", NOT_AVAILABLE))

    def test_a_figure_requirement_cannot_be_ignored(self):
        r = self.transfer({"metric": "prog.nights", "gte": 10})
        pts = [holding("p", "pts.a", quantity=20000)]
        self.assertEqual(self.answer(r, pts), ("NOT_CALCULATED", UNRESOLVED))
        self.assertEqual(self.answer(r, pts, metrics=[metric("prog.nights", 4)]), ("NOT_CALCULATED", NOT_AVAILABLE))
        self.assertEqual(self.answer(r, pts, metrics=[metric("prog.nights", 12)]), ("CALCULATED", ESTABLISHED))

    def test_a_negative_requirement_cannot_be_ignored(self):
        r = self.transfer({"not": H("club.member")})
        pts = [holding("p", "pts.a", quantity=20000)]
        self.assertEqual(self.answer(r, pts), ("NOT_CALCULATED", UNRESOLVED))
        self.assertEqual(self.answer(r, pts + [holding("m", "club.member")]), ("NOT_CALCULATED", NOT_AVAILABLE))
        a = convert_quote(world([r], pts, [absence("a1", "club.member")]), "t", DAY, "pts.a", 10000)["answers"][0]
        self.assertEqual((a["result"], a["amount"]), ("CALCULATED", 5000))

    def test_an_unrelated_rule_for_the_same_benefit_does_not_unlock_a_blocked_rate(self):
        rates = {"currency": "pts.a", "rates": [{"category": "dining", "per_usd": 3}, {"category": "other", "per_usd": 1}]}
        blocked = rule("r.rates", "grants", "b.earn", H("card.a"), earning=rates, restrictions=[GATE], condition_review=reviewed({"text": GATE, "class": "unchecked"}))
        other = rule("r.other", "grants", "b.earn", H("card.b"))
        s = world([blocked, other], [holding("a", "card.a"), holding("b", "card.b")])
        self.assertEqual(have(s, "b.earn"), ESTABLISHED)                            # the benefit IS established, through card B
        a = [x for x in earn_quote(s, "t", DAY, "dining", 100)["answers"] if x["card"] == "card.a"][0]
        self.assertEqual(a["result"], "NOT_CALCULATED")                              # but card A's rate is not usable
        self.assertNotIn("points", a)
        free = dict(blocked, condition_review=reviewed({"text": GATE, "class": "usage"}))
        a = [x for x in earn_quote(world([free, other], [holding("a", "card.a"), holding("b", "card.b")]), "t", DAY, "dining", 100)["answers"]
             if x["card"] == "card.a"][0]
        self.assertEqual((a["result"], a["points"], a["eligibility"]["rule"]), ("CALCULATED", 300, "r.rates"))

    def test_credits_ask_about_their_own_rule(self):
        import test_o_credits as o
        blocked = o.credit_rule("r.hotel", "hotel", o.HOTEL, restrictions=[GATE], condition_review=review((GATE, "unchecked")))
        other = fixture_rule("r.hotel-y", "grants", "hotel", H("card.y"))
        s = o.world(holdings=[o.card(), holding("h-y", "card.y", confirmed_by=o.OWNER)], rules=[blocked, other])
        self.assertEqual(evaluate(s, "t", "2027-03-10").have("hotel"), ESTABLISHED)
        self.assertEqual(o.row(s, "hotel", "2027-03-10")["applies"]["status"], UNRESOLVED)

    def test_arithmetic_is_not_a_transaction(self):
        a = convert_quote(world([self.transfer(H("card.a"))], [holding("p", "pts.a", quantity=100), holding("a", "card.a")]), "t", DAY, "pts.a", 10000)["answers"][0]
        self.assertEqual((a["result"], a["eligibility"]["status"], a["amount"]), ("CALCULATED", ESTABLISHED, 5000))
        self.assertTrue(any("balance" in n for n in a["assumptions"]), a["assumptions"])        # 100 held: the number is arithmetic only

    def test_status_and_calculators_agree_on_every_condition_shape(self):
        leaves = [H("card.a"), H("card.b"), {"metric": "prog.nights", "gte": 10}, {"not": H("club.member")}, H("act.enrol")]
        rnd = random.Random(20261117)

        def cond(depth=0):
            if depth > 1 or rnd.random() < 0.4:
                return copy.deepcopy(rnd.choice(leaves))
            return {rnd.choice(["all", "any"]): [cond(depth + 1) for _ in range(rnd.randint(1, 3))]}
        for n in range(150):
            c = cond()
            hs = [holding("p", "pts.a", quantity=50000)] + [holding("h%d" % i, e, state=rnd.choice(["confirmed", "unconfirmed"]))
                                                            for i, e in enumerate(("card.a", "card.b", "club.member")) if rnd.random() < 0.5]
            ms = [metric("prog.nights", rnd.choice([3, 30]))] if rnd.random() < 0.6 else []
            ab = [absence("a1", "club.member")] if rnd.random() < 0.4 else []
            r = self.transfer(c)
            s = world([r], hs, ab, metrics=ms)
            res = evaluate(s, "t", DAY)
            ap = res.rule_applies("t.x")["status"]
            with self.subTest(n=n, cond=c):
                self.assertEqual(res.have("miles.x"), ap)
                a = convert_quote(s, "t", DAY, "pts.a", 1000)["answers"][0]
                self.assertEqual(a["result"] == "CALCULATED", ap == ESTABLISHED)
                self.assertEqual(a["eligibility"]["status"], ap)


# ============================================================================================ 4. a window is not an action
class TestAWindowIsNotAnAction(unittest.TestCase):
    TEXT = "Activate by December 31, 2026"
    CTX = context(world([]))

    def test_dates_cannot_stand_for_the_activation(self):
        r = rule("r.act", "grants", "b.act", H("card.a"), valid_from="2026-01-01", valid_to="2026-12-31", restrictions=[self.TEXT])
        self.assertTrue(review_issues(r, [enforced(self.TEXT, {"valid_to": "2026-12-31"})], self.CTX))
        self.assertTrue(review_issues(r, [enforced(self.TEXT, {"holds": "card.a"})], self.CTX))          # a card is not the action
        forged = dict(r, condition_review=reviewed(enforced(self.TEXT, {"valid_to": "2026-12-31"})))
        self.assertEqual(have(world([forged], [holding("h", "card.a")]), "b.act"), UNRESOLVED)          # inside the window, nothing recorded

    def test_the_activation_itself_must_be_recorded(self):
        claim = enforced(self.TEXT, {"holds": "act.activate"}, {"valid_to": "2026-12-31"})
        r = rule("r.act", "grants", "b.act", {"all": [H("card.a"), H("act.activate")]}, valid_from="2026-01-01", valid_to="2026-12-31",
                 restrictions=[self.TEXT], condition_review=reviewed(claim))
        self.assertEqual(review_issues(r, [claim], self.CTX), [])
        self.assertEqual(have(world([r], [holding("h", "card.a")]), "b.act"), CONDITIONAL)              # open, not done: never ESTABLISHED
        self.assertEqual(have(world([r], [holding("h", "card.a"), holding("x", "act.activate")]), "b.act"), ESTABLISHED)
        self.assertEqual(have(world([r], [holding("h", "card.a"), holding("x", "act.activate")]), "b.act", "2027-01-15"), NOT_AVAILABLE)

    def test_the_same_applies_to_registration_enrolment_and_linking(self):
        for text in ("Register by March 31, 2027", "Enrollment required", "Requires linking your accounts", "Must opt in", "Sign up first"):
            r = rule("r.act", "grants", "b.act", H("card.a"), valid_to="2027-03-31", restrictions=[text])
            with self.subTest(text):
                self.assertTrue(review_issues(r, [enforced(text, {"valid_to": "2027-03-31"})], self.CTX))

    def test_an_earned_benefit_that_needs_activation(self):
        earn = {"measure": "card.spend", "period": "calendar_year", "threshold": 1000, "unit": "units", "activation": "required",
                "term": {"ends": "fixed", "year_offset": 1, "month": 12, "day": 31}}
        r = rule("r.e", "earns", "b.perk", H("card.a"), earn=earn, restrictions=["Requires linking your account to activate"])
        self.assertEqual(review_issues(r, [enforced("Requires linking your account to activate", {"earn_activation": True})], self.CTX), [])
        auto = dict(r, earn=dict(earn, activation="automatic"))
        self.assertTrue(review_issues(auto, [enforced("Requires linking your account to activate", {"earn_activation": True})], self.CTX))
        self.assertTrue(review_issues(r, [enforced("Requires linking your account to activate", {"earn_threshold": 1000})], self.CTX))


# ============================================================================================== on disk, for 5 and 6
class OnDisk(unittest.TestCase):
    RULES, HOLD = (), ()

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prices-u-")
        self.addCleanup(shutil.rmtree, self.root)
        write_store(world(list(self.RULES), list(self.HOLD)), self.root)
        self.n = 0

    def cs(self, op, **kw):
        self.n += 1
        return dict({"id": "cs-20260601-u-%02d-%s" % (self.n, op.replace("_", "-")), "op": op, "author": "t", "date": DAY, "reason": "invented"}, **kw)

    def apply(self, c, code=None):
        out = changes.apply(self.root, c)
        if code:
            self.assertFalse(out["ok"], c["id"])
            self.assertTrue(any(e.startswith(code) for e in out["errors"]), out["errors"])
        else:
            self.assertTrue(out["ok"], out.get("errors"))
        return c["id"]

    def have(self, entity, day=DAY):
        return have(Store.load(self.root), entity, day)

    def store(self):
        return Store.load(self.root)


# ============================================================================================ 5. personal history
class TestEndingAHoldingKeepsItsHistory(OnDisk):
    RULES = (rule("r.lounge", "grants", "b.lounge", H("card.a")),)
    HOLD = (holding("h-card", "card.a", valid_from="2026-01-01", confirmed_by=OWNER, confirmed_on="2026-01-01"),
            holding("h-maybe", "card.b", valid_from="2026-01-01", state="unconfirmed"))

    def end(self, target, ended_on, by=OWNER):
        return self.cs("end_holding", profile="t", target=target, data={"ended_on": ended_on}, attestation={"by": by, "on": DAY, "statement": "closed"})

    def test_a_card_held_january_to_may_still_answers_for_march(self):
        self.apply(self.end("h-card", "2026-05-31"))
        self.assertEqual((self.have("card.a", "2026-03-15"), self.have("b.lounge", "2026-03-15")), (ESTABLISHED, ESTABLISHED))
        self.assertEqual((self.have("card.a", "2026-05-31"), self.have("b.lounge", "2026-06-01")), (ESTABLISHED, NOT_AVAILABLE))
        h = self.store().profile("t").holdings["h-card"]
        self.assertEqual((h["state"], h["ended_from"], h["valid_to"]), ("ended", "confirmed", "2026-05-31"))
        self.assertNotIn("EXPIRED_HOLDING", {f["code"] for f in evaluate(self.store(), "t", "2026-07-01").flags})   # ended, not overlooked
        self.assertEqual(have(self.store(), "card.a", "2025-12-31"), NOT_AVAILABLE)  # nor before it began

    def test_an_unconfirmed_holding_is_not_promoted_by_ending_it(self):
        self.apply(self.end("h-maybe", "2026-05-31"))
        self.assertEqual(self.have("card.b", "2026-03-15"), UNRESOLVED)

    def test_ending_is_checked(self):
        self.apply(self.end("h-card", "2025-12-01"), "BAD_DATES: ended_on")
        self.apply(self.end("h-card", "soon"), "BAD_DATA")
        self.apply(self.end("h-card", "2026-05-31", by="Somebody Else"), "OWNER_ATTESTATION_REQUIRED")
        self.assertEqual(self.have("card.a"), ESTABLISHED)

    def test_the_state_a_record_gives_on_a_day(self):
        from prices.engine import holding_state as state_on, to_date

        def holding_state(h, day):
            return state_on(h, to_date(day))
        base = dict(id="h", entity="card.a", valid_from="2026-01-01", valid_to="2026-05-31")
        self.assertEqual(holding_state(dict(base, state="ended", ended_from="unconfirmed"), "2026-03-15"), "unconfirmed")
        self.assertEqual(holding_state(dict(base, state="ended", ended_from="confirmed"), "2026-06-01"), None)
        self.assertEqual(holding_state(dict(base, state="withdrawn"), "2026-03-15"), None)          # recorded in error: never true
        self.assertEqual(holding_state(dict(base, state="ended", valid_to=None), "2026-03-15"), None)   # an end with no date says nothing

    def test_credits_keep_the_periods_of_a_card_ended_later(self):
        import test_o_credits as o
        from prices import credits
        h = o.card()
        h.update(state="ended", ended_from="confirmed", valid_to="2026-12-31", confirmed_by=o.OWNER, confirmed_on="2025-03-15")
        s = o.world(holdings=[h])
        self.assertIsNotNone(o.row(s, "hotel", "2026-06-15"))                       # the card was held then
        self.assertIsNone(o.row(s, "hotel", "2027-03-10"))                           # and not after it ended
        ends = {(e["benefit"], e["date"]) for e in credits.events(s, "t", "2026-11-15", "2027-03-31")}
        self.assertIn(("ride", "2026-12-31"), ends)
        self.assertNotIn(("ride", "2027-01-31"), ends)

    def test_older_and_withdrawn_records(self):
        legacy = holding("h-old", "card.a", state="ended", valid_from="2026-01-01", valid_to="2026-05-31", confirmed_by=OWNER, confirmed_on="2026-01-01")
        self.assertEqual(have(world(list(self.RULES), [legacy]), "b.lounge", "2026-03-15"), ESTABLISHED)
        legacy.pop("confirmed_by")
        self.assertEqual(have(world(list(self.RULES), [legacy]), "b.lounge", "2026-03-15"), UNRESOLVED)
        wrong = holding("h-err", "card.a", state="withdrawn", valid_from="2026-01-01", valid_to="2026-05-31")
        self.assertEqual(have(world(list(self.RULES), [wrong]), "b.lounge", "2026-03-15"), NOT_AVAILABLE)   # recorded in error: never true


# ================================================================================ 6. condition changes keep history and review
class TestRestrictionChangesAreDeclaredOrReviewed(OnDisk):
    RULES = (rule("r.perk", "grants", "b.perk", H("card.a"), valid_from="2025-01-01"),
             rule("r.future", "grants", "b.lounge", H("card.a"), valid_from="2026-09-01"),
             rule("r.used", "grants", "b.earn", H("card.a"), valid_from="2025-01-01", restrictions=[USAGE], condition_review=reviewed({"text": USAGE, "class": "usage"})),
             rule("r.gated", "grants", "b.act", H("card.a"), valid_from="2025-01-01", restrictions=[GATE], open_questions=["Is it renewed?"],
                  condition_review=reviewed({"text": GATE, "class": "unchecked"}, {"text": "Is it renewed?", "class": "informational"})))
    HOLD = (holding("h", "card.a", valid_from="2024-01-01"),)
    EV = [ev("ev-u", "official", "Issuer", DAY)]

    def revise(self, target, correction=None, **set_):
        data = {"set": set_}
        if correction:
            data["correction"] = correction
        return self.cs("revise_rule", target=target, data=data, evidence=self.EV)

    def classify(self, target, items):
        return self.cs("classify_conditions", target=target, data={"items": items}, attestation={"by": REVIEWER, "on": DAY, "statement": "invented"})

    def test_a_first_restriction_on_a_rule_that_already_answered(self):
        self.apply(self.revise("r.perk", restrictions=[GATE]), "HISTORY_REWRITE")
        self.assertEqual(self.have("b.perk", "2025-06-01"), ESTABLISHED)
        self.apply(self.revise("r.perk", correction="the new-applicant term was in the source from the start", restrictions=[GATE]))
        self.assertEqual(self.have("b.perk", "2025-06-01"), UNRESOLVED)              # declared: and it waits for a reviewer
        self.apply(self.classify("r.perk", [{"text": GATE, "class": "unchecked"}]))
        self.assertEqual(self.have("b.perk", "2025-06-01"), UNRESOLVED)

    def test_a_genuinely_new_term_on_a_rule_that_has_not_started(self):
        self.apply(self.revise("r.future", restrictions=[USAGE]))
        self.assertEqual(self.have("b.lounge", "2026-10-01"), UNRESOLVED)
        self.apply(self.classify("r.future", [{"text": USAGE, "class": "usage"}]))
        self.assertEqual(self.have("b.lounge", "2026-10-01"), ESTABLISHED)

    def test_a_term_added_from_a_date_is_a_successor(self):
        self.apply(self.revise("r.perk", valid_to="2026-06-30"))
        cand = {"id": "c-perk-2", "status": "proposed", "created_on": DAY, "evidence": self.EV, "search_path": ["q"], "open_questions": [],
                "proposed_rule": {"id": "r.perk-2", "kind": "grants", "output": "b.perk", "when": H("card.a"), "summary": "new terms",
                                  "valid_from": "2026-07-01", "restrictions": [GATE]}}
        self.apply(self.cs("add_candidate", data={"candidate": cand}))
        self.apply(self.cs("promote_candidate", target="c-perk-2", data={"review_by": "2027-05-01", "conditions": [{"text": GATE, "class": "unchecked"}]},
                           attestation={"by": REVIEWER, "on": DAY, "statement": "invented"}))
        self.assertEqual((self.have("b.perk", "2025-06-01"), self.have("b.perk", "2026-06-30")), (ESTABLISHED, ESTABLISHED))   # history kept
        self.assertEqual(self.have("b.perk", "2026-07-01"), UNRESOLVED)

    def test_removing_the_last_reviewed_restriction_does_not_leave_a_stale_approval(self):
        self.apply(self.revise("r.used", restrictions=[]), "HISTORY_REWRITE")
        self.apply(self.revise("r.used", correction="the portal sentence was never a term of this benefit", restrictions=[]))
        s = self.store()
        self.assertEqual(have(s, "b.earn"), UNRESOLVED)                              # no text left, but the review is stale
        self.assertIn("STALE_CLASSIFICATION", {i[1] for i in lint(s)})
        self.apply(self.classify("r.used", []))                                      # a reviewer looks at the rule as it now stands
        self.assertEqual(self.have("b.earn"), ESTABLISHED)

    def test_removing_or_rewording_a_blocking_restriction_does_not_unblock_it(self):
        self.apply(self.revise("r.gated", correction="the sentence was entered on the wrong benefit", restrictions=[]))
        self.assertEqual(self.have("b.act"), UNRESOLVED)
        self.apply(self.revise("r.gated", correction="restoring and rewording the new-applicant term", restrictions=["New applicants only."]))
        self.assertEqual(self.have("b.act"), UNRESOLVED)

    def test_a_resolved_question_is_reviewed_again(self):
        self.apply(self.revise("r.gated", open_questions=[]))
        self.assertIn("stale", [c for c, _t in blockers(self.store().rules["r.gated"], context(self.store()))])


if __name__ == "__main__":
    unittest.main()
