"""Adversarial tests of the foundation safety correction (2026-11-17). Every card, programme, term and person is invented.

Two things must hold together, in every kind of content the engine holds:

    A  eligibility that is not settled is NEVER reported as established
    B  eligibility that is settled and unaffected is STILL reported

The mechanism under test is the reviewed classification of a rule's restrictions and open questions
(prices/conditions.py) and the protection of historical terms (prices/changes.py, engine.standing).
The same behaviour on real sourced content is in tests/test_s_viability_experiment.py and tests/test_live_data.py.
"""
import copy
import os
import shutil
import tempfile
import unittest

from util import H, TEST_VOCAB, ent, ev, holding, make_store, metric, review, write_store
from util import rule as fixture_rule
from prices import cards, changes
from prices.calc import convert_quote, earn_quote
from prices.conditions import blockers, review_issues
from prices.earned import survey
from prices.engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate
from prices.lint import lint
from prices.store import Store, read_audit

DAY = "2026-06-01"
REVIEWER = "Synthetic Reviewer"
VOCAB = dict(copy.deepcopy(TEST_VOCAB), promotion_reviewers=[REVIEWER],
             spend_categories={"other": {"name": "everything else"}, "dining": {"name": "dining"}})
ENTS = [ent("card.a", "card"), ent("card.b", "card"), ent("b.offer", "benefit"), ent("b.lounge", "benefit"), ent("b.earn", "benefit"),
        ent("b.perk", "benefit"), ent("prog.member"), ent("st.silver"), ent("st.gold"), ent("pts.a", "currency"), ent("miles.x", "currency"),
        ent("miles.y", "currency"), ent("act.enrol", "action", how="enrol online"), ent("cap.award", "capability")]
GATE, USAGE, QUESTION = "New applicants only", "Book through the portal", "Whether a minimum number of flights still applies was not established"


def rule(*args, **kw):
    """A fixture rule. This file's store names its reviewers, so the default fixture review is recorded as one of them."""
    r = fixture_rule(*args, **kw)
    if r.get("condition_review", {}).get("by") == "Test Owner":
        r["condition_review"]["by"] = REVIEWER
    return r


def world(rules, holdings=(), **kw):
    return make_store(ENTS, rules, holdings, vocab=VOCAB, **kw)


def by_reviewer(*items):
    return review(*items, by=REVIEWER)


def issues(store, level="ERROR"):
    return {i[1] for i in lint(store) if i[0] == level}


def status(store, entity, day=DAY):
    return evaluate(store, "t", day).have(entity)


# ====================================================================================================== across domains
class TestEveryDomain(unittest.TestCase):
    """One pair per kind of content named in the commission: the unsettled case and the unaffected case side by side."""

    def test_card_benefit(self):
        offer = rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[GATE, USAGE], condition_review=by_reviewer((GATE, "unchecked"), (USAGE, "usage")))
        lounge = rule("r.lounge", "grants", "b.lounge", H("card.a"), restrictions=["Guests pay a fee"], open_questions=["The guest fee was not read"],
                      condition_review=by_reviewer(("Guests pay a fee", "usage"), ("The guest fee was not read", "informational")))
        s = world([offer, lounge], [holding("h1", "card.a")])
        self.assertEqual(issues(s), set())
        r = evaluate(s, "t", DAY)
        self.assertEqual(r.have("b.offer"), UNRESOLVED)                                       # A
        self.assertEqual(r.have("b.lounge"), ESTABLISHED)                                     # B
        rep = r.report()
        self.assertEqual([x["entity"] for x in rep["derived_entitlements"]], ["b.lounge"])
        self.assertIn("b.offer", [x["entity"] for x in rep["unresolved"]])
        self.assertTrue(any(GATE in u for u in r.tokens("have:b.offer")["unknowns"]))         # the reason is the condition itself
        row = {x["benefit"]: x for x in cards.matrix(s, DAY, "t")}
        self.assertEqual(row["b.offer"]["holder_status"], UNRESOLVED)                         # the card table does not say otherwise
        self.assertIn("not established for a holder", row["b.offer"]["detail"])
        self.assertNotIn("not established", row["b.lounge"]["detail"])

    def test_airline_status_by_threshold(self):
        y26 = rule("r.silver-2026", "grants", "st.silver", {"all": [H("prog.member"), {"metric": "prog.2026.flights", "gte": 4}, {"metric": "prog.2026.points", "gte": 6000}]},
                   valid_from="2026-01-01", valid_to="2026-12-31", restrictions=["At least four flights on the airline"], open_questions=["How long the status lasts was not read"],
                   condition_review=by_reviewer(("At least four flights on the airline", "enforced", [{"metric": "prog.2026.flights", "gte": 4}]), ("How long the status lasts was not read", "informational")))
        y27 = rule("r.silver-2027", "grants", "st.silver", {"all": [H("prog.member"), {"metric": "prog.2027.points", "gte": 6000}]},
                   valid_from="2027-01-01", valid_to="2027-12-31", open_questions=[QUESTION], condition_review=by_reviewer((QUESTION, "affects_eligibility")))
        member = [holding("h1", "prog.member")]

        def s(points_2027, rules=(y26, y27)):
            ms = [metric("prog.2026.flights", 9), metric("prog.2026.points", 6500)] + ([metric("prog.2027.points", points_2027)] if points_2027 is not None else [])
            return world(list(rules), member, metrics=ms)
        self.assertEqual(issues(s(6100)), set())
        self.assertEqual(status(s(6100), "st.silver", "2027-10-01"), UNRESOLVED)              # A: the points alone do not settle it
        self.assertEqual(status(s(6100), "st.silver", "2026-11-01"), ESTABLISHED)             # B: the year whose minimum IS checked
        self.assertEqual(status(s(5400), "st.silver", "2027-10-01"), NOT_AVAILABLE)           # a clear no stays a no
        self.assertEqual(status(s(None), "st.silver", "2027-10-01"), UNRESOLVED)              # nothing recorded: unresolved, as before
        settled = dict(y27, condition_review=by_reviewer((QUESTION, "informational")))        # a reviewer decides the answer cannot matter
        self.assertEqual(status(s(6100, (y26, settled)), "st.silver", "2027-10-01"), ESTABLISHED)

    def test_transfer(self):
        gated = rule("t.x", "transfer", "miles.x", H("pts.a"), transfer={"from": "pts.a", "ratio": "2:1"}, restrictions=["US-based accounts only", "Names must match"],
                     condition_review=by_reviewer(("US-based accounts only", "unchecked"), ("Names must match", "usage")))
        plain = rule("t.y", "transfer", "miles.y", H("pts.a"), transfer={"from": "pts.a", "ratio": "2:1"}, restrictions=["Names must match"], open_questions=["Posting time was not read"],
                     condition_review=by_reviewer(("Names must match", "usage"), ("Posting time was not read", "informational")))
        s = world([gated, plain], [holding("h1", "pts.a", quantity=50000)])
        ans = {a["to"]: a for a in convert_quote(s, "t", DAY, "pts.a", 10000)["answers"]}
        self.assertEqual(ans["miles.x"]["result"], "NOT_CALCULATED")                          # A
        self.assertIn("US-based accounts only", ans["miles.x"]["reason"])
        self.assertNotIn("amount", ans["miles.x"])
        self.assertEqual((ans["miles.y"]["result"], ans["miles.y"]["amount"]), ("CALCULATED", 5000))    # B
        self.assertEqual((status(s, "miles.x"), status(s, "miles.y")), (UNRESOLVED, ESTABLISHED))

    def test_activation_requirement(self):
        text = "Requires enrolment before first use"
        # checked: the rule itself asks for the action, so the class may say so
        acq = rule("r.gold", "acquire", "st.gold", {"all": [H("card.a"), H("act.enrol")]}, restrictions=[text], retention={"mode": "unknown"},
                   condition_review=by_reviewer((text, "enforced", [{"holds": "act.enrol"}])))
        self.assertEqual(status(world([acq], [holding("h1", "card.a")]), "st.gold"), CONDITIONAL)        # B: reachable, and it says by what action
        done = evaluate(world([acq], [holding("h1", "card.a"), holding("h2", "act.enrol")]), "t", DAY)
        self.assertEqual([x["entity"] for x in done.report()["eligible_to_acquire"]], ["st.gold"])
        # not checked: the same words on a rule that asks only for the card
        bare = rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[text])
        self.assertTrue(review_issues(bare, [{"text": text, "class": "enforced", "enforced_by": [{"holds": "act.enrol"}]}]))   # a reviewer cannot claim a check that is not there
        self.assertTrue(review_issues(bare, [{"text": text, "class": "enforced", "enforced_by": "when:card.a"}]))   # the old presence-based form
        self.assertTrue(review_issues(bare, [{"text": text, "class": "enforced"}]))
        honest = dict(bare, condition_review=by_reviewer((text, "unchecked")))
        self.assertEqual(status(world([honest], [holding("h1", "card.a")]), "b.offer"), UNRESOLVED)       # A
        forged = dict(bare, condition_review=by_reviewer((text, "enforced", [{"holds": "act.enrol"}])))   # written into the file by hand
        self.assertIn("BAD_CLASSIFICATION", issues(world([forged], [holding("h1", "card.a")])))
        self.assertEqual(status(world([forged], [holding("h1", "card.a")]), "b.offer"), UNRESOLVED)     # and the engine does not rely on it

    def test_spending_threshold(self):
        def earn(*classes, restrictions=("Primary cardholder only",)):
            return rule("r.earn", "earns", "b.perk", H("card.a"), restrictions=list(restrictions), condition_review=by_reviewer(*classes),
                        earn={"measure": "card.spend", "period": "calendar_year", "threshold": 1000, "unit": "units", "activation": "automatic",
                              "term": {"ends": "fixed", "year_offset": 1, "month": 12, "day": 31}})

        def state(r, spend):
            s = world([r], [holding("h-card", "card.a", valid_from="2026-01-01")])
            s.files["profiles/t/qualifications/q1.json"] = {"id": "q1", "account": "h-card", "measure": "card.spend", "cycle": "2026", "readings": [
                {"id": "r1", "value": spend, "observed_on": "2026-05-01", "state": "confirmed", "confirmed_by": "Test Owner", "confirmed_on": "2026-05-01"}]}
            b = survey(s, "t", DAY)["accounts"][0]["cycles"][0]["benefits"][0]
            return b["entitlement"]["state"], b["entitlement"]["detail"], evaluate(s, "t", DAY).have("b.perk")
        st, why, have = state(earn(("Primary cardholder only", "unchecked")), 1500)
        self.assertEqual((st, have), ("UNRESOLVED", UNRESOLVED))                              # A: threshold met, eligibility not settled
        self.assertIn("Primary cardholder only", why)
        st, _why, have = state(earn(("Primary cardholder only", "unchecked")), 400)
        self.assertEqual((st, have), ("NOT_EARNED", NOT_AVAILABLE))                           # below the threshold is still a plain no
        st, _why, have = state(earn(("Counts purchases in the calendar year", "enforced", [{"earn_threshold": 1000}]), restrictions=("Counts purchases in the calendar year",)), 1500)
        self.assertEqual(st, "EARNED_NOT_CONFIRMED")                                          # B: the condition is the threshold itself
        self.assertNotEqual(have, ESTABLISHED)                                                # ... and eligibility is still never possession

    def test_account_eligibility(self):
        text = "The account must have been open for 60 days"
        award = rule("r.award", "grants", "cap.award", H("miles.x"), restrictions=[text, "Awards cannot be changed"],
                     condition_review=by_reviewer((text, "unchecked"), ("Awards cannot be changed", "usage")))
        other = rule("r.award-b", "grants", "cap.award", H("miles.y"), restrictions=["Awards cannot be changed"])
        self.assertEqual(status(world([award], [holding("h1", "miles.x")]), "cap.award"), UNRESOLVED)                       # A
        self.assertEqual(status(world([award, other], [holding("h1", "miles.x"), holding("h2", "miles.y")]), "cap.award"), ESTABLISHED)   # B: another, settled route
        self.assertEqual(status(world([award], [holding("h1", "miles.x"), holding("h3", "cap.award")]), "cap.award"), ESTABLISHED)        # B: the owner's own record


# ================================================================================================== silence is not approval
class TestMissingClassificationIsNeverApproval(unittest.TestCase):
    HOLD = [holding("h1", "card.a")]

    def blocked(self, r):
        s = world([r], self.HOLD)
        self.assertEqual(status(s, "b.offer"), UNRESOLVED, r.get("condition_review"))
        return s

    def test_a_rule_nobody_classified(self):
        s = self.blocked(rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[USAGE], reviewed=False))
        self.assertIn("CONDITIONS_NOT_CLASSIFIED", issues(s, "WARNING"))
        self.assertTrue(any("OP-14" in u for u in evaluate(s, "t", DAY).tokens("have:b.offer")["unknowns"]))

    def test_every_way_a_record_can_fall_short(self):
        base = dict(restrictions=[USAGE, "Limit one per year"], open_questions=["Renewal not read"])
        full = [(USAGE, "usage"), ("Limit one per year", "usage"), ("Renewal not read", "informational")]
        ok = rule("r.offer", "grants", "b.offer", H("card.a"), condition_review=by_reviewer(*full), **base)
        self.assertEqual(status(world([ok], self.HOLD), "b.offer"), ESTABLISHED)              # the complete record does establish
        for name, broken in (
                ("one text left out", by_reviewer(*full[:2])),
                ("empty list", by_reviewer()),
                ("class from the wrong family", by_reviewer(full[0], full[1], ("Renewal not read", "usage"))),
                ("a class that does not exist", by_reviewer(full[0], full[1], ("Renewal not read", "fine"))),
                ("text differs by one character", by_reviewer((USAGE + ".", "usage"), full[1], full[2])),
                ("items is not a list", {"by": REVIEWER, "on": "2026-01-01", "items": "usage"}),
                ("items are not objects", {"by": REVIEWER, "on": "2026-01-01", "items": [USAGE, "Limit one per year", "Renewal not read"]})):
            with self.subTest(name):
                self.blocked(dict(ok, condition_review=broken))

    def test_editing_the_rule_after_review_sets_the_review_aside(self):
        ok = rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[USAGE, GATE], condition_review=by_reviewer((USAGE, "usage"), (GATE, "unchecked")))
        # the blocking condition is deleted from the rule by a later edit: the remaining text does NOT inherit approval
        removed = dict(ok, restrictions=[USAGE])
        s = self.blocked(removed)
        # CHANGED 2026-11-17 (repair): the stale review is now a blocker of its own, so it still blocks when no text is left
        self.assertEqual([cls for cls, _t in blockers(removed)], ["stale", None])
        self.assertIn("STALE_CLASSIFICATION", issues(s, "WARNING"))
        self.blocked(dict(ok, restrictions=[USAGE, "New applicants"]))                         # reworded
        fine = rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[USAGE])
        self.assertEqual(status(world([fine], self.HOLD), "b.offer"), ESTABLISHED)
        self.blocked(dict(fine, open_questions=["Is it still offered?"]))                      # a question added after review

    def test_a_class_cannot_do_more_than_classify(self):
        unverified = rule("r.offer", "grants", "b.offer", H("card.a"), status="unverified", restrictions=[USAGE], condition_review=by_reviewer((USAGE, "usage")))
        self.blocked(unverified)                                                               # usage terms do not verify a rule
        cand = {"id": "c1", "status": "proposed", "created_on": DAY, "search_path": ["q"], "evidence": [ev("ev9")], "open_questions": [],
                "proposed_rule": {"id": "r.offer", "kind": "grants", "output": "b.offer", "when": H("card.a"), "summary": "x", "restrictions": [USAGE],
                                  "condition_review": by_reviewer((USAGE, "usage"))}}
        s = make_store(ENTS, [], self.HOLD, vocab=VOCAB, candidates=[cand])
        self.assertNotEqual(evaluate(s, "t", DAY).have("b.offer"), ESTABLISHED)                # a candidate is never established
        outsider = rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[USAGE], condition_review=review((USAGE, "usage"), by="Somebody Else"))
        self.assertIn("REVIEWER_NOT_AUTHORIZED", issues(world([outsider], self.HOLD)))         # only a named reviewer's record is accepted

    def test_blocking_is_not_indiscriminate(self):
        plain = rule("r.plain", "grants", "b.lounge", H("card.a"))
        asked = rule("r.asked", "grants", "b.earn", H("card.a"), open_questions=["What does the lounge serve?"], condition_review=by_reviewer(("What does the lounge serve?", "informational")))
        gated = rule("r.offer", "grants", "b.offer", H("card.a"), restrictions=[GATE], condition_review=by_reviewer((GATE, "unchecked")))
        onward = rule("r.gold", "grants", "st.gold", H("b.offer"))
        r = evaluate(world([plain, asked, gated, onward], self.HOLD), "t", DAY)
        self.assertEqual((r.have("b.lounge"), r.have("b.earn")), (ESTABLISHED, ESTABLISHED))   # no text; and an open question that is only informational
        self.assertEqual((r.have("b.offer"), r.have("st.gold")), (UNRESOLVED, UNRESOLVED))     # the gate, and what would follow from it
        self.assertEqual(status(world([gated], []), "b.offer"), NOT_AVAILABLE)                 # without the card it is simply not available

    def test_calculations_follow_the_same_rule(self):
        earning = {"currency": "pts.a", "rates": [{"category": "dining", "per_usd": 3}, {"category": "other", "per_usd": 1}]}
        ok = rule("r.earn", "grants", "b.earn", H("card.a"), earning=earning, restrictions=["Excludes fees"])
        self.assertEqual(earn_quote(world([ok], self.HOLD), "t", DAY, "dining", 100)["answers"][0]["points"], 300)
        for cr in (None, by_reviewer(("Excludes fees", "unchecked"))):
            bad = dict(ok, condition_review=cr) if cr else {k: v for k, v in ok.items() if k != "condition_review"}
            a = earn_quote(world([bad], self.HOLD), "t", DAY, "dining", 100)["answers"][0]
            self.assertEqual(a["result"], "NOT_CALCULATED")
            self.assertNotIn("points", a)


# =============================================================================================================== pipeline
class OnDisk(unittest.TestCase):
    RULES = ()
    HOLD = (holding("h1", "card.a"),)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="prices-t-")
        self.addCleanup(shutil.rmtree, self.root)
        write_store(world(list(self.RULES), list(self.HOLD)), self.root)
        self.n = 0

    def cs(self, op, **kw):
        self.n += 1
        return dict({"id": "cs-20260601-t-%02d-%s" % (self.n, op.replace("_", "-")), "op": op, "author": "test", "date": DAY, "reason": "invented"}, **kw)

    def ok(self, c):
        out = changes.apply(self.root, c)
        self.assertTrue(out["ok"], out.get("errors"))
        return c["id"]

    def refused(self, c, code):
        before = Store.load(self.root).digest()
        out = changes.apply(self.root, c)
        self.assertFalse(out["ok"], c["id"])
        self.assertTrue(any(e.startswith(code) for e in out["errors"]), out["errors"])
        self.assertEqual(Store.load(self.root).digest(), before, "a refused changeset must change nothing")

    def have(self, entity, day=DAY):
        return evaluate(Store.load(self.root), "t", day).have(entity)

    @staticmethod
    def attest(by=REVIEWER):
        return {"by": by, "on": DAY, "statement": "invented review"}


class TestClassificationThroughThePipeline(OnDisk):
    def candidate(self, restrictions=(GATE, USAGE), questions=("Is it renewed each year?",), **extra):
        r = dict({"id": "r.offer", "kind": "grants", "output": "b.offer", "when": H("card.a"), "summary": "an offer"}, **extra)
        if restrictions:
            r["restrictions"] = list(restrictions)
        return self.cs("add_candidate", data={"candidate": {"id": "c-offer", "status": "proposed", "created_on": DAY, "proposed_rule": r,
                                                            "evidence": [ev("ev-offer", "official", "Issuer", DAY)], "search_path": ["q"], "open_questions": list(questions)}})

    def promote(self, conditions="absent", by=REVIEWER, **data):
        d = dict({"review_by": "2027-05-01", "accept_open_questions": True}, **data)
        if conditions != "absent":
            d["conditions"] = conditions
        return self.cs("promote_candidate", target="c-offer", data=d, attestation=self.attest(by))

    FULL = [{"text": GATE, "class": "unchecked"}, {"text": USAGE, "class": "usage"}, {"text": "Is it renewed each year?", "class": "informational"}]

    def test_promotion_needs_a_class_for_every_text(self):
        self.ok(self.candidate())
        self.refused(self.promote(), "CONDITIONS_NOT_CLASSIFIED")                             # silence
        self.refused(self.promote(None), "CONDITIONS_NOT_CLASSIFIED")
        self.refused(self.promote([]), "BAD_CLASSIFICATION")                                  # an empty answer
        self.refused(self.promote(self.FULL[:2]), "BAD_CLASSIFICATION")                       # one left out
        self.refused(self.promote(self.FULL + [{"text": "Something else", "class": "usage"}]), "BAD_CLASSIFICATION")
        self.refused(self.promote([dict(self.FULL[0], **{"class": "enforced"})] + self.FULL[1:]), "BAD_CLASSIFICATION")      # enforced by nothing
        self.refused(self.promote([dict(self.FULL[0], **{"class": "enforced", "enforced_by": [{"valid_to": "2027-12-31"}]})] + self.FULL[1:]), "BAD_CLASSIFICATION")   # the rule has no dates
        self.refused(self.promote([dict(self.FULL[0], **{"class": "enforced", "enforced_by": "dates"})] + self.FULL[1:]), "BAD_CLASSIFICATION")   # the old form
        self.refused(self.promote(self.FULL[:2] + [{"text": "Is it renewed each year?", "class": "usage"}]), "BAD_CLASSIFICATION")   # wrong family
        self.refused(self.promote(self.FULL, by="Somebody Else"), "REVIEWER_NOT_AUTHORIZED")
        self.assertNotIn("r.offer", Store.load(self.root).rules)
        cs_id = self.ok(self.promote(self.FULL))
        r = Store.load(self.root).rules["r.offer"]
        self.assertEqual((r["condition_review"]["by"], r["condition_review"]["changeset"]), (REVIEWER, cs_id))     # who, and where it is on file
        self.assertEqual(self.have("b.offer"), UNRESOLVED)                                    # promoted, verified, and still not established
        self.assertEqual(issues(Store.load(self.root)), set())

    def test_a_candidate_cannot_bring_its_own_approval(self):
        self.refused(self.candidate(condition_review=review((GATE, "usage"), (USAGE, "usage"), by=REVIEWER)), "SCHEMA")
        self.assertEqual(Store.load(self.root).candidates, {})

    def test_nothing_to_classify_means_nothing_is_asked(self):
        self.ok(self.candidate(restrictions=(), questions=()))
        self.ok(self.promote())
        self.assertEqual(self.have("b.offer"), ESTABLISHED)

    def test_reclassification_is_a_reviewed_audited_act_and_can_be_undone(self):
        self.ok(self.candidate())
        self.ok(self.promote(self.FULL))
        better = [{"text": GATE, "class": "usage", "note": "invented: suppose the source said it applies to everyone"}] + self.FULL[1:]
        self.refused(self.cs("classify_conditions", target="r.offer", data={"items": better}), "ATTESTATION_REQUIRED")
        self.refused(self.cs("classify_conditions", target="r.offer", data={"items": better}, attestation=self.attest("Somebody Else")), "REVIEWER_NOT_AUTHORIZED: only")
        self.refused(self.cs("classify_conditions", target="r.offer", data={"items": better[:1]}, attestation=self.attest()), "BAD_CLASSIFICATION")
        self.assertEqual(self.have("b.offer"), UNRESOLVED)
        cs_id = self.ok(self.cs("classify_conditions", target="r.offer", data={"items": better}, attestation=self.attest()))
        self.assertEqual(self.have("b.offer"), ESTABLISHED)
        log = read_audit(self.root)[-1]
        self.assertEqual((log["changeset"], log["op"], log["result"]), (cs_id, "classify_conditions", "applied"))
        self.assertTrue(os.path.exists(os.path.join(self.root, "data", "audit", "previous", cs_id + ".json")))     # the earlier classes are kept
        self.ok(self.cs("revert_changeset", data={"changeset": cs_id}, attestation=self.attest()))
        self.assertEqual(self.have("b.offer"), UNRESOLVED)

    def test_a_later_edit_of_the_texts_needs_a_new_review(self):
        self.ok(self.candidate(restrictions=(USAGE,), questions=()))
        self.ok(self.promote([{"text": USAGE, "class": "usage"}]))
        self.assertEqual(self.have("b.offer"), ESTABLISHED)
        self.ok(self.cs("flag_rule", target="r.offer", data={"open_questions": ["Reported as withdrawn"]}, evidence=[ev("ev-flag", "official", "Issuer", DAY)]))
        self.assertEqual(self.have("b.offer"), UNRESOLVED)


# ================================================================================================================ history
class TestHistoricalTermsAreProtected(OnDisk):
    EARNING = {"currency": "pts.a", "rates": [{"category": "dining", "per_usd": 3}, {"category": "other", "per_usd": 1}]}
    RULES = (rule("r.earn", "grants", "b.earn", H("card.a"), valid_from="2025-01-01", earning=EARNING, restrictions=["Excludes fees"]),
             rule("r.lounge", "grants", "b.lounge", H("card.a")),
             rule("r.rumour", "grants", "b.perk", H("card.a"), status="unverified"))
    EV = [ev("ev-new", "official", "Issuer", DAY)]

    def points(self, day):
        return [a.get("points") for a in earn_quote(Store.load(self.root), "t", day, "dining", 100)["answers"]]

    def new_rates(self, n=2):
        e = copy.deepcopy(self.EARNING)
        e["rates"][0]["per_usd"] = n
        return e

    def revise(self, target="r.earn", correction=None, **set_):
        data = {"set": set_}
        if correction:
            data["correction"] = correction
        return self.cs("revise_rule", target=target, data=data, evidence=self.EV)

    def test_an_ordinary_revision_cannot_change_a_past_answer(self):
        for change in (dict(earning=self.new_rates()), dict(summary="reworded terms"), dict(restrictions=["Excludes fees", "And taxes"]),
                       dict(restrictions=[]), dict(valid_from="2026-01-01"), dict(valid_from="2024-01-01"), dict(valid_to="2026-05-31")):
            with self.subTest(change):
                self.refused(self.revise(**change), "HISTORY_REWRITE")
        self.refused(self.revise(correction="typo", earning=self.new_rates()), "HISTORY_REWRITE")           # a one-word excuse is not a declaration
        self.assertEqual(self.points("2025-06-01"), [300])

    def test_what_an_ordinary_revision_may_still_do(self):
        self.ok(self.revise(valid_to="2026-12-31"))                                           # end the terms from a day still to come
        self.ok(self.revise(valid_to="2027-03-31"))                                           # ... and move that day while it has not come
        # CHANGED 2026-11-17 (repair): recording a first restriction on a rule that already answered for earlier dates is no
        # longer an ordinary revision (tests/test_u_repair.py)
        self.refused(self.revise(target="r.lounge", restrictions=["Guests pay a fee"]), "HISTORY_REWRITE")
        self.ok(self.revise(review_by="2028-01-01"))
        self.assertEqual(self.have("b.lounge"), ESTABLISHED)
        self.assertEqual(self.points("2025-06-01"), [300])

    def test_new_terms_come_in_as_a_dated_successor_and_both_stay(self):
        self.ok(self.revise(valid_to="2026-12-31"))
        new = {"id": "r.earn-2027", "kind": "grants", "output": "b.earn", "when": H("card.a"), "summary": "new terms", "earning": self.new_rates(),
               "restrictions": ["Excludes fees"]}
        cand = lambda **kw: self.cs("add_candidate", data={"candidate": {"id": "c-new", "status": "proposed", "created_on": DAY, "proposed_rule": dict(new, **kw),   # noqa: E731
                                                                         "evidence": self.EV, "search_path": ["q"], "open_questions": []}})
        self.refused(cand(valid_from="2026-12-31"), "DUPLICATE_RELATIONSHIP")                 # one shared day is an overlap
        self.refused(cand(), "DUPLICATE_RELATIONSHIP")
        self.ok(cand(valid_from="2027-01-01"))
        self.ok(self.cs("promote_candidate", target="c-new", data={"review_by": "2027-05-01", "conditions": [{"text": "Excludes fees", "class": "usage"}]}, attestation=self.attest()))
        self.assertEqual((self.points("2025-06-01"), self.points("2026-12-31"), self.points("2027-01-01")), ([300], [300], [200]))
        s = Store.load(self.root)
        self.assertEqual(issues(s), set())
        self.assertEqual(s.rules["r.earn"]["earning"], self.EARNING)                          # the old terms are still on file, word for word

    def test_a_declared_correction_is_possible_visible_and_reversible(self):
        why = "the dining rate was keyed as 3 and the source says 2"
        cs_id = self.ok(self.revise(correction=why, earning=self.new_rates()))
        self.assertEqual(self.points("2025-06-01"), [200])
        with open(os.path.join(self.root, "data", "audit", "changesets", cs_id + ".json"), encoding="utf-8") as f:
            self.assertIn(why, f.read())                                                      # the audit trail says history was corrected, and why
        self.assertTrue(os.path.exists(os.path.join(self.root, "data", "audit", "previous", cs_id + ".json")))
        self.ok(self.cs("revert_changeset", data={"changeset": cs_id}, attestation=self.attest()))
        self.assertEqual(self.points("2025-06-01"), [300])

    def test_retirement_keeps_the_answers_the_rule_gave_while_it_was_in_force(self):
        n = len(read_audit(self.root))
        self.refused(self.cs("retire_rule", target="r.earn", data={"ended_on": "2024-06-30"}, evidence=self.EV), "BAD_DATES: ended_on")   # before it began
        self.refused(self.cs("retire_rule", target="r.earn", data={"ended_on": "soon"}, evidence=self.EV), "BAD_DATA")
        self.refused(self.cs("retire_rule", target="r.earn", data={}, evidence=self.EV), "MISSING_DATA")
        cs_id = self.ok(self.cs("retire_rule", target="r.earn", data={"ended_on": "2026-03-31"}, evidence=self.EV))
        self.assertEqual((self.points("2025-06-01"), self.points("2026-03-31")), ([300], [300]))            # history is still answered
        self.assertEqual(self.points("2026-04-01"), [None])                                                 # and no rate after the end
        self.assertEqual((self.have("b.earn", "2026-03-31"), self.have("b.earn", "2026-04-01")), (ESTABLISHED, NOT_AVAILABLE))
        v = Store.load(self.root).rules["r.earn"]["verification"]
        self.assertEqual((v["status"], v["retired_from"]), ("retired", "verified"))
        self.assertEqual(issues(Store.load(self.root)), set())
        self.refused(self.revise(valid_to="2027-01-01"), "RETIRED")                           # a retired rule is history; it is not reopened
        again = {"id": "r.earn-again", "kind": "grants", "output": "b.earn", "when": H("card.a"), "summary": "the same relationship", "valid_from": "2026-03-01"}
        cand = lambda rule_: self.cs("add_candidate", data={"candidate": {"id": "c-" + rule_["id"], "status": "proposed", "created_on": DAY, "proposed_rule": rule_,   # noqa: E731
                                                                          "evidence": self.EV, "search_path": ["q"], "open_questions": []}})
        self.refused(cand(again), "DUPLICATE_RELATIONSHIP")                                   # no second rule may answer for the days it still answers for
        self.ok(cand(dict(again, valid_from="2026-04-01")))                                   # ... a successor from the next day may
        log = read_audit(self.root)[n:]                                                       # every attempt is on the record, refused or applied
        self.assertEqual([e["op"] for e in log if e["result"] == "applied"], ["retire_rule", "add_candidate"])
        self.assertEqual(len([e for e in log if e["result"] == "rejected"]), 5)
        self.assertTrue(os.path.exists(os.path.join(self.root, "data", "audit", "previous", cs_id + ".json")))

    def test_a_rule_that_was_not_trusted_is_not_trusted_in_retrospect(self):
        self.assertEqual(self.have("b.perk", "2026-03-01"), UNRESOLVED)
        self.ok(self.cs("retire_rule", target="r.rumour", data={"ended_on": "2026-03-31"}, evidence=self.EV))
        self.assertEqual(Store.load(self.root).rules["r.rumour"]["verification"]["retired_from"], "unverified")
        self.assertEqual((self.have("b.perk", "2026-03-01"), self.have("b.perk", "2026-04-01")), (UNRESOLVED, NOT_AVAILABLE))

    def test_withdrawing_a_rule_from_every_date_must_be_declared(self):
        self.refused(self.cs("retire_rule", target="r.earn", data={"void": True}, evidence=self.EV), "HISTORY_REWRITE")
        self.refused(self.cs("retire_rule", target="r.earn", data={"void": True, "ended_on": "2026-03-31", "correction": "it was never offered at all"}, evidence=self.EV), "BAD_DATA")
        self.ok(self.cs("retire_rule", target="r.earn", data={"void": True, "correction": "it was never offered at all"}, evidence=self.EV))
        self.assertEqual((self.points("2025-06-01"), self.have("b.earn", "2025-06-01")), ([None], NOT_AVAILABLE))
        self.assertIn("r.earn", Store.load(self.root).rules)                                  # the record itself is kept


if __name__ == "__main__":
    unittest.main()
