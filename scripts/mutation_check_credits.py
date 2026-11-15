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
 ("missing opening date replaced by a guess", "prices/credits.py", 'opened = to_date(holding.get("opened_on"))', 'opened = to_date(holding.get("opened_on") or holding.get("valid_from"))'),
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
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_[op]*.py"], cwd=work, capture_output=True, text=True)
    tail = r.stderr.strip().splitlines()[-1]
    caught = r.returncode != 0
    bad += 0 if caught else 1
    print("%-8s %-45s %s" % ("caught" if caught else "MISSED", name, tail))
shutil.rmtree(TMP)
print("%d of %d mutations caught" % (len(MUTS) - bad, len(MUTS)))
sys.exit(1 if bad else 0)
