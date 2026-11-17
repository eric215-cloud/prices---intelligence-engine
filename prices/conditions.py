"""Reviewed conditions: what a rule's text says about WHO has its output, and whether the engine checks it.

A rule carries terms as text in two lists: `restrictions` (what the source states) and `open_questions` (what
nobody has established yet). Text is not enforcement. Before a rule may establish anything, a reviewer records,
for every one of those texts, which of these it is:

    restrictions
      enforced             a condition on who has the output that the rule itself checks. `enforced_by` lists the
                           machine conditions that check it (see CLAIMS below); each must be demonstrably true on
                           EVERY path by which the rule can establish its output, or the item blocks
      unchecked            a condition on who has the output that is known and that nothing checks      -> BLOCKS
      usage                how the output is used (limits, booking channel, claim rules, notes): it does not decide
                           who has it
    open_questions
      affects_eligibility  the answer could change who has the output                                   -> BLOCKS
      informational        the answer would not change who has the output (a price, a ratio, a validity note)

    (no class recorded)    a text the reviewer has not classified, or that was added or reworded since   -> BLOCKS
    (stale review)         the rule's texts were edited after review (one removed or reworded)          -> BLOCKS

While anything BLOCKS, nothing is established through the rule: the engine reports the output as UNRESOLVED and
gives each blocking text as the reason. A missing classification is never read as approval.

CLAIMS (repair of 2026-11-17). An `enforced` item names the exact structured conditions it relies on:

    {"holds": "<entity>"}                 every path requires holding this entity
    {"not": {"holds": "<entity>"}}        every path requires a RECORDED absence of it (engine: unknown is not absent)
    {"metric": "<id>", "gte": N}          every path requires this figure at N or more (a path checking less fails)
    {"valid_to": "YYYY-MM-DD"}            the rule ends on or before this date
    {"valid_from": "YYYY-MM-DD"}          the rule starts on or after this date
    {"earn_threshold": N}                 an earns rule whose threshold is N or more
    {"earn_activation": true}             an earns rule whose activation is "required": reaching the threshold gives
                                          ACTIVATION_REQUIRED, never the benefit, until the owner records it
    {"earn_term": true}                   an earns rule whose `term` computes when the benefit ends
    {"acquire": true}                     an acquire rule: the output is reached only by the step itself, and held
                                          only once the owner records it
    {"election": true}                    a cardholder election governs the rule

"Every path" is decided on the rule's `when` itself: a leaf satisfies a claim only if it is that claim or stricter;
`all` satisfies it if one part does; `any` only if every alternative does. Anything that cannot be shown that way
fails, and the item blocks. The check is repeated whenever the engine reads the rule, so an item that stops being
demonstrable (for example after the rule's dates change) blocks again. Two cross-checks on the text:

    - a restriction that names an action (register, enrol, activate, link, opt in, sign up, nominate) needs a claim
      that the action itself is recorded: {"holds": <an action entity>}, {"acquire": true}, {"election": true} or
      {"earn_activation": true}.
      A date window says when the action may be taken, never that it was;
    - a {"metric"} or {"earn_threshold"} claim must carry a number that appears in the text, when the text states one.

The record lives on the rule:

    "condition_review": {"by": "<a promotion reviewer>", "on": "YYYY-MM-DD", "changeset": "<id>",
                         "items": [{"text": "<exactly the text>", "class": "unchecked"},
                                   {"text": "...", "class": "enforced", "enforced_by": [{"holds": "act.enrol"}]}]}

It is written only by `promote_candidate` and `classify_conditions`, both of which need a reviewer's attestation.
Texts are matched exactly. Adding a restriction or a question leaves the new text unclassified; removing or rewording
one sets the whole record aside (it describes a rule that no longer exists), and that blocks even when no text is
left. Either way the rule establishes nothing until a reviewer classifies it as it now stands.
"""
import re

RESTRICTION_CLASSES = ("enforced", "unchecked", "usage")
QUESTION_CLASSES = ("affects_eligibility", "informational")
BLOCKING = {"unchecked": "a condition on who has this, not checked by the engine",
            "affects_eligibility": "an open question that could change who has this",
            "unproven": "marked enforced, but the rule does not demonstrably enforce it on every path",
            "stale": "the rule was edited after its review",
            None: "not classified by a reviewer, so not relied on"}
ACTION_WORDS = re.compile(r"\b(regist\w*|enrol\w*|activat\w*|link\w*|opt(?:s|ed|ing)?[- ]in|sign(?:s|ed|ing)?[- ]up|nominat\w*)", re.I)
_DATE = re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)\b", re.I)


def context(store):
    """What claim checks need to know beyond the rule: entity kinds and which rules an election governs."""
    from .elections import governed
    return {"entities": store.entities, "governed": set(governed(store))}


def texts(rule):
    """[(kind, text)] for every text on the rule that needs a class: kind is "restriction" or "open_question"."""
    return [("restriction", t) for t in rule.get("restrictions") or []] + [("open_question", t) for t in rule.get("open_questions") or []]


def _recorded(rule):
    out = {}
    for item in (rule.get("condition_review") or {}).get("items", []) if isinstance((rule.get("condition_review") or {}).get("items"), list) else []:
        if isinstance(item, dict):
            kind = "restriction" if item.get("class") in RESTRICTION_CLASSES else "open_question" if item.get("class") in QUESTION_CLASSES else None
            out[(kind, item.get("text"))] = item
    return out


def stale(rule):
    """True when the review describes texts that are no longer on the rule: it was edited after review."""
    if "condition_review" not in rule:
        return False
    review = rule["condition_review"]
    if not isinstance(review, dict) or not isinstance(review.get("items"), list):
        return True
    now = set(texts(rule))
    return any(key not in now for key in _recorded(rule))


def classes(rule):
    """[(kind, text, class or None)]. None: the reviewer's record has no class for exactly this text and kind.

    The record covers the rule as it was reviewed. If it classifies a text that is no longer on the rule, the rule
    has been edited since (a condition was removed or reworded), so the whole record is set aside: every text
    counts as unclassified until a reviewer looks at the rule as it now stands."""
    recorded = {} if stale(rule) else {k: v.get("class") for k, v in _recorded(rule).items()}
    return [(kind, text, recorded.get((kind, text))) for kind, text in texts(rule)]


def blockers(rule, ctx=None):
    """[(reason class, text)] for everything that stops this rule from establishing its output.

    An `enforced` item counts only while its claims can be demonstrated against the rule as it now stands (ctx gives
    entity kinds and governed rules; without it, claims that need them fail, which is the safe side)."""
    out = []
    if stale(rule):
        gone = [t for (_k, t) in _recorded(rule) if (_k, t) not in set(texts(rule))]
        out.append(("stale", "%d reviewed text(s) are no longer on the rule (%s); a reviewer must classify it as it now stands"
                    % (len(gone), "; ".join(repr(g) for g in gone[:3])) if gone else "the review record is malformed"))
    items = {} if stale(rule) else _recorded(rule)
    for kind, text, cls in classes(rule):
        if cls in BLOCKING:
            out.append((cls, text))
        elif cls == "enforced" and item_issues(rule, items[(kind, text)], ctx):
            out.append(("unproven", text))
    return out


def tokens(rule, ctx=None):
    """The engine's "unknown" tokens for a rule: one per blocking text, worded for a report.

    Texts nobody has classified are counted in one token per rule: the list is in `explain` and in lint."""
    out, waiting = set(), 0
    for cls, text in blockers(rule, ctx):
        if cls is None:
            waiting += 1
        else:
            out.add(("unknown", "%s (%s): %s" % (BLOCKING[cls], rule.get("id"), text)))
    if waiting:
        out.add(("unknown", "%d restriction(s) or open question(s) on %s are %s (OP-14)" % (waiting, rule.get("id"), BLOCKING[None])))
    return frozenset(out)


def describe(rule, ctx=None):
    """Every text on the rule with its recorded class, for a report: [{kind, text, class, enforced_by, blocks}]."""
    items = {} if stale(rule) else _recorded(rule)
    out = []
    for kind, text, cls in classes(rule):
        item = items.get((kind, text), {})
        unproven = cls == "enforced" and bool(item_issues(rule, item, ctx))
        out.append({"kind": kind, "text": text, "class": cls, "enforced_by": item.get("enforced_by"),
                    "blocks": cls in BLOCKING or unproven, "unproven": item_issues(rule, item, ctx) if unproven else []})
    return out


def unclassified(rule):
    return [text for _kind, text, cls in classes(rule) if cls is None]


def implies(cond, claim):
    """True only if EVERY way `cond` can be satisfied also satisfies `claim`. Sound, deliberately not complete:
    when this cannot show it, the answer is False and the item blocks."""
    if not isinstance(cond, dict):
        return False
    if "all" in cond:
        return isinstance(cond["all"], list) and any(implies(c, claim) for c in cond["all"])
    if "any" in cond:
        return isinstance(cond["any"], list) and bool(cond["any"]) and all(implies(c, claim) for c in cond["any"])
    if "holds" in claim:
        return "holds" in cond and cond["holds"] == claim["holds"]
    if "metric" in claim:
        g = cond.get("gte")
        return "metric" in cond and cond["metric"] == claim["metric"] and _num(g) and g >= claim["gte"]
    if "not" in claim:
        return "not" in cond and cond["not"] == claim["not"]
    return False


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def numbers_in(text):
    """Numbers a text states, with dates taken out: '$4,000 by March 31, 2027' -> {4000}."""
    text = _DATE.sub(" ", text)
    out = set()
    for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            out.add(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def claim_issues(rule, claim, ctx=None):
    """Why this one claim is not demonstrated for the rule as it stands ([] when it is)."""
    ctx = ctx or {}
    ents, gov = ctx.get("entities"), ctx.get("governed")
    if not isinstance(claim, dict) or len(claim) not in (1, 2) or (len(claim) == 2 and set(claim) != {"metric", "gte"}):
        return ["%r is not a claim: use holds, not, metric+gte, valid_to, valid_from, earn_threshold, earn_activation, earn_term, acquire "
                "or election" % (claim,)]
    if "holds" in claim:
        if not isinstance(claim["holds"], str):
            return ["holds needs an entity id"]
        if ents is not None and claim["holds"] not in ents:
            return ["%s is not an entity" % claim["holds"]]
        return [] if implies(rule["when"], claim) else ["not every way this rule applies requires holding %s" % claim["holds"]]
    if "not" in claim:
        if not (isinstance(claim["not"], dict) and set(claim["not"]) == {"holds"} and isinstance(claim["not"]["holds"], str)):
            return ["not needs {\"holds\": <entity>}"]
        return [] if implies(rule["when"], claim) else ["not every way this rule applies requires a recorded absence of %s" % claim["not"]["holds"]]
    if "metric" in claim:
        if not _num(claim.get("gte")):
            return ["a metric claim must state its threshold: {\"metric\": id, \"gte\": N}"]
        return [] if implies(rule["when"], claim) else [
            "not every way this rule applies requires %s of at least %s" % (claim["metric"], _fmt(claim["gte"]))]
    if "valid_to" in claim or "valid_from" in claim:
        from .schema import is_date
        key = "valid_to" if "valid_to" in claim else "valid_from"
        if not is_date(claim[key]):
            return ["%s needs a date" % key]
        have = rule.get(key)
        ok = have is not None and (have <= claim[key] if key == "valid_to" else have >= claim[key])
        return [] if ok else ["the rule's %s is %s, so it does not %s %s" % (key, have or "not set", "end by" if key == "valid_to" else "start on or after", claim[key])]
    if "earn_threshold" in claim:
        e = rule.get("earn") if rule.get("kind") == "earns" else None
        if not _num(claim["earn_threshold"]):
            return ["earn_threshold needs a number"]
        ok = isinstance(e, dict) and _num(e.get("threshold")) and e["threshold"] >= claim["earn_threshold"]
        return [] if ok else ["the rule has no earn threshold of at least %s" % _fmt(claim["earn_threshold"])]
    if "earn_activation" in claim or "earn_term" in claim:
        e = rule.get("earn") if rule.get("kind") == "earns" else None
        if "earn_activation" in claim:
            ok = claim["earn_activation"] is True and isinstance(e, dict) and e.get("activation") == "required"
            return [] if ok else ["only an earns rule whose activation is \"required\" can claim earn_activation"]
        ok = claim["earn_term"] is True and isinstance(e, dict) and isinstance(e.get("term"), dict)
        return [] if ok else ["only an earns rule with a term can claim earn_term"]
    if "acquire" in claim:
        return [] if claim["acquire"] is True and rule.get("kind") == "acquire" else ["only an acquire rule can claim acquire"]
    if "election" in claim:
        if claim["election"] is not True:
            return ["election must be true"]
        return [] if gov is not None and rule.get("id") in gov else ["no cardholder election is known to govern this rule"]
    return ["%r is not a claim" % (claim,)]


def item_issues(rule, item, ctx=None):
    """Why an `enforced` item is not demonstrated ([] when every claim holds and the text checks pass)."""
    by = item.get("enforced_by")
    claims = [by] if isinstance(by, dict) else by
    if not isinstance(claims, list) or not claims:
        return ["enforced_by must list the conditions that enforce it, e.g. [{\"holds\": \"act.enrol\"}] (old forms such as "
                "\"when:<id>\" or \"dates\" are not accepted: they named something present, not something enforced)"]
    out = []
    for c in claims:
        out += claim_issues(rule, c, ctx)
    text = item.get("text") or ""
    ents = (ctx or {}).get("entities")
    if ACTION_WORDS.search(text):
        records = [c for c in claims if isinstance(c, dict) and (c.get("acquire") is True or c.get("election") is True or
                   c.get("earn_activation") is True or
                   (isinstance(c.get("holds"), str) and ents is not None and ents.get(c["holds"], {}).get("kind") == "action"))]
        if not records:
            out.append("the text names an action (%r); a date window or a card does not show it was done: claim {\"holds\": <the action>}, "
                       "{\"acquire\": true}, {\"election\": true} or {\"earn_activation\": true}, or class it unchecked" % ACTION_WORDS.search(text).group(0))
    stated = numbers_in(text)
    for c in claims:
        if isinstance(c, dict) and stated:
            n = c.get("gte") if "metric" in c else c.get("earn_threshold") if "earn_threshold" in c else None
            if _num(n) and float(n) not in stated:
                out.append("the claim checks %s, which is not a number the text states (%s)" % (_fmt(n), ", ".join(_fmt(x) for x in sorted(stated))))
    return out


def _fmt(x):
    return ("{:,.0f}".format(x) if float(x).is_integer() else str(x)) if _num(x) else str(x)


def review_issues(rule, items, ctx=None):
    """Why a proposed list of classification items is not acceptable for this rule ([] when it is).

    It must give exactly one class to every restriction and every open question now on the rule, with a class of
    the right family, and an `enforced` item's claims must be demonstrated (item_issues)."""
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
            out += ["%r is marked enforced, but %s" % (text, why) for why in item_issues(rule, item, ctx)]
        elif "enforced_by" in item:
            out.append("enforced_by belongs only on an item of class enforced (%r)" % text)
    for kind, text in want:
        if (kind, text) not in seen:
            out.append("no class given for the %s %r" % (kind.replace("_", " "), text))
    return out
