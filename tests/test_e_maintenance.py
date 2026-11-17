"""Acceptance Test E - maintenance: process a bounded change, reject invalid changes, preserve data."""
import json
import os
import shutil
import tempfile
import unittest

from util import H, ent, ev, holding, make_store, rule, write_store
from prices import changes
from prices.cli import main
from prices.engine import ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.store import Store, read_audit

D = "2026-06-01"


def base():
    es = [ent("card", "card"), ent("gold"), ent("perk", "benefit"), ent("other", "benefit")]
    rs = [rule("r-gold", "grants", "gold", H("card")), rule("r-perk", "grants", "perk", H("gold"))]
    return make_store(es, rs, [holding("h-card", "card", valid_to="2027-12-31")])


def cs(id, op, **kw):
    return dict({"id": id, "op": op, "author": "test-maintainer", "date": D, "reason": "test"}, **kw)


def candidate(id="c-new", output="other", when=None, evidence=None, questions=()):
    return {"id": id, "status": "proposed", "created_on": D, "search_path": ["query one"],
            "proposed_rule": {"id": "r-" + id, "kind": "grants", "output": output, "when": when or H("gold"), "summary": "gold gives other"},
            "evidence": [ev("ev-" + id, "official", "Program", D)] if evidence is None else evidence,
            "open_questions": list(questions)}


OWNER = {"by": "Test Owner", "on": D, "statement": "Confirmed from my account page."}


class TestMaintenance(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prices-test-")
        write_store(base(), self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def digest(self):
        return Store.load(self.root).digest()

    def reject(self, c, code):
        before = self.digest()
        out = changes.apply(self.root, c)
        self.assertFalse(out["ok"], c["id"] if isinstance(c, dict) else c)
        self.assertTrue(any(e.startswith(code) for e in out["errors"]), out["errors"])
        self.assertEqual(self.digest(), before, "a rejected changeset must not change any record")
        return out

    # ---- valid bounded changes
    def test_confirm_rule_valid_routine_update(self):
        c = cs("cs-1", "confirm_rule", target="r-gold", data={"review_by": "2027-06-01"},
               evidence=[ev("ev-2", "official", "Program", D)])
        out = changes.apply(self.root, c)
        self.assertTrue(out["ok"], out["errors"])
        r = Store.load(self.root).rules["r-gold"]
        self.assertEqual(r["verification"], {"status": "verified", "last_verified": D, "review_by": "2027-06-01"})
        self.assertEqual(r["evidence"], ["ev1", "ev-2"])
        self.assertFalse(out["review_needed"])
        log = read_audit(self.root)
        self.assertEqual((log[-1]["changeset"], log[-1]["result"]), ("cs-1", "applied"))
        self.assertTrue(os.path.exists(os.path.join(self.root, "data/audit/changesets/cs-1.json")))

    def test_dry_run_writes_nothing(self):
        before = self.digest()
        c = cs("cs-1", "confirm_rule", target="r-gold", data={"review_by": "2027-06-01"}, evidence=[ev("ev-2", "official", "P", D)])
        out = changes.apply(self.root, c, dry_run=True)
        self.assertTrue(out["ok"])
        self.assertEqual(self.digest(), before)
        self.assertEqual(read_audit(self.root), [])

    def test_retire_rule_keeps_history_and_reports_downstream(self):
        was = evaluate(Store.load(self.root), "t", "2026-01-01").have("gold")
        c = cs("cs-2", "retire_rule", target="r-gold", data={"ended_on": "2026-05-31"}, evidence=[ev("ev-3", "official", "P", D)])
        out = changes.apply(self.root, c)
        self.assertTrue(out["ok"], out["errors"])
        self.assertTrue(out["review_needed"])
        changed = {x["atom"]: x["after"] for x in out["impact"]["t"]["changes"]}
        self.assertEqual(changed, {"have:gold": NOT_AVAILABLE, "have:perk": NOT_AVAILABLE})
        s = Store.load(self.root)
        self.assertEqual(s.rules["r-gold"]["verification"]["status"], "retired")   # record preserved
        self.assertEqual(s.rules["r-gold"]["valid_to"], "2026-05-31")
        # CHANGED 2026-11-17 (safety correction): the relationship ended on 2026-05-31, so a question about 2026-01-01 keeps
        # the answer it had. Before, a retired rule was dropped from every date and this line expected NOT_AVAILABLE.
        self.assertEqual((was, evaluate(s, "t", "2026-01-01").have("gold")), (ESTABLISHED, ESTABLISHED))
        self.assertEqual(evaluate(s, "t", "2026-06-01").have("gold"), NOT_AVAILABLE)
        self.assertEqual(s.rules["r-gold"]["verification"]["retired_from"], "verified")

    def test_flag_rule_downgrades_and_flags_dependents(self):
        out = changes.apply(self.root, cs("cs-3", "flag_rule", target="r-gold", data={"open_questions": ["Terms page moved; is enrollment now required?"]}))
        self.assertTrue(out["ok"], out["errors"])
        self.assertTrue(out["review_needed"])
        r = evaluate(Store.load(self.root), "t", D)
        self.assertEqual((r.have("gold"), r.have("perk")), (UNRESOLVED, UNRESOLVED))

    def test_revise_rule_dates(self):
        # CHANGED 2026-11-17 (repair): adding a restriction to a rule that already answered for earlier dates changes those
        # answers, so it is refused unless declared a correction (or made a successor rule). Before, it was accepted as a
        # "first record". The end date alone is still an ordinary revision.
        c = cs("cs-4", "revise_rule", target="r-perk", data={"set": {"valid_to": "2026-12-31", "restrictions": ["Ends with the 2026 programme year"]}},
               evidence=[ev("ev-4", "official", "P", D)])
        self.reject(c, "HISTORY_REWRITE")
        c["data"]["correction"] = "the programme-year limit was in the source from the start and was left out"
        self.assertTrue(changes.apply(self.root, c)["ok"])
        s = Store.load(self.root)
        self.assertEqual(evaluate(s, "t", "2027-01-01").have("perk"), NOT_AVAILABLE)
        # CHANGED 2026-11-17 (safety correction): the restriction just added has no class from a reviewer, so nothing is
        # established through the rule until one records it. Before, this line expected ESTABLISHED straight away.
        self.assertEqual(evaluate(s, "t", D).have("perk"), UNRESOLVED)
        ok = changes.apply(self.root, cs("cs-4b", "classify_conditions", target="r-perk", attestation=OWNER,
                                         data={"items": [{"text": "Ends with the 2026 programme year", "class": "enforced", "enforced_by": [{"valid_to": "2026-12-31"}]}]}))
        self.assertTrue(ok["ok"], ok["errors"])
        self.assertEqual(evaluate(Store.load(self.root), "t", D).have("perk"), ESTABLISHED)

    def test_candidate_is_quarantined_until_promoted(self):
        self.assertTrue(changes.apply(self.root, cs("cs-5", "add_candidate", data={"candidate": candidate()}))["ok"])
        s = Store.load(self.root)
        self.assertNotIn("r-c-new", s.rules)
        self.assertEqual(evaluate(s, "t", D).have("other"), NOT_AVAILABLE)
        self.reject(cs("cs-6", "promote_candidate", target="c-new", data={"review_by": "2027-01-01"}), "ATTESTATION_REQUIRED")
        ok = changes.apply(self.root, cs("cs-7", "promote_candidate", target="c-new", data={"review_by": "2027-01-01"}, attestation=OWNER))
        self.assertTrue(ok["ok"], ok["errors"])
        s = Store.load(self.root)
        self.assertEqual(evaluate(s, "t", D).have("other"), ESTABLISHED)
        self.assertEqual(s.candidates["c-new"]["status"], "promoted")

    def test_promotion_needs_adequate_evidence_and_closed_questions(self):
        weak = candidate("c-weak", evidence=[ev("ev-w", "community", "Forum", D)])
        self.assertTrue(changes.apply(self.root, cs("cs-8", "add_candidate", data={"candidate": weak}))["ok"])
        self.reject(cs("cs-9", "promote_candidate", target="c-weak", data={"review_by": "2027-01-01"}, attestation=OWNER), "INSUFFICIENT_EVIDENCE")
        self.assertTrue(changes.apply(self.root, cs("cs-9b", "reject_candidate", target="c-weak"))["ok"])
        openq = candidate("c-open", questions=["Does this need registration?"])
        self.assertTrue(changes.apply(self.root, cs("cs-10", "add_candidate", data={"candidate": openq}))["ok"])
        self.reject(cs("cs-11", "promote_candidate", target="c-open", data={"review_by": "2027-01-01"}, attestation=OWNER), "OPEN_QUESTIONS")

    def test_only_named_reviewers_may_promote(self):
        s = Store.load(self.root)
        s.files["data/kb/vocab.json"] = dict(s.files["data/kb/vocab.json"], promotion_reviewers=["Test Owner"])
        s.save(self.root, ["data/kb/vocab.json"])
        self.assertTrue(changes.apply(self.root, cs("cs-40", "add_candidate", data={"candidate": candidate()}))["ok"])
        me = {"by": "test-maintainer", "on": D, "statement": "Looks right to me."}
        self.reject(cs("cs-41", "promote_candidate", target="c-new", data={"review_by": "2027-01-01"}, attestation=me), "REVIEWER_NOT_AUTHORIZED")
        self.assertTrue(changes.apply(self.root, cs("cs-42", "promote_candidate", target="c-new", data={"review_by": "2027-01-01"}, attestation=OWNER))["ok"])

    def test_same_source_can_support_two_rules_but_cannot_be_rewritten(self):
        shared = ev("ev-shared", "official", "Program", D)
        a, b = candidate("c-a", evidence=[shared]), candidate("c-b", output="perk", when=H("card"), evidence=[shared])
        for i, c in enumerate((a, b)):
            self.assertTrue(changes.apply(self.root, cs("cs-5%d" % i, "add_candidate", data={"candidate": c}))["ok"])
            out = changes.apply(self.root, cs("cs-6%d" % i, "promote_candidate", target=c["id"], data={"review_by": "2027-01-01"}, attestation=OWNER))
            self.assertTrue(out["ok"], out["errors"])
        altered = dict(shared, summary="something else entirely")
        self.reject(cs("cs-70", "add_evidence", target="r-gold", evidence=[altered]), "EVIDENCE_ID_EXISTS")

    def test_holding_confirmation_requires_owner(self):
        h = {"id": "h-gold", "entity": "gold", "state": "confirmed", "valid_to": "2027-02-28"}
        self.reject(cs("cs-12", "set_holding", profile="t", data={"holding": h}), "ATTESTATION_REQUIRED")
        imposter = {"by": "test-maintainer", "on": D, "statement": "I am sure."}
        self.reject(cs("cs-13", "set_holding", profile="t", data={"holding": h}, attestation=imposter), "OWNER_ATTESTATION_REQUIRED")
        self.assertTrue(changes.apply(self.root, cs("cs-14", "set_holding", profile="t", data={"holding": h}, attestation=OWNER))["ok"])
        self.assertEqual(Store.load(self.root).profile("t").holdings["h-gold"]["confirmed_by"], "Test Owner")
        unconf = {"id": "h-x", "entity": "other", "state": "unconfirmed"}
        self.assertTrue(changes.apply(self.root, cs("cs-15", "set_holding", profile="t", data={"holding": unconf}))["ok"])
        self.assertEqual(evaluate(Store.load(self.root), "t", D).have("other"), UNRESOLVED)

    def test_end_holding_preserves_record(self):
        out = changes.apply(self.root, cs("cs-16", "end_holding", profile="t", target="h-card", data={"ended_on": "2026-05-15"}, attestation=OWNER))
        self.assertTrue(out["ok"], out["errors"])
        self.assertTrue(out["review_needed"])
        h = Store.load(self.root).profile("t").holdings["h-card"]
        self.assertEqual((h["state"], h["valid_to"], h["entity"]), ("ended", "2026-05-15", "card"))

    def test_observations_are_temporary(self):
        o = {"id": "promo-1", "type": "promotion", "summary": "30% transfer bonus", "tags": ["region:japan"], "checked_on": D,
             "valid_to": "2026-06-30", "url": "https://example.invalid/p", "publisher": "Program"}
        self.assertTrue(changes.apply(self.root, cs("cs-17", "add_observation", data={"observation": o}))["ok"])
        self.assertEqual(len(Store.load(self.root).rules), 2)   # a promotion never becomes a rule
        late = cs("cs-18", "prune_observations")
        late["date"] = "2026-07-15"
        self.assertTrue(changes.apply(self.root, late)["ok"])
        self.assertEqual(Store.load(self.root).observations, {})
        self.assertFalse(os.path.exists(os.path.join(self.root, "data/observations/promo-1.json")))
        avail = dict(o, id="avail-1", type="availability")
        self.reject(cs("cs-19", "add_observation", data={"observation": avail}), "ATTESTATION_REQUIRED")

    # ---- invalid changes: every one must be rejected and leave records untouched
    def test_rejects_malformed(self):
        self.reject({"id": "cs-20", "op": "confirm_rule"}, "SCHEMA")
        self.reject(cs("cs-21", "delete_everything"), "SCHEMA")
        self.reject(cs("cs-22", "confirm_rule", target="r-gold", surprise=True), "SCHEMA")
        bad_date = cs("cs-23", "flag_rule", target="r-gold", data={"open_questions": ["q"]})
        bad_date["date"] = "June 1st"
        self.reject(bad_date, "SCHEMA")

    def test_rejects_unknown_target(self):
        self.reject(cs("cs-24", "flag_rule", target="r-nope", data={"open_questions": ["q"]}), "UNKNOWN_TARGET")

    def test_rejects_confirmation_without_adequate_evidence(self):
        self.reject(cs("cs-25", "confirm_rule", target="r-gold", data={"review_by": "2027-06-01"}), "EVIDENCE_REQUIRED")
        self.reject(cs("cs-26", "confirm_rule", target="r-gold", data={"review_by": "2027-06-01"},
                       evidence=[ev("ev-b", "community", "Forum", D)]), "INSUFFICIENT_EVIDENCE")
        self.reject(cs("cs-27", "confirm_rule", target="r-gold", data={"review_by": "2027-06-01"},
                       evidence=[ev("ev-old", "official", "P", "2025-01-01")]), "STALE_EVIDENCE")
        self.reject(cs("cs-28", "confirm_rule", target="r-gold", data={"review_by": "2031-06-01"},
                       evidence=[ev("ev-c", "official", "P", D)]), "BAD_DATES")

    def test_rejects_structural_edit_of_a_rule(self):
        c = cs("cs-29", "revise_rule", target="r-gold", data={"set": {"when": H("perk")}}, evidence=[ev("ev-d", "official", "P", D)])
        self.reject(c, "FIELD_NOT_REVISABLE")
        c2 = cs("cs-30", "revise_rule", target="r-gold", data={"set": {"verification": {"status": "verified"}}}, evidence=[ev("ev-e", "official", "P", D)])
        self.reject(c2, "FIELD_NOT_REVISABLE")

    def test_rejects_change_that_breaks_references(self):
        bad = candidate("c-bad", output="ghost")
        self.reject(cs("cs-31", "add_candidate", data={"candidate": bad}), "UNKNOWN_REFERENCE")

    def test_rejects_duplicate_relationship_and_replay(self):
        dup = candidate("c-dup", output="perk", when=H("gold"))
        self.reject(cs("cs-32", "add_candidate", data={"candidate": dup}), "DUPLICATE_RELATIONSHIP")
        c = cs("cs-33", "flag_rule", target="r-perk", data={"open_questions": ["q"]})
        self.assertTrue(changes.apply(self.root, c)["ok"])
        self.reject(c, "DUPLICATE_CHANGESET")

    def test_rejects_evidence_overwrite(self):
        self.reject(cs("cs-34", "add_evidence", target="r-gold", evidence=[ev("ev1", "official", "P", D)]), "EVIDENCE_ID_EXISTS")

    def test_rejections_are_audited(self):
        self.reject(cs("cs-35", "flag_rule", target="r-nope", data={"open_questions": ["q"]}), "UNKNOWN_TARGET")
        self.assertEqual(read_audit(self.root)[-1]["result"], "rejected")

    def test_cli_rejects_unreadable_file_and_reports_errors(self):
        p = os.path.join(self.root, "broken.json")
        with open(p, "w") as f:
            f.write("{not json")
        before = self.digest()
        self.assertEqual(main(["--root", self.root, "apply", p]), 2)
        with open(p, "w") as f:
            json.dump(cs("cs-36", "flag_rule", target="r-nope", data={"open_questions": ["q"]}), f)
        self.assertEqual(main(["--root", self.root, "apply", p]), 2)
        self.assertEqual(self.digest(), before)
        self.assertEqual(main(["--root", self.root, "lint"]), 0)

    def test_refuses_to_build_on_an_invalid_store(self):
        with open(os.path.join(self.root, "data/kb/rules/r-gold.json"), "w") as f:
            f.write('{"id": "r-gold"}')
        out = changes.apply(self.root, cs("cs-37", "flag_rule", target="r-perk", data={"open_questions": ["q"]}))
        self.assertFalse(out["ok"])
        self.assertTrue(out["errors"][0].startswith("STORE_ALREADY_INVALID"))


if __name__ == "__main__":
    unittest.main()
