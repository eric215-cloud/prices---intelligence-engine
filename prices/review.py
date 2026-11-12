"""Temporal review: what changes between two evaluations, and what sits downstream."""
import datetime

from .engine import evaluate, to_date


def diff(before, after):
    """List status changes between two Results, with the downstream atoms that relied on each."""
    out = []
    for atom in sorted(set(before.atoms()) | set(after.atoms())):
        if not atom.startswith(("have:", "can_get:")):
            continue
        a, b = before.status(atom), after.status(atom)
        if a != b:
            out.append({"atom": atom, "before": a, "after": b,
                        "downstream_before": before.dependents(atom) if before.level_of(atom) else []})
    return out


def new_flags(before, after):
    return [f for f in after.flags if f not in before.flags]


def review(store, profile, d1, d2):
    a, b = evaluate(store, profile, d1), evaluate(store, profile, d2)
    changes = diff(a, b)
    review_set = set()
    for c in changes:
        review_set.update(c["downstream_before"])
    return {"profile": profile, "from": str(to_date(d1)), "to": str(to_date(d2)), "changes": changes,
            "new_flags": new_flags(a, b),
            "downstream_review": sorted(review_set - {c["atom"] for c in changes})}


def boundaries(store, profile, start, until):
    """Every date in (start, until] on which something could change."""
    start, until = to_date(start), to_date(until)
    one = datetime.timedelta(days=1)
    ds = set()
    recs = list(store.profile(profile).holdings.values()) + list(store.rules.values())
    for rec in recs:
        if rec.get("valid_from"):
            ds.add(to_date(rec["valid_from"]))
        if rec.get("valid_to"):
            ds.add(to_date(rec["valid_to"]) + one)
        rb = rec.get("verification", {}).get("review_by")
        if rb:
            ds.add(to_date(rb) + one)
    return sorted(d for d in ds if start < d <= until)


def timeline(store, profile, start, until):
    events, prev_date = [], to_date(start)
    prev = evaluate(store, profile, prev_date)
    for d in boundaries(store, profile, start, until):
        cur = evaluate(store, profile, d)
        changes, flags = diff(prev, cur), new_flags(prev, cur)
        if changes or flags:
            events.append({"date": d.isoformat(), "changes": changes, "new_flags": flags})
        prev = cur
    return events
