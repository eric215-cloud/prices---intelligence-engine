"""Cardholder elections: mutually exclusive options on one card, chosen by the cardholder.

    public   an entity of kind `election` is ONE option of ONE election group on ONE card, and names the rules
             (or candidate rules) that apply only under that option ("governs"). Rules themselves are not edited:
             card_benefits rules stay exactly as the tables write them.
    personal the cardholder's choice is a holding of the option entity, with its own dates, confirmed only by the
             owner's attestation (set_holding / end_holding, as for any holding).

The engine adds "and the person has elected this option" to every governed rule. This module decides, for one
person on one date, which option of each group is in effect, using these rules and nothing else:

  * Nothing is inferred from silence. With no election recorded, every option that could apply is UNRESOLVED
    (never established), unless the option's public terms make it the default on that date.
  * Exactly one option, confirmed by the owner, in effect on that date, and allowed by its public terms: that
    option is established and no other option in the group applies.
  * Anything else (two options in effect, an unconfirmed record, a record whose start is unknown on that date,
    a record the public terms do not allow, a date that depends on an anniversary nobody recorded, two accounts
    of the same card): every option that could apply is UNRESOLVED and the reason is flagged.

Dates in an option's terms mean "the first card anniversary on or after this date". The anniversary comes from
`opened_on` on the person's holding of the card. It is never guessed from `valid_from`.

Linked options (ENG-02B). Some published arrangements bundle several things into ONE choice. An option may say
`follows: <option of another group>`: it is then in effect exactly when that option is, and nobody records it
separately. A group with such options works in two periods:

  * the choice period - dates before the first card anniversary on or after `choose_before_anniversary` /
    `default_before_anniversary`, for accounts opened before that date. The group's own recorded choices and
    defaults decide, as described above. (If the followed option is already established, it decides.)
  * afterwards, and for accounts opened later - only the followed options decide. A choice recorded for the choice
    period no longer counts. If the followed group is unresolved, so is this one.

Card anniversaries (ENG-02B). `anniversary_cycle_days: N` on an option says the issuer counts the card anniversary
from the first day of the first billing cycle that begins AFTER the account was opened, not from the opening date.
That day is not a recorded fact, so the anniversary is known only as a window (see anniversary_window) unless the
holding of the card records `anniversary_on`, a card anniversary date as the issuer shows it.
"""
import datetime

from .engine import LEVELS, P, U, in_effect, to_date

ONE_DAY = datetime.timedelta(days=1)
TERM_KEYS = ("opened_before", "default_before_anniversary", "starts_at_anniversary", "elect_before_anniversary",
             "choose_before_anniversary")


def groups(store):
    """{group id: [option entities]} for every election group in the knowledge base."""
    out = {}
    for e in sorted(store.entities.values(), key=lambda x: x["id"]):
        if e["kind"] == "election" and isinstance(e.get("election"), dict):
            out.setdefault(e["election"]["group"], []).append(e)
    return out


def governed(store):
    """{rule id: option entity id}. The rule applies only while that option is the person's election."""
    out = {}
    for opts in groups(store).values():
        for e in opts:
            for rid in e["election"].get("governs", []):
                out[rid] = e["id"]
    return out


def gate(rule_id, when, gov):
    """The rule's condition, with the election requirement added when the rule is governed."""
    opt = gov.get(rule_id)
    return when if opt is None else {"all": [when, {"holds": opt}]}


# ------------------------------------------------------------------ anniversaries
def anniversary_window(opened, d0, cycle_days=0, shown=None):
    """First card anniversary on or after d0, as (first day it may fall on, last day it may fall on).

    cycle_days 0   the anniversary is the opening date's own month and day. The two ends are the same day, except
                   for an account opened on February 29, which has no anniversary day in other years: the window is
                   February 28 to March 1 and dates inside it are treated as unknown, not decided by a convention.
    cycle_days N   the anniversary is counted from the first day of the first billing cycle that begins after the
                   account was opened. Only this is known: that day falls 1 to N days after opening. The window
                   covers every anniversary that allows. It can be a few weeks wide, or most of a year when the
                   possible days straddle d0.
    shown          a card anniversary date as the issuer shows it (`anniversary_on`). Its month and day replace
                   the guesswork; the first anniversary is the first such day a year or more after opening."""
    if shown is not None:
        first = _in_year(opened.month, opened.day, opened.year + 1)[0]
        year = first.year if _in_year(shown.month, shown.day, first.year)[0] >= first else first.year + 1
        return _first(shown.month, shown.day, year, d0)
    bases = [opened + datetime.timedelta(days=n) for n in range(1, cycle_days + 1)] or [opened]
    wins = [_first(b.month, b.day, b.year + 1, d0) for b in bases]
    return min(w[0] for w in wins), max(w[1] for w in wins)


def _in_year(month, day, year):
    if month == 2 and day == 29 and not _leap(year):
        return datetime.date(year, 2, 28), datetime.date(year, 3, 1)
    return datetime.date(year, month, day), datetime.date(year, month, day)


def _first(month, day, year, d0):
    year = max(year, d0.year)
    while True:
        lo, hi = _in_year(month, day, year)
        if lo >= d0:
            return lo, hi
        year += 1


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def card_window(card_holding, d0, cycle_days=0):
    """anniversary_window for this account, or None when what is recorded on the holding cannot place it."""
    opened, shown = to_date(card_holding.get("opened_on")), to_date(card_holding.get("anniversary_on"))
    if opened is not None:
        return anniversary_window(opened, d0, cycle_days, shown)
    if shown is not None and shown >= d0 and _in_year(shown.month, shown.day, shown.year - 1)[1] < d0:
        return shown, shown                 # the issuer showed this very anniversary; the one before it is before d0
    return None


def before_anniversary(card_holding, d0, day, cycle_days=0):
    """Is `day` before the first card anniversary on or after d0?  True / False / None (not known)."""
    if day < d0:
        return True                         # that anniversary is never earlier than d0
    w = card_window(card_holding, d0, cycle_days)
    if w is None:
        return None
    lo, hi = w
    if day < lo:
        return True
    if day >= hi:
        return False
    return None                             # inside a window: the anniversary may or may not have come


def opened_before(card_holding, d0):
    """Was the account opened before d0?  True / False / None. Holding it before d0 proves it was opened by then."""
    opened = to_date(card_holding.get("opened_on"))
    if opened is not None:
        return opened < d0
    vf = to_date(card_holding.get("valid_from"))
    return True if vf is not None and vf < d0 else None


# ------------------------------------------------------------------ per-option checks
def _all(values):
    """Combine True / False / None checks: any False -> False, else any None -> None, else True."""
    values = list(values)
    return False if False in values else (None if None in values else True)


def _cycle(option):
    return option["election"].get("anniversary_cycle_days", 0)


def allowed(option, card_holding, day, election=None, history=()):
    """May this option be in effect on `day` under its public terms?  True / False / None.

    `election` is the person's holding of the option, when one is recorded (its start date is checked against
    `elect_before_anniversary`). `history` is every election the person has recorded in this group (for
    `permanent_exit`)."""
    t, checks, why, n = option["election"], [], [], _cycle(option)
    if "opened_before" in t:
        ok = opened_before(card_holding, to_date(t["opened_before"]))
        checks.append(ok)
        if ok is False:
            why.append("only for accounts opened before %s (this one was opened %s)" % (t["opened_before"], card_holding.get("opened_on")))
        elif ok is None:
            why.append("only for accounts opened before %s, and the opening date is not recorded" % t["opened_before"])
    from_opening = "default_opened_on_or_after" in t and opened_before(card_holding, to_date(t["default_opened_on_or_after"])) is False
    if "starts_at_anniversary" in t and not from_opening:
        b = before_anniversary(card_holding, to_date(t["starts_at_anniversary"]), day, n)
        checks.append(None if b is None else not b)
        if b is True:
            why.append("does not start before the first card anniversary on or after %s" % t["starts_at_anniversary"])
        elif b is None:
            why.append("starts at the first card anniversary on or after %s, and that date is not known" % t["starts_at_anniversary"])
    if "choose_before_anniversary" in t:
        b = before_anniversary(card_holding, to_date(t["choose_before_anniversary"]), day, n)
        checks.append(b)
        if b is False:
            why.append("the cardholder's own choice of it counts only before the first card anniversary on or after %s"
                       % t["choose_before_anniversary"])
        elif b is None:
            why.append("can be chosen only before the first card anniversary on or after %s, and that date is not known"
                       % t["choose_before_anniversary"])
    if "elect_before_anniversary" in t and election is not None:
        start = to_date(election.get("valid_from"))
        if start is None:
            checks.append(None)
            why.append("must be elected before the first card anniversary on or after %s; the election's start is not recorded"
                       % t["elect_before_anniversary"])
        else:
            b = before_anniversary(card_holding, to_date(t["elect_before_anniversary"]), start, n)
            checks.append(b)
            if b is False:
                why.append("must be elected before the first card anniversary on or after %s; this election starts %s"
                           % (t["elect_before_anniversary"], start))
            elif b is None:
                why.append("must be elected before the first card anniversary on or after %s, and that date is not known"
                           % t["elect_before_anniversary"])
    if t.get("permanent_exit"):
        # once left, never again: an earlier election of this option that has ended rules out any later one
        ref = day if election is None else to_date(election.get("valid_from"))
        left = [to_date(h["valid_to"]) for h in history if h is not election and h["entity"] == option["id"]
                and h["state"] == "ended" and to_date(h.get("valid_to")) is not None]
        left = [x for x in left if ref is None or x < ref]
        if left:
            checks.append(False)
            why.append("it was left on %s, and under its published terms it cannot be elected again" % max(left))
    return _all(checks), why


def default_now(option, card_holding, day):
    """Does this option apply WITHOUT any election on `day`?  True / False / None."""
    t, out = option["election"], [False]
    if "default_before_anniversary" in t:
        d0 = to_date(t["default_before_anniversary"])
        out.append(_all([opened_before(card_holding, d0), before_anniversary(card_holding, d0, day, _cycle(option))]))
    if "default_opened_on_or_after" in t:
        # applies from the day the account is opened, to accounts opened on or after this date
        ob = opened_before(card_holding, to_date(t["default_opened_on_or_after"]))
        out.append(None if ob is None else not ob)
    return True if True in out else (None if None in out else False)


def presence(h, day):
    """How a recorded election stands on `day`: 'in', 'maybe' (its start date is unknown and the owner had not yet
    confirmed it on that day) or None.  An ended election was confirmed and counts up to its valid_to."""
    vf, vt = to_date(h.get("valid_from")), to_date(h.get("valid_to"))
    if vt is not None and day > vt:
        return None
    if vf is not None:
        return "in" if day >= vf else None
    seen = to_date(h.get("confirmed_on"))
    return "in" if seen is not None and day >= seen else "maybe"


# ------------------------------------------------------------------ the decision for one group
def decide(prof, group, options, day, linked=None):
    """Which option of `group` is in effect for this person on `day`.

    `linked` (only for groups whose options follow another group): {option id: ("est" | "poss", its decision)}
    for the groups decided before this one. decide_all supplies it.

    Returns None when the person does not hold the card (nothing to decide), else a dict:
        established  option id or None
        possible     option ids that are UNRESOLVED (never established)
        via          what the established option rests on
        flags        [(code, severity, subject, detail)]
        reason       one line for reports
    """
    card = options[0]["election"]["card"]
    ids = {o["id"]: o for o in options}
    cards = [h for h in prof.holdings.values() if h["entity"] == card and h["state"] != "ended" and in_effect(h, day)]
    picks = [h for h in prof.holdings.values() if h["entity"] in ids and h["state"] != "withdrawn"]
    live = [(h, presence(h, day)) for h in sorted(picks, key=lambda h: h["id"])]
    live = [(h, p) for h, p in live if p is not None]
    flags = []
    if not cards:
        if live:
            flags.append(("ELECTION_WITHOUT_CARD", "review", live[0][0]["id"],
                          "an election for %s is recorded but %s is not held on this date" % (group, card)))
        return {"established": None, "possible": [], "via": None, "flags": flags, "reason": "card not held", "card": None} if flags else None
    if len(cards) > 1:
        return _unsure(options, None, day, [("MULTIPLE_CARD_ACCOUNTS", "review", group,
                       "%d holdings of %s are in effect; elections are recorded per person, so which account an election "
                       "belongs to cannot be told" % (len(cards), card))], "more than one account of the card")
    if any("follows" in o["election"] for o in options):
        return _linked(group, options, cards[0], picks, live, day, linked or {})
    return _own(group, options, cards[0], picks, live, day)


def _own(group, options, ch, picks, live, day):
    """The group's own recorded choices and defaults decide."""
    card = options[0]["election"]["card"]
    ids = {o["id"]: o for o in options}
    flags = []
    chosen = sorted({h["entity"] for h, _p in live})
    if len(chosen) > 1:
        return _unsure(options, ch, day, [("CONFLICTING_ELECTIONS", "review", group,
                       "more than one option is recorded as in effect on this date (%s); none is applied"
                       % ", ".join("%s=%s" % (h["id"], h["entity"]) for h, _p in live))], "conflicting elections recorded", history=picks)
    if chosen:
        h, pres = next((h, p) for h, p in live if p == "in") if any(p == "in" for _h, p in live) else live[0]
        opt = ids[h["entity"]]
        if pres == "maybe":
            return _unsure(options, ch, day, [("ELECTION_START_NOT_RECORDED", "review", h["id"],
                           "%s has no start date and the owner first confirmed it on %s; before that the election is not known"
                           % (h["entity"], h.get("confirmed_on") or "no date"))], "election start not recorded", history=picks)
        if h["state"] != "confirmed" and h["state"] != "ended":
            return _unsure(options, ch, day, [("UNCONFIRMED_ELECTION", "review", h["id"],
                           "%s is recorded but not confirmed by the owner" % h["entity"])], "election not confirmed", history=picks)
        ok, why = allowed(opt, ch, day, h, picks)
        if ok is False:
            return _unsure(options, ch, day, [("ELECTION_NOT_PERMITTED", "review", h["id"],
                           "%s is recorded, but its published terms do not allow it on this date: %s" % (h["entity"], "; ".join(why)))],
                           "recorded election conflicts with the published terms", keep=opt["id"], history=picks)
        # the day the person last left another option of this group (an ended election), for options that wait on it
        ends = [to_date(x["valid_to"]) for x in picks if x["entity"] != opt["id"] and x["state"] == "ended" and to_date(x.get("valid_to"))]
        ends = [x for x in ends if x < day]
        out = {"established": opt["id"], "possible": [], "via": "election:" + h["id"], "support": ["holding:" + ch["id"]],
               "flags": flags, "reason": "elected (%s)" % h["id"], "card": ch["id"], "exit": max(ends) if ends else None}
        if ok is None:
            out["flags"].append(("ELECTION_TERMS_UNVERIFIED", "info", h["id"],
                                 "%s stands on the owner's confirmation; its published terms could not be checked: %s"
                                 % (h["entity"], "; ".join(why))))
        return out
    # no election recorded on this date
    defaults = [(o, default_now(o, ch, day)) for o in options]
    sure = [o for o, v in defaults if v is True]
    if len(sure) == 1 and not any(v is None for _o, v in defaults):
        return {"established": sure[0]["id"], "possible": [], "via": "election-default:" + group, "support": ["holding:" + ch["id"]],
                "flags": [], "reason": "applies without an election under its published terms", "card": ch["id"]}
    if any(v is None for _o, v in defaults):
        return _unsure(options, ch, day, [("ANNIVERSARY_NOT_RECORDED", "review", ch["id"], _no_anniversary(group, ch))],
                       "card anniversary not recorded", history=picks)
    if not any(allowed(o, ch, day, None, picks)[0] is not False for o in options):
        return {"established": None, "possible": [], "via": None, "flags": [], "card": ch["id"],
                "reason": "no option of this group applies on this date under its published terms"}
    return _unsure(options, ch, day, [("ELECTION_NOT_RECORDED", "review", group,
                   "%s is held, but no election for %s is recorded; none of its options is applied" % (card, group))],
                   "no election recorded", history=picks)


def _no_anniversary(group, ch):
    if not ch.get("opened_on"):
        return ("which option of %s applies on this date depends on the card's anniversary, and %s has no opened_on"
                % (group, ch["id"]))
    return ("which option of %s applies on this date depends on the card's anniversary, which is counted from the first "
            "billing cycle after opening and cannot be placed from opened_on alone; record anniversary_on on %s (the card "
            "anniversary date the issuer shows)" % (group, ch["id"]))


def _unsure(options, ch, day, flags, reason, keep=None, history=()):
    """Every option that could apply on this date is UNRESOLVED; none is established.
    `keep`: an option the owner recorded, kept UNRESOLVED even where its terms say no (neither granted nor dropped)."""
    possible = []
    for o in options:
        if ch is not None and o["id"] != keep:
            ok, _why = allowed(o, ch, day, None, history)
            if ok is False:
                continue
        possible.append(o["id"])
    return {"established": None, "possible": possible, "via": None, "flags": flags, "reason": reason, "card": ch["id"] if ch else None}


# ------------------------------------------------------------------ linked groups (ENG-02B)
def _choice_period(options, ch, day):
    """Is this account, on this day, still in the period when the group's own choices and defaults decide?
    True / False / None. Accounts opened on or after the date never have such a period."""
    out = []
    for o in options:
        for k in ("choose_before_anniversary", "default_before_anniversary"):
            if k in o["election"]:
                d0 = to_date(o["election"][k])
                ob = opened_before(ch, d0)
                out.append(False if ob is False else _all([ob, before_anniversary(ch, d0, day, _cycle(o))]))
    return False if not out else _all(out)


def _linked(group, options, ch, picks, live, day, linked):
    """A group whose options follow options of another group (module text, "Linked options")."""
    ids = {o["id"]: o for o in options}
    flags, mine, state, waits, wait_reason = [], [], {}, set(), None
    for h, p in live:
        if "choose_before_anniversary" in ids[h["entity"]]["election"]:
            mine.append((h, p))
        else:
            flags.append(("ELECTION_NOT_SELECTABLE", "review", h["id"],
                          "%s is not chosen on its own: it applies when %s does. This record is not used; withdraw it and "
                          "record that option instead" % (h["entity"], ids[h["entity"]]["election"].get("follows", "its default"))))
    for o in options:
        up = o["election"].get("follows")
        st, d = linked.get(up, (None, None))
        if d is not None:
            waits.add(d["group"])
        if st == "est" and o["election"].get("after_exit_from_anniversary") and d.get("exit") is not None:
            # the followed option took effect after the person left another one: this option waits for the next anniversary
            start = d["exit"] + ONE_DAY
            b = before_anniversary(ch, start, day, _cycle(o))
            if b is True:
                st, wait_reason = None, "%s starts at the first card anniversary on or after %s" % (o["id"], start)
            elif b is None:
                st = "poss"
                flags.append(("ANNIVERSARY_NOT_RECORDED", "review", ch["id"], _no_anniversary(group, ch)))
        if st:
            state[o["id"]] = (st, up, d)
    est = sorted(k for k, v in state.items() if v[0] == "est")
    period = _choice_period(options, ch, day)
    if len(est) == 1:
        other = [h for h, _p in mine if h["entity"] != est[0]]
        if other and period is not False:
            return {"established": None, "possible": sorted({est[0]} | {h["entity"] for h in other}), "via": None, "card": ch["id"],
                    "reason": "a recorded choice contradicts the linked election", "waits_on": sorted(waits),
                    "flags": flags + [("CONFLICTING_ELECTIONS", "review", group,
                                       "%s applies because %s is in effect, but %s is also recorded as in effect on this date (%s); "
                                       "none is applied" % (est[0], state[est[0]][1], other[0]["entity"], other[0]["id"]))]}
        for h in other:
            flags.append(("ELECTION_SUPERSEDED", "info", h["id"],
                          "%s was the cardholder's own choice and no longer counts; %s now applies because %s is in effect. "
                          "End this record on the day before that change" % (h["entity"], est[0], state[est[0]][1])))
        _st, up, d = state[est[0]]
        return {"established": est[0], "possible": [], "via": "election-link:" + up, "support": list(d.get("support", [])),
                "flags": flags, "reason": "applies with %s (%s)" % (up, d["reason"]), "card": ch["id"], "waits_on": sorted(waits)}
    poss = sorted(k for k, v in state.items() if v[0] != "est" or len(est) > 1)
    own_opts = [o for o in options if "choose_before_anniversary" in o["election"] or "default_before_anniversary" in o["election"]]
    if period is True and own_opts:
        d = _own(group, own_opts, ch, [h for h, _p in mine], mine, day)
        d["flags"] = flags + d["flags"]
        return d
    if period is None and own_opts:
        d = _own(group, own_opts, ch, [h for h, _p in mine], mine, day)
        poss = sorted(set(poss) | set(d["possible"]) | ({d["established"]} if d["established"] else set()))
        flags = flags + [f for f in d["flags"] if f not in flags]
        if not any(f[0] == "ANNIVERSARY_NOT_RECORDED" for f in flags):
            flags.append(("ANNIVERSARY_NOT_RECORDED", "review", ch["id"], _no_anniversary(group, ch)))
        return {"established": None, "possible": poss, "via": None, "flags": flags, "card": ch["id"],
                "reason": "card anniversary not recorded", "waits_on": sorted(waits)}
    if poss:
        reason = "; ".join(sorted({"%s: %s" % (v[2]["group"], v[2]["reason"]) for k, v in state.items() if k in poss}))
    else:
        reason = wait_reason or "no option of this group applies on this date under its published terms"
    return {"established": None, "possible": poss, "via": None, "flags": flags, "reason": reason, "card": ch["id"],
            "waits_on": sorted(waits)}


def decide_all(store, prof, day):
    """decide() for every group, the groups that others follow first. Each decision carries its `group`."""
    gs = groups(store)
    order = sorted(gs, key=lambda g: (any("follows" in o["election"] for o in gs[g]), g))
    linked, out = {}, []
    for g in order:
        d = decide(prof, g, gs[g], day, linked)
        if d is None:
            continue
        d["group"] = g
        out.append(d)
        if d["established"]:
            linked[d["established"]] = ("est", d)
        for oid in d["possible"]:
            linked[oid] = ("poss", d)
    return sorted(out, key=lambda d: d["group"])


# ------------------------------------------------------------------ engine and report entry points
def inject(result, store, prof, as_of):
    """Base facts and flags for every election group, for one person on one date."""
    gs = groups(store)
    gov_rules = set(governed(store))
    active = {rid for rid in gov_rules if rid in store.rules and store.rules[rid]["verification"]["status"] != "retired"}
    group_of = {o["id"]: g for g, opts in gs.items() for o in opts}
    followed = {group_of[o["election"]["follows"]] for opts in gs.values() for o in opts if o["election"].get("follows") in group_of}
    result.elections = decide_all(store, prof, as_of)
    live_rules = {d["group"]: any(rid in active for o in gs[d["group"]] for rid in o["election"]["governs"]) for d in result.elections}
    # a group that only others follow matters once a group with a rule in force is actually waiting on it
    waited = {g for d in result.elections if live_rules[d["group"]] and not d["established"] for g in d.get("waits_on", [])}
    for d in result.elections:
        group = d["group"]
        if d["established"]:
            for L in LEVELS:
                result._offer("have:" + d["established"], L, frozenset(), d["via"], d.get("support", []))
        for oid in d["possible"]:
            tok = frozenset([("unknown", "election %s: %s" % (group, d["reason"]))])
            for L in (P, U):
                result._offer("have:" + oid, L, tok, "election-unknown:" + group, [])
        governs_active = group in waited if group in followed else live_rules[group]
        for code, sev, subj, detail in d["flags"]:
            # "no election recorded" only matters once a governed rule is actually in force (not just a candidate)
            if code == "ELECTION_NOT_RECORDED" and not governs_active:
                continue
            result.flag(code, sev, subj, detail)


def boundary_dates(store, profile):
    """Dates on which an election outcome can change (for the timeline)."""
    prof, out = store.profile(profile), set()
    gs = groups(store)
    ids = {o["id"] for opts in gs.values() for o in opts}
    cards = {opts[0]["election"]["card"] for opts in gs.values()}
    exits = []
    for h in prof.holdings.values():
        if h["entity"] in ids and h["state"] != "withdrawn":
            for k, plus in (("valid_from", 0), ("valid_to", 1), ("confirmed_on", 0)):
                d = to_date(h.get(k))
                if d:
                    out.add(d + plus * ONE_DAY)
            if h["state"] == "ended" and to_date(h.get("valid_to")):
                exits.append(to_date(h["valid_to"]) + ONE_DAY)
    for h in prof.holdings.values():
        if h["entity"] in cards and (h.get("opened_on") or h.get("anniversary_on")):
            for opts in gs.values():
                for o in opts:
                    starts = [to_date(o["election"][k]) for k in TERM_KEYS[1:] if k in o["election"]]
                    if o["election"].get("after_exit_from_anniversary"):
                        starts += exits
                    for d0 in starts:
                        w = card_window(h, d0, _cycle(o))
                        if w:
                            out.update([w[0], w[1], w[1] + ONE_DAY])
    return out
