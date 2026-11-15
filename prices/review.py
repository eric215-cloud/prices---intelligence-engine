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
    out = {"profile": profile, "from": str(to_date(d1)), "to": str(to_date(d2)), "changes": changes,
           "new_flags": new_flags(a, b),
           "downstream_review": sorted(review_set - {c["atom"] for c in changes})}
    ending = _credit_periods(store, profile, d1, d2)
    if ending:                    # key exists only when a structured credit applies to this person in the window
        out["credit_periods"] = ending
    return out


def _credit_periods(store, profile, d1, d2):
    """Allowance periods of recurring credits that end in the window (credits.py). Empty for stores without credit terms."""
    if not any(isinstance(r.get("credit"), dict) for r in store.rules.values()):
        return []
    from .credits import events
    return events(store, profile, d1, d2)


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
    prof = store.profile(profile)
    if prof.qualifications or prof.entitlements:
        from .earned import boundary_dates
        ds |= boundary_dates(store, profile)
    if any(e["kind"] == "election" for e in store.entities.values()):
        from . import elections
        ds |= elections.boundary_dates(store, profile)
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
    by_date = {e["date"]: e for e in events}
    for c in _credit_periods(store, profile, start, until):      # each on the last day of its period
        by_date.setdefault(c["date"], {"date": c["date"], "changes": [], "new_flags": []}).setdefault("credit_periods", []).append(c)
    return [by_date[d] for d in sorted(by_date)]
