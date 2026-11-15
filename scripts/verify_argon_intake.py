"""Re-check the Argon content intake (Bilt Palladium and Chase Sapphire Reserve, 2026-11-14) from the committed input archive.

    python3 scripts/verify_argon_intake.py

Needs git (it unpacks the engineering base with `git archive`). Read-only: works in a temp directory.

What it checks, in order:
  1. The archive opens, every member path is safe, and every file listed in INTEGRATION_MANIFEST.json is present
     with the listed sha256 and size.
  2. Starting from the engineering base, every changeset in Argon's audit log re-applies through the ordinary
     pipeline (prices.changes.apply), in log order, with the same result, changed files and store digests.
  3. After `tables export`, the replayed data/, profiles/ and tables/ equal this checkout's, byte for byte.
  4. Argon's packaged data equals the replay, except two audit records the package left out (listed below).
  5. Counts: 10 active rules (same files as the base), 113 proposed candidates, none promoted by Argon,
     profiles/ byte-identical to the base, lint 0 errors, tables in sync.
Exit 0 only if every check passes.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from prices import changes  # noqa: E402

BASE = "ed92749447413c5d327877618754a5642e3e7f02"
ARCHIVE = os.path.join(ROOT, "docs", "inputs", "Argon_PRICES_Content_Integration_OUTPUT.zip")
ARCHIVE_SHA256 = "bb736f4b31f808e790a6f606cf3dcd06d12f6372b0ea829920da530b4efc0d1e"
# The package's audit trail omits these two base records (Eric's holding changesets of 2026-11-12, by Bradley).
# The intake keeps them: an integration may add to the audit history, never remove from it.
LEFT_OUT_OF_PACKAGE = ["data/audit/changesets/cs-20261112-101-set-holding.json", "data/audit/changesets/cs-20261112-102-set-holding.json"]

bad = []


def check(ok, what):
    print("   %-5s %s" % ("ok" if ok else "FAIL", what))
    if not ok:
        bad.append(what)


def files(root, sub):
    out = set()
    for d, _s, names in os.walk(os.path.join(root, sub)):
        for n in names:
            out.add(os.path.relpath(os.path.join(d, n), root))
    return out


def read(root, rel):
    with open(os.path.join(root, rel), "rb") as f:
        return f.read()


def prices_cmd(root, *args):
    p = subprocess.run([sys.executable, "-m", "prices", "--root", root] + list(args), cwd=ROOT, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


tmp = tempfile.mkdtemp(prefix="prices-argon-intake-")
pkg, base, replay = (os.path.join(tmp, n) for n in ("package", "base", "replay"))

print("1. Archive and manifest")
with open(ARCHIVE, "rb") as f:
    blob = f.read()
check(hashlib.sha256(blob).hexdigest() == ARCHIVE_SHA256, "archive sha256 %s" % ARCHIVE_SHA256[:16])
with zipfile.ZipFile(io.BytesIO(blob)) as z:
    names = z.namelist()
    check(all(not n.startswith("/") and ".." not in n.split("/") for n in names), "no unsafe member paths (%d members)" % len(names))
    check(z.testzip() is None, "every member passes its CRC check")
    z.extractall(pkg)
with open(os.path.join(pkg, "INTEGRATION_MANIFEST.json"), encoding="utf-8") as f:
    manifest = json.load(f)
check(manifest["engineering_base_commit"] == BASE, "manifest names the engineering base %s" % BASE[:7])
listed = {e["path"]: e for e in manifest["files"]}
present = files(pkg, "") - {"INTEGRATION_MANIFEST.json"}
check(set(listed) == present, "manifest lists exactly the %d packaged files" % len(listed))
mism = [p for p, e in listed.items() if p in present and (hashlib.sha256(read(pkg, p)).hexdigest() != e["sha256"] or len(read(pkg, p)) != e["size_bytes"])]
check(not mism, "every listed sha256 and size matches%s" % (": " + ", ".join(mism[:3]) if mism else ""))

print("\n2. Replay of Argon's changesets on the engineering base")
g = subprocess.run(["git", "archive", BASE], cwd=ROOT, capture_output=True)
if g.returncode != 0:
    sys.exit("cannot read base commit %s: %s" % (BASE, g.stderr.decode().strip()))
with tarfile.open(fileobj=io.BytesIO(g.stdout)) as t:
    try:
        t.extractall(base, filter="data")
    except TypeError:
        t.extractall(base)
shutil.copytree(base, replay)
with open(os.path.join(pkg, "data/audit/log.jsonl"), encoding="utf-8") as f:
    pkg_log = [json.loads(line) for line in f]
argon = [r for r in pkg_log if r.get("author") == "Argon"]
keys = ("changeset", "op", "result", "changed", "digest_before", "digest_after", "review_needed", "errors")
mismatch = []
for row in argon:
    with open(os.path.join(pkg, "data/audit/changesets", row["changeset"] + ".json"), encoding="utf-8") as f:
        cs = json.load(f)
    out = changes.apply(replay, cs)
    with open(os.path.join(replay, "data/audit/log.jsonl"), encoding="utf-8") as f:
        mine = json.loads(f.read().splitlines()[-1])
    if not out["ok"] or any(row.get(k) != mine.get(k) for k in keys):
        mismatch.append(row["changeset"])
check(not mismatch, "%d changesets re-applied with identical results and digests%s" % (len(argon), (": " + ", ".join(mismatch[:3])) if mismatch else ""))
code, _out = prices_cmd(replay, "tables", "export")
check(code == 0, "tables export on the replay")

print("\n3. This checkout equals the replay")
for sub in ("data", "profiles", "tables"):
    a, b = files(replay, sub), files(ROOT, sub)
    diff = sorted((a ^ b) | {p for p in a & b if read(replay, p) != read(ROOT, p)})
    check(not diff, "%s/ identical (%d files)%s" % (sub, len(a), ": " + ", ".join(diff[:3]) if diff else ""))

print("\n4. Argon's packaged store equals the replay, apart from what the package left out")
for sub in ("data", "profiles", "tables"):
    a, b = files(replay, sub), files(pkg, sub)
    only_replay, only_pkg = sorted(a - b), sorted(b - a)
    differ = sorted(p for p in a & b if read(replay, p) != read(pkg, p))
    expected_only = LEFT_OUT_OF_PACKAGE if sub == "data" else []
    expected_differ = ["data/audit/log.jsonl"] if sub == "data" else []
    check((only_replay, only_pkg, differ) == (expected_only, [], expected_differ),
          "%s/: package equals replay%s" % (sub, " except the two left-out audit records and the log lines for them" if sub == "data" else ""))
replay_log = read(replay, "data/audit/log.jsonl").decode().splitlines()
base_log = read(base, "data/audit/log.jsonl").decode().splitlines()
pkg_lines = read(pkg, "data/audit/log.jsonl").decode().splitlines()
check(replay_log[:len(base_log)] == base_log, "replay log starts with the complete base log (%d lines)" % len(base_log))
check(replay_log[len(base_log):] == pkg_lines[len(pkg_lines) - len(argon):], "replay log then carries Argon's %d lines exactly" % len(argon))
missing = [json.loads(x)["changeset"] for x in base_log if x not in pkg_lines]
check(missing == [os.path.basename(p)[:-5] for p in LEFT_OUT_OF_PACKAGE], "the package's log lacks only %s" % ", ".join(missing))

print("\n5. Boundaries")
check(files(base, "data/kb/rules") == files(ROOT, "data/kb/rules") and all(read(base, p) == read(ROOT, p) for p in files(base, "data/kb/rules")),
      "data/kb/rules: the same %d files as the base" % len(files(base, "data/kb/rules")))
check(files(base, "profiles") == files(ROOT, "profiles") and all(read(base, p) == read(ROOT, p) for p in files(base, "profiles")),
      "profiles/ byte-identical to the base")
cands = {}
for p in files(ROOT, "data/candidates"):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        cands[p] = json.load(f)
base_cands = files(base, "data/candidates")
check(all(read(base, p) == read(ROOT, p) for p in base_cands), "the %d base candidates are unchanged" % len(base_cands))
new = {p: c for p, c in cands.items() if p not in base_cands}
check(len(new) == 111 and all(c["status"] == "proposed" for c in new.values()), "Argon added 111 candidates, all proposed")
check(sum(c["status"] == "proposed" for c in cands.values()) == 113, "113 proposed candidates in total")
check(not any(r["op"] == "promote_candidate" for r in argon), "no promotion in Argon's changesets")
code, out = prices_cmd(ROOT, "lint")
check(code == 0 and "lint: 0 error(s)" in out, out.strip().splitlines()[-1])
code, out = prices_cmd(ROOT, "tables", "status")
check("out of date with the store: no" in out and "unimported edits:           no" in out, "tables in sync with the store")

shutil.rmtree(tmp)
print("\nARGON INTAKE:", "PASS" if not bad else "FAIL (%d)" % len(bad))
sys.exit(1 if bad else 0)
