"""Command line interface.  Run:  python3 -m prices <command> --help"""
import argparse
import datetime
import json
import os
import sys
import zipfile

from . import changes, discovery, goals, review
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
            print("   %-10s %-8s %s%s" % (x["verification"], x["kind"], x["id"], "" if x["in_effect"] else "  (not in effect)"))
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
    _emit(args, obj, text)
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
    else:
        obj = discovery.coverage_summary(store, args.profile, d, args.max_age)
    if "tasks" in obj and args.budget:
        obj["tasks_omitted_by_budget"] = max(0, len(obj["tasks"]) - args.budget)
        obj["tasks"] = obj["tasks"][:args.budget]
    print(json.dumps(obj, indent=2, sort_keys=True))
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
            p.add_argument("mode", choices=["forward", "backward", "bridge", "exploratory", "coverage"])
            p.add_argument("--target")
            p.add_argument("--budget", type=int, default=0, help="max tasks to emit (0 = all)")
            p.add_argument("--max-age", type=int, default=180, help="days before a coverage cell is stale")
        if name == "goal":
            p.add_argument("text")
            p.add_argument("--tag", action="append", help="explicit goal tag (repeatable); overrides keyword matching")
            p.add_argument("--limit", type=int, default=5)
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
