"""Relational foundation, part 1: card roles, network-tier baselines, exclusions, upgrades, separate holders.

Rule under test: a network tier never gives a cardholder anything. A tier benefit applies to a
card only through a verified card-level rule backed by evidence about that card. Missing
evidence, or the absence of an opt-out, establishes nothing.
"""
import unittest

from util import H, TEST_VOCAB, codes, ent, ev, holding, make_store, rule
from prices import changes, discovery
from prices.cards import CONFIRMED, EXCLUDED, PENDING, SUPERSEDED, UNPROVEN, architecture, matrix
from prices.engine import ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint

D = "2026-06-01"
CARD_EV = dict(ev("ev-card"), applies_to=["card.a"])     # the card's own guide
NET_EV = dict(ev("ev-net"), applies_to=["tier.t"])       # the network's marketing page


def world(extra_rules=(), holdings=None, evidence=None, extra_entities=()):
    es = [ent("org.bank", "organization"), ent("org.net", "organization"),
          ent("tier.t", "network_tier", network="org.net"),
          ent("card.a", "card", card={"issuer": "org.bank", "network": "org.net", "network_tier": "tier.t", "cobrand_partner": None},
              sources=["ev-card"]),
          ent("card.b", "card", card={"issuer": "org.bank", "network": "org.net", "network_tier": "tier.t"}, sources=["ev-card"]),
          ent("b.phone", "benefit"), ent("b.rental", "benefit"), ent("b.lounge", "benefit"), ent("b.better-rental", "benefit")]
    rs = [rule("base.phone", "baseline", "b.phone", H("tier.t"), evidence=("ev-net",)),
          rule("base.rental", "baseline", "b.rental", H("tier.t"), evidence=("ev-net",)),
          rule("base.lounge", "baseline", "b.lounge", H("tier.t"), evidence=("ev-net",))]
    hs = [holding("h-a", "card.a")] if holdings is None else holdings
    return make_store(es + list(extra_entities), rs + list(extra_rules), hs, evidence=evidence or [CARD_EV, NET_EV])


def standings(store, **kw):
    return {(m["card"], m["benefit"]): m["standing"] for m in matrix(store, D, **kw)}


class TestNoInheritance(unittest.TestCase):
    def test_tier_baseline_gives_the_cardholder_nothing(self):
        s = world()
        self.assertEqual(codes(lint(s)), set())
        r = evaluate(s, "t", D)
        self.assertEqual(r.have("card.a"), ESTABLISHED)
        for b in ("b.phone", "b.rental", "b.lounge"):
            self.assertEqual(r.have(b), NOT_AVAILABLE, b)                     # verified baselines, tier on the card: still nothing
            self.assertEqual(evaluate(s, "t", D, include_candidates=True).have(b), NOT_AVAILABLE)
        self.assertEqual(r.report()["derived_entitlements"], [])
        self.assertEqual(set(standings(s).values()), {UNPROVEN})

    def test_a_tier_cannot_be_held_or_routed_through(self):
        held = world(holdings=[holding("h-a", "card.a"), holding("h-t", "tier.t")])
        self.assertIn("NOT_HOLDABLE", codes(lint(held)))
        bridge = world([rule("card-is-tier", "grants", "tier.t", H("card.a"), evidence=("ev-card",))])
        self.assertIn("TIER_INHERITANCE", codes(lint(bridge)))
        via = world([rule("via-tier", "grants", "b.phone", {"all": [H("card.a"), H("tier.t")]}, evidence=("ev-card",))])
        self.assertIn("TIER_INHERITANCE", codes(lint(via)))
        org = world([rule("via-bank", "grants", "b.phone", H("org.bank"), evidence=("ev-card",))])
        self.assertIn("TIER_INHERITANCE", codes(lint(org)))

    def test_absent_opt_out_is_not_proof(self):
        # "inherits the tier benefit unless the card opted out" is exactly what must not pass
        opt = ent("optout.phone", "benefit")
        r = rule("inherit-unless-optout", "grants", "b.phone", {"all": [H("card.a"), {"not": H("optout.phone")}]}, evidence=("ev-net",))
        s = world([r], extra_entities=[opt])
        self.assertIn("CARD_SPECIFIC_EVIDENCE_REQUIRED", codes(lint(s)))

    def test_network_page_alone_cannot_confirm_a_card_benefit(self):
        s = world([rule("a.phone", "grants", "b.phone", H("card.a"), evidence=("ev-net",))])
        self.assertIn("CARD_SPECIFIC_EVIDENCE_REQUIRED", codes(lint(s)))
        unlabelled = world([rule("a.phone", "grants", "b.phone", H("card.a"), evidence=("ev-x",))],
                           evidence=[CARD_EV, NET_EV, ev("ev-x")])       # a source that does not say which card it is about
        self.assertIn("CARD_SPECIFIC_EVIDENCE_REQUIRED", codes(lint(unlabelled)))

    def test_pipeline_refuses_to_promote_without_card_evidence(self):
        s = world()
        s.files["data/kb/vocab.json"] = dict(TEST_VOCAB)
        cand = {"id": "c1", "status": "proposed", "created_on": D, "search_path": ["q"], "open_questions": [],
                "proposed_rule": {"id": "a.phone", "kind": "grants", "output": "b.phone", "when": H("card.a"), "summary": "claims tier benefit"},
                "evidence": [dict(ev("ev-net2"), applies_to=["tier.t"])]}
        out = changes.stage(s, {"id": "cs1", "op": "add_candidate", "author": "m", "date": D, "reason": "r", "data": {"candidate": cand}})
        self.assertTrue(out["ok"], out["errors"])                               # quarantine accepts weak claims
        att = {"by": "Reviewer", "on": D, "statement": "ok"}
        out2 = changes.stage(out["store"], {"id": "cs2", "op": "promote_candidate", "author": "m", "date": D, "reason": "r", "target": "c1",
                                            "data": {"review_by": "2027-01-01"}, "attestation": att})
        self.assertFalse(out2["ok"])
        self.assertTrue(out2["errors"][0].startswith("CARD_SPECIFIC_EVIDENCE_REQUIRED"), out2["errors"])
        self.assertEqual(evaluate(out["store"], "t", D, include_candidates=True).have("b.phone"), UNRESOLVED)
        self.assertEqual(standings(out["store"])[("card.a", "b.phone")], PENDING)


class TestApplicability(unittest.TestCase):
    def test_positive_card_evidence_confirms(self):
        s = world([rule("a.phone", "grants", "b.phone", H("card.a"), evidence=("ev-card",))])
        self.assertEqual(codes(lint(s)), set())
        self.assertEqual(evaluate(s, "t", D).have("b.phone"), ESTABLISHED)
        st = standings(s)
        self.assertEqual(st[("card.a", "b.phone")], CONFIRMED)
        self.assertEqual(st[("card.b", "b.phone")], UNPROVEN)      # same tier, other card: proves nothing

    def test_exclusion(self):
        s = world([rule("a.no-lounge", "excludes", "b.lounge", H("card.a"), evidence=("ev-card",))])
        self.assertEqual(codes(lint(s)), set())
        self.assertEqual(evaluate(s, "t", D).have("b.lounge"), NOT_AVAILABLE)
        self.assertEqual(standings(s)[("card.a", "b.lounge")], EXCLUDED)
        weak = world([rule("a.no-lounge", "excludes", "b.lounge", H("card.a"), evidence=("ev-net",))])
        self.assertIn("CARD_SPECIFIC_EVIDENCE_REQUIRED", codes(lint(weak)))

    def test_upgrade_replaces_baseline_without_merging(self):
        s = world([rule("a.better", "grants", "b.better-rental", H("card.a"), evidence=("ev-card",), restrictions=["Primary cover"]),
                   rule("a.no-base-rental", "excludes", "b.rental", H("card.a"), evidence=("ev-card",), superseded_by="b.better-rental")])
        self.assertEqual([i for i in lint(s)], [])
        r = evaluate(s, "t", D)
        self.assertEqual((r.have("b.better-rental"), r.have("b.rental")), (ESTABLISHED, NOT_AVAILABLE))
        st = standings(s)
        self.assertEqual(st[("card.a", "b.rental")], SUPERSEDED)
        self.assertEqual(st[("card.a", "b.better-rental")], CONFIRMED)
        rows = {m["benefit"]: m for m in matrix(s, D) if m["card"] == "card.a"}
        self.assertEqual(rows["b.better-rental"]["basis"], "card_specific")
        self.assertIn("b.better-rental", rows["b.rental"]["detail"])

    def test_upgrade_pointing_at_ungranted_benefit_warns(self):
        s = world([rule("a.no-base-rental", "excludes", "b.rental", H("card.a"), evidence=("ev-card",), superseded_by="b.better-rental")])
        self.assertIn("SUPERSEDING_BENEFIT_NOT_GRANTED", {i[1] for i in lint(s)})

    def test_grant_and_exclusion_cannot_both_stand(self):
        both = [rule("a.phone", "grants", "b.phone", H("card.a"), evidence=("ev-card",)),
                rule("a.no-phone", "excludes", "b.phone", H("card.a"), evidence=("ev-card",))]
        self.assertIn("CONFLICTING_APPLICABILITY", codes(lint(world(both))))
        both[0]["valid_to"], both[1]["valid_from"] = "2026-06-30", "2026-07-01"     # benefit removed mid-year: consecutive, not conflicting
        s = world(both)
        self.assertEqual(codes(lint(s)), set())
        self.assertEqual(evaluate(s, "t", "2026-06-15").have("b.phone"), ESTABLISHED)
        self.assertEqual(evaluate(s, "t", "2026-07-15").have("b.phone"), NOT_AVAILABLE)
        self.assertEqual({(m["benefit"], m["standing"]) for m in matrix(s, "2026-07-15") if m["card"] == "card.a" and m["benefit"] == "b.phone"},
                         {("b.phone", EXCLUDED)})

    def test_shapes_are_enforced(self):
        cases = [(rule("x", "baseline", "b.phone", H("card.a"), evidence=("ev-net",)), "BAD_BASELINE_SHAPE"),
                 (rule("x", "baseline", "card.b", H("tier.t"), evidence=("ev-net",)), "BAD_BASELINE_SHAPE"),
                 (rule("x", "excludes", "b.phone", H("tier.t"), evidence=("ev-card",)), "BAD_EXCLUSION_SHAPE"),
                 (rule("x", "excludes", "b.phone", {"all": [H("card.a"), H("card.b")]}, evidence=("ev-card",)), "BAD_EXCLUSION_SHAPE"),
                 (rule("x", "excludes", "b.phone", H("card.a"), evidence=("ev-card",), superseded_by="b.phone"), "BAD_EXCLUSION_SHAPE"),
                 (rule("x", "grants", "b.better-rental", H("card.a"), evidence=("ev-card",), superseded_by="b.rental"), "UNEXPECTED_FIELD")]
        for r, code in cases:
            self.assertIn(code, codes(lint(world([r]))), r)

    def test_unverified_or_candidate_claims_are_pending_not_established(self):
        s = world([rule("a.phone", "grants", "b.phone", H("card.a"), status="unverified", evidence=("ev-card",))])
        self.assertEqual(standings(s)[("card.a", "b.phone")], PENDING)
        self.assertEqual(evaluate(s, "t", D).have("b.phone"), UNRESOLVED)

    def test_retired_baseline_drops_out_of_the_matrix(self):
        s = world()
        s.files["data/kb/rules/base.lounge.json"]["verification"]["status"] = "retired"
        self.assertNotIn(("card.a", "b.lounge"), standings(s))

    def test_baselines_are_not_routes_for_discovery(self):
        b = discovery.plan_backward(world(), "t", "b.phone", D)
        self.assertEqual(b["tree"]["routes"], [])
        self.assertEqual(discovery.plan_bridge(world(), "t", D)["near_misses"], [])

    def test_unproven_pairs_become_research_tasks_for_held_cards_only(self):
        s = world([rule("a.phone", "grants", "b.phone", H("card.a"), evidence=("ev-card",))])
        cells = [t["cell"] for t in discovery.plan_applicability(s, "t", D)]
        self.assertEqual(cells, ["card.a|applies:b.lounge", "card.a|applies:b.rental"])   # card.b is not held; b.phone is settled


class TestRolesAndHolders(unittest.TestCase):
    def test_seven_roles_are_recorded_and_distinguish_unknown_from_none(self):
        arch = {c["card"]: c for c in architecture(world())}
        self.assertEqual(arch["card.a"]["cobrand_partner"], "none")
        self.assertEqual(arch["card.b"]["cobrand_partner"], "(not recorded)")
        self.assertIn("org.bank", arch["card.a"]["issuer"])
        self.assertEqual(arch["card.a"]["capital_provider"], "(not recorded)")

    def test_role_references_are_checked(self):
        def with_card(block, **kw):
            s = world()
            s.files["data/kb/entities/card.a.json"] = ent("card.a", "card", card=block, sources=["ev-card"], **kw)
            return codes(lint(s))
        self.assertIn("BAD_ROLE", with_card({"issuer": "tier.t"}))                     # a tier is not a bank
        self.assertIn("BAD_ROLE", with_card({"network_tier": "org.bank"}))
        self.assertIn("BAD_ROLE", with_card({"issuer": "org.ghost"}))
        s = world(extra_entities=[ent("org.other-net", "organization")])
        s.files["data/kb/entities/card.a.json"]["card"]["network"] = "org.other-net"   # tier belongs to a different network
        self.assertIn("BAD_ROLE", codes(lint(s)))
        s2 = world()
        s2.files["data/kb/entities/b.phone.json"]["card"] = {"issuer": "org.bank"}
        self.assertIn("BAD_ROLE", codes(lint(s2)))
        self.assertIn("SCHEMA", with_card({"issuer": "org.bank", "holder": "eric"}))    # people are never part of a card product

    def test_two_people_are_never_conflated(self):
        s = world([rule("a.phone", "grants", "b.phone", H("card.a"), evidence=("ev-card",)),
                   rule("b.lounge", "grants", "b.lounge", H("card.b"), evidence=("ev-card-b",))],
                  evidence=[CARD_EV, NET_EV, dict(ev("ev-card-b"), applies_to=["card.b"])])
        s.files["profiles/u/profile.json"] = {"id": "u", "label": "second person", "synthetic": True, "owner": "Second Owner"}
        s.files["profiles/u/holdings/h-b.json"] = holding("h-b", "card.b")
        self.assertEqual(codes(lint(s)), set())
        first, second = evaluate(s, "t", D), evaluate(s, "u", D)
        self.assertEqual((first.have("card.a"), first.have("card.b")), (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual((second.have("card.a"), second.have("card.b")), (NOT_AVAILABLE, ESTABLISHED))
        self.assertEqual((first.have("b.phone"), first.have("b.lounge")), (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual((second.have("b.phone"), second.have("b.lounge")), (NOT_AVAILABLE, ESTABLISHED))
        self.assertEqual({m["card"] for m in matrix(s, D, "t")}, {"card.a"})
        self.assertEqual({m["card"] for m in matrix(s, D, "u")}, {"card.b"})
        # ending one person's card changes nothing for the other
        # CHANGED 2026-11-17 (repair): ended_on is the last day the card was held, and an ended holding now keeps answering
        # for its own days. Ending it ON the date asked about therefore changes nothing on that date; it ends the day before
        out = changes.stage(s, {"id": "cs", "op": "end_holding", "author": "m", "date": D, "reason": "r", "profile": "t", "target": "h-a",
                                "data": {"ended_on": "2026-05-31"}, "attestation": {"by": "Test Owner", "on": D, "statement": "closed"}})
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(list(out["impact"]), ["t"])
        self.assertEqual(evaluate(out["store"], "u", D).have("b.lounge"), ESTABLISHED)


if __name__ == "__main__":
    unittest.main()
