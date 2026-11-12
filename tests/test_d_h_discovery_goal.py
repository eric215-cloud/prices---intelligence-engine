"""Mechanics behind Test D (discovery) and Test H (goal query). Live-data evidence for D is in test_live_data.py."""
import unittest

from util import H, ent, ev, holding, make_store, rule
from prices import changes, discovery, goals
from prices.engine import evaluate

D = "2026-06-01"


def base():
    es = [ent("hotel.top", name="Hotel Top Tier", program="hotel"), ent("hotel", "program"),
          ent("air.silver", name="Air Silver", program="air"), ent("air", "program"),
          ent("card.plat", "card", name="Plat Card", program="bank"), ent("bank", "program"),
          ent("lounge", "benefit", name="Lounge Access"), ent("far.status", name="Far Status")]
    rs = [rule("combo", "grants", "lounge", {"all": [H("card.plat"), H("air.silver")]})]
    return make_store(es, rs, [holding("h1", "hotel.top", valid_to="2027-02-28"), holding("h2", "card.plat")])


def cand(id, output, when, mentions=()):
    return {"id": id, "status": "proposed", "created_on": D, "search_path": ["q"], "open_questions": [], "mentions": list(mentions),
            "proposed_rule": {"id": "r-" + id, "kind": "acquire", "output": output, "when": when, "summary": "s",
                              "retention": {"mode": "unknown"}},
            "evidence": [ev("ev-" + id, "official", "P", D)]}


class TestDiscovery(unittest.TestCase):
    def test_forward_plan_covers_every_holding_question_cell(self):
        tasks = discovery.plan_forward(base(), "t", D)
        self.assertEqual([t["cell"] for t in tasks], ["card.plat|card_benefits", "hotel.top|status_match_out"])
        self.assertIn("Hotel Top Tier", tasks[1]["ask"])
        self.assertEqual(tasks[1]["suggested_queries"], ["Hotel Top Tier status match"])

    def test_recorded_cells_drop_out_then_go_stale(self):
        s = base()
        run = {"id": "run-1", "date": D, "mode": "forward", "profile": "t", "executor": "test", "tasks": [], "steps": [{"query": "q", "finding": "none"}],
               "cells": [{"cell": "hotel.top|status_match_out", "outcome": "nothing_found", "note": "searched official partner page"}]}
        out = changes.stage(s, {"id": "cs-run", "op": "record_discovery_run", "author": "t", "date": D, "reason": "r", "data": {"run": run}})
        self.assertTrue(out["ok"], out["errors"])
        s2 = out["store"]
        self.assertEqual([t["cell"] for t in discovery.plan_forward(s2, "t", D)], ["card.plat|card_benefits"])
        self.assertEqual(len(discovery.plan_forward(s2, "t", "2027-06-01", max_age=180)), 1)  # hotel.top expired by then
        self.assertEqual(len(discovery.plan_forward(s2, "t", "2027-01-15", max_age=180)), 2)  # cell is stale again
        self.assertEqual(discovery.coverage_summary(s2, "t", D)["nothing_found"], 1)

    def test_found_outcome_must_cite_candidates(self):
        run = {"id": "run-2", "date": D, "mode": "forward", "profile": "t", "executor": "test", "tasks": [], "steps": [{"query": "q", "finding": "f"}],
               "cells": [{"cell": "hotel.top|status_match_out", "outcome": "found"}]}
        out = changes.stage(base(), {"id": "cs", "op": "record_discovery_run", "author": "t", "date": D, "reason": "r", "data": {"run": run}})
        self.assertFalse(out["ok"])

    def test_frontier_expands_through_reachable_entities(self):
        s = base()
        s.files["data/kb/rules/m.json"] = rule("m", "acquire", "air.silver", H("hotel.top"), retention={"mode": "fixed_term"})
        cells = [t["cell"] for t in discovery.plan_forward(s, "t", D)]
        self.assertIn("air.silver|status_match_out", cells)   # not held yet, but reachable: its onward links get researched too

    def test_backward_regression_and_gap_tasks(self):
        b = discovery.plan_backward(base(), "t", "lounge", D)
        route = b["tree"]["routes"][0]
        self.assertEqual(route["rule"], "combo")
        needs = {n["entity"]: n["status"] for n in route["needs"]}
        self.assertEqual(needs, {"air.silver": "NOT_AVAILABLE", "card.plat": "ESTABLISHED"})
        self.assertEqual([t["cell"] for t in b["tasks"]], ["air.silver|inbound_paths"])

    def test_bridge_near_miss_and_pairs(self):
        b = discovery.plan_bridge(base(), "t", D)
        self.assertEqual(b["near_misses"], [{"rule": "combo", "output": "lounge", "verification": "verified", "satisfied": ["card.plat"],
                                             "missing": [{"entity": "air.silver", "status": "NOT_AVAILABLE"}]}])
        self.assertEqual([t["cell"] for t in b["tasks"]], ["card.plat+hotel.top|combined_with"])

    def test_exploratory_unreached_and_mentions(self):
        s = base()
        s.files["data/candidates/c1.json"] = cand("c1", "air.silver", H("hotel.top"), mentions=["Zed Rewards", "Hotel Top Tier"])
        cells = [t["cell"] for t in discovery.plan_exploratory(s, "t", D)]
        self.assertIn("far.status|inbound_paths", cells)
        self.assertIn("mention:zed-rewards|identify", cells)
        self.assertNotIn("mention:hotel-top-tier|identify", cells)   # already modelled

    def test_novelty_ignores_wording(self):
        s = base()
        s.files["data/kb/vocab.json"] = dict(s.files["data/kb/vocab.json"], seeded_signatures=["acquire:hotel.top->far.status"])
        same_as_rule = dict(cand("x1", "lounge", {"all": [H("air.silver"), H("card.plat")]}))
        same_as_rule["proposed_rule"]["kind"] = "grants"
        same_as_rule["proposed_rule"].pop("retention")
        same_as_rule["proposed_rule"]["summary"] = "Completely different wording of the same relationship"
        self.assertFalse(discovery.novelty(s, same_as_rule)["novel"])
        self.assertFalse(discovery.novelty(s, cand("x2", "far.status", H("hotel.top")))["novel"])   # replay of a seed
        wider = cand("x4", "far.status", {"any": [H("hotel.top"), H("card.plat")]})
        self.assertFalse(discovery.novelty(s, wider)["novel"])                                      # seed with an extra alternative
        self.assertTrue(discovery.novelty(s, cand("x3", "air.silver", H("hotel.top")))["novel"])


class TestGoal(unittest.TestCase):
    def store(self):
        es = [ent("pts", "currency", name="Bank Points"), ent("miles", "currency", name="Air Miles"),
              ent("card", "card"), ent("link", "action", name="Link accounts", how="Link in the app"),
              ent("cap.biz", "capability", name="Business award to Japan with Air Miles", tags=["region:japan", "cabin:business", "type:flight"],
                  economics={"points": 60000, "currency": "pts", "cash_note": "plus carrier fees"}),
              ent("cap.eco", "capability", name="Economy award to Japan", tags=["region:japan", "cabin:economy", "type:flight"]),
              ent("cap.other", "capability", name="Business award via other programme", tags=["region:japan", "cabin:business"]),
              ent("cap.maybe", "capability", name="Business award via rumoured partner", tags=["region:japan", "cabin:business"])]
        rs = [rule("t1", "transfer", "miles", {"all": [H("pts"), H("link")]}, transfer={"from": "pts", "ratio": "1:1"}),
              rule("b1", "grants", "cap.biz", H("miles")), rule("b2", "grants", "cap.eco", H("miles")),
              rule("b3", "grants", "cap.maybe", H("pts"), status="unverified")]
        obs = [{"id": "p-now", "type": "promotion", "summary": "25% transfer bonus", "tags": ["region:japan"], "checked_on": D,
                "valid_to": "2026-06-30", "url": "https://example.invalid/a", "publisher": "P"},
               {"id": "p-old", "type": "promotion", "summary": "expired bonus", "tags": ["region:japan"], "checked_on": "2026-01-01",
                "valid_to": "2026-02-01", "url": "https://example.invalid/b", "publisher": "P"}]
        s = make_store(es, rs, [holding("h1", "pts", quantity=120000), holding("h2", "card")], observations=obs)
        s.files["profiles/t/profile.json"]["valuations"] = {"pts": 1.5}
        return s

    def test_goal_tags_from_text(self):
        self.assertEqual(goals.goal_tags(self.store(), "Find promising ways for me to fly business class to Japan"),
                         ["cabin:business", "region:japan", "type:flight"])

    def test_sections_are_separated_and_qualified(self):
        g = goals.run_goal(self.store(), "t", "fly business class to Japan", D)
        self.assertEqual(g["established"], [])
        self.assertEqual([p["entity"] for p in g["conditional"]], ["cap.biz"])
        p = g["conditional"][0]
        self.assertEqual([s["entity"] for s in p["steps"]], ["link"])
        self.assertEqual(p["rules"], ["b1", "t1"])
        self.assertEqual(p["economics"]["points_value_usd"], 900.0)
        self.assertEqual(p["economics"]["funded_by"], ["pts"])
        research = {x["entity"]: x for x in g["research"]}
        self.assertEqual(research["cap.maybe"]["status"], "UNRESOLVED")          # unverified rule: research, not a pathway
        self.assertEqual(research["cap.other"]["status"], "NOT_AVAILABLE")
        self.assertNotIn("cap.eco", [x["entity"] for s in ("established", "conditional", "research") for x in g[s]])  # wrong cabin
        self.assertEqual([x["id"] for x in g["promotions"]], ["p-now"])           # expired promotion is not shown
        self.assertEqual(g["available"], [])
        self.assertTrue(any("No verified availability" in n for n in g["notes"]))
        self.assertTrue(any("SYNTHETIC" in n for n in g["notes"]))

    def test_established_after_action_done(self):
        s = self.store()
        s.files["profiles/t/holdings/h3.json"] = holding("h3", "link")
        g = goals.run_goal(s, "t", "fly business class to Japan", D)
        self.assertEqual([p["entity"] for p in g["established"]], ["cap.biz"])
        self.assertEqual(evaluate(s, "t", D).have("miles"), "ESTABLISHED")

    def test_unknown_goal_says_so(self):
        g = goals.run_goal(self.store(), "t", "buy a kayak", D)
        self.assertEqual(g["tags"], [])
        self.assertTrue(g["notes"])


if __name__ == "__main__":
    unittest.main()
