"""Earned benefits: public rule, personal achievement and current entitlement, kept apart.

Three layers, three kinds of record:

    PUBLIC RULE            data/kb/rules/            kind "earns": reach a threshold on a measure, on one
                                                     card, within one period, and benefit X is on offer.
                                                     Sourced like any rule. Says nothing about any person.
    PERSONAL ACHIEVEMENT   profiles/<p>/qualifications/   that person's dated readings of the measure, on
                                                     one of their own accounts, in one cycle (e.g. 2026).
    CURRENT ENTITLEMENT    profiles/<p>/entitlements/     the benefit as it actually sits on that account:
                                                     its own start, its own expiry, its own allowance and use.

What follows from what
    readings at/above the threshold    -> the person is ELIGIBLE (engine: can_get). Never more.
    a confirmed entitlement record     -> the person HAS the benefit, between its own dates (engine: have).
    nothing recorded                   -> nothing is derived.

Dates are never guessed. A date may be the word "unknown"; the consequences are computed, not assumed:
    - a reading counts only from the date it refers to (a later reading never reaches back);
    - a reading with an unknown date counts from the day its owner confirmed it, or from the end of
      the cycle if that came first, and is unresolved before then;
    - an entitlement with an unknown start is unresolved before the day its owner confirmed it active;
    - an entitlement with an unknown expiry is unresolved after that day.

This module computes; it stores nothing. `survey` is the single source for both the engine's base
facts (`inject`) and the `earned` report, so the two cannot disagree.
"""
import calendar
import datetime

from .engine import C, E, LEVELS, NONE, P, U, in_effect, to_date

UNKNOWN = "unknown"
# achievement
NOT_RECORDED, NOT_STARTED, BELOW, NOT_QUALIFIED, INCOMPLETE = "NOT_RECORDED", "NOT_STARTED", "BELOW", "NOT_QUALIFIED", "INCOMPLETE"
ACHIEVED, UNCERTAIN, CONFLICT = "ACHIEVED", "UNCERTAIN", "CONFLICT"
# entitlement
NOT_OFFERED, NOT_EARNED, UNRESOLVED = "NOT_OFFERED", "NOT_EARNED", "UNRESOLVED"
EARNED_NOT_CONFIRMED, ACTIVATION_REQUIRED, LAPSED_UNCLAIMED = "EARNED_NOT_CONFIRMED", "ACTIVATION_REQUIRED", "LAPSED_UNCLAIMED"
NOT_YET_EFFECTIVE, ACTIVE, EXPIRED, ENDED, EXHAUSTED = "NOT_YET_EFFECTIVE", "ACTIVE", "EXPIRED", "ENDED", "EXHAUSTED"

ONE_DAY = datetime.timedelta(days=1)


def day(s):
    """A date, or None for "unknown" / missing."""
    return None if s in (None, UNKNOWN) else to_date(s)


def cycle_bounds(period, label):
    if period != "calendar_year":
        raise ValueError("unsupported period %r" % period)
    y = int(label)
    return datetime.date(y, 1, 1), datetime.date(y, 12, 31)


def expected_end(term, label):
    """The last day the public rule says the benefit lasts, for a given cycle; None if the rule does not say."""
    if term.get("ends") != "fixed":
        return None
    y, m = int(label) + term["year_offset"], term["month"]
    d = calendar.monthrange(y, m)[1] if term.get("month_end") else term["day"]
    return datetime.date(y, m, d)


def term_text(term):
    if term.get("ends") != "fixed":
        return "end date not stated by the rule" + (" (%s)" % term["note"] if term.get("note") else "")
    month, off = calendar.month_name[term["month"]], term["year_offset"]
    which = "the last day of %s" % month if term.get("month_end") else "%s %d" % (month, term["day"])
    year = "of the qualifying year" if off == 0 else "of the following year" if off == 1 else "%d years after the qualifying year" % off
    return "through %s %s" % (which, year)


def known_from(reading, cycle_end):
    """The first date on which a reading is known to hold; None if it cannot be relied on at all."""
    if reading["observed_on"] != UNKNOWN:
        return to_date(reading["observed_on"])
    c = day(reading.get("confirmed_on"))
    return None if c is None else min(cycle_end, c)


def achievement(threshold, qual, as_of, period="calendar_year"):
    """Has the threshold been reached in this cycle, judged on `as_of`, from the readings on file?

    Cumulative progress within a cycle is taken as non-decreasing. Readings that contradict that
    across the threshold are reported as a conflict, never resolved by picking one.
    """
    start, end = cycle_bounds(period, qual["cycle"])
    live = [r for r in qual["readings"] if r["state"] != "superseded"]
    conf = [r for r in live if r["state"] == "confirmed"]
    below = [r for r in conf if r["observed_on"] != UNKNOWN and r.get("value_kind", "exact") == "exact" and r["value"] < threshold]
    usable = [r for r in conf if known_from(r, end) is not None and known_from(r, end) <= as_of]
    above_now = sorted((r for r in usable if r["value"] >= threshold), key=lambda r: (known_from(r, end), r["id"]))
    shown = sorted((r for r in usable if r["observed_on"] != UNKNOWN), key=lambda r: (r["observed_on"], r["value"]))
    out = {"state": None, "by": None, "basis": [], "detail": "", "progress": None,
           "period": [start.isoformat(), end.isoformat()], "threshold": threshold}
    if shown:
        last = shown[-1]
        out["progress"] = {"value": last["value"], "as_of": last["observed_on"], "reading": last["id"],
                           "kind": last.get("value_kind", "exact"), "final": bool(last.get("final")),
                           "age_days": (as_of - to_date(last["observed_on"])).days}
    elif usable:     # only undated statements so far: show the largest, and say its date is unknown
        last = max(usable, key=lambda r: (r["value"], r["id"]))
        out["progress"] = {"value": last["value"], "as_of": UNKNOWN, "reading": last["id"], "kind": "at_least", "final": False, "age_days": None}
    if as_of < start:
        out.update(state=NOT_STARTED, detail="the qualifying period starts %s" % start)
        return out
    if above_now:
        first, first_on = above_now[0], known_from(above_now[0], end)
        clash = sorted(r["id"] for r in below if to_date(r["observed_on"]) >= first_on)
        if clash:
            out.update(state=CONFLICT, basis=[first["id"]] + clash,
                       detail="reading %s is at or above the threshold by %s, but %s show less on or after that date"
                              % (first["id"], first_on, ", ".join(clash)))
            return out
        dated = first["observed_on"] != UNKNOWN
        out.update(state=ACHIEVED, by=first_on.isoformat(), basis=[first["id"]],
                   detail=("at or above the threshold on %s (reading %s). The day the threshold was crossed is not recorded"
                           % (first_on, first["id"])) if dated else
                          ("owner confirmed reaching the threshold during the cycle, date unknown (reading %s). "
                           "Relied on from %s only" % (first["id"], first_on)))
        return out
    below_until = max((to_date(r["observed_on"]) for r in below), default=None)
    if below_until is not None and as_of <= below_until:
        out.update(state=BELOW, detail="below the threshold; a confirmed reading dated %s still shows less" % below_until)
        return out
    pending = []
    for r in sorted((r for r in live if r["value"] >= threshold), key=lambda r: r["id"]):
        if r["state"] != "confirmed":
            pending.append("%s is not confirmed" % r["id"])
        elif r["observed_on"] == UNKNOWN:
            pending.append("%s has no date and is relied on only from %s" % (r["id"], known_from(r, end)))
        else:
            pending.append("%s is dated %s, after this query date" % (r["id"], r["observed_on"]))
    if pending:
        out.update(state=UNCERTAIN, basis=sorted(r["id"] for r in live if r["value"] >= threshold),
                   detail="not established on this date: " + "; ".join(pending))
    elif any(r.get("final") for r in below):
        out.update(state=NOT_QUALIFIED, basis=[r["id"] for r in below if r.get("final")],
                   detail="final figure for the cycle is below the threshold")
    elif as_of > end:
        out.update(state=INCOMPLETE, detail="the cycle has ended and no final figure is on record")
    elif out["progress"]:
        out.update(state=BELOW, detail="below the threshold as of the latest reading (%s, %d days before this query date); "
                                       "later progress is not recorded" % (out["progress"]["as_of"], out["progress"]["age_days"]))
    else:
        out.update(state=BELOW, detail="no confirmed reading on or before this date")
    return out


def credit(inst, as_of):
    """Allowance, what is confirmed used, what may also have been used. Never merged across instances."""
    allow, used, maybe = inst["allowance"]["amount"], 0, 0
    for u in inst.get("usage", []):
        if u["state"] == "superseded":
            continue
        d, c = day(u["used_on"]), day(u.get("confirmed_on"))
        if u["state"] == "confirmed" and d is not None:
            used += u["amount"] if d <= as_of else 0
        elif u["state"] == "confirmed":            # used on an unrecorded date, at the latest by the confirmation
            if c <= as_of:
                used += u["amount"]
            else:
                maybe += u["amount"]
        elif d is None or d <= as_of:
            maybe += u["amount"]
    return {"allowance": allow, "unit": inst["allowance"]["unit"], "used": used, "possibly_used": maybe,
            "remaining": allow - used, "remaining_at_least": max(0, allow - used - maybe)}


def instance_state(inst, as_of, period="calendar_year"):
    """Where one entitlement record stands on `as_of`: (state, [reasons it is unresolved], credit or None)."""
    start, _end = cycle_bounds(period, inst["cycle"])
    lo, hi, ended, conf = day(inst["effective_from"]), day(inst["expires_on"]), day(inst.get("ended_on")), day(inst.get("confirmed_on"))
    cr = credit(inst, as_of) if "allowance" in inst else None
    if as_of < (lo or start):
        return NOT_YET_EFFECTIVE, [], cr
    if ended is not None and as_of > ended:
        return ENDED, [], cr
    if hi is not None and as_of > hi:
        return EXPIRED, [], cr
    why = []
    if inst["state"] != "confirmed":
        why.append("not confirmed by the owner")
    else:
        if lo is None and as_of < conf:
            why.append("effective date not recorded; first confirmed active on %s" % conf)
        if hi is None and ended is None and as_of > conf:
            why.append("expiry not recorded; last confirmed active on %s" % conf)
    if cr is not None:
        if cr["used"] > cr["allowance"]:
            why.append("recorded use (%s) exceeds the allowance (%s)" % (num(cr["used"]), num(cr["allowance"])))
        elif cr["remaining"] <= 0:
            return (UNRESOLVED if why else EXHAUSTED), why, cr
        elif cr["remaining_at_least"] <= 0:
            why.append("unconfirmed use may have exhausted the credit")
    return (UNRESOLVED if why else ACTIVE), why, cr


def num(v):
    return "{:,.0f}".format(v) if float(v) == int(v) else "{:,.2f}".format(v)


def _covers(rule, start, end):
    """Does the public offer cover this qualifying cycle? (Offer validity, not anyone's personal expiry.)"""
    f, t = to_date(rule.get("valid_from")), to_date(rule.get("valid_to"))
    return (f is None or f <= end) and (t is None or start <= t)


def survey(store, profile, as_of):
    """Everything about earned benefits for one person on one date. Pure; reads the store only."""
    as_of = to_date(as_of)
    prof, ents = store.profile(profile), store.entities
    earn_rules = sorted((r for r in store.rules.values() if r["kind"] == "earns"), key=lambda r: r["id"])
    by_card = {}
    for r in earn_rules:
        by_card.setdefault(r["when"].get("holds"), []).append(r)
    flags, facts, accounts = [], [], []

    def flag(code, severity, subject, detail):
        flags.append({"code": code, "severity": severity, "subject": subject, "detail": detail})

    referenced = {q["account"] for q in prof.qualifications.values()} | {e["account"] for e in prof.entitlements.values()}
    for h in sorted(prof.holdings.values(), key=lambda h: h["id"]):
        rules = by_card.get(h["entity"], [])
        if not rules and h["id"] not in referenced:
            continue
        held = h["state"] == "confirmed" and in_effect(h, as_of)
        acct_note = ("confirmed, held on this date" if held else
                     "recorded but not confirmed" if h["state"] == "unconfirmed" and in_effect(h, as_of) else "not held on this date")
        quals = {(q["measure"], q["cycle"]): q for q in prof.qualifications.values() if q["account"] == h["id"]}
        insts = [e for e in prof.entitlements.values() if e["account"] == h["id"]]
        labels = {c for (_m, c) in quals} | {e["cycle"] for e in insts}
        if held and any(r["verification"]["status"] != "retired" and _covers(r, *cycle_bounds(r["earn"]["period"], str(as_of.year))) for r in rules):
            labels.add(str(as_of.year))
        cycles = []
        for label in sorted(labels):
            for measure in sorted({r["earn"]["measure"] for r in rules} | {m for (m, c) in quals if c == label}):
                group = [r for r in rules if r["earn"]["measure"] == measure]
                period = group[0]["earn"]["period"] if group else "calendar_year"
                start, end = cycle_bounds(period, label)
                q = quals.get((measure, label))
                cyc = {"cycle": label, "period": [start.isoformat(), end.isoformat()], "measure": measure,
                       "unit": group[0]["earn"].get("unit", "") if group else "", "qualification": q["id"] if q else None,
                       "readings": q["readings"] if q else [], "benefits": []}
                for rule in group:
                    cyc["benefits"].append(_benefit(store, prof, h, held, acct_note, rule, label, q, insts, as_of, flag, facts))
                if cyc["benefits"] or q:
                    cyc["progress"] = achievement(0, q, as_of, period)["progress"] if q else None
                    cycles.append(cyc)
        accounts.append({"account": h["id"], "card": h["entity"], "card_name": ents.get(h["entity"], {}).get("name", h["entity"]),
                         "account_state": acct_note, "cycles": cycles})
    return {"profile": profile, "as_of": as_of.isoformat(), "synthetic": bool(prof.meta.get("synthetic")),
            "owner": prof.meta["owner"], "accounts": accounts, "flags": flags, "facts": facts}


def _benefit(store, prof, h, held, acct_note, rule, label, q, insts, as_of, flag, facts):
    ents, earn = store.entities, rule["earn"]
    out_ent, status = rule["output"], rule["verification"]["status"]
    start, end = cycle_bounds(earn["period"], label)
    exp = expected_end(earn["term"], label)
    covers = status != "retired" and _covers(rule, start, end)
    public = {"rule": rule["id"], "summary": rule["summary"], "verification": status, "evidence": rule["evidence"],
              "threshold": earn["threshold"], "unit": earn.get("unit", ""), "period": earn["period"], "measure": earn["measure"],
              "term": term_text(earn["term"]), "expected_end": exp.isoformat() if exp else None,
              "activation": earn["activation"], "activation_action": earn.get("activation_action"),
              "allowance": earn.get("allowance"), "offer_valid": [rule.get("valid_from"), rule.get("valid_to")],
              "offered_for_cycle": covers}
    ach = achievement(earn["threshold"], q, as_of, earn["period"]) if q else \
        {"state": NOT_RECORDED, "by": None, "basis": [], "detail": "no progress recorded for this cycle", "progress": None,
         "period": [start.isoformat(), end.isoformat()], "threshold": earn["threshold"]}
    if ach["state"] == CONFLICT:
        flag("CONFLICTING_PROGRESS", "review", q["id"], ach["detail"])
    if ach["state"] == INCOMPLETE:
        flag("QUALIFICATION_OUTCOME_NOT_RECORDED", "review", q["id"],
             "cycle %s ended %s with no final figure on record; outcome for %s is not known" % (label, end, out_ent))

    mine = sorted((e for e in insts if e["rule"] == rule["id"] and e["cycle"] == label), key=lambda e: e["id"])
    live = [e for e in mine if e["state"] != "superseded"]
    rows = []
    for e in live:
        st, why, cr = instance_state(e, as_of, earn["period"])
        if len(live) > 1 and st in (ACTIVE, EXHAUSTED):
            st, why = UNRESOLVED, why + ["more than one record exists for this benefit, account and cycle"]
        if st in (ACTIVE, EXHAUSTED) and ach["state"] in (NOT_QUALIFIED, CONFLICT):
            st, why = UNRESOLVED, why + ["the progress on record for this cycle does not support it (%s)" % ach["state"]]
            flag("CONFLICTING_QUALIFICATION", "review", e["id"],
                 "%s is recorded as held, but cycle %s progress is %s" % (out_ent, label, ach["state"]))
        elif st == ACTIVE and ach["state"] != ACHIEVED:
            flag("QUALIFICATION_NOT_RECORDED", "review", e["id"],
                 "%s stands on the owner's confirmation alone: reaching the threshold in cycle %s is not established on file (%s)"
                 % (out_ent, label, ach["state"]))
        if st == ACTIVE and not held:
            flag("ACCOUNT_NOT_HELD", "review", e["id"],
                 "%s is recorded as active, but account %s is %s. Confirm whether the benefit survived (revise_entitlement)"
                 % (out_ent, h["id"], acct_note))
        if st == ACTIVE and exp is not None and day(e["expires_on"]) is not None and day(e["expires_on"]) != exp:
            flag("TERM_DIFFERS_FROM_RULE", "info", e["id"],
                 "personal expiry %s differs from the rule's stated term (%s); the personal date is used" % (e["expires_on"], exp))
        if st == ACTIVE and cr and earn.get("allowance") and cr["allowance"] != earn["allowance"]["amount"]:
            flag("ALLOWANCE_DIFFERS_FROM_RULE", "info", e["id"],
                 "recorded allowance %s differs from the rule's %s" % (num(cr["allowance"]), num(earn["allowance"]["amount"])))
        if st in (ACTIVE, UNRESOLVED) and cr and cr["possibly_used"]:
            flag("CREDIT_USE_UNCONFIRMED", "review", e["id"],
                 "%s %s of use is recorded but not confirmed; remaining is between %s and %s"
                 % (num(cr["possibly_used"]), cr["unit"], num(cr["remaining_at_least"]), num(cr["remaining"])))
        if st == UNRESOLVED and e["state"] != "confirmed":
            flag("UNCONFIRMED_ENTITLEMENT", "review", e["id"], "%s is recorded but not confirmed" % out_ent)
        elif st == UNRESOLVED:
            flag("ENTITLEMENT_UNRESOLVED", "review", e["id"], "%s: %s" % (out_ent, "; ".join(why)))
        later = [o for o in insts if o["rule"] == rule["id"] and o["state"] != "superseded" and o["cycle"] > label]
        if st in (EXPIRED, ENDED) and not later:
            flag("EXPIRED_ENTITLEMENT", "review", e["id"],
                 "%s from cycle %s %s on %s and no later cycle's instance is on record"
                 % (out_ent, label, "ended" if st == ENDED else "expired", e.get("ended_on") if st == ENDED else e["expires_on"]))
        # the most recent lapse of a credit line that still had something left on it
        if st in (EXPIRED, ENDED) and cr and cr["remaining"] > 0 and \
                not any(instance_state(o, as_of, earn["period"])[0] in (EXPIRED, ENDED) for o in later):
            flag("CREDIT_LAPSED_UNUSED", "review", e["id"],
                 "%s from cycle %s lapsed with %s %s unused%s" % (out_ent, label, num(cr["remaining"]), cr["unit"],
                 " (possibly less: %s of use is unconfirmed)" % num(cr["possibly_used"]) if cr["possibly_used"] else ""))
        via = "entitlement:" + e["id"]
        if st == ACTIVE:
            facts.append(("have:" + out_ent, LEVELS, NONE, via, []))
        elif st == UNRESOLVED:
            tok = frozenset([("unknown", "entitlement %s (%s): %s" % (e["id"], out_ent, "; ".join(why)))])
            facts.append(("have:" + out_ent, (P, U), tok, via, []))
        rows.append({"id": e["id"], "state": st, "reasons": why, "effective_from": e["effective_from"], "expires_on": e["expires_on"],
                     "ended_on": e.get("ended_on"), "end_reason": e.get("end_reason"), "credit": cr,
                     "record_state": e["state"], "confirmed_by": e.get("confirmed_by"), "confirmed_on": e.get("confirmed_on"),
                     "basis": e.get("basis", ""), "usage": e.get("usage", [])})
    if len(live) > 1:
        flag("CONFLICTING_ENTITLEMENTS", "review", rule["id"],
             "%d records for %s, account %s, cycle %s: %s" % (len(live), out_ent, h["id"], label, ", ".join(e["id"] for e in live)))

    # An award that needs activation is only "eligible" until the day its record says it took effect.
    waiting = bool(rows) and all(r["state"] == NOT_YET_EFFECTIVE for r in rows) and earn["activation"] == "required" \
        and ach["state"] == ACHIEVED and covers
    if rows and not waiting:
        best = sorted(rows, key=lambda r: [ACTIVE, UNRESOLVED, EXHAUSTED, NOT_YET_EFFECTIVE, ENDED, EXPIRED].index(r["state"]))[0]
        state, detail = best["state"], "; ".join(best["reasons"])
    elif not covers:
        state, detail = NOT_OFFERED, ("the rule is retired" if status == "retired" else
                                      "the offer (valid %s to %s) does not cover qualifying cycle %s"
                                      % (rule.get("valid_from") or "open", rule.get("valid_to") or "open", label))
    elif ach["state"] in (UNCERTAIN, CONFLICT):
        state, detail = UNRESOLVED, ach["detail"]
    elif ach["state"] != ACHIEVED:
        state, detail = NOT_EARNED, ach["detail"]
    elif exp is not None and as_of > exp:
        state, detail = LAPSED_UNCLAIMED, "threshold reached, nothing was ever recorded on the account, and the rule's term ended %s" % exp
    else:
        state = ACTIVATION_REQUIRED if earn["activation"] == "required" else EARNED_NOT_CONFIRMED
        detail = ("eligible; the separate activation step had not been done on this date (a record shows it taking effect %s)"
                  % rows[0]["effective_from"] if waiting else
                  "eligible; the separate activation step is not recorded as done" if earn["activation"] == "required" else
                  "eligible; not yet confirmed as present on the account")

    # eligibility (never possession): only while nothing is recorded for this rule, account and cycle
    if (not rows or waiting) and covers and state in (UNRESOLVED, ACTIVATION_REQUIRED, EARNED_NOT_CONFIRMED):
        unknowns = []
        if state == UNRESOLVED:
            unknowns.append("qualification %s for cycle %s is not established: %s" % (q["id"], label, ach["state"]))
        if status != "verified":
            unknowns.append("rule %s is unverified" % rule["id"])
        if not held:
            unknowns.append("account %s is %s" % (h["id"], "recorded but not confirmed" if h["state"] == "unconfirmed" else "not held on this date"))
        if held or h["state"] == "unconfirmed":
            toks = frozenset(("unknown", u) for u in unknowns)
            steps = frozenset([("acquire", out_ent, rule["id"])] +
                              ([("action", earn["activation_action"])] if earn.get("activation_action") else []))
            sup = ["qualification:" + q["id"]]
            facts.append(("can_get:" + out_ent, LEVELS if not toks else (P, U), toks, rule["id"], sup))
            facts.append(("have:" + out_ent, (C, U) if not toks else (U,), toks | steps, rule["id"], ["can_get:" + out_ent]))
    return {"rule": rule["id"], "entity": out_ent, "name": ents.get(out_ent, {}).get("name", out_ent), "public": public,
            "achievement": ach, "entitlement": {"state": state, "detail": detail, "usable": state == ACTIVE},
            "instances": rows, "withdrawn": [e["id"] for e in mine if e["state"] == "superseded"]}


def inject(result, store, prof, as_of):
    """Give the engine its base facts for earned benefits. Called only when the profile has such records."""
    sv = survey(store, prof.name, as_of)
    for atom, levels, toks, via, sup in sv["facts"]:
        for L in levels:
            result._offer(atom, L, toks, via, sup)
    for f in sv["flags"]:
        result.flag(f["code"], f["severity"], f["subject"], f["detail"])
    result.earned = sv


def summary_rows(sv):
    """Flat list of entitlement instances for the status report."""
    rows = []
    for a in sv["accounts"]:
        for c in a["cycles"]:
            for b in c["benefits"]:
                for i in b["instances"]:
                    rows.append({"entitlement": i["id"], "entity": b["entity"], "account": a["account"], "cycle": c["cycle"],
                                 "state": i["state"], "effective_from": i["effective_from"], "expires_on": i["expires_on"],
                                 "remaining": i["credit"]["remaining"] if i["credit"] else None})
    return rows


def boundary_dates(store, profile):
    """Dates on which something about earned benefits can change (for the timeline)."""
    prof, out = store.profile(profile), set()
    rules = store.rules
    for q in prof.qualifications.values():
        start, end = cycle_bounds("calendar_year", q["cycle"])
        out.update([start, end + ONE_DAY])
        for r in q["readings"]:
            for d in (day(r["observed_on"]), day(r.get("confirmed_on"))):
                if d:
                    out.update([d, d + ONE_DAY])
    for e in prof.entitlements.values():
        for key, plus in (("effective_from", 0), ("confirmed_on", 0), ("confirmed_on", 1), ("expires_on", 1), ("ended_on", 1)):
            d = day(e.get(key))
            if d:
                out.add(d + plus * ONE_DAY)
        for u in e.get("usage", []):
            for d in (day(u["used_on"]), day(u.get("confirmed_on"))):
                if d:
                    out.add(d)
        rule = rules.get(e["rule"])
        if rule and rule["kind"] == "earns":
            exp = expected_end(rule["earn"]["term"], e["cycle"])
            if exp:
                out.add(exp + ONE_DAY)
    for q in prof.qualifications.values():
        for rule in rules.values():
            if rule["kind"] == "earns" and rule["earn"]["measure"] == q["measure"]:
                exp = expected_end(rule["earn"]["term"], q["cycle"])
                if exp:
                    out.add(exp + ONE_DAY)
    return out
