"""Condition classes for INVENTED data and for scratch copies used by tests and demonstrations.

A real promotion needs a reviewer who has read each restriction and open question (prices/conditions.py, OP-14).
Nothing here is that. `invented` labels made-up fixture rules; `scratch_real` applies engineering's reading of the
real candidates (experiments/viability/restriction_classes.json), which is a measurement aid, in a throwaway copy.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _texts(candidate):
    rule = candidate["proposed_rule"]
    questions = list(rule.get("open_questions") or []) or list(candidate.get("open_questions") or [])
    return list(rule.get("restrictions") or []), questions


def invented(candidate, classes=None):
    """Items for a made-up candidate: every restriction is a usage term and every question informational, unless
    `classes` gives {text: class} or {text: {"class": ..., "enforced_by": ...}} for the ones the fixture means otherwise."""
    classes = classes or {}
    restrictions, questions = _texts(candidate)
    out = []
    for text, default in [(t, "usage") for t in restrictions] + [(t, "informational") for t in questions]:
        given = classes.get(text, default)
        out.append(dict({"text": text}, **(given if isinstance(given, dict) else {"class": given})))
    return out


def scratch_real(candidate, governed=False, store=None):
    """Items for a REAL candidate promoted in a scratch copy, from engineering's letter classification.

    U usage and M research note -> usage. G -> unchecked. T (a time window) and g (a condition said to be checked)
    -> enforced, with the exact claim that checks it (prices/conditions.py, CLAIMS). A claim that cannot be
    demonstrated against the rule falls back to unchecked, with a note saying why: nothing is marked enforced on
    engineering's word alone. Pass the store the candidate will be promoted into, so entity kinds and elections count."""
    from prices.conditions import ACTION_WORDS, context, item_issues
    with open(os.path.join(ROOT, "experiments", "viability", "restriction_classes.json"), encoding="utf-8") as f:
        spec = json.load(f)
    rule = candidate["proposed_rule"]
    if store is not None:
        ctx = context(store)
        ctx["entities"] = dict(ctx["entities"], **{e["id"]: e for e in candidate.get("proposed_entities", [])})
    else:
        ctx = {"entities": None, "governed": {rule["id"]} if governed else set()}

    def checked(item):
        if item["class"] != "enforced":
            return item
        why = item_issues(rule, item, ctx)
        if not why:
            return item
        return {"text": item["text"], "class": "unchecked", "note": "scratch copy: the claim %s could not be demonstrated (%s)"
                % (json.dumps(item["enforced_by"]), "; ".join(why))}
    restrictions, questions = _texts(candidate)
    if rule["id"] not in spec["classes"] and restrictions:              # the transfer candidates: classed by exact text
        missing = [x for x in restrictions if x not in spec["texts"]]
        if missing:
            raise ValueError("restriction_classes.json does not cover %s: %r" % (rule["id"], missing[0][:80]))
        return [checked(dict({"text": x}, **spec["texts"][x])) for x in restrictions] + _questions(spec, questions)
    letters = spec["classes"].get(rule["id"], "")
    if len(letters) != len(restrictions):
        raise ValueError("restriction_classes.json does not cover %s" % rule["id"])
    leaf_claims = _leaf_claims(rule["when"])
    out = []
    for text, letter in zip(restrictions, letters):
        by = None
        if letter in "UM":
            cls = "usage"
        elif letter == "G":
            cls = "unchecked"
        elif letter == "T":
            by = ({"valid_to": rule["valid_to"]} if rule.get("valid_to") else {"valid_from": rule["valid_from"]} if rule.get("valid_from")
                  else {"earn_term": True} if rule.get("kind") == "earns" else None)
            cls = "enforced" if by else "unchecked"
        else:                                                   # g
            earns = rule.get("kind") == "earns"
            by = ({"election": True} if governed or rule["id"] in (ctx.get("governed") or ()) else
                  {"earn_activation": True} if earns and ACTION_WORDS.search(text) else
                  {"earn_threshold": rule["earn"]["threshold"]} if earns else
                  leaf_claims[0] if len(leaf_claims) == 1 else None)
            cls = "enforced" if by else "unchecked"
        out.append(checked(dict({"text": text, "class": cls}, **({"enforced_by": [by]} if by else {}))))
    return out + _questions(spec, questions)


def _leaf_claims(cond):
    """The positive non-card leaves of a condition, as claims (a metric keeps its own threshold)."""
    if "all" in cond or "any" in cond:
        return [c for sub in cond.get("all") or cond.get("any") or [] for c in _leaf_claims(sub)]
    if "holds" in cond and not cond["holds"].startswith("card."):
        return [{"holds": cond["holds"]}]
    if "metric" in cond:
        return [{"metric": cond["metric"], "gte": cond["gte"]}]
    return []


def _questions(spec, questions):
    out = []
    for text in questions:
        cls = next((q["class"] for q in spec["questions"] if text.startswith(q["starts"])), None)
        if cls is None:
            raise ValueError("restriction_classes.json has no class for the open question %r" % text[:80])
        out.append({"text": text, "class": cls})
    return out
