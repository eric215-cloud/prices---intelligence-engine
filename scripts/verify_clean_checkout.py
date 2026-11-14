"""Clone the committed state of this repository into an empty directory and prove it works there, offline.

    python3 scripts/verify_clean_checkout.py

Uses `git clone` of the local repository (no network), a minimal environment (no proxy settings,
empty HOME, no PYTHONPATH), and only the commands a new maintainer would run. Uncommitted files
are not part of the clone, so this also catches "works only on my machine" omissions.
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dst = os.path.join(tempfile.mkdtemp(prefix="prices-checkout-"), "prices")
ENV = {"PATH": os.environ.get("PATH", ""), "HOME": tempfile.mkdtemp(),
       # any attempt to reach the network through the usual variables fails immediately
       "http_proxy": "http://127.0.0.1:9", "https_proxy": "http://127.0.0.1:9", "no_proxy": ""}


def run(cmd, cwd, env=ENV):
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
    print("%-4s %s   | %s" % ("ok" if p.returncode == 0 else "FAIL", " ".join(cmd[1:] if cmd[0] == sys.executable else cmd), tail[0]))
    return p.returncode == 0


head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
print("commit under test: %s%s" % (head, "  (NOTE: working tree has uncommitted changes; they are not tested)" if dirty else ""))
ok = run(["git", "clone", "--quiet", "--no-hardlinks", ROOT, dst], ROOT, dict(os.environ))
ok &= run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], dst)
ok &= run([sys.executable, "-m", "prices", "lint"], dst)
ok &= run([sys.executable, "-m", "prices", "tables", "status"], dst)
ok &= run([sys.executable, "-m", "prices", "status", "--profile", "eric", "--as-of", "2026-11-14"], dst)
ok &= run([sys.executable, "fixtures/synthetic_cards.py", os.path.join(os.path.dirname(dst), "fixture")], dst)
ok &= run([sys.executable, "scripts/demo_card_maintenance.py"], dst)
ok &= run(["git", "status", "--porcelain"], dst, dict(os.environ))   # the run must not have modified the checkout
left = subprocess.run(["git", "status", "--porcelain"], cwd=dst, capture_output=True, text=True).stdout.strip()
if left:
    print("FAIL checkout was modified by the run:\n" + left)
    ok = False
print("CLEAN CHECKOUT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
