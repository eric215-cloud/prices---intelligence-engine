"""Mutation check for the foundation safety correction (condition review and protected history).

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
BLOCK = '    return [(cls, text) for _kind, text, cls in classes(rule) if cls in BLOCKING]'
# Two of these are also stopped by a second line of defence (lint refuses a record by a non-reviewer, and a rule whose
# valid_to is before its valid_from). The tests name the first line's own message so that losing it is still noticed.
MUTS = [
 ("an unchecked condition no longer blocks", C, BLOCK, BLOCK.replace('cls in BLOCKING', 'cls != "unchecked" and cls in BLOCKING')),
 ("an eligibility question no longer blocks", C, BLOCK, BLOCK.replace('cls in BLOCKING', 'cls != "affects_eligibility" and cls in BLOCKING')),
 ("a missing class is read as approval", C, BLOCK, BLOCK.replace('cls in BLOCKING', 'cls is not None and cls in BLOCKING')),
 ("a rule edited after review keeps its review", C, '    if any(key not in now for key in recorded):\n        recorded = {}', '    if False:\n        recorded = {}'),
 ("'enforced' accepted with nothing that enforces", C, '            if by not in enforcers(rule, governed):', '            if False:'),
 ("a partial classification is accepted", C, '        if (kind, text) not in seen:\n            out.append("no class given', '        if False:\n            out.append("no class given'),
 ("a class for a text the rule does not have is accepted", C, '        if (kind, text) not in want:', '        if False:'),
 ("the engine ignores the blocking conditions", E, '        blocked = condition_tokens(rule)', '        blocked = frozenset()'),
 ("a blocked rule still establishes", E, '            levels, toks = (P, U), toks | blocked', '            levels, toks = levels, toks'),
 ("a transfer is calculated despite an unchecked condition", "prices/calc.py", '        elif blockers(rule):\n            row.update(result="NOT_CALCULATED", reason="who may', '        elif False:\n            row.update(result="NOT_CALCULATED", reason="who may'),
 ("a threshold reached counts despite a condition", "prices/earned.py", '    if blocked and elig in (ACTIVATION_REQUIRED, EARNED_NOT_CONFIRMED):', '    if False:'),
 ("promotion without classes is accepted", G, '    if texts(proposed) or items is not None:', '    if items is not None:'),
 ("anyone may classify", G, '    a = _attested(cs)\n    _reviewer(store, a)\n    items = _data(cs, "items", list)', '    a = _attested(cs)\n    items = _data(cs, "items", list)'),
 ("classification needs no well-formed answer", G, '    issues = review_issues(r, items, r["id"] in governed(store))\n    _need(not issues, "BAD_CLASSIFICATION", "; ".join(issues))', '    issues = []'),
 ("a non-reviewer's record passes the checks", "prices/lint.py", '            if reviewers and review.get("by") not in reviewers:', '            if False:'),
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
 ("overlapping versions of a relationship are accepted", "prices/lint.py", 'def windows_overlap(a, b):\n', 'def windows_overlap(a, b):\n    return False\n'),
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
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_[rt]*.py"], cwd=work, capture_output=True, text=True)
    tail = (r.stderr.strip().splitlines() or ["no output"])[-1]
    caught = r.returncode != 0
    bad += 0 if caught else 1
    print("%-8s %-55s %s" % ("caught" if caught else "MISSED", name, tail))
shutil.rmtree(TMP, ignore_errors=True)
print("\n%d mutations, %d not caught" % (len(MUTS), bad))
sys.exit(1 if bad else 0)
