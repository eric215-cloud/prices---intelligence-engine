"""Acceptance Test A - conditional eligibility: direct, conjunctive, alternative, multistep."""
import unittest

from util import H, ent, holding, make_store, metric, rule
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import errors

D = "2026-06-01"


class TestConditional(unittest.TestCase):
    def test_direct(self):
        s = make_store([ent("card", "card"), ent("perk", "benefit")],
                       [rule("r1", "grants", "perk", H("card"))], [holding("h1", "card")])
        self.assertEqual(errors(s), [])
        r = evaluate(s, "t", D)
        self.assertEqual(r.have("perk"), ESTABLISHED)
        self.assertEqual(r.basis("have:perk"), "derived")
        self.assertEqual(r.basis("have:card"), "personal")

    def test_missing_qualification_is_not_satisfied(self):
        s = make_store([ent("card", "card"), ent("perk", "benefit")], [rule("r1", "grants", "perk", H("card"))])
        self.assertEqual(evaluate(s, "t", D).have("perk"), NOT_AVAILABLE)

    def test_conjunctive(self):
        es = [ent("a"), ent("b"), ent("x", "benefit")]
        rs = [rule("r1", "grants", "x", {"all": [H("a"), H("b")]})]
        self.assertEqual(evaluate(make_store(es, rs, [holding("h1", "a")]), "t", D).have("x"), NOT_AVAILABLE)
        both = make_store(es, rs, [holding("h1", "a"), holding("h2", "b")])
        self.assertEqual(evaluate(both, "t", D).have("x"), ESTABLISHED)

    def test_alternative(self):
        es = [ent("a"), ent("b"), ent("x", "benefit")]
        rs = [rule("r1", "grants", "x", {"any": [H("a"), H("b")]})]
        r = evaluate(make_store(es, rs, [holding("h2", "b")]), "t", D)
        self.assertEqual(r.have("x"), ESTABLISHED)
        self.assertIn("have:b", r.chain_atoms("have:x"))
        self.assertNotIn("have:a", r.chain_atoms("have:x"))

    def test_alternative_rules_for_same_output(self):
        es = [ent("a"), ent("b"), ent("x", "benefit")]
        rs = [rule("r1", "grants", "x", H("a")), rule("r2", "grants", "x", H("b"))]
        self.assertEqual(evaluate(make_store(es, rs, [holding("h", "b")]), "t", D).have("x"), ESTABLISHED)

    def test_nested_all_any(self):
        es = [ent("a"), ent("b"), ent("c"), ent("x", "benefit")]
        rs = [rule("r1", "grants", "x", {"all": [H("a"), {"any": [H("b"), H("c")]}]})]
        self.assertEqual(evaluate(make_store(es, rs, [holding("h1", "a"), holding("h2", "c")]), "t", D).have("x"), ESTABLISHED)
        self.assertEqual(evaluate(make_store(es, rs, [holding("h2", "c")]), "t", D).have("x"), NOT_AVAILABLE)

    def test_multistep_chain_has_no_length_cap(self):
        n = 60
        es = [ent("n%d" % i) for i in range(n + 1)]
        rs = [rule("r%d" % i, "grants", "n%d" % (i + 1), H("n%d" % i)) for i in range(n)]
        # rules deliberately listed in reverse so order of evaluation cannot help
        r = evaluate(make_store(es, list(reversed(rs)), [holding("h", "n0")]), "t", D)
        self.assertEqual(r.have("n%d" % n), ESTABLISHED)
        self.assertEqual(len(r.chain_atoms("have:n%d" % n)), n + 1)
        self.assertIn("have:n%d" % n, r.dependents("have:n0"))

    def test_action_required_is_conditional_until_done(self):
        es = [ent("card", "card"), ent("enroll", "action", how="Enroll online"), ent("gold")]
        rs = [rule("r1", "grants", "gold", {"all": [H("card"), H("enroll")]})]
        r = evaluate(make_store(es, rs, [holding("h1", "card")]), "t", D)
        self.assertEqual(r.have("gold"), CONDITIONAL)
        self.assertEqual([s["entity"] for s in r.tokens("have:gold")["steps"]], ["enroll"])
        done = make_store(es, rs, [holding("h1", "card"), holding("h2", "enroll")])
        self.assertEqual(evaluate(done, "t", D).have("gold"), ESTABLISHED)

    def test_action_alone_does_not_help_without_qualification(self):
        es = [ent("card", "card"), ent("enroll", "action"), ent("gold")]
        rs = [rule("r1", "grants", "gold", {"all": [H("card"), H("enroll")]})]
        self.assertEqual(evaluate(make_store(es, rs), "t", D).have("gold"), NOT_AVAILABLE)

    def test_acquire_is_eligibility_not_possession(self):
        es = [ent("src"), ent("dst"), ent("perk", "benefit")]
        rs = [rule("m", "acquire", "dst", H("src"), retention={"mode": "fixed_term"}),
              rule("p", "grants", "perk", H("dst"))]
        r = evaluate(make_store(es, rs, [holding("h", "src")]), "t", D)
        self.assertEqual(r.status("can_get:dst"), ESTABLISHED)
        self.assertEqual(r.have("dst"), CONDITIONAL)
        self.assertEqual(r.have("perk"), CONDITIONAL)
        steps = r.tokens("have:perk")["steps"]
        self.assertEqual([(s["type"], s["entity"]) for s in steps], [("acquire", "dst")])
        rep = r.report()
        self.assertEqual([x["entity"] for x in rep["eligible_to_acquire"]], ["dst"])
        self.assertEqual(rep["derived_entitlements"], [])

    def test_fewest_steps_derivation_is_preferred(self):
        es = [ent("card", "card"), ent("a1", "action"), ent("a2", "action"), ent("a3", "action"), ent("x", "benefit")]
        rs = [rule("long", "grants", "x", {"all": [H("card"), H("a1"), H("a2")]}),
              rule("short", "grants", "x", {"all": [H("card"), H("a3")]})]
        r = evaluate(make_store(es, rs, [holding("h", "card")]), "t", D)
        self.assertEqual([s["entity"] for s in r.tokens("have:x")["steps"]], ["a3"])

    def test_metric_threshold(self):
        es = [ent("gold")]
        rs = [rule("r", "grants", "gold", {"metric": "nights", "gte": 50})]
        self.assertEqual(evaluate(make_store(es, rs, metrics=[metric("nights", 60)]), "t", D).have("gold"), ESTABLISHED)
        self.assertEqual(evaluate(make_store(es, rs, metrics=[metric("nights", 40)]), "t", D).have("gold"), NOT_AVAILABLE)
        self.assertEqual(evaluate(make_store(es, rs), "t", D).have("gold"), UNRESOLVED)
        self.assertEqual(evaluate(make_store(es, rs, metrics=[metric("nights", 60, "unconfirmed")]), "t", D).have("gold"), UNRESOLVED)

    def test_exclusion(self):
        es = [ent("card", "card"), ent("blocker"), ent("x", "benefit")]
        rs = [rule("r", "grants", "x", {"all": [H("card"), {"not": H("blocker")}]})]
        # CHANGED 2026-11-17 (repair): with no record about the blocker, "not held" is unknown, not proven. This line expected
        # ESTABLISHED; that was the defect. Only the owner's recorded absence establishes it (tests/test_u_repair.py)
        self.assertEqual(evaluate(make_store(es, rs, [holding("h", "card")]), "t", D).have("x"), UNRESOLVED)
        absent = make_store(es, rs, [holding("h", "card")])
        absent.files["profiles/t/absences/a1.json"] = {"id": "a1", "entity": "blocker", "confirmed_by": "Test Owner", "confirmed_on": D}
        self.assertEqual(evaluate(absent, "t", D).have("x"), ESTABLISHED)
        blocked = make_store(es, rs, [holding("h", "card"), holding("b", "blocker")])
        self.assertEqual(evaluate(blocked, "t", D).have("x"), NOT_AVAILABLE)
        maybe = make_store(es, rs, [holding("h", "card"), holding("b", "blocker", "unconfirmed")])
        self.assertEqual(evaluate(maybe, "t", D).have("x"), UNRESOLVED)

    def test_four_categories_stay_separate(self):
        es = [ent("card", "card"), ent("perk", "benefit"), ent("maybe", "benefit"), ent("claimed")]
        rs = [rule("r1", "grants", "perk", H("card")), rule("r2", "grants", "maybe", H("claimed"))]
        s = make_store(es, rs, [holding("h1", "card"), holding("h2", "claimed", "unconfirmed")])
        rep = evaluate(s, "t", D).report()
        self.assertEqual(len(rep["sourced_rules"]), 2)
        self.assertEqual([x["entity"] for x in rep["personal_qualifications"]], ["card", "claimed"])
        self.assertEqual([x["entity"] for x in rep["derived_entitlements"]], ["perk"])
        self.assertEqual(sorted(x["entity"] for x in rep["unresolved"]), ["claimed", "maybe"])


if __name__ == "__main__":
    unittest.main()
