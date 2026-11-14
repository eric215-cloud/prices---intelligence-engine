"""Acceptance Test F: export the project, unpack it somewhere clean, and reproduce setup and tests there.

    python3 scripts/verify_export.py [output.zip]

Uses only the exported files (no git history, no caches). Exit 0 only if everything passes.
"""
import os
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(tempfile.mkdtemp(), "prices-export.zip")


def run(cmd, cwd):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": tempfile.mkdtemp()}   # clean environment
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
    print("%-4s %s   | %s" % ("ok" if p.returncode == 0 else "FAIL", " ".join(cmd[1:]), tail[0]))
    return p.returncode == 0


ok = run([sys.executable, "-m", "prices", "export", "--out", out], ROOT)
clean = tempfile.mkdtemp(prefix="prices-clean-")
with zipfile.ZipFile(out) as z:
    z.extractall(clean)
    n = len(z.namelist())
proj = os.path.join(clean, "prices")
print("unpacked %d files into %s" % (n, proj))
ok &= run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], proj)
ok &= run([sys.executable, "-m", "prices", "lint"], proj)
ok &= run([sys.executable, "-m", "prices", "status", "--profile", "synthetic-demo", "--as-of", "2026-11-12"], proj)
ok &= run([sys.executable, "-m", "prices", "goal", "fly business class to Japan", "--profile", "synthetic-demo", "--as-of", "2026-11-12"], proj)
ok &= run([sys.executable, "successor_test/harness.py", "setup", os.path.join(clean, "disposable")], proj)
ok &= run([sys.executable, "-m", "prices", "tables", "status"], proj)
ok &= run([sys.executable, "fixtures/synthetic_cards.py", os.path.join(clean, "fixture-rebuild")], proj)
ok &= run([sys.executable, "-m", "prices", "--root", "fixtures/synthetic-cards", "cards", "--profile", "synthetic-alex", "--as-of", "2026-11-14"], proj)
ok &= run([sys.executable, "scripts/demo_card_maintenance.py"], proj)
print("zip: %s (%d bytes)" % (out, os.path.getsize(out)))
print("TEST F:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
