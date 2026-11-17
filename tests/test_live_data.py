"""Checks against the live project data (data/ and profiles/), including the evidence trail for Test D.

These tests describe invariants the live knowledge base must always satisfy, plus the
record of the commissioning discovery run. If a later, legitimate change breaks one of
the "commissioning record" tests, update that test in the same commit and say why.
"""
import os
import unittest

import util  # noqa: F401  (sets sys.path)
from prices import discovery, goals
from prices.engine import ESTABLISHED, UNRESOLVED, evaluate
from prices.lint import lint, signature
from prices.store import Store, read_audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestLiveInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Store.load(ROOT)

    def test_lint_is_clean(self):
        self.assertEqual([i for i in lint(self.s) if i[0] == "ERROR"], [])

    def test_no_synthetic_evidence_in_live_kb(self):
        self.assertEqual([e["id"] for e in self.s.evidence.values() if e["source_type"] == "synthetic"], [])
        self.assertNotIn("synthetic", self.s.vocab["evidence_policy"]["primary_types"])

    def test_personal_profile_is_separate_and_makes_no_claims(self):
        eric = self.s.profile("eric")
        self.assertFalse(eric.meta["synthetic"])
        for h in eric.holdings.values():   # anything recorded for Eric must carry his own attestation
            if h["state"] == "confirmed":
                self.assertEqual(h["confirmed_by"], eric.meta["owner"])
        for name in self.s.profile_names():
            if name != "eric":
                self.assertTrue(self.s.profile(name).meta["synthetic"], name)

    def test_every_applied_changeset_is_on_file(self):
        for e in read_audit(ROOT):
            if e["result"] == "applied":
                self.assertTrue(os.path.exists(os.path.join(ROOT, "data/audit/changesets", e["changeset"] + ".json")), e["changeset"])


class TestCommissioningRecord(unittest.TestCase):
    """Test D evidence: a relationship that was not seeded, found by the documented procedure."""

    @classmethod
    def setUpClass(cls):
        cls.s = Store.load(ROOT)

    def test_discovery_run_is_preserved(self):
        run = self.s.discovery_runs["run-20261112-forward-01"]
        self.assertEqual(run["tasks"][0]["cell"], "marriott.titanium|status_match_out")   # the planner asked the question
        self.assertTrue(all(st.get("query") and st.get("finding") for st in run["steps"]))  # search path kept
        self.assertTrue(run["verification"])
        cell = self.s.ledger["cells"]["marriott.titanium|status_match_out"]
        self.assertEqual(cell["outcome"], "found")
        self.assertIn("c-jal-crystal-via-marriott-top-tier", cell["candidates"])

    def test_discovered_rule_is_not_a_seed_and_has_official_evidence(self):
        rule = self.s.rules["jal-crystal-via-marriott-top-tier"]
        seeded_outputs = {s.split("->")[1] for s in self.s.vocab["seeded_signatures"]}
        self.assertNotIn(rule["output"], seeded_outputs)
        self.assertNotIn(signature(rule), self.s.vocab["seeded_signatures"])
        types = {self.s.evidence[e]["source_type"] for e in rule["evidence"]}
        self.assertIn("official", types)
        cand = self.s.candidates["c-jal-crystal-via-marriott-top-tier"]
        self.assertEqual(cand["status"], "promoted")
        self.assertTrue(cand["search_path"])
        self.assertTrue(rule["open_questions"])   # what is still unknown stays visible on the rule

    def test_candidate_went_through_quarantine_before_promotion(self):
        log = [e for e in read_audit(ROOT) if e["result"] == "applied"]
        ops = [e["op"] for e in log]
        self.assertLess(ops.index("add_candidate"), ops.index("promote_candidate"))
        self.assertIn("rejected", {e["result"] for e in read_audit(ROOT)})   # the pipeline did refuse something for real

    def test_second_hop_was_found_by_frontier_expansion(self):
        run = self.s.discovery_runs["run-20261112-forward-02"]
        self.assertEqual(run["tasks"][0]["cell"], "jal.crystal|status_match_out")
        # CHANGED 2026-11-17 (safety correction): was CONDITIONAL. The rule that leads here says in its own text that
        # JAL Global Club members get Sapphire instead, and the rule before it that Crystal "depends on accumulated FLY ON
        # Points, not on the link alone". Neither is checked, and no reviewer has classified them, so the honest answer
        # is UNRESOLVED. The run and the rule are still on file; what changed is how far the engine trusts the text.
        self.assertEqual(evaluate(self.s, "synthetic-demo", "2026-11-12").have("oneworld.ruby"), UNRESOLVED)

    def test_unpromoted_candidates_stay_out_of_established_results(self):
        self.assertEqual(self.s.candidates["c-united-silver-via-marriott-top-tier"]["status"], "proposed")
        self.assertNotIn("united-silver-via-marriott-top-tier", self.s.rules)
        self.assertNotIn("united.premier_silver", self.s.entities)

    def test_replaying_the_seed_is_not_counted_as_discovery(self):
        replay = {"id": "x", "proposed_rule": {"id": "x", "kind": "acquire", "output": "aeroplan.25k",
                                               "when": {"holds": "marriott.titanium"}, "summary": "reworded seed"}}
        self.assertFalse(discovery.novelty(self.s, replay)["novel"])

    def test_illustrative_case_on_real_rules(self):
        # Official terms do not say what happens to a matched Aeroplan 25K when Titanium lapses,
        # so the engine must neither keep it as fact nor delete it.
        before = evaluate(self.s, "synthetic-acquired", "2026-11-12")
        after = evaluate(self.s, "synthetic-acquired", "2027-03-15")
        self.assertEqual(before.have("aeroplan.25k"), ESTABLISHED)
        self.assertEqual(after.have("aeroplan.25k"), UNRESOLVED)
        self.assertIn("RETENTION_TERMS_UNKNOWN", {f["code"] for f in after.flags})

    def test_practical_query(self):
        # CHANGED 2026-11-17 (safety correction): was two established pathways and one conditional. None of the nine
        # verified rules has a reviewer's classification of its restrictions and open questions yet, so nothing is
        # established through them; every pathway is listed as research. TestLiveRulesAwaitReview shows what returns
        # once a reviewer classifies them, and what stays blocked.
        g = goals.run_goal(self.s, "synthetic-demo", "Find promising ways for me to fly business class to Japan", "2026-11-12")
        self.assertEqual(g["established"], [])
        self.assertEqual(g["conditional"], [])
        research = [p["entity"] for p in g["research"]]
        for e in ("cap.japan-business.ana-via-aeroplan", "cap.japan-business.jal-via-jal-miles", "cap.japan-business.ana-via-ana-miles", "jal.crystal"):
            self.assertIn(e, research)
        self.assertEqual(g["available"], [])      # nothing invented
        self.assertEqual(g["promotions"], [])     # expired sale was not stored


class TestLiveRulesAwaitReview(unittest.TestCase):
    """The verified rules predate condition review. Until a reviewer classifies their texts, nothing rests on them."""

    @classmethod
    def setUpClass(cls):
        import shutil
        import sys
        import tempfile
        sys.path.insert(0, os.path.join(ROOT, "experiments", "safety"))
        import proposal
        cls.proposal = proposal
        cls.s = Store.load(ROOT)
        cls.tmp = tempfile.mkdtemp(prefix="prices-live-review-")
        for sub in ("data", "profiles", "tables"):
            shutil.copytree(os.path.join(ROOT, sub), os.path.join(cls.tmp, sub))
        proposal.apply_to_copy(cls.tmp, "2026-11-17")
        cls.copy = Store.load(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_engineering_has_not_classified_the_project_rules(self):
        self.assertEqual([r["id"] for r in self.s.rules.values() if "condition_review" in r], [])
        waiting = sorted(i[2].split("/")[-1][:-5] for i in lint(self.s) if i[1] == "CONDITIONS_NOT_CLASSIFIED")
        self.assertEqual(len(waiting), 9)
        self.assertNotIn("jal-miles-from-marriott-points", waiting)       # it states no restriction and no question

    def test_a_rule_with_nothing_to_classify_still_establishes(self):
        self.assertEqual(evaluate(self.s, "synthetic-demo", "2026-11-12").have("jal.miles"), ESTABLISHED)

    def test_the_proposal_covers_exactly_the_texts_now_on_the_rules(self):
        from prices.conditions import review_issues, texts
        rules = self.proposal.load()
        self.assertEqual(sorted(rules), sorted(r["id"] for r in self.s.rules.values() if texts(r)))
        for rule_id, items in rules.items():
            self.assertEqual(review_issues(self.s.rules[rule_id], items), [], rule_id)

    def test_the_proposal_refuses_to_run_on_the_project(self):
        with self.assertRaises(RuntimeError):
            self.proposal.apply_to_copy(ROOT, "2026-11-17")

    def test_in_a_copy_reviewed_rules_establish_what_is_unaffected(self):
        r = evaluate(self.copy, "synthetic-demo", "2026-11-12")
        for e in ("aeroplan.points", "ana.miles", "jal.miles", "cap.japan-business.ana-via-aeroplan"):
            self.assertEqual(r.have(e), ESTABLISHED, e)
        self.assertEqual([i for i in lint(self.copy) if i[1] == "CONDITIONS_NOT_CLASSIFIED"], [])

    def test_in_a_copy_known_unchecked_conditions_still_block(self):
        # each of these was ESTABLISHED or CONDITIONAL before the correction, on text the engine never checked
        r = evaluate(self.copy, "synthetic-demo", "2026-11-12")
        for e in ("cap.japan-business.jal-via-jal-miles",        # the JAL account must be 60 days old: not recorded anywhere
                  "jal.crystal",                                 # depends on FLY ON Points, not on the link alone
                  "oneworld.ruby",                               # JAL Global Club members get Sapphire instead
                  "aeroplan.25k"):                               # trial or temporary Marriott status does not qualify
            self.assertEqual(r.have(e), UNRESOLVED, e)
        g = goals.run_goal(self.copy, "synthetic-demo", "Find promising ways for me to fly business class to Japan", "2026-11-12")
        self.assertEqual([p["entity"] for p in g["established"]], ["cap.japan-business.ana-via-aeroplan"])
        self.assertTrue(all(p["evidence"] for p in g["established"]))
        self.assertIn("cap.japan-business.jal-via-jal-miles", [p["entity"] for p in g["research"]])

if __name__ == "__main__":
    unittest.main()
