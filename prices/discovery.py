"""Discovery planning. Deterministic: decides WHAT to research and records what was covered.

The research itself (web search, reading sources) is done by whoever executes the
task list - an AI model with search, or a person. Results come back only as
changesets: add_candidate (one per relationship) and record_discovery_run.

The coverage ledger (data/coverage/ledger.json) has one cell per
"<entity>|<question>". An empty or old cell is a known gap. Discovery is the act of
filling cells, so relationships nobody thought to ask about still get asked about.
"""
import re

from .engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, evaluate, leaves, to_date
from .lint import signature

OUTPUT_CONTRACT = ("For each relationship found: one add_candidate changeset. Then exactly one "
                   "record_discovery_run changeset listing every cell investigated, including cells where "
                   "nothing was found. See docs/DISCOVERY.md.")


def _fresh(store, cell, as_of, max_age):
    c = store.ledger["cells"].get(cell)
    return c is not None and (to_date(as_of) - to_date(c["last_run"])).days <= max_age


def _task(store, mode, cell, question, names, priority, why):
    q = store.vocab["questions"][question]
    fmt = dict(names)
    return {"task_id": "%s:%s" % (mode, cell), "mode": mode, "cell": cell, "question": question,
            "ask": q["ask"].format(**fmt), "suggested_queries": [s.format(**fmt) for s in q.get("queries", [])],
            "priority": priority, "why": why, "output": OUTPUT_CONTRACT}


def _questions(store, mode, kind):
    return sorted(q for q, spec in store.vocab["questions"].items()
                  if mode in spec.get("modes", []) and kind in spec.get("applies_to", []))


def plan_forward(store, profile, as_of, max_age=180):
    """What can existing holdings unlock? One task per (held or reachable entity) x (applicable question)."""
    res, tasks = evaluate(store, profile, as_of), []
    for ent in sorted(store.entities.values(), key=lambda e: e["id"]):
        st = res.have(ent["id"])
        if st not in (ESTABLISHED, CONDITIONAL) or ent["kind"] == "action":
            continue
        for q in _questions(store, "forward", ent["kind"]):
            cell = "%s|%s" % (ent["id"], q)
            if _fresh(store, cell, as_of, max_age):
                continue
            never = cell not in store.ledger["cells"]
            pr = (30 if st == ESTABLISHED else 20) + (5 if never else 0)
            tasks.append(_task(store, "forward", cell, q, {"name": ent["name"]}, pr,
                               "%s is %s; cell %s" % (ent["id"], st, "never investigated" if never else "stale")))
    return sorted(tasks, key=lambda t: (-t["priority"], t["cell"]))


def _producers(store, entity, include_candidates=True):
    out = [(r["id"], r, r["verification"]["status"]) for r in store.rules.values()
           if r["output"] == entity and r["verification"]["status"] != "retired"]
    if include_candidates:
        out += [("candidate:" + c["id"], c["proposed_rule"], "candidate") for c in store.candidates.values()
                if c["status"] == "proposed" and c["proposed_rule"]["output"] == entity]
    return sorted(out, key=lambda x: x[0])


def plan_backward(store, profile, target, as_of, max_age=180):
    """What qualification pathways lead to the target? Goal regression over rules and candidates."""
    res, tasks = evaluate(store, profile, as_of), []

    def node(entity, seen):
        st = res.have(entity)
        n = {"entity": entity, "status": st}
        if st == ESTABLISHED or entity in seen:
            return n
        seen = seen | {entity}
        prods = _producers(store, entity)
        n["routes"] = []
        for rid, rule, ver in prods:
            needs = sorted({i for k, i, neg in leaves(rule["when"]) if k == "holds" and not neg})
            n["routes"].append({"rule": rid, "kind": rule["kind"], "verification": ver,
                                "needs": [node(x, seen) for x in needs]})
        ent = store.entities.get(entity, {})
        if not prods and ent.get("kind") != "action":
            for q in _questions(store, "backward", ent.get("kind", "")):
                cell = "%s|%s" % (entity, q)
                if not _fresh(store, cell, as_of, max_age):
                    tasks.append(_task(store, "backward", cell, q, {"name": ent.get("name", entity)}, 25,
                                       "no known route to %s, which the target needs" % entity))
        return n

    tree = node(target, frozenset())
    uniq = {t["cell"]: t for t in tasks}
    return {"target": target, "tree": tree, "tasks": sorted(uniq.values(), key=lambda t: t["cell"])}


def plan_bridge(store, profile, as_of, max_age=180):
    """Can two or more holdings combine? (a) near-misses among known rules, (b) unexplored pairs."""
    res = evaluate(store, profile, as_of)
    near = []
    for ent_id in sorted(store.entities):
        if res.have(ent_id) == ESTABLISHED:
            continue
        for rid, rule, ver in _producers(store, ent_id):
            needs = sorted({i for k, i, neg in leaves(rule["when"]) if k == "holds" and not neg})
            have = [x for x in needs if res.have(x) == ESTABLISHED]
            if len(needs) >= 2 and have:
                near.append({"rule": rid, "output": ent_id, "verification": ver, "satisfied": have,
                             "missing": [{"entity": x, "status": res.have(x)} for x in needs if x not in have]})
    held = [e for e in sorted(store.entities.values(), key=lambda e: e["id"])
            if e["kind"] in ("status", "card") and res.have(e["id"]) == ESTABLISHED]
    tasks = []
    for i, a in enumerate(held):
        for b in held[i + 1:]:
            if a.get("program") and a.get("program") == b.get("program"):
                continue
            for q in _questions(store, "bridge", "pair"):
                cell = "%s+%s|%s" % (a["id"], b["id"], q)
                if not _fresh(store, cell, as_of, max_age):
                    tasks.append(_task(store, "bridge", cell, q, {"a": a["name"], "b": b["name"]}, 10,
                                       "both held; combination never investigated"))
    return {"near_misses": near, "tasks": tasks}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def plan_exploratory(store, profile, as_of, max_age=180):
    """What lies outside the known network? Unreached entities, and names seen in research but not modelled."""
    res, tasks = evaluate(store, profile, as_of), []
    for ent in sorted(store.entities.values(), key=lambda e: e["id"]):
        if res.have(ent["id"]) != NOT_AVAILABLE:
            continue
        for q in _questions(store, "exploratory", ent["kind"]):
            cell = "%s|%s" % (ent["id"], q)
            if not _fresh(store, cell, as_of, max_age):
                tasks.append(_task(store, "exploratory", cell, q, {"name": ent["name"]}, 15,
                                   "%s is in the knowledge base but currently unreachable" % ent["id"]))
    known = {_slug(e["name"]) for e in store.entities.values()} | {_slug(e) for e in store.entities}
    mentions = set()
    for c in store.candidates.values():
        mentions.update(c.get("mentions", []))
    for run in store.discovery_runs.values():
        mentions.update(run.get("mentions", []))
    mentions.update(store.vocab.get("watchlist", []))
    for m in sorted(mentions):
        cell = "mention:%s|identify" % _slug(m)
        if _slug(m) not in known and "identify" in store.vocab["questions"] and not _fresh(store, cell, as_of, max_age):
            tasks.append(_task(store, "exploratory", cell, "identify", {"name": m}, 12,
                               "%r was named in research but is not modelled" % m))
    return sorted(tasks, key=lambda t: (-t["priority"], t["cell"]))


def _parts(sig):
    kind, rest = sig.split(":", 1)
    needs, out = rest.split("->")
    return kind, set(x for x in needs.split("+") if x), out


def novelty(store, candidate):
    """Is this candidate a relationship the system did not already have, in any wording?

    Not novel if a rule, a seeded example or another candidate already leads to the same
    output from any of the same qualifications (so a narrower or reworded copy is caught).
    """
    sig = signature(candidate["proposed_rule"])
    _k, needs, out = _parts(sig)
    known = [("rule " + r["id"], signature(r)) for r in store.rules.values()]
    known += [("seed/example from the commissioning brief", s) for s in store.vocab.get("seeded_signatures", [])]
    known += [("candidate " + c["id"], signature(c["proposed_rule"])) for c in store.candidates.values()
              if c["id"] != candidate["id"]]
    reasons = []
    for label, other in known:
        _ok, o_needs, o_out = _parts(other)
        if o_out == out and (o_needs & needs or o_needs == needs):
            reasons.append("overlaps %s (%s)" % (label, other))
    return {"signature": sig, "novel": not reasons, "reasons": reasons}


def coverage_summary(store, profile, as_of, max_age=180):
    fwd = plan_forward(store, profile, as_of, max_age)
    cells = store.ledger["cells"]
    return {"cells_recorded": len(cells),
            "found": sum(1 for c in cells.values() if c["outcome"] == "found"),
            "nothing_found": sum(1 for c in cells.values() if c["outcome"] == "nothing_found"),
            "inconclusive": sum(1 for c in cells.values() if c["outcome"] == "inconclusive"),
            "forward_gaps": len(fwd)}
