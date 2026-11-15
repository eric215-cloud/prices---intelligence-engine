"""Mutation check for the cardholder-election guarantees (ENG-02, and the ENG-02B correction).

    python3 scripts/mutation_check_elections.py

Each entry below breaks ONE guarantee in a scratch copy of the project (never in this checkout) and
runs the election tests against the broken copy. Every line must say "caught": a "MISSED" line
means a guarantee could be broken without any test noticing. Exit code 0 only if all are caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUTS = [
 ("rules are no longer gated by elections", "prices/elections.py", 'return when if opt is None else {"all": [when, {"holds": opt}]}', 'return when'),
 ("no election recorded is taken as elected", "prices/elections.py", 'tok = frozenset([("unknown", "election %s: %s" % (group, d["reason"]))])\n            for L in (P, U):', 'tok = frozenset()\n            for L in LEVELS:'),
 ("contradictory elections ignored", "prices/elections.py", '    if len(chosen) > 1:', '    if False:'),
 ("transition at Jan 1 2027, not the anniversary", "prices/elections.py", '    lo, hi = w\n    if day < lo:', '    lo = hi = d0\n    if day < lo:'),
 ("February 29 decided by convention", "prices/elections.py", '        return datetime.date(year, 2, 28), datetime.date(year, 3, 1)', '        return datetime.date(year, 2, 28), datetime.date(year, 2, 28)'),
 ("unconfirmed election accepted", "prices/elections.py", '        if h["state"] != "confirmed" and h["state"] != "ended":', '        if False:'),
 ("published terms not enforced", "prices/elections.py", '        if ok is False:\n            return _unsure(', '        if False:\n            return _unsure('),
 ("default ignores the opening-date cutoff", "prices/elections.py", 'out.append(_all([opened_before(card_holding, d0), before_anniversary(card_holding, d0, day, _cycle(option))]))', 'out.append(_all([before_anniversary(card_holding, d0, day, _cycle(option))]))'),
 ("undated election counted before confirmation", "prices/elections.py", 'return "in" if seen is not None and day >= seen else "maybe"', 'return "in"'),
 ("two card accounts ignored", "prices/elections.py", '    if len(cards) > 1:', '    if False:'),
 ("election holdings counted one by one", "prices/engine.py", '        if store.entities.get(h["entity"], {}).get("kind") == "election":\n            continue', '        if False:\n            continue'),
 ("withdrawn election still counted", "prices/elections.py", 'picks = [h for h in prof.holdings.values() if h["entity"] in ids and h["state"] != "withdrawn"]', 'picks = [h for h in prof.holdings.values() if h["entity"] in ids]'),
 ("election definitions revisable without a reviewer", "prices/changes.py", '            _reviewer(store, _attested(cs))\n    _add_evidence(store, cs)', '            pass\n    _add_evidence(store, cs)'),
 # ---- ENG-02B: the Bilt Legacy Election is one linked arrangement
 ("linked options ignore the election they follow", "prices/elections.py", '        st, d = linked.get(up, (None, None))', '        st, d = None, None'),
 ("a housing choice outlives the transition anniversary", "prices/elections.py", '    return False if not out else _all(out)', '    return False if not out else True'),
 ("annual benefits electable on their own", "prices/elections.py", '        if "choose_before_anniversary" in ids[h["entity"]]["election"]:\n            mine.append((h, p))', '        if True:\n            mine.append((h, p))'),
 ("a Legacy Election does not lock the housing option", "prices/elections.py", '        if other and period is not False:', '        if False:'),
 ("2027 accounts are not refreshed from opening", "prices/elections.py", '        out.append(None if ob is None else not ob)', '        out.append(False)'),
 ("refreshed arrangement assumed when nothing is recorded", "prices/elections.py", '        out.append(None if ob is None else not ob)', '        out.append(True)'),
 ("a permanent exit can be reversed", "prices/elections.py", '        if left:\n            checks.append(False)', '        if False:\n            checks.append(False)'),
 ("$600 starts at once after leaving the legacy arrangement", "prices/elections.py", '        if st == "est" and o["election"].get("after_exit_from_anniversary") and d.get("exit") is not None:', '        if False:'),
 ("anniversary taken as the opening date", "prices/elections.py", '    bases = [opened + datetime.timedelta(days=n) for n in range(1, cycle_days + 1)] or [opened]', '    bases = [opened]'),
 ("the issuer's anniversary date is ignored", "prices/elections.py", '    if shown is not None:\n        first =', '    if False:\n        first ='),
 ("a link to a missing option passes the checks", "prices/lint.py", '                    err("UNKNOWN_REFERENCE", p, "follows %r: no election option has that id" % up)', '                    pass'),
]
bad = 0
TMP = tempfile.mkdtemp(prefix="prices-mutation-elections-")
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
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_[nq]*.py"], cwd=work, capture_output=True, text=True)
    tail = r.stderr.strip().splitlines()[-1]
    caught = r.returncode != 0
    bad += 0 if caught else 1
    print("%-8s %-45s %s" % ("caught" if caught else "MISSED", name, tail))
shutil.rmtree(TMP)
print("%d of %d mutations caught" % (len(MUTS) - bad, len(MUTS)))
sys.exit(1 if bad else 0)
