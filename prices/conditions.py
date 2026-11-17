"""Reviewed conditions: what a rule's text says about WHO has its output, and whether the engine checks it.

A rule carries terms as text in two lists: `restrictions` (what the source states) and `open_questions` (what
nobody has established yet). Text is not enforcement. Before a rule may establish anything, a reviewer records,
for every one of those texts, which of these it is:

    restrictions
      enforced             a condition on who has the output that the rule itself checks. `enforced_by` says where:
                           "when:<entity or metric id>", "dates" (valid_from / valid_to), "earn" (the earn block)
                           or "election" (a cardholder election governs the rule)
      unchecked            a condition on who has the output that is known and that nothing checks      -> BLOCKS
      usage                how the output is used (limits, booking channel, claim rules, notes): it does not decide
                           who has it
    open_questions
      affects_eligibility  the answer could change who has the output                                   -> BLOCKS
      informational        the answer would not change who has the output (a price, a ratio, a validity note)

    (no class recorded)    a text the reviewer has not classified, or that was added or reworded since   -> BLOCKS

While anything BLOCKS, nothing is established through the rule: the engine reports the output as UNRESOLVED and
gives each blocking text as the reason. A missing classification is never read as approval.

The record lives on the rule:

    "condition_review": {"by": "<a promotion reviewer>", "on": "YYYY-MM-DD", "changeset": "<id>",
                         "items": [{"text": "<exactly the text>", "class": "unchecked"},
                                   {"text": "...", "class": "enforced", "enforced_by": "when:action.enrol"}]}

It is written only by `promote_candidate` and `classify_conditions`, both of which need a reviewer's attestation.
Texts are matched exactly. Adding a restriction or a question leaves the new text unclassified; removing or rewording
one sets the whole record aside (it describes a rule that no longer exists). Either way the rule establishes nothing
until a reviewer classifies it as it now stands.
"""
RESTRICTION_CLASSES = ("enforced", "unchecked", "usage")
QUESTION_CLASSES = ("affects_eligibility", "informational")
BLOCKING = {"unchecked": "a condition on who has this, not checked by the engine",
            "affects_eligibility": "an open question that could change who has this",
            None: "not classified by a reviewer, so not relied on"}


def texts(rule):
    """[(kind, text)] for every text on the rule that needs a class: kind is "restriction" or "open_question"."""
    return [("restriction", t) for t in rule.get("restrictions") or []] + [("open_question", t) for t in rule.get("open_questions") or []]


def classes(rule):
    """[(kind, text, class or None)]. None: the reviewer's record has no class for exactly this text and kind.

    The record covers the rule as it was reviewed. If it classifies a text that is no longer on the rule, the rule
    has been edited since (a condition was removed or reworded), so the whole record is set aside: every text
    counts as unclassified until a reviewer looks at the rule as it now stands."""
    recorded, now = {}, set(texts(rule))
    for item in (rule.get("condition_review") or {}).get("items", []):
        if isinstance(item, dict):
            kind = "restriction" if item.get("class") in RESTRICTION_CLASSES else "open_question" if item.get("class") in QUESTION_CLASSES else None
            recorded[(kind, item.get("text"))] = item.get("class")
    if any(key not in now for key in recorded):
        recorded = {}
    return [(kind, text, recorded.get((kind, text))) for kind, text in texts(rule)]


def blockers(rule):
    """[(class or None, text)] for everything that stops this rule from establishing its output."""
    return [(cls, text) for _kind, text, cls in classes(rule) if cls in BLOCKING]


def tokens(rule):
    """The engine's "unknown" tokens for a rule: one per blocking text, worded for a report.

    Texts nobody has classified are counted in one token per rule: the list is in `explain` and in lint."""
    out, waiting = set(), 0
    for cls, text in blockers(rule):
        if cls is None:
            waiting += 1
        else:
            out.add(("unknown", "%s (%s): %s" % (BLOCKING[cls], rule.get("id"), text)))
    if waiting:
        out.add(("unknown", "%d restriction(s) or open question(s) on %s are %s (OP-14)" % (waiting, rule.get("id"), BLOCKING[None])))
    return frozenset(out)


def describe(rule):
    """Every text on the rule with its recorded class, for a report: [{kind, text, class, enforced_by, blocks}]."""
    by = {(i.get("text"), i.get("class")): i.get("enforced_by") for i in (rule.get("condition_review") or {}).get("items", []) if isinstance(i, dict)}
    return [{"kind": kind, "text": text, "class": cls, "enforced_by": by.get((text, cls)), "blocks": cls in BLOCKING} for kind, text, cls in classes(rule)]


def unclassified(rule):
    return [text for _kind, text, cls in classes(rule) if cls is None]


def enforcers(rule, governed=False):
    """What a reviewer may name in `enforced_by` for this rule."""
    from .engine import leaves
    out = {"when:" + i for _k, i, neg in leaves(rule["when"]) if not neg}
    if rule.get("valid_from") or rule.get("valid_to"):
        out.add("dates")
    if "earn" in rule:
        out.add("earn")
    if governed:
        out.add("election")
    return out


def review_issues(rule, items, governed=False):
    """Why a proposed list of classification items is not acceptable for this rule ([] when it is).

    It must give exactly one class to every restriction and every open question now on the rule, with a class of
    the right family, and an `enforced` item must point at something the rule really has."""
    out, seen, want = [], set(), texts(rule)
    if not isinstance(items, list):
        return ["items must be a list of {text, class}"]
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str) or not isinstance(item.get("class"), str):
            out.append("each item needs a text and a class")
            continue
        cls, text = item["class"], item["text"]
        kind = "restriction" if cls in RESTRICTION_CLASSES else "open_question" if cls in QUESTION_CLASSES else None
        if kind is None:
            out.append("unknown class %r (restrictions: %s; open questions: %s)" % (cls, ", ".join(RESTRICTION_CLASSES), ", ".join(QUESTION_CLASSES)))
            continue
        if (kind, text) not in want:
            other = "open question" if kind == "restriction" else "restriction"
            out.append("%r is not a %s on this rule%s" % (text, kind.replace("_", " "),
                       " (it is a %s: use one of that family's classes)" % other if any(t == text for _k, t in want) else ""))
            continue
        if (kind, text) in seen:
            out.append("%r is classified twice" % text)
        seen.add((kind, text))
        if cls == "enforced":
            by = item.get("enforced_by")
            if by not in enforcers(rule, governed):
                out.append("%r is marked enforced, so enforced_by must name what checks it; this rule offers: %s"
                           % (text, ", ".join(sorted(enforcers(rule, governed))) or "nothing"))
        elif "enforced_by" in item:
            out.append("enforced_by belongs only on an item of class enforced (%r)" % text)
    for kind, text in want:
        if (kind, text) not in seen:
            out.append("no class given for the %s %r" % (kind.replace("_", " "), text))
    return out
