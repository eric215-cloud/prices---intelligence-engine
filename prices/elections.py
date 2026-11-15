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
"""
import datetime

from .engine import LEVELS, P, U, in_effect, to_date

ONE_DAY = datetime.timedelta(days=1)
TERM_KEYS = ("opened_before", "default_before_anniversary", "starts_at_anniversary", "elect_before_anniversary")


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
def anniversary_window(opened, d0):
    """First anniversary of `opened` on or after d0, as (first day it may fall on, last day it may fall on).

    Normally the two are the same day. An account opened on February 29 has no anniversary day in other years:
    the window is February 28 to March 1 and dates inside it are treated as unknown, not decided by a convention."""
    year = max(d0.year, opened.year + 1)
    while True:
        if opened.month == 2 and opened.day == 29 and not _leap(year):
            lo, hi = datetime.date(year, 2, 28), datetime.date(year, 3, 1)
        else:
            lo = hi = opened.replace(year=year)
        if lo >= d0:
            return lo, hi
        year += 1


def _leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def before_anniversary(card_holding, d0, day):
    """Is `day` before the first card anniversary on or after d0?  True / False / None (not known)."""
    if day < d0:
        return True                         # that anniversary is never earlier than d0
    opened = to_date(card_holding.get("opened_on"))
    if opened is None:
        return None
    lo, hi = anniversary_window(opened, d0)
    if day < lo:
        return True
    if day >= hi:
        return False
    return None                             # inside a February 28 - March 1 window


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


def allowed(option, card_holding, day, election=None):
    """May this option be in effect on `day` under its public terms?  True / False / None.

    `election` is the person's holding of the option, when one is recorded (its start date is checked against
    `elect_before_anniversary`)."""
    t, checks, why = option["election"], [], []
    if "opened_before" in t:
        ok = opened_before(card_holding, to_date(t["opened_before"]))
        checks.append(ok)
        if ok is False:
            why.append("only for accounts opened before %s (this one was opened %s)" % (t["opened_before"], card_holding.get("opened_on")))
        elif ok is None:
            why.append("only for accounts opened before %s, and the opening date is not recorded" % t["opened_before"])
    if "starts_at_anniversary" in t:
        b = before_anniversary(card_holding, to_date(t["starts_at_anniversary"]), day)
        checks.append(None if b is None else not b)
        if b is True:
            why.append("does not start before the first card anniversary on or after %s" % t["starts_at_anniversary"])
        elif b is None:
            why.append("starts at the first card anniversary on or after %s, and that date is not known" % t["starts_at_anniversary"])
    if "elect_before_anniversary" in t and election is not None:
        start = to_date(election.get("valid_from"))
        if start is None:
            checks.append(None)
            why.append("must be elected before the first card anniversary on or after %s; the election's start is not recorded"
                       % t["elect_before_anniversary"])
        else:
            b = before_anniversary(card_holding, to_date(t["elect_before_anniversary"]), start)
            checks.append(b)
            if b is False:
                why.append("must be elected before the first card anniversary on or after %s; this election starts %s"
                           % (t["elect_before_anniversary"], start))
            elif b is None:
                why.append("must be elected before the first card anniversary on or after %s, and that date is not known"
                           % t["elect_before_anniversary"])
    return _all(checks), why


def default_now(option, card_holding, day):
    """Does this option apply WITHOUT any election on `day`?  True / False / None."""
    t = option["election"]
    if "default_before_anniversary" not in t:
        return False
    d0 = to_date(t["default_before_anniversary"])
    return _all([opened_before(card_holding, d0), before_anniversary(card_holding, d0, day)])


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
def decide(prof, group, options, day):
    """Which option of `group` is in effect for this person on `day`.

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
    picks = [h for h in prof.holdings.values() if h["entity"] in ids]
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
    ch = cards[0]
    chosen = sorted({h["entity"] for h, _p in live})
    if len(chosen) > 1:
        return _unsure(options, ch, day, [("CONFLICTING_ELECTIONS", "review", group,
                       "more than one option is recorded as in effect on this date (%s); none is applied"
                       % ", ".join("%s=%s" % (h["id"], h["entity"]) for h, _p in live))], "conflicting elections recorded")
    if chosen:
        h, pres = next((h, p) for h, p in live if p == "in") if any(p == "in" for _h, p in live) else live[0]
        opt = ids[h["entity"]]
        if pres == "maybe":
            return _unsure(options, ch, day, [("ELECTION_START_NOT_RECORDED", "review", h["id"],
                           "%s has no start date and the owner first confirmed it on %s; before that the election is not known"
                           % (h["entity"], h.get("confirmed_on") or "no date"))], "election start not recorded")
        if h["state"] != "confirmed" and h["state"] != "ended":
            return _unsure(options, ch, day, [("UNCONFIRMED_ELECTION", "review", h["id"],
                           "%s is recorded but not confirmed by the owner" % h["entity"])], "election not confirmed")
        ok, why = allowed(opt, ch, day, h)
        if ok is False:
            return _unsure(options, ch, day, [("ELECTION_NOT_PERMITTED", "review", h["id"],
                           "%s is recorded, but its published terms do not allow it on this date: %s" % (h["entity"], "; ".join(why)))],
                           "recorded election conflicts with the published terms", keep=opt["id"])
        out = {"established": opt["id"], "possible": [], "via": "election:" + h["id"], "support": ["holding:" + ch["id"]],
               "flags": flags, "reason": "elected (%s)" % h["id"], "card": ch["id"]}
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
                "flags": [], "reason": "applies without an election until the transition anniversary", "card": ch["id"]}
    if any(v is None for _o, v in defaults):
        return _unsure(options, ch, day, [("ANNIVERSARY_NOT_RECORDED", "review", ch["id"],
                       "which option of %s applies on this date depends on the card's anniversary, and %s has no opened_on"
                       % (group, ch["id"]))], "card anniversary not recorded")
    if not any(allowed(o, ch, day)[0] is not False for o in options):
        return {"established": None, "possible": [], "via": None, "flags": [], "card": ch["id"],
                "reason": "no option of this group applies on this date under its published terms"}
    return _unsure(options, ch, day, [("ELECTION_NOT_RECORDED", "review", group,
                   "%s is held, but no election for %s is recorded; none of its options is applied" % (card, group))],
                   "no election recorded")


def _unsure(options, ch, day, flags, reason, keep=None):
    """Every option that could apply on this date is UNRESOLVED; none is established.
    `keep`: an option the owner recorded, kept UNRESOLVED even where its terms say no (neither granted nor dropped)."""
    possible = []
    for o in options:
        if ch is not None and o["id"] != keep:
            ok, _why = allowed(o, ch, day)
            if ok is False:
                continue
        possible.append(o["id"])
    return {"established": None, "possible": possible, "via": None, "flags": flags, "reason": reason, "card": ch["id"] if ch else None}


# ------------------------------------------------------------------ engine and report entry points
def inject(result, store, prof, as_of):
    """Base facts and flags for every election group, for one person on one date."""
    gov_rules = set(governed(store))
    active = {rid for rid in gov_rules if rid in store.rules and store.rules[rid]["verification"]["status"] != "retired"}
    result.elections = []
    for group, options in sorted(groups(store).items()):
        d = decide(prof, group, options, as_of)
        if d is None:
            continue
        d["group"] = group
        result.elections.append(d)
        if d["established"]:
            for L in LEVELS:
                result._offer("have:" + d["established"], L, frozenset(), d["via"], d.get("support", []))
        for oid in d["possible"]:
            tok = frozenset([("unknown", "election %s: %s" % (group, d["reason"]))])
            for L in (P, U):
                result._offer("have:" + oid, L, tok, "election-unknown:" + group, [])
        governs_active = any(rid in active for o in options for rid in o["election"]["governs"])
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
    for h in prof.holdings.values():
        if h["entity"] in ids:
            for k, plus in (("valid_from", 0), ("valid_to", 1), ("confirmed_on", 0)):
                d = to_date(h.get(k))
                if d:
                    out.add(d + plus * ONE_DAY)
        if h["entity"] in cards and h.get("opened_on"):
            opened = to_date(h["opened_on"])
            for opts in gs.values():
                for o in opts:
                    for k in TERM_KEYS[1:]:
                        if k in o["election"]:
                            lo, hi = anniversary_window(opened, to_date(o["election"][k]))
                            out.update([lo, hi, hi + ONE_DAY])
    return out
