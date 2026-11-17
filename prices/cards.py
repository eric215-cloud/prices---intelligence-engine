"""Card architecture and the applicability matrix. Reporting only: nothing here creates an entitlement.

A card entity may carry a `card` block naming who plays each of seven roles:

    card product (the entity itself), cobrand_partner, program_manager, issuer,
    capital_provider, network, network_tier

Those roles are descriptive. The engine ignores them. In particular a card's network tier
gives its holder nothing. What a tier advertises is recorded as `baseline` rules; whether
one of those benefits applies to a given card is decided only by card-level rules:

    grants    card -> benefit, verified, with evidence about that card   => CONFIRMED
    excludes  card -> benefit (optionally superseded_by a stronger one)  => EXCLUDED / SUPERSEDED
    neither                                                              => UNPROVEN (not an entitlement)
"""
from .engine import NOT_AVAILABLE, evaluate, in_effect, to_date
from .conditions import blockers, context
from .engine import standing as rule_standing
from .lint import ROLES, single_holds

CONFIRMED, EXCLUDED, SUPERSEDED, UNPROVEN, PENDING = "CONFIRMED", "EXCLUDED", "SUPERSEDED", "UNPROVEN", "PENDING_REVIEW"
MEANING = {
    CONFIRMED: "applies: card-specific evidence on record",
    EXCLUDED: "does not apply: card-specific exclusion on record",
    SUPERSEDED: "does not apply as advertised: replaced by a card-specific benefit",
    UNPROVEN: "NOT established: advertised for the network tier only; no card-specific evidence",
    PENDING: "claimed but not verified or not yet reviewed; NOT established",
}


def card_pair(rule, kind_of):
    """(card id, benefit id) if the rule is a card-level benefit statement, else None."""
    subject = single_holds(rule["when"])
    if rule["kind"] in ("grants", "excludes") and kind_of(subject) == "card" and kind_of(rule["output"]) == "benefit":
        return subject, rule["output"]
    return None


def architecture(store, only=None):
    """One row per card: the seven roles with names resolved. Missing = not recorded, 'none' = recorded as none."""
    ents, out = store.entities, []
    for c in sorted((e for e in ents.values() if e["kind"] == "card"), key=lambda e: e["id"]):
        if only is not None and c["id"] not in only:
            continue
        block = c.get("card", {})
        row = {"card": c["id"], "name": c["name"], "sources": c.get("sources", []),
               "annual_fee_usd": block.get("annual_fee_usd")}
        for role in ROLES:
            if role not in block:
                row[role] = "(not recorded)"
            elif block[role] is None:
                row[role] = "none"
            else:
                row[role] = "%s [%s]" % (ents.get(block[role], {}).get("name", "?"), block[role])
        out.append(row)
    return out


def matrix(store, as_of=None, profile=None):
    """Applicability of benefits to cards.

    as_of=None ignores validity windows (used for the generated table view, so the view does not
    change merely because time passes). With a profile, only cards that person holds are listed
    and each row carries the engine's status of the benefit for that person.
    """
    ents = store.entities
    kind_of = lambda i: ents.get(i, {}).get("kind")   # noqa: E731
    day = to_date(as_of) if as_of else None
    live = [r for r in store.rules.values() if (rule_standing(r) if day is not None else r["verification"]["status"]) != "retired"
            and (day is None or in_effect(r, day))]
    baselines, card_rules, pending = {}, {}, {}
    for r in sorted(live, key=lambda r: r["id"]):
        if r["kind"] == "baseline":
            baselines.setdefault(single_holds(r["when"]), []).append(r)
        elif card_pair(r, kind_of):
            card_rules.setdefault(card_pair(r, kind_of), []).append(r)
    for c in store.candidates.values():
        if c["status"] != "proposed":
            continue
        kinds = {e["id"]: e["kind"] for e in c.get("proposed_entities", [])}
        pair = card_pair(c["proposed_rule"], lambda i: kind_of(i) or kinds.get(i))
        if pair:
            pending.setdefault(pair, []).append(c["id"])
    res = evaluate(store, profile, day) if profile else None

    def classify(card, benefit):
        rules = card_rules.get((card, benefit), [])
        for r in rules:
            if r["verification"]["status"] == "verified" and r["kind"] == "grants":
                return CONFIRMED, r["id"]
        for r in rules:
            if r["verification"]["status"] == "verified" and r["kind"] == "excludes":
                if r.get("superseded_by"):
                    return SUPERSEDED, "%s (replaced by %s)" % (r["id"], r["superseded_by"])
                return EXCLUDED, r["id"]
        waiting = [r["id"] for r in rules] + ["candidate " + c for c in sorted(pending.get((card, benefit), []))]
        if waiting:
            return PENDING, ", ".join(waiting)
        return UNPROVEN, ""

    rows, ctx = [], context(store)
    for card in sorted((e for e in ents.values() if e["kind"] == "card"), key=lambda e: e["id"]):
        if res is not None and res.have(card["id"]) == NOT_AVAILABLE:
            continue
        tier = card.get("card", {}).get("network_tier")
        listed = []
        for b in sorted(baselines.get(tier, []), key=lambda r: r["output"]):
            listed.append((b["output"], "network_baseline", b))
        seen = {x[0] for x in listed}
        own = sorted({b for (c, b) in list(card_rules) + list(pending) if c == card["id"]} - seen)
        listed += [(b, "card_specific", None) for b in own]
        for benefit, basis, brule in listed:
            standing, detail = classify(card["id"], benefit)
            row = {"card": card["id"], "card_name": card["name"], "network_tier": tier or "",
                   "benefit": benefit, "benefit_name": ents.get(benefit, {}).get("name", benefit),
                   "basis": basis, "standing": standing, "meaning": MEANING[standing], "detail": detail}
            confirming = next((r for r in card_rules.get((card["id"], benefit), []) if r["id"] == detail), None)
            if standing == CONFIRMED and confirming is not None and blockers(confirming, ctx):
                # the card carries the benefit, but who among its holders has it is not settled (conditions.py)
                row["detail"] = "%s; %d condition(s) on who has it are unchecked, open or unclassified: not established for a holder" % (
                    detail, len(blockers(confirming, ctx)))
            if brule is not None and brule["verification"]["status"] != "verified":
                row["detail"] = (detail + "; " if detail else "") + "baseline rule %s is itself unverified" % brule["id"]
            if res is not None:
                row["card_status"] = res.have(card["id"])
                row["holder_status"] = res.have(benefit)            # from any source the person has
                if confirming is not None:                          # through THIS card's own rule (Result.rule_applies)
                    row["via_this_card"] = res.rule_applies(confirming["id"])["status"]
            rows.append(row)
    return rows
