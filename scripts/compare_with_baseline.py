"""Show that people and data with no earned-benefit records get byte-identical output from an older commit and from this checkout.

    python3 scripts/compare_with_baseline.py [baseline-commit]        (default: 6eb9ec9, the commit before earned benefits)

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
BASE = sys.argv[1] if len(sys.argv) > 1 else "6eb9ec9"
DATES = ("2026-11-14", "2027-03-15", "2028-01-05")
UNCHANGED = ("data", "profiles", "tables", "fixtures/synthetic-cards", "fixtures/synthetic-cards-input", "fixtures/synthetic_cards.py",
             "tests/util.py", "tests/test_a_conditional.py", "tests/test_b_temporal.py", "tests/test_c_i_evidence_cycles.py",
             "tests/test_d_h_discovery_goal.py", "tests/test_e_maintenance.py", "tests/test_j_relational.py", "tests/test_k_tables.py",
             "tests/test_live_data.py", "successor_test")


def commands(tree):
    out = [("lint",), ("--json", "cards", "--as-of", DATES[0]), ("tables", "status"), ("audit", "--last", "50")]
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
            path = os.path.join(d, n)
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
    same = tree_digest(old, rel) == tree_digest(ROOT, rel)
    bad += 0 if same else 1
    print("   %-9s %s" % ("same" if same else "DIFFERENT", rel))

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
print("\n%d commands compared, %d file sets compared, %d difference(s)" % (len(cmds), len(UNCHANGED), bad))
print("BASELINE COMPARISON:", "PASS" if not bad else "FAIL")
sys.exit(1 if bad else 0)
