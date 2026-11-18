"""Recurring card credits: published terms, the allowance period for a date, and what is recorded for a person.

Three things, never mixed:

    published   a `credit` block on a grants rule "card C carries benefit B": the amount per period, the cycle,
                caps and conditions, exactly as far as the source states them. A key that is absent means "the
                source does not say" and is reported that way: never as zero, unlimited or unrestricted.
                The rule's own valid_from / valid_to are the offer's effective and expiration dates.
    applies     whether the benefit applies to a person on a date. This is the engine's ordinary answer for
                have:<benefit>, so holdings, verification and cardholder elections (elections.py) all count.
    personal    what the owner's account shows for one period: an entitlement record for (rule, account, period)
                with its allowance and its uses - the same record type and operations as earned benefits
                (earned.py does the arithmetic). No record means "not recorded", never "unused".

A period that depends on a date nobody recorded (the account's opening date, the last use, a statement closing
date) is UNRESOLVED.

Two anniversary cycles, kept apart:

    anniversary_year            exact calendar anniversaries of opened_on: opened 2025-03-15 gives
                                2025-03-15..2026-03-14, 2026-03-15..2027-03-14, ...
    anniversary_statement_year  billing-cycle anniversaries (DEP-01): the first year runs from opened_on through
                                the first statement closing date AFTER the opening anniversary; each later year runs
                                from the day after that closing date through the closing date 12 monthly billing
                                cycles later. Closing dates are a profile fact on the card holding (owner-attested):
                                statement_closings (dates actually shown on statements) and/or statement_closing_day
                                (the day of the month statements close). A boundary whose closing date is not
                                recorded and cannot be read from the closing day (the day does not exist in that
                                month) is UNRESOLVED; nothing is guessed. A closing date that falls on the
                                anniversary itself is UNRESOLVED too ("after" is ambiguous for that day).
"""
import datetime

from .earned import credit as arithmetic, day, instance_state, num
from .elections import governed, groups
from .engine import ESTABLISHED, NOT_AVAILABLE, evaluate, in_effect, to_date
from .lint import single_holds

ONE_DAY = datetime.timedelta(days=1)
CYCLES = ("calendar_year", "calendar_half", "calendar_quarter", "calendar_month", "anniversary_year", "anniversary_statement_year", "multi_year")
PER_YEAR = {"calendar_half": 2, "calendar_quarter": 4, "calendar_month": 12}
KNOWN, UNRESOLVED, BEFORE_ACCOUNT = "KNOWN", "UNRESOLVED", "BEFORE_ACCOUNT"
NOT_RECORDED = "NOT_RECORDED"
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")


# ------------------------------------------------------------------ the block itself
def _positive(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def shape(c):
    """Problems with a credit block beyond what the schema checks. Empty list = fine."""
    out = []
    if not _positive(c.get("amount")):
        out.append("amount must be a number greater than zero (leave the credit block out if the source gives no amount)")
    if c.get("cycle") == "multi_year":
        if not (isinstance(c.get("years"), int) and not isinstance(c.get("years"), bool) and c["years"] >= 2):
            out.append("a multi_year credit needs years: a whole number of 2 or more")
    else:
        for k in ("years", "anchor"):
            if k in c:
                out.append("%s belongs only on a multi_year credit" % k)
    for k in ("max_per_transaction", "rollover_max"):
        if k in c and c[k] != "none" and not _positive(c[k]):
            out.append("%s must be a number greater than zero, or the word none" % k)
    if "min_stay_nights" in c and not (isinstance(c["min_stay_nights"], int) and not isinstance(c["min_stay_nights"], bool) and c["min_stay_nights"] >= 1):
        out.append("min_stay_nights must be a whole number of 1 or more (leave it out if the source states no minimum)")
    if "min_transaction" in c and not _positive(c["min_transaction"]):
        out.append("min_transaction must be a number greater than zero (leave it out if the source states no minimum)")
    if "rollover_max" in c and c.get("rollover") != "allowed":
        out.append("rollover_max belongs only with rollover: allowed")
    return out


def is_credit_rule(rule):
    return rule is not None and rule.get("kind") == "grants" and isinstance(rule.get("credit"), dict)


def cycle_text(c):
    cy = c["cycle"]
    if cy == "calendar_year":
        return "each calendar year (January 1 to December 31)"
    if cy == "calendar_half":
        return "each half of the calendar year (January-June, July-December), separately"
    if cy == "calendar_quarter":
        return "each calendar quarter, separately"
    if cy == "calendar_month":
        return "each calendar month, separately"
    if cy == "anniversary_year":
        return "each card-anniversary year (counted from the account's opening date)"
    if cy == "anniversary_statement_year":
        return ("each account-anniversary billing year (from the opening date through the first statement closing date after the "
                "opening anniversary, then each 12 monthly billing cycles)")
    anchor = {"account_opening": "the account's opening date", "last_use": "the date the credit was last used"}.get(c.get("anchor"))
    return "once every %s years, counted from %s" % (c.get("years", "?"), anchor or "a starting point the source does not state")


def terms(c):
    """The block as report fields. None = the source does not say."""
    out = {"amount": c["amount"], "unit": c["unit"], "cycle": c["cycle"], "cycle_text": cycle_text(c),
           "max_per_transaction": c.get("max_per_transaction"), "min_stay_nights": c.get("min_stay_nights"),
           "min_transaction": c.get("min_transaction"), "rollover": c.get("rollover"), "rollover_max": c.get("rollover_max"),
           "note": c.get("note")}
    if c["cycle"] == "multi_year":
        out.update(years=c.get("years"), anchor=c.get("anchor"))
    n = PER_YEAR.get(c["cycle"])
    out["per_calendar_year_at_most"] = c["amount"] * n if n else None
    return out


def unused_text(c):
    if c.get("rollover") == "none":
        return "unused allowance does not roll over"
    if c.get("rollover") == "allowed":
        cap = c.get("rollover_max")
        return "unused allowance rolls over" + (" without a stated limit" if cap == "none" else
                                                " (the source does not state a maximum)" if cap is None else
                                                ", up to %s %s" % (num(cap), c["unit"]))
    return "the source does not say whether unused allowance rolls over"


# ------------------------------------------------------------------ periods
def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def _anniv(opened, k):
    """The window in which the date k years after `opened` falls: one day, or Feb 28 - Mar 1 for a Feb 29 start."""
    y = opened.year + k
    if opened.month == 2 and opened.day == 29 and not _leap(y):
        return datetime.date(y, 2, 28), datetime.date(y, 3, 1)
    d = opened.replace(year=y)
    return d, d


def _month_end(y, m):
    return (datetime.date(y + (m == 12), m % 12 + 1, 1)) - ONE_DAY


def calendar_period(cycle, d):
    """(label, first day, last day) of the calendar period containing d."""
    if cycle == "calendar_year":
        return str(d.year), datetime.date(d.year, 1, 1), datetime.date(d.year, 12, 31)
    if cycle == "calendar_half":
        h = 1 if d.month <= 6 else 2
        return "%d-H%d" % (d.year, h), datetime.date(d.year, 6 * h - 5, 1), _month_end(d.year, 6 * h)
    if cycle == "calendar_quarter":
        q = (d.month + 2) // 3
        return "%d-Q%d" % (d.year, q), datetime.date(d.year, 3 * q - 2, 1), _month_end(d.year, 3 * q)
    if cycle == "calendar_month":
        return "%d-%02d" % (d.year, d.month), datetime.date(d.year, d.month, 1), _month_end(d.year, d.month)
    raise ValueError(cycle)


def label_ok(c, label):
    """Is `label` a well-formed period label for this credit's cycle?"""
    try:
        y = int(label[:4])
        tail = label[4:]
        if c["cycle"] in ("calendar_year", "anniversary_year", "anniversary_statement_year", "multi_year"):
            return tail == "" and len(label) == 4 and y > 0
        if c["cycle"] == "calendar_half":
            return tail in ("-H1", "-H2")
        if c["cycle"] == "calendar_quarter":
            return tail in ("-Q1", "-Q2", "-Q3", "-Q4")
        return len(tail) == 3 and tail[0] == "-" and 1 <= int(tail[1:]) <= 12
    except (ValueError, IndexError, TypeError):
        return False


def label_bounds(c, label):
    """(first day, last day) for a calendar period label; None when the period depends on the account."""
    if c["cycle"] not in PER_YEAR and c["cycle"] != "calendar_year":
        return None
    y = int(label[:4])
    if c["cycle"] == "calendar_year":
        probe = datetime.date(y, 1, 1)
    elif c["cycle"] == "calendar_half":
        probe = datetime.date(y, 1 if label.endswith("1") else 7, 1)
    elif c["cycle"] == "calendar_quarter":
        probe = datetime.date(y, 3 * int(label[-1]) - 2, 1)
    else:
        probe = datetime.date(y, int(label[-2:]), 1)
    return calendar_period(c["cycle"], probe)[1:]


def _from_opening(opened, d, step):
    """The step-year period, counted from `opened`, that contains d."""
    if d < opened:
        return {"state": BEFORE_ACCOUNT, "reason": "this date is before the account was opened (%s)" % opened}
    k = ((d.year - opened.year) // step) * step
    lo, hi = _anniv(opened, k)
    if d < lo:
        k -= step
        lo, hi = _anniv(opened, k)
    elif d < hi:
        return {"state": UNRESOLVED, "reason": "the account was opened on February 29; in %d its anniversary falls on February 28 or March 1, "
                                               "and which one is not known" % d.year}
    nlo, nhi = _anniv(opened, k + step)
    out = {"state": KNOWN, "label": str(opened.year + k), "start": hi, "end": nlo - ONE_DAY}
    if lo != hi or nlo != nhi:
        out["note"] = "the account was opened on February 29: this period may begin or end one day differently (February 28 or March 1)"
    return out


def period(c, d, holding=None, uses=()):
    """The allowance period containing date d.

    holding: the person's holding of the card (for opened_on). uses: this account's live records for the credit
    (needed only when the period is counted from the last use). Without a person, pass neither."""
    cy = c["cycle"]
    if cy in PER_YEAR or cy == "calendar_year":
        label, start, end = calendar_period(cy, d)
        return {"state": KNOWN, "label": label, "start": start, "end": end}
    if cy == "multi_year" and "anchor" not in c:
        return {"state": UNRESOLVED, "reason": "the source does not say what the %s-year period is counted from" % c.get("years", "?")}
    if cy == "multi_year" and c["anchor"] == "last_use":
        return _from_last_use(c, d, holding, uses)
    if cy == "anniversary_statement_year":
        if holding is None:
            return {"state": UNRESOLVED, "reason": "depends on the opening date and statement closing dates of each cardholder's own account"}
        return statement_year(holding, d)
    step = 1 if cy == "anniversary_year" else c["years"]
    if holding is None:
        return {"state": UNRESOLVED, "reason": "depends on the opening date of each cardholder's own account"}
    opened = to_date(holding.get("opened_on"))
    if opened is None:
        return {"state": UNRESOLVED, "reason": "the opening date of account %s is not recorded (opened_on), so its anniversary is not known"
                                               % holding["id"]}
    return _from_opening(opened, d, step)


def _months_after(y, m, n):
    k = y * 12 + (m - 1) + n
    return k // 12, k % 12 + 1


def closing_in(holding, y, m):
    """(date or None, how): the statement closing date of account `holding` in month y-m.

    A date recorded in statement_closings wins ("recorded"). Otherwise statement_closing_day gives it ("from the
    closing day"), unless that day does not exist in the month. Otherwise None: not known, and never guessed."""
    seen = sorted({day(x) for x in holding.get("statement_closings") or [] if day(x) and (day(x).year, day(x).month) == (y, m)})
    if len(seen) > 1:
        return None, "two closing dates are recorded for %d-%02d (%s)" % (y, m, ", ".join(map(str, seen)))
    if seen:
        return seen[0], "recorded"
    n = holding.get("statement_closing_day")
    if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= 31:
        if n <= _month_end(y, m).day:
            return datetime.date(y, m, n), "from the closing day"
        return None, "the recorded closing day (%d) does not exist in %s %d, and no closing date is recorded for that month" % (n, MONTHS[m - 1], y)
    return None, "no statement closing date is recorded for %s %d" % (MONTHS[m - 1], y)


def statement_year(holding, d):
    """The account-anniversary billing year containing d (cycle anniversary_statement_year)."""
    opened = to_date(holding.get("opened_on"))
    if opened is None:
        return {"state": UNRESOLVED, "reason": "the opening date of account %s is not recorded (opened_on), so its anniversary is not known" % holding["id"]}
    if d < opened:
        return {"state": BEFORE_ACCOUNT, "reason": "this date is before the account was opened (%s)" % opened}
    if not holding.get("statement_closings") and holding.get("statement_closing_day") is None:
        return {"state": UNRESOLVED, "reason": "the statement closing date of account %s is not recorded (statement_closing_day or "
                                               "statement_closings), so its billing-year boundaries are not known" % holding["id"]}
    # the first boundary: the first closing date strictly after the opening anniversary (a Feb 29 opening has a two-day window)
    lo, hi = _anniv(opened, 1)
    y, m = lo.year, lo.month
    hows = []
    for _ in range(3):
        c, how = closing_in(holding, y, m)
        if c is None:
            return {"state": UNRESOLVED, "reason": "the first billing year of account %s ends at the first statement closing after %s, but %s"
                                                   % (holding["id"], lo, how)}
        if c < lo:
            y, m = _months_after(y, m, 1)
            continue
        if c <= hi:                                       # closes ON the anniversary: which boundary is meant is not settled
            return {"state": UNRESOLVED, "reason": "account %s's statement closed on %s, the opening anniversary itself; whether that "
                                                   "closing ends the first billing year ('after the anniversary') is not settled" % (holding["id"], c)}
        break
    else:
        return {"state": UNRESOLVED, "reason": "no statement closing after the anniversary %s could be found" % lo}
    start, end, k = opened, c, 0
    hows.append(how)
    while d > end:
        y, m = _months_after(end.year, end.month, 12)
        nxt, how = closing_in(holding, y, m)
        if nxt is None:
            return {"state": UNRESOLVED, "reason": "billing year %d of account %s ends at the statement closing 12 cycles after %s, but %s"
                                                   % (opened.year + k + 1, holding["id"], end, how)}
        start, end, k = end + ONE_DAY, nxt, k + 1
        hows = [how]
    out = {"state": KNOWN, "label": str(opened.year + k), "start": start, "end": end}
    if "from the closing day" in hows:
        out["note"] = ("the end date %s is computed from the recorded closing day (%d); no statement showing it is recorded"
                       % (end, holding["statement_closing_day"]))
    return out


def _from_last_use(c, d, holding, uses):
    if holding is None:
        return {"state": UNRESOLVED, "reason": "depends on when each cardholder last used the credit"}
    live = [u for u in uses if u["state"] != "superseded"]
    if any(u["state"] != "confirmed" for u in live):
        return {"state": UNRESOLVED, "reason": "a use of this credit is recorded on account %s but not confirmed by the owner" % holding["id"]}
    if any(day(u["effective_from"]) is None for u in live):
        return {"state": UNRESOLVED, "reason": "a use of this credit is recorded on account %s without its date" % holding["id"]}
    past = sorted((day(u["effective_from"]), u["id"]) for u in live if day(u["effective_from"]) <= d)
    if not past:
        return {"state": UNRESOLVED, "reason": "the %d-year period runs from the last use of the credit on account %s, and no use is recorded"
                                               % (c["years"], holding["id"])}
    used_on, rec = past[-1]
    lo, _hi = _anniv(used_on, c["years"])
    if d < lo:
        return {"state": KNOWN, "label": str(used_on.year), "start": used_on, "end": lo - ONE_DAY, "record": rec}
    return {"state": KNOWN, "label": None, "start": lo, "end": None,
            "note": "the last recorded use was on %s (%s); no later use is recorded, so the published allowance is available again from %s"
                    % (used_on, rec, lo)}


def offer(rule, d):
    """Is the published offer in effect on d?  (state, text)"""
    vf, vt = to_date(rule.get("valid_from")), to_date(rule.get("valid_to"))
    if rule.get("verification", {}).get("status") == "retired":
        return "ENDED", "the rule is retired" + (" (ended %s)" % vt if vt else "")
    if vf is not None and d < vf:
        return "NOT_YET_EFFECTIVE", "the offer starts on %s" % vf
    if vt is not None and d > vt:
        return "ENDED", "the offer ended on %s" % vt
    return "IN_EFFECT", "in effect" + (" through %s" % vt if vt else "")


def clip(p, rule):
    """Cut a known period to the offer's own dates. A cut-short period keeps the published amount (not pro-rated)."""
    if p["state"] != KNOWN:
        return p
    vf, vt = to_date(rule.get("valid_from")), to_date(rule.get("valid_to"))
    p = dict(p)
    if vf is not None and p["start"] < vf:
        p["start"], p["cut"] = vf, "the offer starts on %s, part-way through this period" % vf
    if vt is not None and (p["end"] is None or p["end"] > vt):
        p["end"], p["cut"], p["last"] = vt, "the offer ends on %s%s" % (vt, "" if p["end"] is None else ", part-way through this period"), True
    elif vt is not None and p["end"] == vt:
        p["last"] = True
    return p


# ------------------------------------------------------------------ rules that carry a credit
def credit_rules(store, include_candidates=False):
    """[(rule-like dict, state, candidate id or None)] for every rule (and, if asked, open candidate) with a credit block."""
    out = [(r, r["verification"]["status"], None) for r in store.rules.values() if is_credit_rule(r)]
    if include_candidates:
        for c in store.candidates.values():
            if c["status"] == "proposed" and is_credit_rule(c["proposed_rule"]):
                out.append((c["proposed_rule"], "candidate", c["id"]))
    return sorted(out, key=lambda x: x[0]["id"])


def find(store, rule_id):
    """(owner record, rule-like dict, 'rule'|'candidate') for a rule id, looking at rules then open candidates."""
    if rule_id in store.rules:
        return store.rules[rule_id], store.rules[rule_id], "rule"
    for c in store.candidates.values():
        if c["status"] == "proposed" and c["proposed_rule"].get("id") == rule_id:
            return c, c["proposed_rule"], "candidate"
    return None, None, None


def _public(store, rule, state, cand, as_of):
    ents = store.entities
    st, text = offer(rule, as_of)
    ev = rule.get("evidence") if cand is None else [e["id"] for e in store.candidates[cand]["evidence"]]
    return {"rule": rule["id"], "rule_state": state, "candidate": cand, "card": single_holds(rule["when"]),
            "benefit": rule["output"], "name": ents.get(rule["output"], {}).get("name", rule["output"]),
            "terms": terms(rule["credit"]), "offer": {"state": st, "text": text, "valid_from": rule.get("valid_from"),
                                                       "valid_to": rule.get("valid_to")},
            "evidence": list(ev or []), "summary": rule.get("summary", "")}


def _iso(p):
    return {k: (v.isoformat() if isinstance(v, datetime.date) else v) for k, v in p.items()}


def published(store, as_of, include_candidates=False, card=None):
    """Every structured credit as published, with the period for `as_of` where it does not depend on a person."""
    as_of, out = to_date(as_of), []
    for rule, state, cand in credit_rules(store, include_candidates):
        pub = _public(store, rule, state, cand, as_of)
        if card and pub["card"] != card:
            continue
        pub["period"] = _iso(clip(period(rule["credit"], as_of), rule)) if pub["offer"]["state"] == "IN_EFFECT" else None
        out.append(pub)
    return {"as_of": as_of.isoformat(), "credits": out}


# ------------------------------------------------------------------ one person
def _records(prof, rule_id, account):
    return sorted((e for e in prof.entitlements.values() if e["rule"] == rule_id and e["account"] == account and e["state"] != "superseded"),
                  key=lambda e: e["id"])


def _personal(rule, recs, p, as_of, flag):
    """What is on file for this account and period. Never derived from the published terms."""
    c = rule["credit"]
    if p["state"] == KNOWN and p.get("label"):
        mine = [e for e in recs if e["cycle"] == p["label"]]
    elif p["state"] == KNOWN:
        mine = []                                            # a fresh period after the last recorded use
    else:                                                    # period not computable: go by each record's own dates
        mine = [e for e in recs if (day(e["effective_from"]) or as_of) <= as_of <= (day(e["expires_on"]) or as_of)]
    if not mine:
        return {"state": NOT_RECORDED, "text": "nothing is recorded for this account and period; the personal balance is not known"}
    if len(mine) > 1:
        flag("CONFLICTING_ENTITLEMENTS", "review", mine[0]["id"], "%d live records for %s, the same account and period (%s); "
             "no personal balance is reported" % (len(mine), rule["output"], ", ".join(e["id"] for e in mine)))
        return {"state": "UNRESOLVED", "text": "conflicting records: " + ", ".join(e["id"] for e in mine), "records": [e["id"] for e in mine]}
    e = mine[0]
    start = p["start"] if p["state"] == KNOWN else (day(e["effective_from"]) or as_of)
    state, why, cr = instance_state(e, as_of, start=start)
    out = {"record": e["id"], "state": state, "reasons": why, "effective_from": e["effective_from"], "expires_on": e["expires_on"],
           "confirmed_by": e.get("confirmed_by"), "confirmed_on": e.get("confirmed_on"), "basis": e.get("basis")}
    out.update(cr or arithmetic(e, as_of))
    out["established"] = state in ("ACTIVE", "EXHAUSTED") and out["possibly_used"] == 0
    if e["state"] != "confirmed":
        flag("UNCONFIRMED_ENTITLEMENT", "review", e["id"], "the credit record for %s is not confirmed by the owner" % rule["output"])
    elif out["possibly_used"]:
        flag("CREDIT_USE_UNCONFIRMED", "review", e["id"], "%s %s of use on %s is recorded but not confirmed; remaining is a range"
             % (num(out["possibly_used"]), out["unit"], rule["output"]))
    if e["allowance"]["amount"] != c["amount"]:
        flag("ALLOWANCE_DIFFERS_FROM_RULE", "info", e["id"], "the account shows %s %s for this period; the published amount is %s. "
             "The account's figure is used for the personal balance" % (num(e["allowance"]["amount"]), e["allowance"]["unit"], num(c["amount"])))
    if p["state"] == KNOWN and p.get("label"):
        lo, hi = day(e["effective_from"]), day(e["expires_on"])
        if (lo is not None and lo != p["start"]) or (hi is not None and p["end"] is not None and hi != p["end"]):
            flag("PERIOD_DIFFERS_FROM_RULE", "info", e["id"], "the account shows %s to %s; the period computed from the published terms is %s to %s"
                 % (e["effective_from"], e["expires_on"], p["start"], p["end"]))
    cap = c.get("max_per_transaction")
    if isinstance(cap, (int, float)):
        for u in e.get("usage", []):
            if u["state"] != "superseded" and u["amount"] > cap:
                flag("USE_OVER_TRANSACTION_CAP", "review", e["id"], "use %s of %s exceeds the published per-transaction maximum of %s"
                     % (u["id"], num(u["amount"]), num(cap)))
    return out


def survey(store, profile, as_of, include_candidates=False, card=None):
    """Every structured credit on every card account of one person, on one date."""
    as_of = to_date(as_of)
    prof = store.profile(profile)
    cache, flags, accounts = {}, [], []

    def result(d):
        if d not in cache:
            cache[d] = evaluate(store, profile, d, include_candidates=include_candidates)
        return cache[d]

    def flag(code, severity, subject, detail):
        f = {"code": code, "severity": severity, "subject": subject, "detail": detail}
        if f not in flags:
            flags.append(f)

    gov = governed(store)
    group_of = {o["id"]: g for g, opts in groups(store).items() for o in opts}
    res = result(as_of)
    rules = credit_rules(store, include_candidates)
    for h in sorted(prof.holdings.values(), key=lambda h: h["id"]):
        mine = [x for x in rules if single_holds(x[0]["when"]) == h["entity"]]
        if not mine or (card and h["entity"] != card) or h["state"] in ("ended", "withdrawn") or not in_effect(h, as_of):
            continue
        rows = []
        for rule, state, cand in mine:
            c, atom = rule["credit"], "have:" + rule["output"]
            row = _public(store, rule, state, cand, as_of)
            status = res.status(atom)
            toks = res.tokens(atom) if status != NOT_AVAILABLE else {"steps": [], "unknowns": []}
            needs = ["CONFIRM: " + u for u in toks.get("unknowns", [])] + [
                "%s %s" % ("DO" if s["type"] == "action" else "ACQUIRE", s.get("name", s.get("entity"))) for s in toks.get("steps", [])]
            row["applies"] = {"status": status, "needs": needs}
            opt = gov.get(rule["id"])
            if opt:
                d = next((x for x in getattr(res, "elections", []) if x["group"] == group_of[opt]), None)
                row["applies"]["election"] = {"group": group_of[opt], "option": opt,
                                              "in_effect": bool(d and d["established"] == opt),
                                              "reason": d["reason"] if d else "card not held"}
            p = {"state": "NO_OFFER", "reason": row["offer"]["text"]}
            if row["offer"]["state"] == "IN_EFFECT":
                p = clip(period(c, as_of, h, _records(prof, rule["id"], h["id"])), rule)
            row["period"] = _iso(p)
            if p["state"] == UNRESOLVED and status != NOT_AVAILABLE:
                flag("CREDIT_PERIOD_UNRESOLVED", "review", h["id"], "%s: the current allowance period cannot be determined: %s"
                     % (rule["output"], p["reason"]))
            if p["state"] == KNOWN and status != NOT_AVAILABLE:
                row["allowance"] = {"amount": c["amount"], "unit": c["unit"],
                                    "note": "published allowance for this period; not a personal balance" +
                                            ("" if status == ESTABLISHED else "; whether it applies to this person is not established") +
                                            ("; the period is cut short and the amount is not pro-rated" if p.get("cut") else "")}
                if p["end"] is not None:
                    after = p["end"] + ONE_DAY
                    row["next"] = {"date": after.isoformat(), "what": "offer ends" if p.get("last") else "new period, allowance resets",
                                   "unused": unused_text(c)}
                    if status == ESTABLISHED and p["end"] > as_of and result(p["end"]).status(atom) != ESTABLISHED:
                        row["applies"]["needs"].append("on %s, the last day of this period, this benefit is %s for this person: "
                                                       "the period may be cut short (see the timeline)" % (p["end"], result(p["end"]).status(atom)))
            row["personal"] = _personal(rule, _records(prof, rule["id"], h["id"]), p, as_of, flag)
            rows.append(row)
        accounts.append({"account": h["id"], "card": h["entity"], "card_name": store.entities.get(h["entity"], {}).get("name", h["entity"]),
                         "account_state": h["state"], "opened_on": h.get("opened_on"), "credits": rows})
    return {"profile": profile, "owner": prof.meta["owner"], "synthetic": bool(prof.meta.get("synthetic")), "as_of": as_of.isoformat(),
            "accounts": accounts, "flags": flags}


# ------------------------------------------------------------------ what the calendar does next
def events(store, profile, start, until, include_candidates=False):
    """Allowance periods of this person's applicable credits that end in (start, until], each on its last day."""
    start, until = to_date(start), to_date(until)
    prof, out, cache = store.profile(profile), [], {}

    def applies(d, atom):
        if d not in cache:
            cache[d] = evaluate(store, profile, d, include_candidates=include_candidates)
        return cache[d].status(atom)

    for h in sorted(prof.holdings.values(), key=lambda h: h["id"]):
        if h["state"] in ("ended", "withdrawn"):
            continue
        for rule, _state, _cand in credit_rules(store, include_candidates):
            if single_holds(rule["when"]) != h["entity"]:
                continue
            c, d, n = rule["credit"], start + ONE_DAY, 0
            recs = _records(prof, rule["id"], h["id"])
            while d <= until and n < 500:
                n += 1
                if offer(rule, d)[0] != "IN_EFFECT":
                    vf = to_date(rule.get("valid_from"))
                    if vf is not None and d < vf <= until:
                        d = vf
                        continue
                    break
                p = clip(period(c, d, h, recs), rule)
                if p["state"] != KNOWN or p["end"] is None:
                    break
                if p["end"] <= until and in_effect(h, p["end"]):
                    status = applies(p["end"], "have:" + rule["output"])
                    if status != NOT_AVAILABLE:
                        out.append({"date": p["end"].isoformat(), "rule": rule["id"], "benefit": rule["output"], "account": h["id"],
                                    "period": p["label"], "period_start": p["start"].isoformat(), "amount": c["amount"], "unit": c["unit"],
                                    "applies": status, "unused": unused_text(c),
                                    "then": "the offer ends" if p.get("last") else "a new period starts on %s" % (p["end"] + ONE_DAY)})
                d = p["end"] + ONE_DAY
    return sorted(out, key=lambda e: (e["date"], e["account"], e["rule"]))
