"""The defects reproduced by Bradley and Astra, as small invented scenarios, run with ONE source tree's code.

    python3 experiments/safety/repair_scenarios.py <tree>        -> one JSON object on stdout

<tree> is a checkout of this project (this one, or an earlier commit unpacked by repair_before_after.py). Only APIs
that exist in both the earlier and the repaired code are used. Where the two expect a classification in different
forms, each tree is given the form it accepts, so that each is shown at its best. All data is invented; every store
is a throwaway directory.
"""
import json
import os
import shutil
import sys
import tempfile

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
sys.path.insert(0, os.path.join(tree, "tests"))
from util import H, TEST_VOCAB, ent, ev, holding, make_store, metric, write_store   # noqa: E402
from util import rule as _rule                                                       # noqa: E402
from prices import changes, conditions                                               # noqa: E402
from prices.calc import convert_quote, earn_quote                                    # noqa: E402
from prices.engine import evaluate                                                   # noqa: E402
from prices.store import Store                                                       # noqa: E402

NEW = hasattr(conditions, "claim_issues")
DAY, OWNER = "2026-06-01", "Test Owner"
ENTS = [ent("card.a", "card"), ent("card.b", "card"), ent("pts.a", "currency"), ent("miles.x", "currency"), ent("b.perk", "benefit"),
        ent("b.earn", "benefit"), ent("b.act", "benefit"), ent("st.silver"), ent("prog.member"), ent("club.member"), ent("st.top")]
out = {"tree": "repaired" if NEW else "earlier"}


def rule(*a, **kw):
    return _rule(*a, **kw)


VOCAB = dict(TEST_VOCAB, spend_categories={"other": {"name": "everything else"}, "dining": {"name": "dining"}})


def world(rules, holdings=(), **kw):
    return make_store(ENTS, rules, list(holdings), vocab=VOCAB, **kw)


def review(*items):
    return {"by": OWNER, "on": "2026-01-01", "items": list(items)}


def claim(old, new):
    return new if NEW else old


def accepted(r, item):
    return conditions.review_issues(r, [item]) == []


def disk(store):
    root = tempfile.mkdtemp(prefix="prices-repair-")
    write_store(store, root)
    return root


# 1a  restriction requires A; the rule establishes through A OR B
r = rule("r.perk", "grants", "b.perk", {"any": [H("card.a"), H("card.b")]}, restrictions=["Card A holders only"])
item = {"text": "Card A holders only", "class": "enforced", "enforced_by": claim("when:card.a", [{"holds": "card.a"}])}
out["1a"] = {"review_accepted": accepted(r, item),
             "status_card_b_only": evaluate(world([dict(r, condition_review=review(item))], [holding("h", "card.b")]), "t", DAY).have("b.perk")}

# 1b  restriction says at least 1,000; the machine predicate checks at least 1
r = rule("r.silver", "grants", "st.silver", {"all": [H("prog.member"), {"metric": "prog.nights", "gte": 1}]}, restrictions=["At least 1,000 qualifying nights"])
item = {"text": "At least 1,000 qualifying nights", "class": "enforced", "enforced_by": claim("when:prog.nights", [{"metric": "prog.nights", "gte": 1000}])}
out["1b"] = {"review_accepted": accepted(r, item),
             "status_5_nights": evaluate(world([dict(r, condition_review=review(item))], [holding("h", "prog.member")], metrics=[metric("prog.nights", 5)]), "t", DAY).have("st.silver")}

# 2   "not a member" with no record about membership
r = rule("r.top", "grants", "st.top", {"all": [H("card.a"), {"not": H("club.member")}]})
out["2"] = {"status_no_record": evaluate(world([r], [holding("h", "card.a")]), "t", DAY).have("st.top"),
            "status_member": evaluate(world([r], [holding("h", "card.a"), holding("m", "club.member")]), "t", DAY).have("st.top")}
if NEW:
    s = world([r], [holding("h", "card.a")])
    s.files["profiles/t/absences/a1.json"] = {"id": "a1", "entity": "club.member", "confirmed_by": OWNER, "confirmed_on": DAY}
    out["2"]["status_recorded_absence"] = evaluate(s, "t", DAY).have("st.top")


# 3   calculators
def transfer(extra):
    return rule("t.x", "transfer", "miles.x", {"all": [H("pts.a"), extra]}, transfer={"from": "pts.a", "ratio": "2:1"})


def conv(r, hs, **kw):
    return convert_quote(world([r], hs, **kw), "t", DAY, "pts.a", 10000)["answers"][0]["result"]


pts = holding("p", "pts.a", quantity=20000)
out["3a"] = {"A_or_B_holding_B": conv(transfer({"any": [H("card.a"), H("card.b")]}), [pts, holding("b", "card.b")])}
out["3b"] = {"figure_not_recorded": conv(transfer({"metric": "prog.nights", "gte": 10}), [pts])}
out["3c"] = {"not_member_no_record": conv(transfer({"not": H("club.member")}), [pts])}
rates = {"currency": "pts.a", "rates": [{"category": "dining", "per_usd": 3}, {"category": "other", "per_usd": 1}]}
blocked = rule("r.rates", "grants", "b.earn", H("card.a"), earning=rates, restrictions=["New applicants only"],
               condition_review=review({"text": "New applicants only", "class": "unchecked"}))
s = world([blocked, rule("r.other", "grants", "b.earn", H("card.b"))], [holding("a", "card.a"), holding("b", "card.b")])
a = [x for x in earn_quote(s, "t", DAY, "dining", 100)["answers"] if x["card"] == "card.a"][0]
out["3d"] = {"blocked_rate_card_a": a["result"], "points": a.get("points")}
import test_o_credits as o                                                           # noqa: E402
cr = o.credit_rule("r.hotel", "hotel", o.HOTEL, restrictions=["New applicants only"], condition_review=review({"text": "New applicants only", "class": "unchecked"}))
s = o.world(holdings=[o.card(), holding("h-y", "card.y", confirmed_by=o.OWNER)], rules=[cr, _rule("r.hotel-y", "grants", "hotel", H("card.y"))])
out["3e"] = {"blocked_credit_applies": o.row(s, "hotel", "2027-03-10")["applies"]["status"]}

# 4   inside an activation window, no activation recorded
r = rule("r.act", "grants", "b.act", H("card.a"), valid_from="2026-01-01", valid_to="2026-12-31", restrictions=["Activate by December 31, 2026"])
item = {"text": "Activate by December 31, 2026", "class": "enforced", "enforced_by": claim("dates", [{"valid_to": "2026-12-31"}])}
out["4"] = {"review_accepted": accepted(r, item),
            "status_in_window_not_activated": evaluate(world([dict(r, condition_review=review(item))], [holding("h", "card.a")]), "t", DAY).have("b.act")}

# 5   a card held January to May, ended in May: what about March?
root = disk(world([rule("r.perk", "grants", "b.perk", H("card.a"))], [holding("h", "card.a", valid_from="2026-01-01", confirmed_by=OWNER, confirmed_on="2026-01-01")]))
res = changes.apply(root, {"id": "cs-20260601-x-01-end-holding", "op": "end_holding", "author": "t", "date": DAY, "reason": "closed", "profile": "t",
                           "target": "h", "data": {"ended_on": "2026-05-31"}, "attestation": {"by": OWNER, "on": DAY, "statement": "closed"}})
s = Store.load(root)
out["5"] = {"ended": res["ok"], "march": evaluate(s, "t", "2026-03-15").have("b.perk"), "june": evaluate(s, "t", "2026-06-15").have("b.perk")}
shutil.rmtree(root, ignore_errors=True)

# 6   restrictions added to / removed from a rule that has answered since 2025
EV = [ev("ev-x", "official", "Issuer", DAY)]
root = disk(world([rule("r.perk", "grants", "b.perk", H("card.a"), valid_from="2025-01-01"),
                   rule("r.used", "grants", "b.earn", H("card.a"), valid_from="2025-01-01", restrictions=["Book through the portal"],
                        condition_review=review({"text": "Book through the portal", "class": "usage"}))],
                  [holding("h", "card.a", valid_from="2024-01-01")]))
add = changes.apply(root, {"id": "cs-20260601-x-02-revise-rule", "op": "revise_rule", "author": "t", "date": DAY, "reason": "r", "target": "r.perk",
                           "data": {"set": {"restrictions": ["New applicants only"]}}, "evidence": EV})
before = evaluate(Store.load(root), "t", "2026-06-01").have("b.earn")
rm = changes.apply(root, {"id": "cs-20260601-x-03-revise-rule", "op": "revise_rule", "author": "t", "date": DAY, "reason": "r", "target": "r.used",
                          "data": {"set": {"restrictions": []}, "correction": "the portal sentence was entered on the wrong rule"}, "evidence": EV})
out["6a"] = {"first_restriction_on_past_rule_without_declaration": "accepted" if add["ok"] else "refused: " + add["errors"][0].split(":")[0]}
out["6b"] = {"last_reviewed_restriction_removed": rm["ok"], "status_before": before,
             "status_after_removal_no_new_review": evaluate(Store.load(root), "t", DAY).have("b.earn")}
shutil.rmtree(root, ignore_errors=True)
print(json.dumps(out))
