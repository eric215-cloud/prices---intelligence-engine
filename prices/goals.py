"""Goal-directed research: objective text -> a short list of qualified pathways.

Deterministic part (this file): map the goal to tags, find tagged target entities,
evaluate each with the engine, and sort the results into five separate sections.
External part (done by a researcher, recorded via changesets): temporary promotions
and actual availability are stored as dated observations, never as rules.
"""
from .discovery import plan_backward
from .engine import CONDITIONAL, ESTABLISHED, NOT_AVAILABLE, UNRESOLVED, evaluate, in_effect, to_date


def goal_tags(store, text):
    low = " " + text.lower() + " "
    return sorted(t for t, spec in store.vocab["tags"].items()
                  if any(k.lower() in low for k in spec.get("keywords", [])))


def _dims(tags):
    d = {}
    for t in tags:
        d.setdefault(t.split(":", 1)[0], set()).add(t)
    return d


def relevance(entity_tags, gtags):
    """Number of goal dimensions matched; None if the entity conflicts with the goal or matches nothing."""
    e, g, score = _dims(entity_tags), _dims(gtags), 0
    for dim, wanted in g.items():
        if dim in e:
            if not (e[dim] & wanted):
                return None
            score += 1
    return score or None


def chain_lines(node, depth=0):
    label = node["atom"]
    if node.get("via"):
        label += "  <- " + node["via"]
    lines = ["  " * depth + label]
    for s in node.get("supports", []):
        lines += chain_lines(s, depth + 1)
    return lines


def run_goal(store, profile, text, as_of, tags=None, limit=5):
    as_of = to_date(as_of)
    gtags = sorted(tags) if tags else goal_tags(store, text)
    res = evaluate(store, profile, as_of, include_candidates=True)
    prof = store.profile(profile)
    val = prof.meta.get("valuations", {})
    out = {"goal": text, "tags": gtags, "profile": profile, "as_of": as_of.isoformat(),
           "synthetic": bool(prof.meta.get("synthetic")),
           "established": [], "conditional": [], "research": [], "promotions": [], "available": [],
           "notes": []}
    if not gtags:
        out["notes"].append("No vocabulary tag matched the goal text. Pass tags explicitly or add keywords to data/kb/vocab.json.")
        return out

    stale = {f["subject"] for f in res.flags if f["code"] == "STALE_RULE"}
    pool = dict(store.entities)
    cand_rules = {}
    for c in store.candidates.values():
        if c["status"] == "proposed":
            cand_rules["candidate:" + c["id"]] = c
            for e in c.get("proposed_entities", []):
                pool.setdefault(e["id"], e)
    for ent in sorted(pool.values(), key=lambda e: e["id"]):
        rel = relevance(ent.get("tags", []), gtags)
        if rel is None or ent["kind"] == "action":
            continue
        atom = "have:" + ent["id"]
        st = res.status(atom)
        p = {"entity": ent["id"], "name": ent["name"], "relevance": rel, "status": st}
        if st == NOT_AVAILABLE:
            back = plan_backward(store, profile, ent["id"], as_of)
            p["why"] = "no route from current holdings"
            p["research_tasks"] = [t["ask"] for t in back["tasks"]]
            out["research"].append(p)
            continue
        p.update(res.tokens(atom))
        ch = res.chain(atom)
        p["chain"] = chain_lines(ch)
        rules_used = sorted(a for a in _vias(ch) if a in store.rules)
        p["rules"] = rules_used
        p["evidence"] = sorted({e for r in rules_used for e in store.rules[r]["evidence"]})
        p["stale_rules"] = sorted(set(rules_used) & stale)
        p["restrictions"] = [x for r in rules_used for x in store.rules[r].get("restrictions", [])]
        p["open_questions"] = [x for r in rules_used for x in store.rules[r].get("open_questions", [])]
        p["transfers"] = ["%s -> %s at %s%s" % (store.rules[r]["transfer"]["from"], store.rules[r]["output"],
                                                store.rules[r]["transfer"].get("ratio", "?"),
                                                (" (" + store.rules[r]["transfer"]["note"] + ")") if store.rules[r]["transfer"].get("note") else "")
                          for r in rules_used if store.rules[r]["kind"] == "transfer"]
        p["notes"] = [store.rules[r]["value_note"] for r in rules_used if store.rules[r].get("value_note")]
        for via in sorted(_vias(ch)):
            if via in cand_rules:
                p["open_questions"] += ["(candidate %s) %s" % (cand_rules[via]["id"], q) for q in cand_rules[via]["open_questions"]]
        eco = dict(ent.get("economics", {}))
        funding = sorted(a.split(":", 1)[1] for a in res.chain_atoms(atom)
                         if a.startswith("have:") and res.level_of(a) and res.basis(a) == "personal"
                         and store.entities.get(a.split(":", 1)[1], {}).get("kind") == "currency")
        if funding:
            eco["funded_by"] = funding
            held = {h["entity"]: h.get("quantity") for h in prof.holdings.values() if h["state"] == "confirmed"}
            eco["balance_on_record"] = ", ".join("%s: %s" % (f, "{:,.0f}".format(held[f]) if held.get(f) is not None else "not recorded") for f in funding)
        if isinstance(eco.get("points"), (int, float)) and eco.get("currency") in val:
            eco["points_value_usd"] = round(eco["points"] * val[eco["currency"]] / 100.0, 2)
            eco["valuation_basis"] = "%s at %.2f cents/pt (owner assumption in profile.json)" % (eco["currency"], val[eco["currency"]])
        p["economics"] = eco
        section = {ESTABLISHED: "established", CONDITIONAL: "conditional", UNRESOLVED: "research"}[st]
        out[section].append(p)

    def rank(p):
        return (-p["relevance"], len(p.get("steps", [])), len(p.get("unknowns", [])),
                p.get("economics", {}).get("points_value_usd", 1e12), p["entity"])
    for sec in ("established", "conditional", "research"):
        out[sec] = sorted(out[sec], key=rank)
        if len(out[sec]) > limit:
            out["notes"].append("%s: showing %d of %d (ranked by relevance, steps, cost)" % (sec, limit, len(out[sec])))
            out[sec] = out[sec][:limit]

    # foregone alternatives: established/conditional pathways that draw on the same funding currency
    for sec in ("established", "conditional"):
        for p in out[sec]:
            cur = set(p["economics"].get("funded_by", []))
            rivals = sorted(q["entity"] for s in ("established", "conditional") for q in out[s]
                            if q is not p and cur & set(q["economics"].get("funded_by", [])))
            if rivals:
                p["economics"]["competes_for_same_points_with"] = rivals

    for o in sorted(store.observations.values(), key=lambda o: o["id"]):
        if relevance(o["tags"], gtags) is None or not in_effect(o, as_of):
            continue
        out["promotions" if o["type"] == "promotion" else "available"].append(
            {"id": o["id"], "summary": o["summary"], "checked_on": o["checked_on"], "valid_to": o["valid_to"],
             "url": o["url"], "publisher": o["publisher"], "confirmed_by": o.get("confirmed_by")})

    for g in store.vocab.get("goal_research", []):
        if set(g.get("applies_dims", [])) <= set(_dims(gtags)):
            out["research"].append({"entity": None, "name": g["id"], "relevance": 0, "status": "EXTERNAL_RESEARCH",
                                    "research_tasks": [g["ask"]], "record_as": g["record_as"]})
    if not out["available"]:
        out["notes"].append("No verified availability on record. Nothing here confirms that a specific flight, room or "
                            "redemption can be booked; that requires a live check recorded as an observation.")
    if out["synthetic"]:
        out["notes"].append("Profile is SYNTHETIC demonstration data. This is not a statement about any real person's holdings.")
    return out


def _vias(node):
    out = set()
    if node.get("via"):
        out.add(node["via"])
    for s in node.get("supports", []):
        out |= _vias(s)
    return out
