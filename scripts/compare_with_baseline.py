"""Show that people and data with no earned-benefit records get byte-identical output from an older commit and from this checkout.

    python3 scripts/compare_with_baseline.py [baseline-commit]        (default: bb95d8b, the commit before ENG-02B)

The default baseline moves with each commission, so the comparison isolates what the latest work changed:
6eb9ec9 before earned benefits, cdce9e1 before elections (ENG-02), 8039477 before recurring credits (ENG-01), bb95d8b before the Bilt election correction (ENG-02B).
ENG-01 added one table, credits.csv. Wherever tables are kept (live, and in the two older fixtures) that file is new
and the tables MANIFEST.json lists it; those two files are left out of the file-set comparison and checked
separately: every such credits.csv must be the header line only.
ENG-02B corrected the six Bilt election definitions through the pipeline and moved ONE assertion in
tests/test_n_elections.py. Those are compared exactly: section 1 lists every data file that differs from the
baseline and fails unless the list is the six definitions and their audit records, and the test file must be
the baseline's file with that one assertion replaced and nothing else.

Needs git (it unpacks the baseline commit into a temp directory with `git archive`); nothing else.
Runs the same list of read-only commands with the OLD code on the OLD files and with the NEW code on
the NEW files, and compares the output byte for byte. It also checks that the live records, the
existing tests and the existing synthetic card fixture are the same files in both.
Exit 0 only if everything is identical.
"""
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = sys.argv[1] if len(sys.argv) > 1 else "bb95d8b"
DATES = ("2026-11-14", "2027-03-15", "2028-01-05")
NEW_TABLE_FILES = ("credits.csv", "MANIFEST.json")      # see the note above
ENG02B_DATA = ("data/audit/log.jsonl", "data/audit/changesets/cs-20261115-eng02b-", "data/audit/previous/cs-20261115-eng02b-",
               "data/kb/entities/election.bilt-palladium.")          # the only data paths ENG-02B may add or change
ENG02B_TEST = ("tests/test_n_elections.py",
               '''            self.assertEqual(set(got("2027-06-01").values()), {UNRESOLVED})          # this cardholder's 2027 anniversary, nothing recorded''',
               '''            # ENG-02B: the published Card Anniversary Date is counted from the first billing cycle after opening, so for an
            # account opened 2025-06-01 it falls between 2027-06-02 and 2027-08-02 (it is not 2027-06-01, as ENG-02 assumed).
            self.assertEqual(set(got("2027-08-02").values()), {UNRESOLVED})          # this cardholder's 2027 anniversary has come, nothing recorded''')
EMPTY_CREDITS = ("tables/credits.csv", "fixtures/synthetic-cards/tables/credits.csv", "fixtures/synthetic-earned/tables/credits.csv",
                 "fixtures/synthetic-cards-input/credits.csv")
UNCHANGED = ("data", "profiles", "tables", "fixtures/synthetic-cards", "fixtures/synthetic-earned",
             "tests/test_l_earned.py", "tests/test_m_earned_pipeline.py", "tests/test_n_elections.py", "fixtures/synthetic-cards-input", "fixtures/synthetic_cards.py",
             "tests/util.py", "tests/test_a_conditional.py", "tests/test_b_temporal.py", "tests/test_c_i_evidence_cycles.py",
             "tests/test_d_h_discovery_goal.py", "tests/test_e_maintenance.py", "tests/test_j_relational.py", "tests/test_k_tables.py",
             "tests/test_live_data.py", "successor_test")


def commands(tree):
    out = [("lint",), ("--json", "cards", "--as-of", DATES[0]), ("tables", "status")]   # the audit log is checked as append-only below
    for p in sorted(os.listdir(os.path.join(tree, "profiles"))):
        for d in DATES:
            out += [("--json", "status", "--profile", p, "--as-of", d), ("status", "--profile", p, "--as-of", d)]
        out += [("timeline", "--profile", p, "--as-of", DATES[0], "--until", "2028-12-31"),
                ("--json", "review", "--profile", p, "--from", DATES[0], "--to", DATES[2]),
                ("--json", "cards", "--profile", p, "--as-of", DATES[0]),
                ("--json", "goal", "fly business class to Japan", "--profile", p, "--as-of", DATES[0]),
                ("--json", "discover", "forward", "--profile", p, "--as-of", DATES[0]),
                ("--json", "discover", "coverage", "--profile", p, "--as-of", DATES[0])]
    fx = os.path.join("fixtures", "synthetic-cards")
    for p in sorted(os.listdir(os.path.join(tree, fx, "profiles"))):
        for d in DATES:
            out += [("--root", fx, "--json", "status", "--profile", p, "--as-of", d)]
        out += [("--root", fx, "--json", "cards", "--profile", p, "--as-of", DATES[0]),
                ("--root", fx, "timeline", "--profile", p, "--as-of", DATES[0], "--until", "2028-12-31")]
    return out


def run(tree, args):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": tempfile.gettempdir(), "PYTHONDONTWRITEBYTECODE": "1"}
    p = subprocess.run([sys.executable, "-m", "prices"] + list(args), cwd=tree, env=env, capture_output=True)
    return p.returncode, p.stdout + p.stderr


def tree_digest(tree, rel):
    h, base = hashlib.sha256(), os.path.join(tree, rel)
    if os.path.isfile(base):
        with open(base, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    for d, subdirs, names in os.walk(base):
        subdirs[:] = sorted(s for s in subdirs if s != "__pycache__")
        for n in sorted(names):
            if n in NEW_TABLE_FILES and (os.path.basename(d) == "tables" or d.endswith("synthetic-cards-input")):
                continue
            path = os.path.join(d, n)
            if os.path.relpath(path, tree).replace(os.sep, "/").startswith(ENG02B_DATA):
                continue                   # listed and checked one by one below
            h.update(os.path.relpath(path, tree).encode())
            with open(path, "rb") as f:
                h.update(hashlib.sha256(f.read()).digest())
    return h.hexdigest()


old = tempfile.mkdtemp(prefix="prices-baseline-")
blob = subprocess.run(["git", "archive", BASE], cwd=ROOT, capture_output=True)
if blob.returncode != 0:
    sys.exit("cannot read baseline commit %s: %s" % (BASE, blob.stderr.decode().strip()))
with tarfile.open(fileobj=io.BytesIO(blob.stdout)) as t:
    try:
        t.extractall(old, filter="data")
    except TypeError:                      # Python older than 3.12 has no filter argument
        t.extractall(old)
print("baseline %s unpacked to %s\n" % (BASE, old))

bad = 0
print("1. Files that must be the same in both")
for rel in UNCHANGED:
    if rel == ENG02B_TEST[0]:
        with open(os.path.join(old, rel), encoding="utf-8") as f_old, open(os.path.join(ROOT, rel), encoding="utf-8") as f_new:
            was, now = f_old.read(), f_new.read()
        same = was.count(ENG02B_TEST[1]) == 1 and was.replace(ENG02B_TEST[1], ENG02B_TEST[2]) == now
        bad += 0 if same else 1
        print("   %-9s %s (the baseline's file with one assertion moved to the published anniversary; nothing else)" % ("same" if same else "DIFFERENT", rel))
        continue
    same = tree_digest(old, rel) == tree_digest(ROOT, rel)
    bad += 0 if same else 1
    print("   %-9s %s" % ("same" if same else "DIFFERENT", rel))

def files(tree, rel):
    out = {}
    for d, _subdirs, names in os.walk(os.path.join(tree, rel)):
        for n in names:
            path = os.path.join(d, n)
            with open(path, "rb") as f:
                out[os.path.relpath(path, tree).replace(os.sep, "/")] = f.read()
    return out


was, now = files(old, "data"), files(ROOT, "data")
changed = sorted(k for k in set(was) | set(now) if was.get(k) != now.get(k))
expected = [k for k in changed if k.startswith(ENG02B_DATA) and k in now]
entities = [k for k in changed if k.startswith("data/kb/entities/")]
ok = changed == expected and len(entities) == 6 and len(changed) == 6 + 12 + 1
bad += 0 if ok else 1
print("   %-9s data/ differs in %d file(s): %d election definitions, their %d audit records and the audit log%s"
      % ("ok" if ok else "DIFFERENT", len(changed), len(entities), len(changed) - len(entities) - 1,
         "" if ok else "; unexpected: " + ", ".join(sorted(set(changed) - set(expected))[:5])))

for rel in EMPTY_CREDITS:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        empty = len(f.read().splitlines()) == 1
    bad += 0 if empty else 1
    print("   %-9s %s is the header line only" % ("ok" if empty else "DIFFERENT", rel))

print("\n2. Output of the old program on the old files vs this program on these files")
cmds = commands(old)
if cmds != commands(ROOT):
    print("   DIFFERENT  the two trees do not have the same profiles")
    bad += 1
for args in cmds:
    a, b = run(old, args), run(ROOT, args)
    same = a == b
    bad += 0 if same else 1
    print("   %-9s %s  %s" % ("identical" if same else "DIFFERENT", hashlib.sha256(b[1]).hexdigest()[:12], " ".join(args)))
with open(os.path.join(old, "data/audit/log.jsonl"), "rb") as f_old, open(os.path.join(ROOT, "data/audit/log.jsonl"), "rb") as f_new:
    old_log, new_log = f_old.read(), f_new.read()
prefix = new_log.startswith(old_log)
bad += 0 if prefix else 1
print("\n3. Audit history\n   %-9s the baseline's audit log is an unchanged prefix (%d -> %d entries)"
      % ("ok" if prefix else "DIFFERENT", old_log.count(b"\n"), new_log.count(b"\n")))
print("\n%d commands compared, %d file sets compared, %d difference(s)" % (len(cmds), len(UNCHANGED), bad))
print("BASELINE COMPARISON:", "PASS" if not bad else "FAIL")
sys.exit(1 if bad else 0)
