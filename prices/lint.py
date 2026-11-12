"""Whole-store validation. A store with any ERROR must never be written to disk.

Each issue is (severity, code, path, message). Codes are stable so maintainers and
tests can match on them.
"""
from .engine import leaves
from .schema import Schema
from .store import PREFIX, VOCAB_PATH, LEDGER_PATH

_KIND_BY_PREFIX = [(PREFIX["entities"], "entity"), (PREFIX["rules"], "rule"), (PREFIX["evidence"], "evidence"),
                   (PREFIX["candidates"], "candidate"), (PREFIX["observations"], "observation"),
                   (PREFIX["discovery_runs"], "discovery_run")]


def record_kind(path):
    for pre, kind in _KIND_BY_PREFIX:
        if path.startswith(pre):
            return kind
    if path.startswith("profiles/"):
        parts = path.split("/")
        if len(parts) == 3 and parts[2] == "profile.json":
            return "profile"
        if len(parts) == 4 and parts[2] == "holdings":
            return "holding"
        if len(parts) == 4 and parts[2] == "metrics":
            return "metric"
    return None


def signature(rule):
    """Identity of a relationship, independent of wording: kind:sorted(positive holds)->output."""
    pos = sorted({i for k, i, neg in leaves(rule["when"]) if k == "holds" and not neg})
    return "%s:%s->%s" % (rule["kind"], "+".join(pos), rule["output"])


def evidence_ok(policy, records):
    """Evidence policy: one primary source, or N independent secondary publishers."""
    if any(e["source_type"] in policy["primary_types"] for e in records):
        return True
    pubs = {e["publisher"].strip().lower() for e in records if e["source_type"] in policy["secondary_types"]}
    return len(pubs) >= policy["secondary_min"]


def lint(store):
    issues = []
    schema = Schema()

    def err(code, path, msg):
        issues.append(("ERROR", code, path, msg))

    def warn(code, path, msg):
        issues.append(("WARNING", code, path, msg))

    # 1. shape of every record, and id == file name
    for path, obj in sorted(store.files.items()):
        if isinstance(obj, dict) and "__unparseable__" in obj:
            err("UNPARSEABLE_JSON", path, obj["__unparseable__"])
            continue
        kind = record_kind(path)
        if kind is None:
            if path not in (VOCAB_PATH, LEDGER_PATH):
                warn("UNKNOWN_FILE", path, "file is not part of the schema and is ignored")
            continue
        for e in schema.validate(obj, kind):
            err("SCHEMA", path, e)
        stem = path.rsplit("/", 1)[-1][:-5]
        if kind != "profile" and isinstance(obj, dict) and obj.get("id") != stem:
            err("ID_FILENAME_MISMATCH", path, "id %r must equal file name %r" % (obj.get("id"), stem))
        if kind == "profile" and isinstance(obj, dict) and obj.get("id") != path.split("/")[1]:
            err("ID_FILENAME_MISMATCH", path, "profile id must equal its directory name")
    if any(i[0] == "ERROR" for i in issues):
        return issues   # reference checks assume well-formed records

    ents, rules, evid = store.entities, store.rules, store.evidence
    vocab = store.vocab
    policy = vocab["evidence_policy"]

    # 2. entities
    for e in ents.values():
        p = store.path("entities", e["id"])
        if "program" in e and e["program"] not in ents:
            err("UNKNOWN_REFERENCE", p, "program %r is not an entity" % e["program"])
        for t in e.get("tags", []):
            if t not in vocab["tags"]:
                err("UNKNOWN_TAG", p, "tag %r is not in data/kb/vocab.json" % t)

    # 3. rules
    def check_condition(cond, path, known_entities):
        pos, neg = set(), set()
        for kind, ident, is_neg in leaves(cond):
            if kind == "holds":
                if ident not in known_entities:
                    err("UNKNOWN_REFERENCE", path, "condition refers to unknown entity %r" % ident)
                (neg if is_neg else pos).add(ident)
        return pos, neg

    def contradictory(cond):
        if "all" in cond:
            need = {c["holds"] for c in cond["all"] if "holds" in c}
            deny = {c["not"]["holds"] for c in cond["all"] if "not" in c}
            if need & deny:
                return True
        return any(contradictory(c) for c in (cond.get("all") or cond.get("any") or []))

    sigs = {}
    for r in rules.values():
        p = store.path("rules", r["id"])
        if r["output"] not in ents:
            err("UNKNOWN_REFERENCE", p, "output %r is not an entity" % r["output"])
        check_condition(r["when"], p, ents)
        if contradictory(r["when"]):
            err("CONTRADICTORY_CONDITION", p, "an 'all' both requires and excludes the same entity; rule can never apply")
        if r["kind"] == "acquire" and "retention" not in r:
            err("MISSING_RETENTION", p, "acquire rules must state retention (use mode 'unknown' if not established)")
        if r["kind"] != "acquire" and "retention" in r:
            err("UNEXPECTED_RETENTION", p, "only acquire rules have retention; grants/transfer last while the condition holds")
        if "retention" in r and "retain_when" in r["retention"]:
            check_condition(r["retention"]["retain_when"], p, ents)
        if r["kind"] == "transfer":
            if "transfer" not in r:
                err("MISSING_TRANSFER", p, "transfer rules need a 'transfer' block")
            elif r["transfer"]["from"] not in ents:
                err("UNKNOWN_REFERENCE", p, "transfer.from %r is not an entity" % r["transfer"]["from"])
        recs = []
        for eid in r["evidence"]:
            if eid not in evid:
                err("UNKNOWN_REFERENCE", p, "evidence %r does not exist" % eid)
            else:
                recs.append(evid[eid])
        v = r["verification"]
        if v["status"] == "verified":
            if not evidence_ok(policy, recs):
                err("INSUFFICIENT_EVIDENCE", p, "verified rules need one %s source or %d independent %s sources"
                    % ("/".join(policy["primary_types"]), policy["secondary_min"], "/".join(policy["secondary_types"])))
            if "last_verified" not in v or "review_by" not in v:
                err("MISSING_VERIFICATION_DATES", p, "verified rules need last_verified and review_by")
            elif v["review_by"] <= v["last_verified"]:
                err("BAD_DATES", p, "review_by must be after last_verified")
        if r.get("valid_from") and r.get("valid_to") and r["valid_to"] < r["valid_from"]:
            err("BAD_DATES", p, "valid_to is before valid_from")
        if v["status"] != "retired":
            s = signature(r)
            if s in sigs:
                err("DUPLICATE_RELATIONSHIP", p, "same relationship as rule %s (%s)" % (sigs[s], s))
            sigs[s] = r["id"]

    # 4. negation must not sit on a dependency cycle (keeps evaluation well-defined)
    deps = {}
    for r in rules.values():
        if r["verification"]["status"] == "retired":
            continue
        for kind, ident, is_neg in leaves(r["when"]):
            if kind == "holds":
                deps.setdefault(r["output"], set()).add((ident, is_neg))

    def reaches(start, goal, seen=None):
        seen = seen or set()
        for nxt, _neg in deps.get(start, ()):
            if nxt == goal or (nxt not in seen and not seen.add(nxt) and reaches(nxt, goal, seen)):
                return True
        return False

    for out, ds in deps.items():
        for ident, is_neg in ds:
            if is_neg and (ident == out or reaches(ident, out)):
                err("NEGATIVE_CYCLE", "data/kb/rules/", "%s is excluded by a rule for %s, which itself depends on %s" % (ident, out, out))

    # 5. profiles
    for name in store.profile_names():
        base = "profiles/%s/" % name
        if base + "profile.json" not in store.files:
            err("MISSING_PROFILE_META", base, "profile directory has no profile.json")
            continue
        prof = store.profile(name)
        seen = {}
        for h in prof.holdings.values():
            p = store.path("holdings", h["id"], name)
            if h["entity"] not in ents:
                err("UNKNOWN_REFERENCE", p, "entity %r does not exist" % h["entity"])
            if h["state"] == "confirmed" and not (h.get("confirmed_on") and h.get("confirmed_by")):
                err("UNATTESTED_CONFIRMATION", p, "confirmed holdings need confirmed_on and confirmed_by")
            if h["state"] == "confirmed" and h.get("confirmed_by") == "synthetic" and not prof.meta["synthetic"]:
                err("SYNTHETIC_IN_REAL_PROFILE", p, "synthetic confirmation in a non-synthetic profile")
            if h.get("acquired_via") and h["acquired_via"] not in rules:
                warn("ACQUISITION_RULE_MISSING", p, "acquired_via %r is not a rule" % h["acquired_via"])
            if h.get("valid_from") and h.get("valid_to") and h["valid_to"] < h["valid_from"]:
                err("BAD_DATES", p, "valid_to is before valid_from")
            if h["state"] == "confirmed" and ents.get(h["entity"], {}).get("kind") == "status" and not h.get("valid_to"):
                warn("STATUS_WITHOUT_EXPIRY", p, "status holding has no valid_to; expiry cannot be tracked")
            if h["state"] != "ended":
                other = seen.get(h["entity"])
                if other and other["state"] != h["state"]:
                    warn("CONFLICTING_HOLDINGS", p, "disagrees with %s about %s" % (other["id"], h["entity"]))
                seen[h["entity"]] = h
        for m in prof.metrics.values():
            if m["state"] == "confirmed" and not m.get("confirmed_by"):
                err("UNATTESTED_CONFIRMATION", store.path("metrics", m["id"], name), "confirmed metrics need confirmed_by")

    # 6. candidates stay self-contained; they may introduce entities but never touch rules
    for c in store.candidates.values():
        p = store.path("candidates", c["id"])
        known = set(ents) | {e["id"] for e in c.get("proposed_entities", [])}
        pr = c["proposed_rule"]
        if pr["output"] not in known:
            err("UNKNOWN_REFERENCE", p, "proposed output %r is neither an entity nor in proposed_entities" % pr["output"])
        check_condition(pr["when"], p, known)
        if pr["kind"] == "acquire" and "retention" not in pr:
            err("MISSING_RETENTION", p, "acquire rules must state retention (use mode 'unknown' if not established)")
        if c["status"] == "proposed" and not c["evidence"]:
            warn("CANDIDATE_WITHOUT_EVIDENCE", p, "candidate has no evidence yet")

    # 7. observations are temporary by construction
    for o in store.observations.values():
        for t in o["tags"]:
            if t not in vocab["tags"]:
                err("UNKNOWN_TAG", store.path("observations", o["id"]), "tag %r is not in vocab" % t)
    return issues


def errors(store):
    return [i for i in lint(store) if i[0] == "ERROR"]
