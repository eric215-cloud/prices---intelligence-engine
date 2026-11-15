"""Mutation check for the earned-benefit guarantees.

    python3 scripts/mutation_check_earned.py

Each entry below breaks ONE guarantee in a scratch copy of the project (never in this checkout) and
runs the earned-benefit tests against the broken copy. Every line must say "caught": a "MISSED" line
means a guarantee could be broken without any test noticing. Exit code 0 only if all are caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUTS = [
 ("engine: legacy metric ignores as_of again", "prices/engine.py", 'if m is not None and to_date(m["as_of"]) > self.as_of:', 'if False:'),
 ("threshold reached => possession", "prices/earned.py", 'facts.append(("have:" + out_ent, (C, U) if not toks else (U,), toks | steps, rule["id"], ["can_get:" + out_ent]))', 'facts.append(("have:" + out_ent, LEVELS, frozenset(), rule["id"], ["can_get:" + out_ent]))'),
 ("later reading reaches back", "prices/earned.py", 'usable = [r for r in conf if known_from(r, end) is not None and known_from(r, end) <= as_of]', 'usable = [r for r in conf if known_from(r, end) is not None]'),
 ("undated reading counted from cycle start", "prices/earned.py", '    return None if c is None else min(cycle_end, c)', '    return datetime.date(cycle_end.year, 1, 1)'),
 ("personal expiry ignored", "prices/earned.py", '    if hi is not None and as_of > hi:\n        return EXPIRED, [], cr', '    if False:\n        return EXPIRED, [], cr'),
 ("entitlement active before its start", "prices/earned.py", '    if as_of < (lo or start):', '    if as_of < start:'),
 ("unknown expiry persists silently", "prices/earned.py", '        if hi is None and ended is None and as_of > conf:', '        if False:'),
 ("unknown start assumed", "prices/earned.py", '        if lo is None and as_of < conf:', '        if False:'),
 ("later use counted earlier", "prices/earned.py", '            used += u["amount"] if d <= as_of else 0', '            used += u["amount"]'),
 ("unconfirmed use counted as used", "prices/earned.py", '        elif d is None or d <= as_of:\n            maybe += u["amount"]', '        elif d is None or d <= as_of:\n            used += u["amount"]'),
 ("unconfirmed entitlement established", "prices/earned.py", '    if inst["state"] != "confirmed":\n        why.append("not confirmed by the owner")', '    if False:\n        why.append("x")'),
 ("unconfirmed reading counted", "prices/earned.py", '    conf = [r for r in live if r["state"] == "confirmed"]', '    conf = live'),
 ("offer end revokes existing instance", "prices/earned.py", '        if st == ACTIVE:\n            facts.append(', '        if st == ACTIVE and covers:\n            facts.append('),
 ("maintainer can confirm", "prices/changes.py", '        a = _attested(cs, by=prof.meta["owner"])\n        _need(a["on"] <= cs["date"]', '        a = _attested(cs)\n        _need(a["on"] <= cs["date"]'),
 ("duplicate reading accepted", "prices/changes.py", '    _need(not same, "DUPLICATE_READING"', '    _need(True, "DUPLICATE_READING"'),
 ("earns rule evaluated as ordinary rule", "prices/engine.py", 'PERSONAL_KINDS = ("earns",)', 'PERSONAL_KINDS = ()'),
 ("cycles merged: any cycle's readings count", "prices/earned.py", 'mine = sorted((e for e in insts if e["rule"] == rule["id"] and e["cycle"] == label)', 'mine = sorted((e for e in insts if e["rule"] == rule["id"])'),
]
bad = 0
TMP = tempfile.mkdtemp(prefix="prices-mutation-")
for name, path, a, b in MUTS:
    work = os.path.join(TMP, "copy")
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(SRC, work, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    p = os.path.join(work, path)
    with open(p, encoding="utf-8") as f:
        s = f.read()
    if s.count(a) != 1:
        print("STALE    %-45s the line this mutation edits has changed; update this script" % name)
        bad += 1
        continue
    with open(p, "w", encoding="utf-8") as f:
        f.write(s.replace(a, b))
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_[lm]*.py"], cwd=work, capture_output=True, text=True)
    tail = r.stderr.strip().splitlines()[-1]
    caught = r.returncode != 0
    bad += 0 if caught else 1
    print("%-8s %-45s %s" % ("caught" if caught else "MISSED", name, tail))
shutil.rmtree(TMP)
print("%d of %d mutations caught" % (len(MUTS) - bad, len(MUTS)))
sys.exit(1 if bad else 0)
