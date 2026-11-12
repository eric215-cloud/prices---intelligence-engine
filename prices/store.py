"""Record storage: one JSON file per record, held in memory as {relative_path: object}.

Nothing here interprets records. Writing is only done through save(), which the
changeset pipeline (changes.py) calls after validation has passed.
"""
import copy
import hashlib
import json
import os

DEFAULT_VOCAB = {
    "tags": {},
    "questions": {},
    "goal_research": [],
    "seeded_signatures": [],
    "evidence_policy": {"primary_types": ["official"], "secondary_types": ["reputable_secondary"], "secondary_min": 2},
}

PREFIX = {
    "entities": "data/kb/entities/",
    "rules": "data/kb/rules/",
    "evidence": "data/kb/evidence/",
    "candidates": "data/candidates/",
    "observations": "data/observations/",
    "discovery_runs": "data/discovery_runs/",
}
VOCAB_PATH = "data/kb/vocab.json"
LEDGER_PATH = "data/coverage/ledger.json"
AUDIT_LOG = "data/audit/log.jsonl"


def dumps(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class Profile:
    def __init__(self, name, meta, holdings, metrics):
        self.name, self.meta, self.holdings, self.metrics = name, meta, holdings, metrics


class Store:
    def __init__(self, files=None):
        self.files = files or {}

    # ---------- loading / saving ----------
    @classmethod
    def load(cls, root):
        files = {}
        for top in ("data", "profiles"):
            base = os.path.join(root, top)
            for dirpath, _dirs, names in os.walk(base):
                rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
                if rel_dir.startswith("data/audit"):
                    continue
                for n in sorted(names):
                    if n.endswith(".json"):
                        rel = rel_dir + "/" + n
                        with open(os.path.join(dirpath, n), encoding="utf-8") as f:
                            try:
                                files[rel] = json.load(f)
                            except json.JSONDecodeError as e:
                                files[rel] = {"__unparseable__": str(e)}
        return cls(files)

    def copy(self):
        return Store(copy.deepcopy(self.files))

    def changed_paths(self, other):
        """Paths whose content differs between self (old) and other (new)."""
        paths = set(self.files) | set(other.files)
        return sorted(p for p in paths if self.files.get(p) != other.files.get(p))

    def save(self, root, paths):
        """Write the given paths (delete if absent from store). Temp file + rename per file."""
        for rel in paths:
            full = os.path.join(root, rel)
            if rel not in self.files:
                if os.path.exists(full):
                    os.remove(full)
                continue
            os.makedirs(os.path.dirname(full), exist_ok=True)
            tmp = full + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(dumps(self.files[rel]))
            os.replace(tmp, full)

    def digest(self):
        h = hashlib.sha256()
        for p in sorted(self.files):
            h.update(p.encode())
            h.update(json.dumps(self.files[p], sort_keys=True).encode())
        return h.hexdigest()[:16]

    # ---------- typed views ----------
    def _coll(self, key):
        pre = PREFIX[key]
        return {v.get("id", p): v for p, v in self.files.items()
                if p.startswith(pre) and isinstance(v, dict)}

    entities = property(lambda self: self._coll("entities"))
    rules = property(lambda self: self._coll("rules"))
    evidence = property(lambda self: self._coll("evidence"))
    candidates = property(lambda self: self._coll("candidates"))
    observations = property(lambda self: self._coll("observations"))
    discovery_runs = property(lambda self: self._coll("discovery_runs"))

    @property
    def vocab(self):
        v = dict(DEFAULT_VOCAB)
        v.update(self.files.get(VOCAB_PATH, {}))
        return v

    @property
    def ledger(self):
        return self.files.get(LEDGER_PATH, {"cells": {}})

    def profile_names(self):
        return sorted({p.split("/")[1] for p in self.files if p.startswith("profiles/") and p.count("/") >= 2})

    def profile(self, name):
        base = "profiles/%s/" % name
        meta = self.files.get(base + "profile.json")
        if meta is None:
            raise KeyError("no such profile: %s (have: %s)" % (name, ", ".join(self.profile_names())))
        hold = {v["id"]: v for p, v in self.files.items() if p.startswith(base + "holdings/")}
        mets = {v["id"]: v for p, v in self.files.items() if p.startswith(base + "metrics/")}
        return Profile(name, meta, hold, mets)

    # ---------- paths ----------
    @staticmethod
    def path(kind, rec_id, profile=None):
        if kind in PREFIX:
            return PREFIX[kind] + rec_id + ".json"
        if kind in ("holdings", "metrics"):
            return "profiles/%s/%s/%s.json" % (profile, kind, rec_id)
        raise KeyError(kind)


def append_audit(root, entry):
    full = os.path.join(root, AUDIT_LOG)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")


def read_audit(root):
    full = os.path.join(root, AUDIT_LOG)
    if not os.path.exists(full):
        return []
    with open(full, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
