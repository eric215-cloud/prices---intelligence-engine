"""Acceptance Tests C (evidence integrity) and I (circular dependency integrity)."""
import unittest

from util import H, codes, ent, ev, flag_codes, holding, make_store, rule
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint

D = "2026-06-01"
STRICT = {"evidence_policy": {"primary_types": ["official"], "secondary_types": ["reputable_secondary"], "secondary_min": 2},
          "tags": {}, "questions": {}}


def cand(id, output, when, **kw):
    return dict({"id": id, "status": "proposed", "created_on": "2026-05-01",
                 "proposed_rule": {"id": "r-" + id, "kind": "grants", "output": output, "when": when, "summary": "candidate"},
                 "evidence": [], "search_path": ["q"], "open_questions": []}, **kw)


class TestEvidenceIntegrity(unittest.TestCase):
    def test_unverified_rule_cannot_establish(self):
        s = make_store([ent("card", "card"), ent("x", "benefit")],
                       [rule("r", "grants", "x", H("card"), status="unverified")], [holding("h", "card")])
        r = evaluate(s, "t", D)
        self.assertEqual(r.have("x"), UNRESOLVED)
        self.assertIn("rule r is unverified", r.tokens("have:x")["unknowns"])

    def test_unconfirmed_holding_cannot_establish(self):
        s = make_store([ent("card", "card"), ent("x", "benefit")],
                       [rule("r", "grants", "x", H("card"))], [holding("h", "card", "unconfirmed")])
        r = evaluate(s, "t", D)
        self.assertEqual((r.have("card"), r.have("x")), (UNRESOLVED, UNRESOLVED))
        self.assertIn("UNCONFIRMED_HOLDING", flag_codes(r))

    def test_unsupported_intermediate_blocks_whole_chain(self):
        es = [ent("a"), ent("b"), ent("c"), ent("d", "benefit")]
        rs = [rule("r1", "grants", "b", H("a")), rule("r2", "grants", "c", H("b"), status="unverified"),
              rule("r3", "grants", "d", H("c"))]
        r = evaluate(make_store(es, rs, [holding("h", "a")]), "t", D)
        self.assertEqual([r.have(x) for x in "abcd"], [ESTABLISHED, ESTABLISHED, UNRESOLVED, UNRESOLVED])
        self.assertEqual(r.report()["derived_entitlements"], [{"entity": "b", "name": "b", "steps": [], "unknowns": [], "via": "r1"}])

    def test_unknown_is_not_upgraded_by_actions(self):
        es = [ent("claimed"), ent("enroll", "action"), ent("x", "benefit")]
        rs = [rule("r", "grants", "x", {"all": [H("claimed"), H("enroll")]})]
        r = evaluate(make_store(es, rs, [holding("h", "claimed", "unconfirmed")]), "t", D)
        self.assertEqual(r.have("x"), UNRESOLVED)   # not CONDITIONAL: an unknown remains

    def test_verified_rule_needs_evidence(self):
        es = [ent("card", "card"), ent("x", "benefit")]
        no_ev = make_store(es, [rule("r", "grants", "x", H("card"), evidence=())], vocab=STRICT)
        self.assertIn("INSUFFICIENT_EVIDENCE", codes(lint(no_ev)))
        one_sec = make_store(es, [rule("r", "grants", "x", H("card"), evidence=("e1",))],
                             evidence=[ev("e1", "reputable_secondary", "Blog A")], vocab=STRICT)
        self.assertIn("INSUFFICIENT_EVIDENCE", codes(lint(one_sec)))
        same_pub = make_store(es, [rule("r", "grants", "x", H("card"), evidence=("e1", "e2"))],
                              evidence=[ev("e1", "reputable_secondary", "Blog A"), ev("e2", "reputable_secondary", "blog a ")], vocab=STRICT)
        self.assertIn("INSUFFICIENT_EVIDENCE", codes(lint(same_pub)))
        two_sec = make_store(es, [rule("r", "grants", "x", H("card"), evidence=("e1", "e2"))],
                             evidence=[ev("e1", "reputable_secondary", "Blog A"), ev("e2", "reputable_secondary", "Blog B")], vocab=STRICT)
        self.assertEqual(codes(lint(two_sec)), set())
        official = make_store(es, [rule("r", "grants", "x", H("card"), evidence=("e1",))],
                              evidence=[ev("e1", "official", "Program")], vocab=STRICT)
        self.assertEqual(codes(lint(official)), set())
        community = make_store(es, [rule("r", "grants", "x", H("card"), evidence=("e1", "e2"))],
                               evidence=[ev("e1", "community", "Forum A"), ev("e2", "community", "Forum B")], vocab=STRICT)
        self.assertIn("INSUFFICIENT_EVIDENCE", codes(lint(community)))
        synthetic = make_store(es, [rule("r", "grants", "x", H("card"), evidence=("e1",))],
                               evidence=[ev("e1", "synthetic")], vocab=STRICT)
        self.assertIn("INSUFFICIENT_EVIDENCE", codes(lint(synthetic)))  # synthetic evidence never verifies a live rule

    def test_candidates_never_establish(self):
        es = [ent("card", "card"), ent("x", "benefit")]
        s = make_store(es, [], [holding("h", "card")], candidates=[cand("c1", "x", H("card"))])
        self.assertEqual(evaluate(s, "t", D).have("x"), NOT_AVAILABLE)                      # ignored by default
        self.assertEqual(evaluate(s, "t", D, include_candidates=True).have("x"), UNRESOLVED)  # visible, never established

    def test_stale_rule_is_flagged_loudly(self):
        s = make_store([ent("card", "card"), ent("x", "benefit")],
                       [rule("r", "grants", "x", H("card"), review_by="2026-03-01")], [holding("h", "card")])
        r = evaluate(s, "t", D)
        self.assertIn("STALE_RULE", flag_codes(r))

    def test_dangling_references_are_lint_errors(self):
        s = make_store([ent("x", "benefit")], [rule("r", "grants", "x", H("ghost"), evidence=("nope",))])
        self.assertIn("UNKNOWN_REFERENCE", codes(lint(s)))

    def test_synthetic_confirmation_rejected_in_real_profile(self):
        s = make_store([ent("card", "card")], [], [holding("h", "card")])
        s.files["profiles/t/profile.json"]["synthetic"] = False
        self.assertIn("SYNTHETIC_IN_REAL_PROFILE", codes(lint(s)))


class TestCycles(unittest.TestCase):
    def test_two_cycle_without_foundation(self):
        s = make_store([ent("a"), ent("b")], [rule("r1", "grants", "a", H("b")), rule("r2", "grants", "b", H("a"))])
        r = evaluate(s, "t", D)
        self.assertEqual((r.have("a"), r.have("b")), (NOT_AVAILABLE, NOT_AVAILABLE))

    def test_self_loop(self):
        s = make_store([ent("a")], [rule("r", "grants", "a", H("a"))])
        self.assertEqual(evaluate(s, "t", D).have("a"), NOT_AVAILABLE)

    def test_acquire_cycle_is_not_even_conditional(self):
        ret = {"mode": "fixed_term"}
        s = make_store([ent("a"), ent("b")], [rule("r1", "acquire", "a", H("b"), retention=ret),
                                              rule("r2", "acquire", "b", H("a"), retention=ret)])
        r = evaluate(s, "t", D)
        self.assertEqual((r.have("a"), r.have("b")), (NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertEqual(r.status("can_get:a"), NOT_AVAILABLE)

    def test_cycle_with_unknown_entry_stays_unresolved(self):
        es = [ent("a"), ent("b"), ent("c"), ent("claimed")]
        rs = [rule("r1", "grants", "a", H("c")), rule("r2", "grants", "b", H("a")), rule("r3", "grants", "c", H("b")),
              rule("in", "grants", "a", H("claimed"))]
        r = evaluate(make_store(es, rs, [holding("h", "claimed", "unconfirmed")]), "t", D)
        self.assertEqual([r.have(x) for x in "abc"], [UNRESOLVED] * 3)

    def test_cycle_with_real_foundation_is_fine_and_chain_ends_at_the_fact(self):
        es = [ent("a"), ent("b"), ent("c")]
        rs = [rule("r1", "grants", "b", H("a")), rule("r2", "grants", "c", H("b")), rule("r3", "grants", "a", H("c"))]
        r = evaluate(make_store(es, rs, [holding("h", "a")]), "t", D)
        self.assertEqual([r.have(x) for x in "abc"], [ESTABLISHED] * 3)
        self.assertEqual(r.via["E"]["have:a"][0], "holding:h")     # a rests on the fact, not on the loop
        self.assertEqual(r.chain("have:c")["supports"][0]["supports"][0]["via"], "holding:h")

    def test_every_established_atom_traces_to_a_base_fact(self):
        es = [ent(x) for x in "abcdef"]
        rs = [rule("r1", "grants", "b", H("a")), rule("r2", "grants", "c", {"any": [H("b"), H("e")]}),
              rule("r3", "grants", "d", {"all": [H("c"), H("b")]}), rule("r4", "grants", "e", H("d")),
              rule("r5", "grants", "f", H("f"))]
        r = evaluate(make_store(es, rs, [holding("h", "a")]), "t", D)

        def walk(atom, path):
            self.assertNotIn(atom, path, "derivation loops back on itself")
            via, sup = r.via["E"][atom]
            if not sup:
                self.assertTrue(via.startswith("holding:"), (atom, via))
            for s_ in sup:
                walk(s_, path | {atom})
        for atom in r.best["E"]:
            walk(atom, frozenset())
        self.assertEqual(r.have("f"), NOT_AVAILABLE)

    def test_mutually_dependent_acquired_statuses_cannot_keep_each_other_alive(self):
        ret = {"mode": "while_qualified"}
        es = [ent("x"), ent("y"), ent("perk", "benefit")]
        rs = [rule("mx", "acquire", "x", H("y"), retention=ret), rule("my", "acquire", "y", H("x"), retention=ret),
              rule("p", "grants", "perk", H("x"))]
        hs = [holding("hx", "x", acquired_via="mx", valid_to="2027-12-31"), holding("hy", "y", acquired_via="my", valid_to="2027-12-31")]
        r = evaluate(make_store(es, rs, hs), "t", D)
        self.assertEqual((r.have("x"), r.have("y"), r.have("perk")), (UNRESOLVED, UNRESOLVED, UNRESOLVED))
        self.assertEqual(len([f for f in r.flags if f["code"] == "RETENTION_CONDITION_FAILED"]), 2)
        self.assertEqual(r.report()["derived_entitlements"], [])

    def test_conflicting_condition_never_applies(self):
        es = [ent("a"), ent("x", "benefit")]
        s = make_store(es, [rule("r", "grants", "x", {"all": [H("a"), {"not": H("a")}]})], [holding("h", "a")])
        self.assertIn("CONTRADICTORY_CONDITION", codes(lint(s)))
        self.assertEqual(evaluate(s, "t", D).have("x"), NOT_AVAILABLE)

    def test_conflicting_holding_records_are_not_actionable(self):
        es = [ent("a"), ent("x", "benefit")]
        s = make_store(es, [rule("r", "grants", "x", H("a"))], [holding("h1", "a"), holding("h2", "a", "unconfirmed")])
        r = evaluate(s, "t", D)
        self.assertEqual((r.have("a"), r.have("x")), (UNRESOLVED, UNRESOLVED))
        self.assertIn("CONFLICTING_HOLDINGS", flag_codes(r))

    def test_negation_on_a_cycle_is_rejected_and_ignored(self):
        es = [ent("a"), ent("b"), ent("base")]
        rs = [rule("r1", "grants", "a", {"all": [H("base"), {"not": H("b")}]}), rule("r2", "grants", "b", H("a"))]
        s = make_store(es, rs, [holding("h", "base")])
        self.assertIn("NEGATIVE_CYCLE", codes(lint(s)))
        r = evaluate(s, "t", D)
        self.assertIn("NEGATIVE_CYCLE", flag_codes(r))
        self.assertNotEqual(r.have("a"), ESTABLISHED)

    def test_conditional_needs_real_foundation_too(self):
        es = [ent("a"), ent("b"), ent("act", "action")]
        rs = [rule("r1", "grants", "a", {"all": [H("b"), H("act")]}), rule("r2", "grants", "b", H("a"))]
        r = evaluate(make_store(es, rs), "t", D)
        self.assertEqual((r.have("a"), r.have("b")), (NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertNotEqual(r.have("a"), CONDITIONAL)


if __name__ == "__main__":
    unittest.main()
