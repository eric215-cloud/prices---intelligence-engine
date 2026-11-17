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


def scratch_real(candidate, governed=False):
    """Items for a REAL candidate promoted in a scratch copy, from engineering's letter classification.

    U usage and M research note -> usage. G -> unchecked. T (a time window) and g (a condition said to be checked)
    -> enforced, naming what checks it; where nothing on the rule does, they fall back to unchecked."""
    with open(os.path.join(ROOT, "experiments", "viability", "restriction_classes.json"), encoding="utf-8") as f:
        spec = json.load(f)
    rule = candidate["proposed_rule"]
    restrictions, questions = _texts(candidate)
    if rule["id"] not in spec["classes"] and restrictions:              # the transfer candidates: classed by exact text
        missing = [x for x in restrictions if x not in spec["texts"]]
        if missing:
            raise ValueError("restriction_classes.json does not cover %s: %r" % (rule["id"], missing[0][:80]))
        return [dict({"text": x}, **spec["texts"][x]) for x in restrictions] + _questions(spec, questions)
    letters = spec["classes"].get(rule["id"], "")
    if len(letters) != len(restrictions):
        raise ValueError("restriction_classes.json does not cover %s" % rule["id"])
    from prices.engine import leaves
    others = sorted(i for _k, i, neg in leaves(rule["when"]) if not neg and not i.startswith("card."))
    dated = bool(rule.get("valid_from") or rule.get("valid_to"))
    out = []
    for text, letter in zip(restrictions, letters):
        by = None
        if letter in "UM":
            cls = "usage"
        elif letter == "G":
            cls = "unchecked"
        elif letter == "T":
            by = "dates" if dated else "earn" if "earn" in rule else None
            cls = "enforced" if by else "unchecked"
        else:                                                   # g
            by = "election" if governed else "earn" if "earn" in rule else ("when:" + others[0]) if len(others) == 1 else None
            cls = "enforced" if by else "unchecked"
        out.append(dict({"text": text, "class": cls}, **({"enforced_by": by} if by else {})))
    return out + _questions(spec, questions)


def _questions(spec, questions):
    out = []
    for text in questions:
        cls = next((q["class"] for q in spec["questions"] if text.startswith(q["starts"])), None)
        if cls is None:
            raise ValueError("restriction_classes.json has no class for the open question %r" % text[:80])
        out.append({"text": text, "class": cls})
    return out
