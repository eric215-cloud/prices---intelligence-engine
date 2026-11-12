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
        self.assertEqual(evaluate(self.s, "synthetic-demo", "2026-11-12").have("oneworld.ruby"), "CONDITIONAL")

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
        g = goals.run_goal(self.s, "synthetic-demo", "Find promising ways for me to fly business class to Japan", "2026-11-12")
        self.assertEqual({p["entity"] for p in g["established"]},
                         {"cap.japan-business.ana-via-aeroplan", "cap.japan-business.jal-via-jal-miles"})
        self.assertEqual([p["entity"] for p in g["conditional"]], ["jal.crystal"])
        self.assertIn("cap.japan-business.ana-via-ana-miles", [p["entity"] for p in g["research"]])
        self.assertEqual(g["available"], [])      # nothing invented
        self.assertEqual(g["promotions"], [])     # expired sale was not stored
        for p in g["established"]:
            self.assertTrue(p["evidence"])


if __name__ == "__main__":
    unittest.main()
