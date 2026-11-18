"""Mutation check for the recurring-credit safeguards (ENG-01).

    python3 scripts/mutation_check_credits.py

Each entry below breaks ONE guarantee in a scratch copy of the project (never in this checkout) and
runs the recurring-credit tests against the broken copy. Every line must say "caught": a "MISSED" line
means a guarantee could be broken without any test noticing. Exit code 0 only if all are caught.
"""
import os
import shutil
import subprocess
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUTS = [
 ("published allowance reported as a personal balance", "prices/credits.py",
  'return {"state": NOT_RECORDED, "text": "nothing is recorded for this account and period; the personal balance is not known"}',
  'return {"state": "ACTIVE", "record": "assumed", "remaining": c["amount"], "used": 0, "possibly_used": 0, "established": True, "text": ""}'),
 ("missing opening date replaced by a guess", "prices/credits.py", 'cardholder\'s own account"}\n    opened = to_date(holding.get("opened_on"))', 'cardholder\'s own account"}\n    opened = to_date(holding.get("opened_on") or holding.get("valid_from"))'),   # pattern widened 2026-11-18 (DEP-01): the line now also occurs in statement_year
 ("missing opening date replaced by a guess (statement anchor)", "prices/credits.py", 'cycle anniversary_statement_year)."""\n    opened = to_date(holding.get("opened_on"))', 'cycle anniversary_statement_year)."""\n    opened = to_date(holding.get("opened_on") or holding.get("valid_from"))'),
 ("anniversary credit reset on January 1", "prices/credits.py", '    return _from_opening(opened, d, step)', '    return _from_opening(datetime.date(opened.year, 1, 1), d, step)'),
 ("February 29 anniversary decided by convention", "prices/credits.py", '    elif d < hi:\n        return {"state": UNRESOLVED, "reason": "the account was opened on February 29', '    elif False:\n        return {"state": UNRESOLVED, "reason": "the account was opened on February 29'),
 ("the two half-year periods merged", "prices/credits.py", '        h = 1 if d.month <= 6 else 2', '        h = 1'),
 ("monthly credit does not end with the month", "prices/credits.py", 'datetime.date(d.year, d.month, 1), _month_end(d.year, d.month)', 'datetime.date(d.year, d.month, 1), datetime.date(d.year, 12, 31)'),
 ("unstated per-transaction cap reported as none", "prices/credits.py", '"max_per_transaction": c.get("max_per_transaction"),', '"max_per_transaction": c.get("max_per_transaction", "none"),'),
 ("unstated rollover reported as no rollover", "prices/credits.py", '"rollover": c.get("rollover"), "rollover_max"', '"rollover": c.get("rollover", "none"), "rollover_max"'),
 ("offer expiration ignored", "prices/credits.py", '    if vt is not None and d > vt:\n        return "ENDED"', '    if False:\n        return "ENDED"'),
 ("period not cut at the end of the offer", "prices/credits.py", '    if vt is not None and (p["end"] is None or p["end"] > vt):', '    if False:'),
 ("unconfirmed last use fixes the period", "prices/credits.py", '    if any(u["state"] != "confirmed" for u in live):', '    if False:'),
 ("no recorded use treated as available", "prices/credits.py", '    if not past:\n        return {"state": UNRESOLVED,', '    if not past:\n        return {"state": KNOWN, "label": None, "start": d, "end": None, "note":'),
 ("credit shown as applying regardless of the engine (elections bypassed)", "prices/credits.py", '            status = res.status(atom)', '            status = ESTABLISHED'),
 ("candidate terms treated as in force", "prices/credits.py", '    if include_candidates:\n        for c in store.candidates.values():', '    if True:\n        for c in store.candidates.values():'),
 ("records of other periods counted in this one", "prices/credits.py", '        mine = [e for e in recs if e["cycle"] == p["label"]]', '        mine = list(recs)[:1]'),
 ("unconfirmed use reported as an established balance", "prices/credits.py", 'out["established"] = state in ("ACTIVE", "EXHAUSTED") and out["possibly_used"] == 0', 'out["established"] = True'),
 ("period ends listed for credits that do not apply", "prices/credits.py", '                    if status != NOT_AVAILABLE:\n                        out.append(', '                    if True:\n                        out.append('),
 ("per-transaction maximum not enforced on recorded use", "prices/changes.py", '    _need(cap is None or u["amount"] <= cap, "USE_EXCEEDS_TRANSACTION_CAP",', '    _need(True, "USE_EXCEEDS_TRANSACTION_CAP",'),
 ("terms of a rule in force changeable without evidence", "prices/changes.py", '        _need(cs.get("evidence"), "EVIDENCE_REQUIRED", "changing the published terms', '        cs.setdefault("evidence", [])\n        _need(True, "EVIDENCE_REQUIRED", "changing the published terms'),
 ("a balance can be recorded against a candidate", "prices/changes.py", '    rule = store.rules.get(e.get("rule", ""))\n    recurring = is_credit_rule(rule)', '    from .credits import find as _find\n    rule = store.rules.get(e.get("rule", "")) or _find(store, e.get("rule", ""))[1]\n    recurring = is_credit_rule(rule)'),
 ("credit period records treated as earned benefits", "prices/earned.py", 'earned_recs = [e for e in prof.entitlements.values() if store.rules.get(e["rule"], {}).get("kind") != "grants"]', 'earned_recs = list(prof.entitlements.values())'),
 ("credit terms allowed on a rule that is not a card benefit", "prices/lint.py", '        elif kind_of(subject) != "card" or kind_of(target) != "benefit":\n            out.append(("BAD_CREDIT_SHAPE"', '        elif False:\n            out.append(("BAD_CREDIT_SHAPE"'),
 ("zero or negative amounts accepted", "prices/credits.py", '    if not _positive(c.get("amount")):', '    if False:'),
 # DEP-01: statement-cycle anniversary anchor
 ("a missing statement closing date is assumed (the 1st)", "prices/credits.py", '    if not holding.get("statement_closings") and holding.get("statement_closing_day") is None:\n        return {',
  '    if not holding.get("statement_closings") and holding.get("statement_closing_day") is None:\n        holding = dict(holding, statement_closing_day=1)\n    if False:\n        return {'),
 ("a closing day the month lacks is clamped to its last day", "prices/credits.py", '        if n <= _month_end(y, m).day:', '        if True:\n            return _month_end(y, m) if n > _month_end(y, m).day else datetime.date(y, m, n), "from the closing day"\n        if n <= _month_end(y, m).day:'),
 ("a closing on the anniversary itself is taken as the boundary", "prices/credits.py", '        if c <= hi:                                       # closes ON the anniversary', '        if False:                                         # closes ON the anniversary'),
 ("recorded statement dates are ignored", "prices/credits.py", '    if seen:\n        return seen[0], "recorded"', '    if False:\n        return seen[0], "recorded"'),
 ("the first year ends at the anniversary, as for the calendar cycle", "prices/credits.py", '        if c < lo:\n            y, m = _months_after(y, m, 1)\n            continue', '        if c < lo:\n            break'),
 ("later boundaries are extrapolated without a recorded closing", "prices/credits.py", '        nxt, how = closing_in(holding, y, m)\n        if nxt is None:', '        nxt, how = closing_in(holding, y, m)\n        nxt = nxt or datetime.date(y, m, end.day)\n        if nxt is None:'),
]
bad = 0
TMP = tempfile.mkdtemp(prefix="prices-mutation-credits-")
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
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_[opq]*.py"], cwd=work, capture_output=True, text=True)
    tail = r.stderr.strip().splitlines()[-1]
    caught = r.returncode != 0
    bad += 0 if caught else 1
    print("%-8s %-45s %s" % ("caught" if caught else "MISSED", name, tail))
shutil.rmtree(TMP)
print("%d of %d mutations caught" % (len(MUTS) - bad, len(MUTS)))
sys.exit(1 if bad else 0)
