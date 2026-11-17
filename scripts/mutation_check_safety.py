"""Mutation check for the foundation safety correction and the consolidated repair (2026-11-17).

    python3 scripts/mutation_check_safety.py

Each entry below breaks ONE guarantee in a scratch copy of the project (never in this checkout) and runs the
safety tests against the broken copy. Every line must say "caught": a "MISSED" line means a guarantee could be
broken without any test noticing. Exit code 0 only if all are caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C, E, G = "prices/conditions.py", "prices/engine.py", "prices/changes.py"
BLOCK = '        if cls in BLOCKING:\n            out.append((cls, text))'
CALC, CRED, EARN, LINT, ELEC = "prices/calc.py", "prices/credits.py", "prices/earned.py", "prices/lint.py", "prices/elections.py"
# Some of these are also stopped by a second line of defence (lint refuses a record by a non-reviewer; a rule whose
# valid_to is before its valid_from is refused by lint). The tests name the first line's own message so that losing it
# is still noticed.
MUTS = [
 # ---- condition review (foundation safety correction)
 ("an unchecked condition no longer blocks", C, BLOCK, BLOCK.replace('cls in BLOCKING', 'cls != "unchecked" and cls in BLOCKING')),
 ("an eligibility question no longer blocks", C, BLOCK, BLOCK.replace('cls in BLOCKING', 'cls != "affects_eligibility" and cls in BLOCKING')),
 ("a missing class is read as approval", C, BLOCK, BLOCK.replace('cls in BLOCKING', 'cls is not None and cls in BLOCKING')),
 ("a rule edited after review keeps its review", C, '    return any(key not in now for key in _recorded(rule))', '    return False'),
 ("a partial classification is accepted", C, '        if (kind, text) not in seen:\n            out.append("no class given', '        if False:\n            out.append("no class given'),
 ("a class for a text the rule does not have is accepted", C, '        if (kind, text) not in want:', '        if False:'),
 ("the engine ignores the blocking conditions", E, '        blocked = condition_tokens(rule, ctx)', '        blocked = frozenset()'),
 ("a blocked rule still establishes", E, '            levels, toks = (P, U), toks | blocked', '            levels, toks = levels, toks'),
 ("a threshold reached counts despite a condition", EARN, '    if blocked and elig in (ACTIVATION_REQUIRED, EARNED_NOT_CONFIRMED):', '    if False:'),
 ("promotion without classes is accepted", G, '    if texts(proposed) or items is not None:', '    if items is not None:'),
 ("anyone may classify", G, '    a = _attested(cs)\n    _reviewer(store, a)\n    items = (cs.get("data") or {}).get("items")', '    a = _attested(cs)\n    items = (cs.get("data") or {}).get("items")'),
 ("classification needs no well-formed answer", G, '    issues = review_issues(r, items, context(store))', '    issues = []'),
 ("a non-reviewer's record passes the checks", LINT, '            if reviewers and review.get("by") not in reviewers:', '            if False:'),
 # ---- 1. enforced means enforced on every path (repair)
 ("an OR counts as enforcing when one alternative does", C, 'and bool(cond["any"]) and all(implies(c, claim) for c in cond["any"])', 'and any(implies(c, claim) for c in cond["any"])'),
 ("any leaf counts as the claimed predicate", C, '        return "holds" in cond and cond["holds"] == claim["holds"]', '        return True'),
 ("a lower threshold enforces a higher one", C, 'and _num(g) and g >= claim["gte"]', 'and _num(g)'),
 ("'enforced' is accepted at the door without proof", C, '            out += ["%r is marked enforced, but %s" % (text, why) for why in item_issues(rule, item, ctx)]', '            pass'),
 ("the engine trusts 'enforced' without re-checking it", C, '        elif cls == "enforced" and item_issues(rule, items[(kind, text)], ctx):', '        elif False:'),
 ("the old 'when:<id>' form is read as a claim", C, '    claims = [by] if isinstance(by, dict) else by',
  '    claims = [{"holds": by[5:]}] if isinstance(by, str) and by.startswith("when:") else [by] if isinstance(by, dict) else by'),
 ("a claimed end date need not be the rule's", C, 'ok = have is not None and (have <= claim[key] if key == "valid_to" else have >= claim[key])', 'ok = True'),
 ("a claimed threshold need not be the one the text states", C, '            if _num(n) and float(n) not in stated:', '            if False:'),
 ("an election is claimed for a rule no election governs", C, 'return [] if gov is not None and rule.get("id") in gov else', 'return [] if True else'),
 # ---- 2. unknown is not absent (repair)
 ("a missing record counts as proof of absence", E, '            proven = ent in self.absent and a not in self.best[P]', '            proven = a not in self.best[P]'),
 ("a contradicted absence is still relied on", E, '        if x["entity"] in by_entity:\n            r.flag("CONFLICTING_HOLDINGS"', '        if False:\n            r.flag("CONFLICTING_HOLDINGS"'),
 ("an unattested absence is relied on", E, '        if not in_effect(x, as_of) or not x.get("confirmed_by"):', '        if not in_effect(x, as_of):'),
 ("anyone may record an absence", G, '    a = _attested(cs, by=prof.meta["owner"])\n    x["confirmed_by"]', '    a = cs.get("attestation") or {"by": "?", "on": cs["date"]}\n    x["confirmed_by"]'),
 # ---- 3. one question about the rule in use (repair)
 ("an earning rate is used because another rule gives the benefit", CALC, '            elif res.rule_applies(rule["id"])["status"] != ESTABLISHED:', '            elif res.have(rule["output"]) != ESTABLISHED:'),
 ("a transfer is calculated whatever its own condition says", CALC, '        elif ap["status"] != ESTABLISHED:', '        elif False:'),
 ("a credit applies because another rule gives the benefit", CRED, '            toks = res.rule_applies(rid)', '            toks = dict(res.tokens("have:" + rule["output"]), status=res.status("have:" + rule["output"]))'),
 ("rule_applies drops the rule's own blocking reasons", E, '                out = self._describe(got[0] | ru["tokens"])', '                out = self._describe(got[0])'),
 # ---- 4. a window is not an action (repair)
 ("a date window stands in for an action", C, '        if not records:\n            out.append("the text names an action', '        if False:\n            out.append("the text names an action'),
 ("any holding counts as the action", C, 'ents.get(c["holds"], {}).get("kind") == "action"', 'True'),
 ("activation is claimed on an automatic earned benefit", C, 'isinstance(e, dict) and e.get("activation") == "required"', 'isinstance(e, dict)'),
 # ---- 5. personal history (repair)
 ("ending a holding erases its past", E, '        return h.get("ended_from") or ("confirmed" if h.get("confirmed_by") else "unconfirmed")', '        return None'),
 ("an ended holding is promoted to confirmed", E, '        return h.get("ended_from") or ("confirmed" if h.get("confirmed_by") else "unconfirmed")', '        return "confirmed"'),
 ("a withdrawn holding answers for its old dates", E, '    if h["state"] == "withdrawn" or not in_effect(h, day):', '    if not in_effect(h, day):'),
 ("a holding may be ended before it began", G, '    _need(not h.get("valid_from") or ended >= h["valid_from"], "BAD_DATES", "ended_on', '    _need(True, "BAD_DATES", "ended_on'),
 ("credits forget a card ended later", CRED, '                if p["end"] <= until and holding_state(h, p["end"]) is not None:', '                if p["end"] <= until and h["state"] != "ended" and in_effect(h, p["end"]):'),
 # ---- 6. restriction changes (repair) and protected history (correction)
 ("a first restriction on a past rule is an ordinary revision", G, '            if set(v or []) != set(rule.get(k) or []) and answered_before(rule, today):', '            if False:'),
 ("a rule with no start date counts as not yet started", G, '    return rule.get("valid_from") is None or rule["valid_from"] < today', '    return rule.get("valid_from") is not None and rule["valid_from"] < today'),
 ("a stale review blocks nothing once its texts are gone", C, '    out = []\n    if stale(rule):\n        gone', '    out = []\n    if False:\n        gone'),
 ("a revision in place rewrites history", G, '    if rewrites:\n        _correction(cs, "%s of rule %s"', '    if False:\n        _correction(cs, "%s of rule %s"'),
 ("a term already recorded may be replaced", G, '        elif rule.get(k) in (None, [], ""):\n            continue', '        elif True:\n            continue'),
 ("a date already passed may be moved", G, '            if (v is None or v >= today) and (old is None or old >= today):', '            if True:'),
 ("a one-word excuse counts as a declared correction", G, 'isinstance(why, str) and len(why.strip()) >= 10', 'isinstance(why, str)'),
 ("retirement erases the answers the rule gave", E, '    if v["status"] == "retired" and v.get("retired_from") and rule.get("valid_to"):', '    if False:'),
 ("a retired rule is trusted more than it was", E, '        return v["retired_from"]', '        return "verified"'),
 ("a rule may be withdrawn from every date undeclared", G, '        _correction(cs, "rule %s on every date" % r["id"])', '        pass'),
 ("a rule may be retired as ended before it began", G, '    _need(not r.get("valid_from") or ended >= r["valid_from"], "BAD_DATES",', '    _need(True, "BAD_DATES",'),
 ("a second rule may answer for an ended rule's dates", G, '        _need(standing(r) == "retired" or signature(r) != sig or not windows_overlap(r, c["proposed_rule"]),',
  '        _need(r["verification"]["status"] == "retired" or signature(r) != sig or not windows_overlap(r, c["proposed_rule"]),'),
 ("overlapping versions of a relationship are accepted", LINT, 'def windows_overlap(a, b):\n', 'def windows_overlap(a, b):\n    return False\n'),
]
bad = 0
TMP = tempfile.mkdtemp(prefix="prices-mutation-safety-")
for name, path, a, b in MUTS:
    work = os.path.join(TMP, "copy")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(SRC, work, ignore=shutil.ignore_patterns(".git", "__pycache__", "dist"))
    p = os.path.join(work, path)
    with open(p, encoding="utf-8") as f:
        s = f.read()
    if s.count(a) != 1:
        print("STALE    %-55s the line this mutation edits has changed; update this script" % name)
        bad += 1
        continue
    with open(p, "w", encoding="utf-8") as f:
        f.write(s.replace(a, b))
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_[rtu]*.py"], cwd=work, capture_output=True, text=True)
    tail = (r.stderr.strip().splitlines() or ["no output"])[-1]
    caught = r.returncode != 0
    bad += 0 if caught else 1
    print("%-8s %-55s %s" % ("caught" if caught else "MISSED", name, tail))
shutil.rmtree(TMP, ignore_errors=True)
print("\n%d mutations, %d not caught" % (len(MUTS), bad))
sys.exit(1 if bad else 0)
