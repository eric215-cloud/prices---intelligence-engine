"""Calculations from published terms: points earned for a purchase, and points after a transfer.

A calculation is arithmetic on sourced numbers. It is kept apart from the two other kinds of answer:

    recorded     a sourced statement, shown as text (a restriction, a summary)
    evaluated    the engine decided whether something applies to a person (status, explain)
    calculated   this module: a number worked out from a published rate or ratio

Every result is either CALCULATED, with the rule, its verification and every assumption listed, or
NOT_CALCULATED, with the reason. Nothing is estimated: a missing rate, a missing ratio, an unverified
rule, an unconfirmed holding or a benefit the engine could not establish each stop the calculation.

Earning rates live in an `earning` block on a grants rule {"holds": <card>}:

    "earning": {"currency": "<currency entity>",
                "rates": [{"category": "<slug from vocab spend_categories>", "per_usd": 3, "label": "dining worldwide"}]}

Each rate is the TOTAL the source states for that category. Rates are never added together. When more than one
rule in force lists a category for the same card, the highest is used and the others are listed.

Categories form a tree in vocab.json: "spend_categories": {"portal-hotels": {"name": "...", "parent": "portal-travel"}}.
A rate published for a broader category applies to the narrower ones under it. Which rate answers a question:

    1. the category asked about, else the nearest broader category that has a rate;
    2. else, if the card has rates only for NARROWER categories, no calculation (the question is too broad);
    3. else the source's catch-all rate ("other"), said to be the catch-all.
"""
from .engine import ESTABLISHED, evaluate, in_effect, leaves, to_date

CATCH_ALL = "other"          # the category a source uses for "all other purchases"
ALWAYS = ("the issuer decides how a purchase is categorised; PRICES does not know the merchant's coding",
          "the terms listed are recorded as text and were not evaluated",
          "this is not a balance: nothing here says the points were earned or have posted")


def card_of(rule, kind_of):
    """The one card a card-benefit rule is about, or None."""
    cards = sorted({i for k, i, neg in leaves(rule["when"]) if k == "holds" and not neg and kind_of(i) == "card"})
    return cards[0] if len(cards) == 1 else None


def earning_shape(rule, kind_of):
    out, e = [], rule["earning"]
    if rule["kind"] != "grants":
        out.append("an 'earning' block belongs only on grants rules")
    if card_of(rule, kind_of) is None:
        out.append("earning rates belong on a rule about exactly one card: when {\"holds\": <card>}")
    if not isinstance(e, dict) or not isinstance(e.get("rates"), list):
        return out + ["earning needs a currency and a list of rates"]
    if kind_of(e.get("currency")) != "currency":
        out.append("earning.currency %r is not a currency entity" % e.get("currency"))
    seen = set()
    for r in e["rates"]:
        if not isinstance(r, dict) or not isinstance(r.get("per_usd"), (int, float)) or isinstance(r.get("per_usd"), bool) or r["per_usd"] <= 0:
            out.append("each rate needs a category and a per_usd greater than zero")
            continue
        if r.get("category") in seen:
            out.append("category %r is listed twice in one earning block" % r.get("category"))
        seen.add(r.get("category"))
    return out


def lineage(category, cats):
    """[category, its parent, its grandparent, ...]"""
    out = []
    while category is not None and category not in out:
        out.append(category)
        parent = cats.get(category, {})
        category = parent.get("parent") if isinstance(parent, dict) else None
    return out


def narrower(category, cats):
    return sorted(c for c in cats if c != category and category in lineage(c, cats))


def unknown_categories(rule, vocab):
    known = vocab.get("spend_categories", {})
    return sorted({r.get("category") for r in rule["earning"].get("rates", []) if isinstance(r, dict) and r.get("category") not in known})


def _basis(rule):
    v = rule["verification"]
    return {"rule": rule["id"], "verification": v["status"], "last_verified": v.get("last_verified"), "review_by": v.get("review_by"),
            "evidence": list(rule.get("evidence", []))}


def _stop(card, reason, **more):
    return dict({"card": card, "result": "NOT_CALCULATED", "reason": reason}, **more)


def earn_quote(store, profile, as_of, category, amount, card=None):
    """Points for spending `amount` US dollars in `category`, one answer per card the person holds."""
    as_of = to_date(as_of)
    if category not in store.vocab.get("spend_categories", {}):
        raise KeyError("unknown spend category %r (known: %s)" % (category, ", ".join(sorted(store.vocab.get("spend_categories", {}))) or "none"))
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise KeyError("amount must be a number of US dollars greater than zero")
    res = evaluate(store, profile, as_of)
    kind_of = lambda i: store.entities.get(i, {}).get("kind")          # noqa: E731
    up, down = lineage(category, store.vocab["spend_categories"]), narrower(category, store.vocab["spend_categories"])
    cards = sorted(e["id"] for e in store.entities.values() if e["kind"] == "card" and (card is None or e["id"] == card))
    out = []
    for c in cards:
        st = res.have(c)
        if st == "NOT_AVAILABLE":
            continue
        if st != ESTABLISHED:
            out.append(_stop(c, "holding of %s is not established for this person (%s)" % (c, st)))
            continue
        offers, blocked, waiting, too_broad = [], [], [], []
        for rule in sorted(store.rules.values(), key=lambda r: r["id"]):
            if "earning" not in rule or card_of(rule, kind_of) != c or rule["verification"]["status"] == "retired":
                continue
            rates = {r["category"]: r for r in rule["earning"]["rates"]}
            hit = next((rates[c] for c in up if c in rates), None)
            rank = 2 if hit is not None else 0            # 2: the category or a broader one; 1: the catch-all
            if hit is None and any(c in rates for c in down):
                too_broad.append("%s lists only narrower categories (%s)" % (rule["id"], ", ".join(c for c in down if c in rates)))
                continue
            if hit is None and CATCH_ALL in rates:
                hit, rank = rates[CATCH_ALL], 1
            if hit is None:
                continue
            if not in_effect(rule, as_of):
                waiting.append("%s is not in effect on %s" % (rule["id"], as_of))
            elif rule["verification"]["status"] != "verified":
                blocked.append("%s is %s" % (rule["id"], rule["verification"]["status"]))
            elif res.have(rule["output"]) != ESTABLISHED:
                why = res.tokens("have:" + rule["output"])["unknowns"] or ["%s is %s" % (rule["output"], res.have(rule["output"]))]
                blocked.append("%s could not be established for this person: %s" % (rule["id"], "; ".join(why)))
            else:
                offers.append((rank == 2, hit["per_usd"], rule, hit))
        specific = [o for o in offers if o[0]]
        pool = specific or offers
        if too_broad and not specific:
            out.append(_stop(c, "%r is too broad for this card: %s. Ask about one of those" % (category, "; ".join(too_broad))))
            continue
        if not pool:
            reason = ("no published rate is recorded for %r on %s" % (category, c)) if not (blocked or waiting) else \
                     "; ".join(blocked + waiting)
            out.append(_stop(c, reason))
            continue
        _spec, per, rule, hit = max(pool, key=lambda o: (o[1], o[2]["id"]))
        stale = to_date(rule["verification"].get("review_by")) is not None and to_date(rule["verification"]["review_by"]) < as_of
        notes = list(ALWAYS)
        if not specific:
            notes.insert(0, "no rate is recorded for %r; the source's catch-all rate (%s) is used, which applies only if the purchase is an "
                            "eligible purchase under the terms below" % (category, hit.get("label", CATCH_ALL)))
        elif hit["category"] != category:
            notes.insert(0, "the rate is the one published for the broader category %r (%s)" % (hit["category"], hit.get("label", "")))
        if len(pool) > 1:
            notes.append("other rules in force also list this category and were not added: %s"
                         % ", ".join("%s (%s per $1)" % (o[2]["id"], _num(o[1])) for o in pool if o[2] is not rule))
        if blocked:
            notes.append("not used: " + "; ".join(blocked))
        if stale:
            notes.append("the rule is past its review date %s: re-verify before relying on this" % rule["verification"]["review_by"])
        out.append({"card": c, "result": "CALCULATED", "points": round(amount * per, 2), "currency": rule["earning"]["currency"],
                    "per_usd": per, "category_used": hit["category"], "label": hit.get("label", ""), "basis": _basis(rule), "stale": stale,
                    "arithmetic": "%s x %s" % (_num(amount), _num(per)), "assumptions": notes,
                    "terms_not_evaluated": list(rule.get("restrictions", []))})
    return {"question": "points for $%s of %s" % (_num(amount), category), "profile": profile, "as_of": as_of.isoformat(), "answers": out}


def parse_ratio(text):
    """'2:1.5' -> (2.0, 1.5): 2 of the source currency become 1.5 of the destination. None when it is not that shape."""
    try:
        a, b = (float(x) for x in str(text).split(":"))
    except ValueError:
        return None
    return (a, b) if a > 0 and b > 0 else None


def convert_quote(store, profile, as_of, source, amount, to=None):
    """`amount` of currency `source` after each transfer the person can make, one answer per destination."""
    as_of = to_date(as_of)
    if store.entities.get(source, {}).get("kind") != "currency":
        raise KeyError("%r is not a currency entity" % source)
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise KeyError("amount must be a number greater than zero")
    res = evaluate(store, profile, as_of)
    prof = store.profile(profile)
    held = [h for h in prof.holdings.values() if h["entity"] == source and h["state"] == "confirmed" and in_effect(h, as_of)]
    if not held:
        balance = "no confirmed holding of %s is recorded" % source
    elif any(h.get("quantity") is None for h in held):
        balance = "balance not recorded"
    else:
        total = sum(h["quantity"] for h in held)
        balance = "balance on record %s (confirmed %s)%s" % (_num(total), ", ".join(sorted(h.get("confirmed_on") or "no date" for h in held)),
                                                             "" if total >= amount else "; LESS than the amount asked about")
    out = []
    for rule in sorted(store.rules.values(), key=lambda r: r["id"]):
        if rule["kind"] != "transfer" or rule["transfer"].get("from") != source or rule["verification"]["status"] == "retired":
            continue
        if to is not None and rule["output"] != to:
            continue
        row = {"to": rule["output"], "basis": _basis(rule)}
        missing = sorted(i for k, i, neg in leaves(rule["when"]) if k == "holds" and not neg and res.have(i) != ESTABLISHED)
        if not in_effect(rule, as_of):
            row.update(result="NOT_CALCULATED", reason="%s is not in effect on %s" % (rule["id"], as_of))
        elif rule["verification"]["status"] != "verified":
            row.update(result="NOT_CALCULATED", reason="%s is %s" % (rule["id"], rule["verification"]["status"]))
        elif rule.get("unchecked"):
            row.update(result="NOT_CALCULATED", reason="conditions on who may use this transfer are recorded as text and not checked: "
                                                       + "; ".join(rule["unchecked"]))
        elif missing:
            row.update(result="NOT_CALCULATED", reason="this person is not established as holding: " + ", ".join(missing))
        elif parse_ratio(rule["transfer"].get("ratio")) is None:
            row.update(result="NOT_CALCULATED", reason="no transfer ratio is recorded" if not rule["transfer"].get("ratio")
                       else "the recorded ratio %r is not of the form a:b" % rule["transfer"]["ratio"],
                       open_questions=list(rule.get("open_questions", [])))
        else:
            a, b = parse_ratio(rule["transfer"]["ratio"])
            stale = to_date(rule["verification"].get("review_by")) is not None and to_date(rule["verification"]["review_by"]) < as_of
            notes = ["exact arithmetic; the programme's own minimums, increments and rounding are recorded as text below and were not applied",
                     balance, "transfers are generally one-way: check the terms before acting"]
            if stale:
                notes.append("the rule is past its review date %s: re-verify before relying on this" % rule["verification"]["review_by"])
            row.update(result="CALCULATED", amount=round(amount * b / a, 2), ratio=rule["transfer"]["ratio"], stale=stale,
                       arithmetic="%s x %s / %s" % (_num(amount), _num(b), _num(a)), assumptions=notes,
                       terms_not_evaluated=list(rule.get("restrictions", [])) + ([rule["transfer"]["note"]] if rule["transfer"].get("note") else []),
                       open_questions=list(rule.get("open_questions", [])))
        out.append(row)
    return {"question": "%s %s transferred" % (_num(amount), source), "profile": profile, "as_of": as_of.isoformat(), "answers": out}


def _num(x):
    return "{:,.0f}".format(x) if float(x).is_integer() else "{:,.2f}".format(x).rstrip("0").rstrip(".")
