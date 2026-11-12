"""Acceptance Test B - temporal integrity: acquisition vs retention, expiry, downstream review.

Includes the brief's illustrative case (hotel top tier -> airline status -> downstream
opportunity). The case is run under every retention mode and again with unrelated
names, to show the outcome comes from the rules, not from hardcoded conclusions.
"""
import unittest

from util import H, ent, flag_codes, holding, make_store, metric, rule
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.review import review, timeline

BEFORE, AFTER_SRC, AFTER_ALL = "2026-12-01", "2027-03-15", "2028-01-05"


def case(retention, src="marriott.titanium", mid="aeroplan.25k", far="hyatt.opportunity", acquired=True, metrics=()):
    es = [ent(src), ent(mid), ent(far, "benefit")]
    rs = [rule("match", "acquire", mid, H(src), retention=retention),
          rule("onward", "grants", far, H(mid))]
    hs = [holding("h-src", src, valid_to="2027-02-28")]
    if acquired:
        hs.append(holding("h-mid", mid, acquired_via="match", acquired_on="2026-10-01", valid_to="2027-12-31"))
    return make_store(es, rs, hs, metrics)


class TestTemporal(unittest.TestCase):
    def test_all_established_while_source_is_held(self):
        for mode in ("fixed_term", "while_qualified", "unknown"):
            r = evaluate(case({"mode": mode}), "t", BEFORE)
            self.assertEqual((r.have("aeroplan.25k"), r.have("hyatt.opportunity")), (ESTABLISHED, ESTABLISHED), mode)
            self.assertEqual(r.basis("have:aeroplan.25k"), "personal")

    def test_fixed_term_survives_loss_of_source(self):
        r = evaluate(case({"mode": "fixed_term"}), "t", AFTER_SRC)
        self.assertEqual(r.have("marriott.titanium"), NOT_AVAILABLE)
        self.assertEqual(r.have("aeroplan.25k"), ESTABLISHED)
        self.assertEqual(r.have("hyatt.opportunity"), ESTABLISHED)
        self.assertIn("EXPIRED_HOLDING", flag_codes(r))
        self.assertIn("SOURCE_LAPSED_FIXED_TERM", flag_codes(r))
        self.assertEqual(r.status("can_get:aeroplan.25k"), NOT_AVAILABLE)  # could not re-acquire today

    def test_while_qualified_is_flagged_not_terminated(self):
        r = evaluate(case({"mode": "while_qualified"}), "t", AFTER_SRC)
        self.assertEqual(r.have("aeroplan.25k"), UNRESOLVED)       # neither kept as fact nor silently deleted
        self.assertEqual(r.have("hyatt.opportunity"), UNRESOLVED)  # downstream inherits the doubt
        f = [x for x in r.flags if x["code"] == "RETENTION_CONDITION_FAILED"]
        self.assertEqual(len(f), 1)
        self.assertIn("have:hyatt.opportunity", f[0]["detail"])    # downstream consequence is named
        self.assertTrue(any("retention needs confirmation" in u for u in r.tokens("have:aeroplan.25k")["unknowns"]))

    def test_unknown_retention_terms_are_unresolved(self):
        r = evaluate(case({"mode": "unknown"}), "t", AFTER_SRC)
        self.assertEqual(r.have("aeroplan.25k"), UNRESOLVED)
        self.assertIn("RETENTION_TERMS_UNKNOWN", flag_codes(r))

    def test_separate_retention_condition(self):
        ret = {"mode": "while_qualified", "retain_when": {"metric": "segments", "gte": 4}}
        kept = evaluate(case(ret, metrics=[metric("segments", 5)]), "t", AFTER_SRC)
        self.assertEqual(kept.have("aeroplan.25k"), ESTABLISHED)   # keeps status on its own terms, source gone
        lost = evaluate(case(ret, metrics=[metric("segments", 1)]), "t", AFTER_SRC)
        self.assertEqual(lost.have("aeroplan.25k"), UNRESOLVED)
        self.assertIn("RETENTION_CONDITION_FAILED", flag_codes(lost))

    def test_own_expiry_ends_it_under_every_mode(self):
        for mode in ("fixed_term", "while_qualified", "unknown"):
            r = evaluate(case({"mode": mode}), "t", AFTER_ALL)
            self.assertEqual((r.have("aeroplan.25k"), r.have("hyatt.opportunity")), (NOT_AVAILABLE, NOT_AVAILABLE), mode)

    def test_never_acquired_means_only_eligible(self):
        s = case({"mode": "fixed_term"}, acquired=False)
        r = evaluate(s, "t", BEFORE)
        self.assertEqual(r.status("can_get:aeroplan.25k"), ESTABLISHED)
        self.assertEqual(r.have("aeroplan.25k"), CONDITIONAL)
        self.assertEqual(evaluate(s, "t", AFTER_SRC).have("aeroplan.25k"), NOT_AVAILABLE)

    def test_not_hardcoded_same_outcome_with_other_names(self):
        for mode, expect in (("fixed_term", ESTABLISHED), ("while_qualified", UNRESOLVED), ("unknown", UNRESOLVED)):
            r = evaluate(case({"mode": mode}, "zz.alpha", "qq.beta", "kk.gamma"), "t", AFTER_SRC)
            self.assertEqual((r.have("qq.beta"), r.have("kk.gamma")), (expect, expect), mode)

    def test_review_lists_changes_and_downstream(self):
        rv = review(case({"mode": "while_qualified"}), "t", BEFORE, AFTER_SRC)
        changed = {c["atom"]: (c["before"], c["after"]) for c in rv["changes"]}
        self.assertEqual(changed["have:marriott.titanium"], (ESTABLISHED, NOT_AVAILABLE))
        self.assertEqual(changed["have:aeroplan.25k"], (ESTABLISHED, UNRESOLVED))
        src = [c for c in rv["changes"] if c["atom"] == "have:marriott.titanium"][0]
        self.assertIn("have:aeroplan.25k", src["downstream_before"])
        self.assertIn("have:hyatt.opportunity", src["downstream_before"])
        self.assertIn("RETENTION_CONDITION_FAILED", {f["code"] for f in rv["new_flags"]})

    def test_fixed_term_review_reports_no_downstream_loss(self):
        rv = review(case({"mode": "fixed_term"}), "t", BEFORE, AFTER_SRC)
        changed = {c["atom"] for c in rv["changes"]}
        self.assertIn("have:marriott.titanium", changed)
        self.assertNotIn("have:aeroplan.25k", changed)
        self.assertNotIn("have:hyatt.opportunity", changed)

    def test_timeline_finds_each_boundary(self):
        ev = timeline(case({"mode": "fixed_term"}), "t", BEFORE, "2028-06-01")
        self.assertEqual([e["date"] for e in ev], ["2027-03-01", "2028-01-01"])

    def test_rule_validity_window(self):
        es = [ent("card", "card"), ent("promo", "benefit")]
        rs = [rule("r", "grants", "promo", H("card"), valid_from="2026-03-01", valid_to="2026-09-30")]
        s = make_store(es, rs, [holding("h", "card")])
        self.assertEqual(evaluate(s, "t", "2026-02-01").have("promo"), NOT_AVAILABLE)
        self.assertEqual(evaluate(s, "t", "2026-06-01").have("promo"), ESTABLISHED)
        self.assertEqual(evaluate(s, "t", "2026-10-01").have("promo"), NOT_AVAILABLE)

    def test_activation_expires(self):
        es = [ent("card", "card"), ent("enroll", "action"), ent("gold")]
        rs = [rule("r", "grants", "gold", {"all": [H("card"), H("enroll")]})]
        s = make_store(es, rs, [holding("h1", "card"), holding("h2", "enroll", valid_to="2026-12-31")])
        self.assertEqual(evaluate(s, "t", "2026-06-01").have("gold"), ESTABLISHED)
        self.assertEqual(evaluate(s, "t", "2027-01-01").have("gold"), CONDITIONAL)  # must re-enroll

    def test_retired_source_rule_keeps_history(self):
        s = case({"mode": "fixed_term"})
        s.files["data/kb/rules/match.json"]["verification"]["status"] = "retired"
        r = evaluate(s, "t", BEFORE)
        self.assertEqual(r.have("aeroplan.25k"), ESTABLISHED)            # already acquired, own dates stand
        self.assertEqual(r.status("can_get:aeroplan.25k"), NOT_AVAILABLE)  # but nobody new can acquire it


if __name__ == "__main__":
    unittest.main()
