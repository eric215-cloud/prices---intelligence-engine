"""Shared tools for the foundation viability experiment. Everything happens in a throwaway copy of the store.

Nothing here writes to the project's own data/, profiles/ or tables/. Real candidates are promoted ONLY in the
copy, by the first listed reviewer, with a statement that says it is an experiment and not a content review.

Since the safety correction (2026-11-17) a promotion must record a class for every restriction and open question
(prices/conditions.py). In the copy those classes are engineering's reading: restriction_classes.json for the real
candidates, the `condition_classes` map of a sheet for its records, and experiments/safety/live_rules_proposal.json
for the rules already verified in the store. None of it is a content review.
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
sys.path.insert(1, os.path.join(ROOT, "fixtures"))
sys.path.insert(1, os.path.join(ROOT, "experiments", "safety"))

from prices import changes                      # noqa: E402
from prices.store import Store                  # noqa: E402
from condition_classes import scratch_real      # noqa: E402
import proposal                                 # noqa: E402

TODAY = "2026-11-16"
AUTHOR = "viability experiment (scratch copy)"
STATEMENT = "Foundation viability experiment, scratch copy only. Not a content review; nothing is promoted in the project."


def load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


class Lab:
    """A scratch copy of the live store, plus a log of every pipeline operation attempted in it."""

    def __init__(self, keep=None, classify_live=True):
        self.root = keep or tempfile.mkdtemp(prefix="prices-viability-")
        for sub in ("data", "profiles", "tables"):
            dst = os.path.join(self.root, sub)
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(os.path.join(ROOT, sub), dst)
        self.reviewer = self.store().vocab["promotion_reviewers"][0]
        self.log, self.n = [], 0
        if classify_live:           # the verified rules predate condition review: apply the proposal, in the copy only
            proposal.apply_to_copy(self.root, TODAY)

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

    def promote(self, cand_id, batch, record=None, conditions=None):
        """Promote a candidate in the scratch copy, recording a class for each of its restrictions and open questions.

        `conditions` are the items to record. Left out, they come from engineering's reading of the REAL candidates
        (restriction_classes.json); a candidate that file does not cover cannot be promoted this way."""
        c = self.store().candidates[cand_id]
        data = {"review_by": "2027-11-16", "conditions": scratch_real(c, store=self.store()) if conditions is None else conditions}
        if c["open_questions"]:
            data["accept_open_questions"] = True
        return self.apply("promote_candidate", batch, record or cand_id, target=cand_id, data=data, attestation=self.attest())

    def promote_bare(self, cand_id, batch):
        """The promotion as it was before the safety correction: no class recorded for anything."""
        c = self.store().candidates[cand_id]
        data = {"review_by": "2027-11-16"}
        if c["open_questions"]:
            data["accept_open_questions"] = True
        return self.apply("promote_candidate", batch, cand_id, target=cand_id, data=data, attestation=self.attest())

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


def items(rule, questions, classes):
    """Classification items for a sheet record: {text: class} or {text: {"class": ..., "enforced_by": ...}} -> items.

    A text the map does not mention gets no item, so the pipeline refuses the promotion: nothing is defaulted."""
    out = []
    for text in list(rule.get("restrictions") or []) + list(questions or []):
        if text in classes:
            given = classes[text]
            out.append(dict({"text": text}, **(given if isinstance(given, dict) else {"class": given})))
    return out


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
