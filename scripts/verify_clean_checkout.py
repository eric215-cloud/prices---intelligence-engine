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
# earned benefits: rebuild the synthetic fixture and compare it with the committed copy, then report, demo and guards
rebuilt = os.path.join(os.path.dirname(dst), "fixture-earned")
ok &= run([sys.executable, "fixtures/synthetic_earned.py", rebuilt], dst)
ok &= run(["diff", "-r", "-q", rebuilt, os.path.join(dst, "fixtures", "synthetic-earned")], dst)
ok &= run([sys.executable, "-m", "prices", "--root", "fixtures/synthetic-earned", "earned", "--profile", "synthetic-alex", "--as-of", "2027-03-10"], dst)
ok &= run([sys.executable, "scripts/demo_earned.py"], dst)
ok &= run([sys.executable, "scripts/mutation_check_earned.py"], dst)
# (scripts/compare_with_baseline.py is no longer run: the safety correction changes answers on purpose. See below.)
# recurring credits (ENG-01): rebuild the fixture and compare it with the committed copy, then report, demo and guards
rebuilt = os.path.join(os.path.dirname(dst), "fixture-credits")
ok &= run([sys.executable, "fixtures/synthetic_credits.py", rebuilt], dst)
ok &= run(["diff", "-r", "-q", rebuilt, os.path.join(dst, "fixtures", "synthetic-credits")], dst)
ok &= run([sys.executable, "-m", "prices", "--root", "fixtures/synthetic-credits", "credits", "--profile", "synthetic-alex", "--as-of", "2027-03-10"], dst)
ok &= run([sys.executable, "scripts/demo_credits.py"], dst)
ok &= run([sys.executable, "scripts/mutation_check_credits.py"], dst)
# Argon intake and cardholder elections
ok &= run([sys.executable, "scripts/verify_argon_intake.py"], dst, dict(ENV, GIT_CONFIG_NOSYSTEM="1"))
ok &= run([sys.executable, "scripts/demo_elections.py"], dst)
ok &= run([sys.executable, "scripts/mutation_check_elections.py"], dst)
# foundation safety correction: real content in a throwaway copy, the earlier commit side by side, and the guards
ok &= run([sys.executable, "experiments/viability/run.py"], dst)
ok &= run([sys.executable, "experiments/safety/before_after.py"], dst, dict(ENV, GIT_CONFIG_NOSYSTEM="1"))
ok &= run([sys.executable, "scripts/mutation_check_safety.py"], dst)
ok &= run(["git", "status", "--porcelain"], dst, dict(os.environ))   # the run must not have modified the checkout
left = subprocess.run(["git", "status", "--porcelain"], cwd=dst, capture_output=True, text=True).stdout.strip()
if left:
    print("FAIL checkout was modified by the run:\n" + left)
    ok = False
print("CLEAN CHECKOUT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
