"""Shared tools for the foundation viability experiment. Everything happens in a throwaway copy of the store.

Nothing here writes to the project's own data/, profiles/ or tables/. Real candidates are promoted ONLY in the
copy, by the first listed reviewer, with a statement that says it is an experiment and not a content review.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)

from prices import changes                      # noqa: E402
from prices.store import Store                  # noqa: E402

TODAY = "2026-11-16"
AUTHOR = "viability experiment (scratch copy)"
STATEMENT = "Foundation viability experiment, scratch copy only. Not a content review; nothing is promoted in the project."


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


class Lab:
    """A scratch copy of the live store, plus a log of every pipeline operation attempted in it."""

    def __init__(self, keep=None):
        self.root = keep or tempfile.mkdtemp(prefix="prices-viability-")
        for sub in ("data", "profiles", "tables"):
            dst = os.path.join(self.root, sub)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(os.path.join(ROOT, sub), dst)
        self.reviewer = self.store().vocab["promotion_reviewers"][0]
        self.log, self.n = [], 0

    def store(self):
        return Store.load(self.root)

    # ---- pipeline
    def apply(self, op, batch, record=None, **body):
        """One changeset through the real pipeline. Returns the pipeline's result; every attempt is logged."""
        self.n += 1
        cs = dict({"id": "cs-%s-via-%04d-%s" % (TODAY.replace("-", ""), self.n, op.replace("_", "-")), "op": op, "author": AUTHOR,
                   "date": TODAY, "reason": "viability experiment: " + batch}, **body)
        out = changes.apply(self.root, cs)
        self.log.append({"batch": batch, "record": record, "op": op, "ok": out["ok"], "errors": [str(e)[:300] for e in out.get("errors", [])],
                         "bytes": len(json.dumps(cs)), "fields": _fields(body)})
        return out

    def attest(self):
        return {"by": self.reviewer, "on": TODAY, "statement": STATEMENT}

    def promote(self, cand_id, batch, record=None):
        """Promote a candidate in the scratch copy. Open questions are accepted explicitly and stay on the rule."""
        c = self.store().candidates[cand_id]
        data = {"review_by": "2027-11-16"}
        if c["open_questions"]:
            data["accept_open_questions"] = True
        return self.apply("promote_candidate", batch, record or cand_id, target=cand_id, data=data, attestation=self.attest())

    def evidence_of(self, rule_id):
        s = self.store()
        return [s.evidence[e] for e in s.rules[rule_id]["evidence"]]

    def vocab(self, patch):
        """Vocabulary is a hand-edited file (docs/MAINTAINER_GUIDE.md); lint is the check."""
        path = os.path.join(self.root, "data", "kb", "vocab.json")
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
        for key, val in patch.items():
            v.setdefault(key, {}).update(val)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(v, f, indent=2, sort_keys=True)

    # ---- invented people (written as files, exactly as the test suites do)
    def person(self, name, holdings, metrics=()):
        owner = "%s (invented)" % name
        base = os.path.join(self.root, "profiles", name)
        os.makedirs(os.path.join(base, "holdings"), exist_ok=True)
        with open(os.path.join(base, "profile.json"), "w", encoding="utf-8") as f:
            json.dump({"id": name, "label": "invented person for the viability experiment", "synthetic": True, "owner": owner}, f)
        for h in holdings:
            h = dict(h)
            if h.get("state", "confirmed") == "confirmed":
                h.update(state="confirmed", confirmed_by=owner, confirmed_on=h.get("confirmed_on", TODAY))
            with open(os.path.join(base, "holdings", h["id"] + ".json"), "w", encoding="utf-8") as f:
                json.dump(h, f)
        if metrics:
            os.makedirs(os.path.join(base, "metrics"), exist_ok=True)
            for m in metrics:
                m = dict(m, state="confirmed", confirmed_by=owner)
                with open(os.path.join(base, "metrics", m["id"] + ".json"), "w", encoding="utf-8") as f:
                    json.dump(m, f)
        return owner

    # ---- questions
    def cli(self, *args):
        """Run the command-line tool on the scratch copy. Returns (exit code, text)."""
        p = subprocess.run([sys.executable, "-m", "prices", "--root", self.root] + [str(a) for a in args], cwd=ROOT, capture_output=True, text=True)
        return p.returncode, (p.stdout + p.stderr).rstrip()

    def js(self, *args):
        code, text = self.cli("--json", *args)
        if code not in (0, 1):
            raise RuntimeError("%s\n%s" % (" ".join(str(a) for a in args), text))
        return json.loads(text)

    def lint_errors(self):
        code, text = self.cli("lint")
        return [ln for ln in text.splitlines() if ln.startswith("ERROR")]


def _fields(obj):
    """Number of leaf values an operator had to write (a rough, tool-independent measure of authoring effort)."""
    if isinstance(obj, dict):
        return sum(_fields(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_fields(v) for v in obj)
    return 1


def status_of(report, entity):
    """ESTABLISHED / CONDITIONAL / UNRESOLVED / NOT_AVAILABLE for one entity, from a `--json status` report."""
    for key, label in (("derived_entitlements", "ESTABLISHED"), ("conditional", "CONDITIONAL"), ("unresolved", "UNRESOLVED")):
        if any(x["entity"] == entity for x in report[key]):
            return label
    if any(x["entity"] == entity and x["effective"] == "ESTABLISHED" for x in report["personal_qualifications"]):
        return "ESTABLISHED"
    return "NOT_AVAILABLE"
