"""Command line interface.  Run:  python3 -m prices <command> --help"""
import argparse
import datetime
import json
import os
import sys
import zipfile

from . import calc, cards, changes, discovery, earned, goals, review, tables
from .conditions import describe as describe_conditions
from .engine import evaluate
from .lint import lint
from .store import Store, read_audit


def _root(args):
    return os.path.abspath(args.root)


def _today(args):
    return args.as_of or datetime.date.today().isoformat()


def _emit(args, obj, text_fn):
    if args.json:
        print(json.dumps(obj, indent=2, sort_keys=True, default=str))
    else:
        text_fn(obj)


def _steps(row):
    parts = ["%s %s" % ("DO" if s["type"] == "action" else "ACQUIRE", s["name"]) for s in row.get("steps", [])]
    parts += ["CONFIRM: " + u for u in row.get("unknowns", [])]
    return "; ".join(parts)


def cmd_lint(args):
    issues = lint(Store.load(_root(args)))
    st = tables.status(_root(args))
    if st["exists"] and st["stale"]:
        issues.append(("WARNING", "TABLES_STALE", "tables/", "out of date with the store (%s); run `python3 -m prices tables export`"
                       % ", ".join(st["stale"])))
    if st["exists"] and st["edited"]:
        issues.append(("WARNING", "TABLES_EDITED", "tables/", "unimported edits in %s; run `python3 -m prices tables import` or re-export"
                       % ", ".join(st["edited"])))
    for sev, code, path, msg in issues:
        print("%-7s %-26s %s: %s" % (sev, code, path, msg))
    n_err = sum(1 for i in issues if i[0] == "ERROR")
    print("lint: %d error(s), %d warning(s)" % (n_err, len(issues) - n_err))
    return 1 if n_err else 0


def cmd_status(args):
    store = Store.load(_root(args))
    rep = evaluate(store, args.profile, _today(args)).report()

    def text(r):
        print("PRICES status  profile=%s  as-of=%s%s" % (r["profile"], r["as_of"], "  [SYNTHETIC DATA]" if r["synthetic"] else ""))
        print("\n1. SOURCED RULES (%d)" % len(r["sourced_rules"]))
        for x in r["sourced_rules"]:
            print("   %-10s %-8s %s%s%s" % (x["verification"], x["kind"], x["id"], "" if x["in_effect"] else "  (not in effect)",
                                          "  (establishes nothing: %d condition(s) block; see explain)" % x["blocked_by"] if x.get("blocked_by") else ""))
        print("\n2. PERSONAL QUALIFICATIONS (%d)" % len(r["personal_qualifications"]))
        for x in r["personal_qualifications"]:
            print("   %-11s %-28s to %-10s -> %s" % (x["state"], x["entity"], x["valid_to"] or "open", x["effective"]))
        print("\n3. DERIVED ENTITLEMENTS - established (%d)" % len(r["derived_entitlements"]))
        for x in r["derived_entitlements"]:
            print("   %-32s via %s" % (x["entity"], x["via"]))
        print("\n   Eligible to acquire now (%d)" % len(r["eligible_to_acquire"]))
        for x in r["eligible_to_acquire"]:
            print("   %-32s via %s" % (x["entity"], x["rule"]))
        print("\n   Conditional - needs action (%d)" % len(r["conditional"]))
        for x in r["conditional"]:
            print("   %-32s %s" % (x["entity"], _steps(x)))
        print("\n4. UNRESOLVED POSSIBILITIES (%d)" % len(r["unresolved"]))
        for x in r["unresolved"]:
            print("   %-32s %s" % (x["entity"], _steps(x)))
        if "earned_entitlements" in r:
            print("\n   Earned benefits on record (%d)  - detail: python3 -m prices earned --profile %s" % (len(r["earned_entitlements"]), r["profile"]))
            for x in r["earned_entitlements"]:
                left = "" if x["remaining"] is None else "  remaining %s" % earned.num(x["remaining"])
                print("   %-18s %-32s cycle %s  %s to %s%s" % (x["state"], x["entity"], x["cycle"], x["effective_from"], x["expires_on"], left))
        if "elections" in r:
            print("\n   Card elections (%d)  - one option per group; nothing is assumed when none is recorded" % len(r["elections"]))
            for x in r["elections"]:
                state = ("IN EFFECT  " + x["established"]) if x["established"] else (
                    "UNRESOLVED " + (", ".join(x["unresolved"]) if x["unresolved"] else "(no option possible)"))
                print("   %-36s %s  - %s" % (x["group"], state, x["reason"]))
        print("\nFLAGS (%d)" % len(r["flags"]))
        for f in r["flags"]:
            print("   [%s] %s %s: %s" % (f["severity"], f["code"], f["subject"], f["detail"]))
    _emit(args, rep, text)
    return 0


def cmd_explain(args):
    store = Store.load(_root(args))
    res = evaluate(store, args.profile, _today(args), include_candidates=args.candidates)
    atom = "have:" + args.entity
    obj = {"entity": args.entity, "status": res.status(atom), "chain": res.chain(atom),
           "downstream": res.dependents(atom)}
    obj.update(res.tokens(atom))

    def text(o):
        print("%s: %s" % (o["entity"], o["status"]))
        for line in goals.chain_lines(o["chain"], 1):
            print(line)
        if o["steps"] or o["unknowns"]:
            print("  needs: " + _steps(o))
        print("  downstream: " + (", ".join(o["downstream"]) or "none"))
        if o["conditions"]:
            print("  restrictions and open questions on %s, as a reviewer classed them (text is shown, not evaluated):" % o["chain"].get("via", "the rule"))
            for c in o["conditions"]:
                label = "not classified" if c["class"] is None else c["class"].replace("_", " ") + (" by " + c["enforced_by"] if c["enforced_by"] else "")
                print("    - [%s%s] %s" % (label, ": BLOCKS" if c["blocks"] else "", c["text"]))
            if o["condition_review"]:
                print("    classed by %s on %s" % (o["condition_review"]["by"], o["condition_review"]["on"]))
    via = store.rules.get(obj["chain"].get("via", ""), {})
    obj["conditions"] = describe_conditions(via) if via else []
    obj["condition_review"] = {k: via["condition_review"][k] for k in ("by", "on")} if via.get("condition_review") else None
    obj["terms_not_evaluated"] = [c["text"] for c in obj["conditions"] if c["kind"] == "restriction" and c["class"] != "enforced"]
    _emit(args, obj, text)
    return 0


def _calc_rows(o, unit):
    print("%s  profile=%s  as-of=%s" % (o["question"], o["profile"], o["as_of"]))
    if not o["answers"]:
        print("  no answer: nothing on record for this person applies")
    for a in o["answers"]:
        head = a.get("card") or a.get("to")
        if a["result"] != "CALCULATED":
            print("  %-34s NOT CALCULATED: %s" % (head, a["reason"]))
            for q in a.get("open_questions", []):
                print("      open question: " + q)
            continue
        b = a["basis"]
        print("  %-34s CALCULATED %s %s  = %s" % (head, calc._num(a.get("points", a.get("amount"))), a.get("currency", a.get("to")), a["arithmetic"]))
        print("      from rule %s (%s %s, review by %s; evidence %s)" % (b["rule"], b["verification"], b["last_verified"], b["review_by"],
                                                                         ", ".join(b["evidence"]) or "none"))
        for n in a["assumptions"]:
            print("      note: " + n)
        for t in a["terms_not_evaluated"]:
            print("      term (text, not evaluated): " + t)
        for q in a.get("open_questions", []):
            print("      open question: " + q)


def cmd_earnings(args):
    store = Store.load(_root(args))
    obj = calc.earn_quote(store, args.profile, _today(args), args.category, args.amount, args.card)
    _emit(args, obj, lambda o: _calc_rows(o, "points"))
    return 0


def cmd_convert(args):
    store = Store.load(_root(args))
    obj = calc.convert_quote(store, args.profile, _today(args), args.source, args.amount, args.to)
    _emit(args, obj, lambda o: _calc_rows(o, "amount"))
    return 0


def _print_changes(changes_list, indent="   "):
    for c in changes_list:
        print("%s%s: %s -> %s" % (indent, c["atom"], c["before"], c["after"]))
        if c["downstream_before"]:
            print("%s   relied on by: %s" % (indent, ", ".join(c["downstream_before"])))


def cmd_review(args):
    store = Store.load(_root(args))
    obj = review.review(store, args.profile, args.date_from, args.date_to)

    def text(o):
        print("Review %s  %s -> %s" % (o["profile"], o["from"], o["to"]))
        _print_changes(o["changes"])
        for f in o["new_flags"]:
            print("   [%s] %s %s: %s" % (f["severity"], f["code"], f["subject"], f["detail"]))
        print("   downstream review list: " + (", ".join(o["downstream_review"]) or "none"))
        if o.get("credit_periods"):
            print("   credit periods ending in this window (published allowance; not a personal balance):")
            for c in o["credit_periods"]:
                print("      " + _credit_event(c))
    _emit(args, obj, text)
    return 0


def cmd_timeline(args):
    store = Store.load(_root(args))
    ev = review.timeline(store, args.profile, _today(args), args.until)

    def text(events):
        if not events:
            print("No changes between %s and %s." % (_today(args), args.until))
        for e in events:
            print(e["date"])
            _print_changes(e["changes"])
            for f in e["new_flags"]:
                print("   [%s] %s %s: %s" % (f["severity"], f["code"], f["subject"], f["detail"]))
            for c in e.get("credit_periods", []):
                print("   credit period ends: " + _credit_event(c, dated=False))
    _emit(args, ev, text)
    return 0


def cmd_apply(args):
    try:
        with open(args.changeset, encoding="utf-8") as f:
            cs = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print("REJECTED\n  UNREADABLE_CHANGESET: %s" % e)
        return 2
    out = changes.apply(_root(args), cs, dry_run=args.dry_run)
    out.pop("store", None)
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
    elif out["ok"]:
        print("%s  %s" % ("VALID (dry run, nothing written)" if args.dry_run else "APPLIED", cs["id"]))
        for p in out["changed"]:
            print("  changed: " + p)
        for name, imp in out["impact"].items():
            print("  impact on profile %s:" % name)
            _print_changes(imp["changes"], "    ")
            for f in imp["new_flags"]:
                print("    [%s] %s %s" % (f["severity"], f["code"], f["subject"]))
        print("  DOWNSTREAM REVIEW NEEDED: %s" % ("yes" if out["review_needed"] else "no"))
        if not args.dry_run:
            note = tables.refresh_if_clean(_root(args))
            if note:
                print("  " + note)
    else:
        print("REJECTED  (no record was changed)")
        for e in out["errors"]:
            print("  " + e)
    return 0 if out["ok"] else 2


def cmd_discover(args):
    store = Store.load(_root(args))
    d = _today(args)
    if args.mode == "forward":
        obj = {"tasks": discovery.plan_forward(store, args.profile, d, args.max_age)}
    elif args.mode == "backward":
        if not args.target:
            print("backward mode needs --target <entity id>")
            return 2
        obj = discovery.plan_backward(store, args.profile, args.target, d, args.max_age)
    elif args.mode == "bridge":
        obj = discovery.plan_bridge(store, args.profile, d, args.max_age)
    elif args.mode == "exploratory":
        obj = {"tasks": discovery.plan_exploratory(store, args.profile, d, args.max_age)}
    elif args.mode == "applicability":
        obj = {"tasks": discovery.plan_applicability(store, args.profile, d, args.max_age)}
    else:
        obj = discovery.coverage_summary(store, args.profile, d, args.max_age)
    if "tasks" in obj and args.budget:
        obj["tasks_omitted_by_budget"] = max(0, len(obj["tasks"]) - args.budget)
        obj["tasks"] = obj["tasks"][:args.budget]
    print(json.dumps(obj, indent=2, sort_keys=True))
    return 0


def cmd_earned(args):
    store = Store.load(_root(args))
    day = _today(args)
    sv = earned.survey(store, args.profile, day)
    res = evaluate(store, args.profile, day)
    sv.pop("facts")
    sv["accounts"] = [a for a in sv["accounts"] if not args.account or a["account"] == args.account]
    for a in sv["accounts"]:
        a["cycles"] = [c for c in a["cycles"] if not args.cycle or c["cycle"] == args.cycle]
        for c in a["cycles"]:
            for b in c["benefits"]:
                b["engine_status"] = res.have(b["entity"])      # entity-level: all accounts and cycles together
                lvl = res.level_of("have:" + b["entity"])
                b["engine_source"] = res.via[lvl]["have:" + b["entity"]][0] if lvl else None
                b["chain"] = {"rule_evidence": [store.evidence[e] for e in b["public"]["evidence"] if e in store.evidence],
                              "readings": [r for r in c["readings"] if r["id"] in b["achievement"]["basis"]]}
    # flags that belong to this report: the earned-benefit ones, and general ones raised on the rules shown here
    shown = {b["rule"] for a in sv["accounts"] for c in a["cycles"] for b in c["benefits"]}
    own = [f for f in res.flags if f in sv["flags"] or f["subject"] in shown]
    sv["other_flags"] = len(res.flags) - len(own)
    sv["flags"] = own

    def text(o):
        n = earned.num
        print("EARNED BENEFITS  profile=%s  owner=%s  as-of=%s%s" % (o["profile"], o["owner"], o["as_of"], "  [SYNTHETIC DATA]" if o["synthetic"] else ""))
        print("Each benefit shows three separate things: the PUBLIC RULE (what is on offer to anyone), the ACHIEVEMENT")
        print("(what this person's own dated records show) and the ENTITLEMENT (what is actually on the account on this date).")
        if not o["accounts"]:
            print("\nNo account of this person has an earned-benefit rule or record.")
        for a in o["accounts"]:
            print("\nACCOUNT %s  %s  [%s]" % (a["account"], a["card_name"], a["account_state"]))
            if not a["cycles"]:
                print("   nothing on offer and nothing recorded for this account on this date")
            for c in a["cycles"]:
                print("  QUALIFYING YEAR %s  (%s to %s)   measure %s" % (c["cycle"], c["period"][0], c["period"][1], c["measure"]))
                pr = c["progress"]
                if pr:
                    print("    progress on file  %s%s%s %s  (reading %s%s)" % (
                        "at least " if pr["kind"] == "at_least" else "", n(pr["value"]), " " + c["unit"] if c["unit"] else "",
                        "on a date that is not recorded" if pr["as_of"] == "unknown" else "as of " + pr["as_of"] + (", final" if pr["final"] else ""),
                        pr["reading"], "" if pr["age_days"] is None else ", %d days before this date" % pr["age_days"]))
                else:
                    print("    progress on file  none usable on this date" + ("" if c["qualification"] else " (no record for this cycle)"))
                if args.detail:
                    for r in c["readings"]:
                        print("      reading %-14s %10s %-8s observed %-10s %-11s %s" % (
                            r["id"], n(r["value"]), r.get("value_kind", "exact"), r["observed_on"], r["state"],
                            ("by %s on %s" % (r["confirmed_by"], r["confirmed_on"]) if r["state"] == "confirmed" else "") +
                            ("  -> %s" % r["superseded_by"] if r.get("superseded_by") else "") + ("  [%s]" % r["basis"] if r.get("basis") else "")))
                for b in c["benefits"]:
                    pub, ach, ent = b["public"], b["achievement"], b["entitlement"]
                    print("\n    %s  [%s]" % (b["name"], b["entity"]))
                    print("      PUBLIC RULE   %s (%s)%s: %s %s on %s in one %s; lasts %s%s; activation %s%s" % (
                        pub["rule"], pub["verification"], "" if pub["offered_for_cycle"] else ", NOT ON OFFER FOR THIS CYCLE",
                        n(pub["threshold"]), pub["unit"], pub["measure"], pub["period"].replace("_", " "), pub["term"],
                        " (for this cycle: %s)" % pub["expected_end"] if pub["expected_end"] else "", pub["activation"],
                        "; allowance %s %s" % (n(pub["allowance"]["amount"]), pub["allowance"]["unit"]) if pub["allowance"] else ""))
                    print("                    evidence: %s%s" % (", ".join(pub["evidence"]) or "none",
                          "; offer valid %s to %s" % (pub["offer_valid"][0] or "open", pub["offer_valid"][1] or "open") if any(pub["offer_valid"]) else ""))
                    if args.detail:
                        for e in b["chain"]["rule_evidence"]:
                            print("                    source %s: %s (%s, %s, retrieved %s)" % (e["id"], e["title"], e["publisher"], e["source_type"], e["retrieved_on"]))
                    print("      ACHIEVEMENT   %s%s" % (ach["state"], " - " + ach["detail"] if ach["detail"] else ""))
                    print("      ENTITLEMENT   %s%s" % (ent["state"], " - " + ent["detail"] if ent["detail"] else ""))
                    for i in b["instances"]:
                        who = "confirmed by %s on %s" % (i["confirmed_by"], i["confirmed_on"]) if i["record_state"] == "confirmed" else "NOT CONFIRMED"
                        print("                    record %s: %s  %s to %s%s  (%s)" % (
                            i["id"], i["state"], i["effective_from"], i["expires_on"],
                            ", ended %s" % i["ended_on"] if i["ended_on"] else "", who))
                        for why in i["reasons"]:
                            print("                      unresolved: %s" % why)
                        cr = i["credit"]
                        if cr:
                            print("                      credit: allowance %s %s; used %s (confirmed)%s; remaining %s%s" % (
                                n(cr["allowance"]), cr["unit"], n(cr["used"]),
                                "; possibly used %s (not confirmed or undated)" % n(cr["possibly_used"]) if cr["possibly_used"] else "",
                                n(cr["remaining"]), " (at least %s)" % n(cr["remaining_at_least"]) if cr["possibly_used"] else ""))
                        if args.detail:
                            if i["basis"]:
                                print("                      basis: %s" % i["basis"])
                            for u in i["usage"]:
                                print("                      use %-12s %8s on %-10s %s%s" % (u["id"], n(u["amount"]), u["used_on"], u["state"],
                                      "  [%s]" % u["basis"] if u.get("basis") else ""))
                    if b["withdrawn"]:
                        print("                    withdrawn records (kept as history): %s" % ", ".join(b["withdrawn"]))
                    print("      WHOLE PERSON  %s on this date across all of this person's accounts and qualifying years%s" % (
                        b["engine_status"], " (from %s)" % (b["engine_source"].replace(":", " ") if b["engine_source"].startswith("entitlement:") else "rule " + b["engine_source"]) if b["engine_source"] else ""))
        print("\nFLAGS on earned benefits (%d)" % len(o["flags"]))
        for f in o["flags"]:
            print("   [%s] %s %s: %s" % (f["severity"], f["code"], f["subject"], f["detail"]))
        if o["other_flags"]:
            print("   (%d other flag(s) not about earned benefits: python3 -m prices status --profile %s)" % (o["other_flags"], o["profile"]))
        print("\nOnly ENTITLEMENT = ACTIVE means the benefit can be used on this date. ACHIEVED means eligible, not held.")
    _emit(args, sv, text)
    return 0


def _credit_event(c, dated=True):
    return "%s%s  period %s ends (%s %s published, account %s, applies: %s); %s; %s" % (
        c["date"] + "  " if dated else "", c["benefit"], c["period"], earned.num(c["amount"]), c["unit"], c["account"], c["applies"],
        c["unused"], c["then"])


def _credit_terms(t):
    """Published terms as text. 'not stated' is printed for everything the source does not say."""
    def stated(v, fmt):
        return "not stated by the source" if v is None else ("none" if v == "none" else fmt % earned.num(v))
    lines = ["%s %s %s" % (earned.num(t["amount"]), t["unit"], t["cycle_text"]) +
             (" (at most %s %s in a calendar year)" % (earned.num(t["per_calendar_year_at_most"]), t["unit"]) if t["per_calendar_year_at_most"] else ""),
             "per transaction: maximum %s; minimum stay %s; minimum transaction %s" % (
                 stated(t["max_per_transaction"], "%s " + t["unit"]), stated(t["min_stay_nights"], "%s night(s)"),
                 stated(t["min_transaction"], "%s " + t["unit"])),
             "rollover: " + ("not stated by the source" if t["rollover"] is None else "none; unused allowance expires with the period"
                             if t["rollover"] == "none" else "allowed, maximum " + stated(t["rollover_max"], "%s " + t["unit"]))]
    if t.get("note"):
        lines.append("note: " + t["note"])
    return lines


def _credit_period(p):
    if p is None or p["state"] == "NO_OFFER":
        return "none on this date - %s" % (p["reason"] if p else "the offer is not in effect")
    if p["state"] != "KNOWN":
        return "%s - %s" % (p["state"], p["reason"])
    text = "%s  %s to %s" % (p["label"] or "(new period)", p["start"], p["end"] or "the next use")
    for k in ("cut", "note"):
        if p.get(k):
            text += "  [%s]" % p[k]
    return text


def cmd_credits(args):
    from . import credits
    store = Store.load(_root(args))
    day = _today(args)
    if not args.profile:
        obj = credits.published(store, day, args.candidates, args.card)

        def text(o):
            print("PUBLISHED RECURRING CREDITS  as-of=%s%s" % (o["as_of"], "  (including candidates awaiting review)" if args.candidates else ""))
            print("These are the card's published terms. Nothing here is anyone's balance.")
            if not o["credits"]:
                print("\nNo rule%s has structured credit terms." % (" or candidate" if args.candidates else " in force"))
            for c in o["credits"]:
                print("\n%s  [%s]  on %s" % (c["name"], c["benefit"], c["card"]))
                print("   RULE        %s (%s)%s; offer %s; evidence: %s" % (c["rule"], c["rule_state"], " " + c["candidate"] if c["candidate"] else "",
                                                                         c["offer"]["text"], ", ".join(c["evidence"]) or "none"))
                for i, line in enumerate(_credit_terms(c["terms"])):
                    print("   %-11s %s" % ("TERMS" if i == 0 else "", line))
                print("   PERIOD NOW  %s" % _credit_period(c["period"]))
        _emit(args, obj, text)
        return 0
    obj = credits.survey(store, args.profile, day, args.candidates, args.card)
    if args.until:
        obj["periods_ending"] = credits.events(store, args.profile, day, args.until, args.candidates)

    def text(o):
        print("RECURRING CREDITS  profile=%s  owner=%s  as-of=%s%s%s" % (o["profile"], o["owner"], o["as_of"], "  [SYNTHETIC DATA]" if o["synthetic"] else "",
                                                                     "  (including candidates awaiting review)" if args.candidates else ""))
        if not o["accounts"]:
            print("\nNo card this person holds on this date has structured credit terms%s." % ("" if args.candidates else " in force"))
        for a in o["accounts"]:
            print("\nACCOUNT %s  %s  [%s; opened %s]" % (a["account"], a["card_name"], a["account_state"], a["opened_on"] or "not recorded"))
            for c in a["credits"]:
                print("\n  %s  [%s]" % (c["name"], c["benefit"]))
                lines = _credit_terms(c["terms"])
                print("     PUBLISHED   %s (%s): %s" % (c["rule"], c["rule_state"], lines[0]))
                for line in lines[1:] + ["offer: %s; evidence: %s" % (c["offer"]["text"], ", ".join(c["evidence"]) or "none")]:
                    print("                 " + line)
                ap = c["applies"]
                print("     APPLIES     %s for this person on this date%s" % (ap["status"], "" if not ap["needs"] else " - " + "; ".join(ap["needs"])))
                if "election" in ap:
                    e = ap["election"]
                    print("                 only under election %s (%s): %s" % (e["option"], e["group"], "in effect" if e["in_effect"] else "NOT in effect - " + e["reason"]))
                print("     PERIOD      %s" % _credit_period(c["period"]))
                if "next" in c and ap["status"] != "NOT_AVAILABLE":
                    print("                 %s: %s; %s" % (c["next"]["date"], c["next"]["what"], c["next"]["unused"]))
                if "allowance" in c:
                    print("     ALLOWANCE   %s %s - %s" % (earned.num(c["allowance"]["amount"]), c["allowance"]["unit"], c["allowance"]["note"]))
                elif ap["status"] == "NOT_AVAILABLE":
                    print("     ALLOWANCE   none for this person: the benefit does not apply to them on this date")
                else:
                    print("     ALLOWANCE   not determined: the allowance period is not known")
                p = c["personal"]
                if "record" not in p:
                    print("     PERSONAL    %s - %s" % (p["state"].replace("_", " "), p["text"]))
                else:
                    left = "remaining %s" % earned.num(p["remaining"]) + ("" if not p["possibly_used"] else " (at least %s; %s more may have been used, unconfirmed)"
                                                                         % (earned.num(p["remaining_at_least"]), earned.num(p["possibly_used"])))
                    print("     PERSONAL    record %s: %s%s  %s to %s  (%s)" % (
                        p["record"], p["state"], " - " + "; ".join(p["reasons"]) if p["reasons"] else "", p["effective_from"], p["expires_on"],
                        "confirmed by %s on %s" % (p["confirmed_by"], p["confirmed_on"]) if p["confirmed_by"] else "not confirmed by the owner"))
                    print("                 allowance %s %s; used %s (confirmed); %s" % (earned.num(p["allowance"]), p["unit"], earned.num(p["used"]), left))
        if "periods_ending" in o:
            print("\nPERIODS ENDING through %s (%d)" % (args.until, len(o["periods_ending"])))
            for c in o["periods_ending"]:
                print("   " + _credit_event(c))
        print("\nFLAGS (%d)" % len(o["flags"]))
        for f in o["flags"]:
            print("   [%s] %s %s: %s" % (f["severity"], f["code"], f["subject"], f["detail"]))
        print("\nPUBLISHED and ALLOWANCE are the card's terms. Only PERSONAL says anything about this person's own balance, "
              "and only from records the owner confirmed.")
    _emit(args, obj, text)
    return 0


def cmd_cards(args):
    store = Store.load(_root(args))
    held = None
    if args.profile:
        res = evaluate(store, args.profile, _today(args))
        held = {e["id"] for e in store.entities.values() if e["kind"] == "card" and res.have(e["id"]) != "NOT_AVAILABLE"}
    obj = {"as_of": _today(args), "profile": args.profile, "architecture": cards.architecture(store, held),
           "matrix": cards.matrix(store, _today(args), args.profile)}

    def text(o):
        print("CARD ARCHITECTURE (descriptive only; no role confers a benefit)")
        for c in o["architecture"]:
            print("  %s  [%s]" % (c["name"], c["card"]))
            for role in ("issuer", "program_manager", "capital_provider", "cobrand_partner", "network", "network_tier"):
                print("      %-17s %s" % (role, c[role]))
            fee = c["annual_fee_usd"]
            print("      %-17s %s" % ("annual_fee_usd", "(not recorded)" if fee is None else ("%g" % fee)))
            print("      %-17s %s" % ("sources", ", ".join(c["sources"]) or "(none)"))
        who = " held by %s" % o["profile"] if o["profile"] else ""
        print("\nBENEFIT APPLICABILITY%s, as of %s" % (who, o["as_of"]))
        last = None
        for m in o["matrix"]:
            if m["card"] != last:
                print("  %s  (network tier: %s)" % (m["card_name"], m["network_tier"] or "not recorded"))
                last = m["card"]
            extra = "   -> for %s: %s" % (o["profile"], m["holder_status"]) if "holder_status" in m else ""
            print("      %-14s %-16s %s%s" % (m["standing"], m["basis"], m["benefit_name"], extra))
            if m["detail"]:
                print("      %-14s %s" % ("", m["detail"]))
        if not o["matrix"]:
            print("  (no card benefits on record%s)" % who)
        print("\nCONFIRMED is the only standing that gives the holder the benefit. UNPROVEN means the network tier "
              "advertises it and nothing shows it applies to this card.")
    _emit(args, obj, text)
    return 0


def cmd_tables(args):
    root = _root(args)
    if args.action == "export":
        for name in tables.export(root, args.dir):
            print("wrote %s/%s" % (args.dir, name))
        return 0
    if args.action == "status":
        st = tables.status(root, args.dir)
        if not st["exists"]:
            print("no tables exported yet (run: python3 -m prices tables export)")
            return 1
        print("out of date with the store: %s" % (", ".join(st["stale"]) or "no"))
        print("unimported edits:           %s" % (", ".join(st["edited"]) or "no"))
        return 1 if st["stale"] or st["edited"] else 0
    if not args.author or not args.date:
        print("plan and import need --author and --date YYYY-MM-DD")
        return 2
    dry = args.action == "plan" or args.dry_run
    out = tables.import_tables(root, args.dir, args.author, args.date, dry_run=dry)
    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
        return 0 if out["ok"] else 2
    if not out["ok"]:
        print("REJECTED  (no record was changed)")
        for e in out["errors"]:
            print("  " + e)
        return 2
    if not out["changesets"]:
        print("NOTHING TO DO  (tables match the store)")
        return 0
    print("%s  %d changeset(s)" % ("PLAN (nothing written)" if dry else "IMPORTED", len(out["changesets"])))
    for cs, origin in zip(out["changesets"], out["origins"]):
        print("  %-18s %-44s %s" % (cs["op"], origin, cs["id"]))
    if not dry:
        print("  DOWNSTREAM REVIEW NEEDED: %s" % ("yes" if out.get("review_needed") else "no"))
        print("  %s/ refreshed" % args.dir)
        if any(cs["op"] == "add_candidate" for cs in out["changesets"]):
            print("  New benefit rows are CANDIDATES. They establish nothing until a reviewer promotes them.")
    return 0


def cmd_novelty(args):
    store = Store.load(_root(args))
    with open(args.candidate, encoding="utf-8") as f:
        c = json.load(f)
    c = c.get("data", {}).get("candidate", c)
    print(json.dumps(discovery.novelty(store, c), indent=2, sort_keys=True))
    return 0


def cmd_goal(args):
    store = Store.load(_root(args))
    obj = goals.run_goal(store, args.profile, args.text, _today(args), tags=args.tag or None, limit=args.limit)

    def text(o):
        print("GOAL: %s" % o["goal"])
        print("tags: %s   profile: %s   as-of: %s%s" % (", ".join(o["tags"]) or "(none)", o["profile"], o["as_of"],
                                                       "   [SYNTHETIC DATA]" if o["synthetic"] else ""))

        def show(p):
            print("  * %s  [%s]" % (p["name"], p["status"]))
            if p.get("steps") or p.get("unknowns"):
                print("      needs: " + _steps(p))
            for line in p.get("chain", []):
                print("      " + line)
            eco = p.get("economics") or {}
            for k in sorted(eco):
                print("      %s: %s" % (k, ", ".join(eco[k]) if isinstance(eco[k], list) else eco[k]))
            for x in p.get("transfers", []):
                print("      transfer: " + x)
            for x in p.get("notes", []):
                print("      note: " + x)
            for x in p.get("restrictions", []):
                print("      restriction: " + x)
            for x in p.get("open_questions", []):
                print("      open question: " + x)
            if p.get("stale_rules"):
                print("      STALE RULES (re-verify before relying): " + ", ".join(p["stale_rules"]))
            if p.get("evidence"):
                print("      evidence: " + ", ".join(p["evidence"]))
            for t in p.get("research_tasks", []):
                print("      research: " + t)
        for title, key in (("1. ESTABLISHED CAPABILITIES", "established"), ("2. CONDITIONAL PATHWAYS (action required)", "conditional"),
                           ("3. PLAUSIBLE - WORTH RESEARCHING", "research")):
            print("\n%s (%d)" % (title, len(o[key])))
            for p in o[key]:
                show(p)
        for title, key in (("4. CURRENT VERIFIED PROMOTIONS", "promotions"), ("5. ACTUALLY AVAILABLE OPTIONS", "available")):
            print("\n%s (%d)" % (title, len(o[key])))
            for x in o[key]:
                print("  * %s (checked %s, valid to %s) %s" % (x["summary"], x["checked_on"], x["valid_to"], x["url"]))
        print()
        for n in o["notes"]:
            print("NOTE: " + n)
    _emit(args, obj, text)
    return 0


def cmd_audit(args):
    for e in read_audit(_root(args))[-args.last:]:
        print("%s  %-9s %-22s %-28s by %s%s" % (e.get("date"), e.get("result"), e.get("op"), e.get("changeset"), e.get("author"),
                                                 "  REVIEW" if e.get("review_needed") else ""))
    return 0


def cmd_export(args):
    root = _root(args)
    out = os.path.abspath(args.out)
    skip_dirs = {".git", "__pycache__", "dist", ".pytest_cache"}
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in skip_dirs)
            for name in sorted(names):
                full = os.path.join(dirpath, name)
                if os.path.abspath(full) == out or name.endswith((".pyc", ".tmp")):
                    continue
                z.write(full, os.path.join("prices", os.path.relpath(full, root)))
                n += 1
    print("exported %d files to %s" % (n, out))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="prices", description="PRICES - Points, Rewards, Incentives, Cards & Elite Status")
    ap.add_argument("--root", default=".", help="project root (directory containing data/ and profiles/)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd")

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.set_defaults(fn=fn)
        return p

    add("lint", cmd_lint, "validate every record; exit 1 on any error")
    for name, fn, h in (("status", cmd_status, "four-category report for a profile"),
                        ("explain", cmd_explain, "derivation chain for one entity"),
                        ("timeline", cmd_timeline, "upcoming changes (expiries, stale rules)"),
                        ("review", cmd_review, "what changes between two dates, and what depends on it"),
                        ("discover", cmd_discover, "emit discovery research tasks"),
                        ("goal", cmd_goal, "pathways for an objective")):
        p = add(name, fn, h)
        p.add_argument("--profile", required=True)
        p.add_argument("--as-of", dest="as_of", help="evaluation date YYYY-MM-DD (default today)")
        if name == "explain":
            p.add_argument("entity")
            p.add_argument("--candidates", action="store_true", help="also consider unpromoted candidates (never establishes anything)")
        if name == "timeline":
            p.add_argument("--until", required=True)
        if name == "review":
            p.add_argument("--from", dest="date_from", required=True)
            p.add_argument("--to", dest="date_to", required=True)
        if name == "discover":
            p.add_argument("mode", choices=["forward", "backward", "bridge", "exploratory", "applicability", "coverage"])
            p.add_argument("--target")
            p.add_argument("--budget", type=int, default=0, help="max tasks to emit (0 = all)")
            p.add_argument("--max-age", type=int, default=180, help="days before a coverage cell is stale")
        if name == "goal":
            p.add_argument("text")
            p.add_argument("--tag", action="append", help="explicit goal tag (repeatable); overrides keyword matching")
            p.add_argument("--limit", type=int, default=5)
    p = add("earned", cmd_earned, "earned benefits per person, account and qualifying year: public rule, achievement, entitlement")
    p.add_argument("--profile", required=True)
    p.add_argument("--as-of", dest="as_of", help="evaluation date YYYY-MM-DD (default today)")
    p.add_argument("--account", help="only this account (holding id)")
    p.add_argument("--cycle", help="only this qualifying year, e.g. 2026")
    p.add_argument("--detail", action="store_true", help="also list every reading, use and source behind each line")
    p = add("credits", cmd_credits, "recurring card credits: published terms, the allowance period for a date, and what is recorded for a person")
    p.add_argument("--profile", help="show the credits on this person's card accounts (without it: published terms only)")
    p.add_argument("--as-of", dest="as_of", help="evaluation date YYYY-MM-DD (default today)")
    p.add_argument("--card", help="only this card (entity id)")
    p.add_argument("--until", help="with --profile: also list allowance periods ending up to this date")
    p.add_argument("--candidates", action="store_true", help="also show credit terms on candidates awaiting review (never established)")
    p = add("earnings", cmd_earnings, "points for a purchase, from published earning rates; says so when it cannot be calculated")
    p.add_argument("--profile", required=True)
    p.add_argument("--as-of", dest="as_of", help="evaluation date YYYY-MM-DD (default today)")
    p.add_argument("--category", required=True, help="a spend category from vocab.json spend_categories")
    p.add_argument("--amount", required=True, type=float, help="US dollars")
    p.add_argument("--card", help="only this card (entity id)")
    p = add("convert", cmd_convert, "points after a transfer, from recorded ratios; says so when no ratio is recorded")
    p.add_argument("--profile", required=True)
    p.add_argument("--as-of", dest="as_of", help="evaluation date YYYY-MM-DD (default today)")
    p.add_argument("--from", dest="source", required=True, help="currency entity transferred from")
    p.add_argument("--amount", required=True, type=float)
    p.add_argument("--to", help="only this destination currency")
    p = add("cards", cmd_cards, "card roles and which benefits are confirmed, excluded or unproven per card")
    p.add_argument("--profile", help="only cards this person holds, with the benefit's status for them")
    p.add_argument("--as-of", dest="as_of", help="evaluation date YYYY-MM-DD (default today)")
    p = add("tables", cmd_tables, "CSV tables: export from the store, or compile edits into changesets")
    p.add_argument("action", choices=["export", "status", "plan", "import"])
    p.add_argument("--dir", default="tables", help="tables directory, relative to --root")
    p.add_argument("--author")
    p.add_argument("--date", help="changeset date YYYY-MM-DD")
    p.add_argument("--dry-run", action="store_true")
    p = add("apply", cmd_apply, "validate and apply a changeset file")
    p.add_argument("changeset")
    p.add_argument("--dry-run", action="store_true")
    p = add("novelty", cmd_novelty, "check a candidate file against known relationships")
    p.add_argument("candidate")
    p = add("audit", cmd_audit, "show recent audit log entries")
    p.add_argument("--last", type=int, default=20)
    p = add("export", cmd_export, "write a portable zip of the whole project")
    p.add_argument("--out", default="prices-export.zip")

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 2
    try:
        return args.fn(args)
    except KeyError as e:
        print("error: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
