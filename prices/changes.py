"""Maintenance pipeline. The ONLY way records change.

    stage()  = validate changeset -> apply to an in-memory copy -> lint the copy -> impact report
    apply()  = stage(), then write files and append to the audit log only if everything passed

A rejected changeset changes no record. Each operation (op) may touch only the
fields listed in its handler; anything else is rejected with a stable error code.
Operation cards for maintainers: docs/operations/.
"""
import datetime
import hashlib
import json
import os

from .engine import evaluate, to_date
from .lint import errors, evidence_ok, lint, signature
from .review import diff, new_flags
from .schema import Schema
from .store import LEDGER_PATH, Store, append_audit, read_audit

RANK = {"ESTABLISHED": 3, "CONDITIONAL": 2, "UNRESOLVED": 1, "NOT_AVAILABLE": 0}
ENTITY_REVISABLE = ("name", "notes", "tags", "how", "economics", "program", "network", "card", "sources")
REVISABLE = ("valid_from", "valid_to", "restrictions", "open_questions", "value_note", "summary", "review_by", "retention_note")
MAX_REVIEW_DAYS = 400


class Reject(Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, "%s: %s" % (code, msg))
        self.code, self.msg = code, msg


def _need(cond, code, msg):
    if not cond:
        raise Reject(code, msg)


def _data(cs, key, typ=None):
    d = cs.get("data", {})
    _need(key in d, "MISSING_DATA", "data.%s is required for op %s" % (key, cs["op"]))
    if typ is not None:
        _need(isinstance(d[key], typ), "BAD_DATA", "data.%s has the wrong type" % key)
    return d[key]


def _rule(store, cs):
    _need("target" in cs, "MISSING_TARGET", "target (rule id) is required")
    r = store.rules.get(cs["target"])
    _need(r is not None, "UNKNOWN_TARGET", "no rule %r" % cs["target"])
    return r


def _add_evidence(store, cs, rule=None):
    ids = []
    for e in cs.get("evidence", []):
        _need(store.evidence.get(e["id"], e) == e, "EVIDENCE_ID_EXISTS",
              "evidence id %r already exists with different content; evidence is never overwritten" % e["id"])
        _need(e["retrieved_on"] <= cs["date"], "BAD_DATES", "evidence %r retrieved after the changeset date" % e["id"])
        store.files[store.path("evidence", e["id"])] = e
        ids.append(e["id"])
    if rule is not None:
        rule["evidence"] = rule["evidence"] + [i for i in ids if i not in rule["evidence"]]
    return ids


def _review_by(cs):
    rb = _data(cs, "review_by", str)
    d0 = to_date(cs["date"])
    try:
        d1 = to_date(rb)
    except ValueError:
        raise Reject("BAD_DATES", "data.review_by is not a date")
    _need(d0 < d1 <= d0 + datetime.timedelta(days=MAX_REVIEW_DAYS), "BAD_DATES",
          "review_by must be after the changeset date and at most %d days later" % MAX_REVIEW_DAYS)
    return rb


def _attested(cs, by=None):
    a = cs.get("attestation")
    _need(a is not None, "ATTESTATION_REQUIRED", "op %s needs an attestation {by, on, statement}" % cs["op"])
    if by is not None:
        _need(a["by"].strip().lower() == by.strip().lower(), "OWNER_ATTESTATION_REQUIRED",
              "attestation must be by the profile owner %r, not %r" % (by, a["by"]))
    return a


def _profile(store, cs):
    _need("profile" in cs, "MISSING_PROFILE", "profile is required")
    _need(cs["profile"] in store.profile_names(), "UNKNOWN_PROFILE", "no profile %r" % cs["profile"])
    return store.profile(cs["profile"])


# ---------------------------------------------------------------- handlers
def op_confirm_rule(store, cs):
    r = _rule(store, cs)
    _need(r["verification"]["status"] == "verified", "NOT_VERIFIED", "only verified rules can be re-confirmed; use promote/flag")
    _need(cs.get("evidence"), "EVIDENCE_REQUIRED", "re-confirmation needs fresh evidence")
    _need(evidence_ok(store.vocab["evidence_policy"], cs["evidence"]), "INSUFFICIENT_EVIDENCE",
          "fresh evidence must by itself satisfy the evidence policy")
    last = r["verification"].get("last_verified", "0000-00-00")
    _need(all(e["retrieved_on"] >= last for e in cs["evidence"]), "STALE_EVIDENCE",
          "evidence must be retrieved on or after the previous verification (%s)" % last)
    rb = _review_by(cs)
    _add_evidence(store, cs, r)
    r["verification"].update({"last_verified": cs["date"], "review_by": rb})


def op_revise_rule(store, cs):
    r = _rule(store, cs)
    _need(r["verification"]["status"] != "retired", "RETIRED", "retired rules are history; they are not revised")
    changes = _data(cs, "set", dict)
    _need(changes, "MISSING_DATA", "data.set is empty")
    for k in changes:
        _need(k in REVISABLE, "FIELD_NOT_REVISABLE",
              "%r cannot be revised (allowed: %s). Changes to kind/output/when/retention.mode are new "
              "relationships: use add_candidate and escalate." % (k, ", ".join(REVISABLE)))
    _need(cs.get("evidence"), "EVIDENCE_REQUIRED", "a revision needs evidence")
    _need(evidence_ok(store.vocab["evidence_policy"], cs["evidence"]), "INSUFFICIENT_EVIDENCE",
          "revision evidence must satisfy the evidence policy")
    _add_evidence(store, cs, r)
    for k, v in changes.items():
        if k == "review_by":
            r["verification"]["review_by"] = v
        elif k == "retention_note":
            _need("retention" in r, "BAD_DATA", "rule has no retention block")
            r["retention"]["note"] = v
        else:
            r[k] = v
    if r["verification"]["status"] == "verified":
        r["verification"]["last_verified"] = cs["date"]


def op_flag_rule(store, cs):
    r = _rule(store, cs)
    _need(r["verification"]["status"] != "retired", "RETIRED", "rule is already retired")
    qs = _data(cs, "open_questions", list)
    _need(qs and all(isinstance(q, str) and q.strip() for q in qs), "BAD_DATA", "open_questions must be non-empty strings")
    r["verification"]["status"] = "unverified"
    r["open_questions"] = r.get("open_questions", []) + qs
    _add_evidence(store, cs, r)


def op_retire_rule(store, cs):
    r = _rule(store, cs)
    _need(r["verification"]["status"] != "retired", "RETIRED", "rule is already retired")
    ended = _data(cs, "ended_on", str)
    _need(cs.get("evidence") or cs.get("attestation"), "EVIDENCE_REQUIRED", "retirement needs evidence or an attestation")
    _add_evidence(store, cs, r)
    r["verification"]["status"] = "retired"
    r["valid_to"] = ended


def op_add_evidence(store, cs):
    r = _rule(store, cs)
    _need(cs.get("evidence"), "EVIDENCE_REQUIRED", "nothing to add")
    _add_evidence(store, cs, r)


def op_add_entity(store, cs):
    e = _data(cs, "entity", dict)
    _need(isinstance(e.get("id"), str), "BAD_DATA", "entity.id missing")
    _need(e["id"] not in store.entities, "ID_EXISTS", "entity %r already exists" % e["id"])
    _add_evidence(store, cs)   # sources the entity cites may be registered in the same changeset
    store.files[store.path("entities", e["id"])] = e


def op_revise_entity(store, cs):
    """Change descriptive fields of an entity. Its id and kind are permanent."""
    _need("target" in cs, "MISSING_TARGET", "target (entity id) is required")
    e = store.entities.get(cs["target"])
    _need(e is not None, "UNKNOWN_TARGET", "no entity %r" % cs["target"])
    changes = _data(cs, "set", dict)
    _need(changes, "MISSING_DATA", "data.set is empty")
    for k, v in changes.items():
        _need(k in ENTITY_REVISABLE, "FIELD_NOT_REVISABLE",
              "%r cannot be revised (allowed: %s). An entity's id and kind never change: add a new entity instead."
              % (k, ", ".join(ENTITY_REVISABLE)))
        if k == "sources":
            _need(isinstance(v, list) and set(e.get("sources", [])) <= set(v), "EVIDENCE_REMOVED",
                  "sources may be added to an entity, never removed")
    _add_evidence(store, cs)
    for k, v in changes.items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = v


def _reviewer(store, a):
    reviewers = store.vocab.get("promotion_reviewers") or []
    _need(not reviewers or a["by"] in reviewers, "REVIEWER_NOT_AUTHORIZED",
          "only %s may do this; escalate to one of them" % ", ".join(reviewers))


def _sha(obj):
    return None if obj is None else hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def op_revert_changeset(store, cs, previous=None):
    """Put back exactly what one earlier changeset replaced. Refused if anything it touched has changed since."""
    target = _data(cs, "changeset", str)
    _reviewer(store, _attested(cs))
    _need(previous is not None, "SNAPSHOT_UNAVAILABLE", "revert needs the audit directory; run it through `prices apply`")
    snap = previous(target)
    _need(snap is not None, "UNKNOWN_TARGET", "no before-snapshot for changeset %r in data/audit/previous/" % target)
    for path, rec in sorted(snap["records"].items()):
        _need(_sha(store.files.get(path)) == rec["after"], "LATER_CHANGES",
              "%s has changed since %s was applied; revert the later changeset first" % (path, target))
    for path, rec in snap["records"].items():
        if rec["before"] is None:
            store.files.pop(path, None)
        else:
            store.files[path] = rec["before"]


def op_add_candidate(store, cs):
    c = _data(cs, "candidate", dict)
    errs = Schema().validate(c, "candidate")
    _need(not errs, "SCHEMA", "; ".join(errs))
    _need(c["id"] not in store.candidates, "ID_EXISTS", "candidate %r already exists" % c["id"])
    _need(c["status"] == "proposed", "BAD_DATA", "new candidates must have status 'proposed'")
    sig = signature(c["proposed_rule"])
    for r in store.rules.values():
        _need(r["verification"]["status"] == "retired" or signature(r) != sig, "DUPLICATE_RELATIONSHIP",
              "rule %s already records %s" % (r["id"], sig))
    for o in store.candidates.values():
        _need(o["status"] != "proposed" or signature(o["proposed_rule"]) != sig, "DUPLICATE_RELATIONSHIP",
              "candidate %s already proposes %s" % (o["id"], sig))
    store.files[store.path("candidates", c["id"])] = c


def op_promote_candidate(store, cs):
    _need("target" in cs, "MISSING_TARGET", "target (candidate id) is required")
    c = store.candidates.get(cs["target"])
    _need(c is not None, "UNKNOWN_TARGET", "no candidate %r" % cs["target"])
    _need(c["status"] == "proposed", "BAD_STATE", "candidate is %s" % c["status"])
    a = _attested(cs)
    _reviewer(store, a)
    if c["open_questions"]:
        _need(cs.get("data", {}).get("accept_open_questions") is True, "OPEN_QUESTIONS",
              "candidate has open questions; resolve them or set data.accept_open_questions=true (they stay on the rule)")
    rb = _review_by(cs)
    for e in c.get("proposed_entities", []):
        cur = store.entities.get(e["id"])
        _need(cur is None or cur == e, "ID_EXISTS", "entity %r exists with different content" % e["id"])
        store.files[store.path("entities", e["id"])] = e
    ev_ids = []
    for e in c["evidence"]:
        _need(store.evidence.get(e["id"], e) == e, "EVIDENCE_ID_EXISTS",
              "evidence id %r already exists with different content" % e["id"])
        store.files[store.path("evidence", e["id"])] = e
        ev_ids.append(e["id"])
    rule = dict(c["proposed_rule"])
    _need(rule["id"] not in store.rules, "ID_EXISTS", "rule %r already exists" % rule["id"])
    rule["evidence"] = ev_ids
    rule["verification"] = {"status": "verified", "last_verified": cs["date"], "review_by": rb}
    if c["open_questions"]:
        rule["open_questions"] = list(c["open_questions"])
    store.files[store.path("rules", rule["id"])] = rule
    c["status"] = "promoted"
    c["review"] = {"decided_on": cs["date"], "decided_by": a["by"], "reason": cs["reason"], "rule": rule["id"]}


def op_reject_candidate(store, cs):
    _need("target" in cs, "MISSING_TARGET", "target (candidate id) is required")
    c = store.candidates.get(cs["target"])
    _need(c is not None, "UNKNOWN_TARGET", "no candidate %r" % cs["target"])
    _need(c["status"] == "proposed", "BAD_STATE", "candidate is %s" % c["status"])
    c["status"] = "rejected"
    c["review"] = {"decided_on": cs["date"], "decided_by": cs["author"], "reason": cs["reason"]}


def op_set_holding(store, cs):
    prof = _profile(store, cs)
    h = dict(_data(cs, "holding", dict))
    _need(isinstance(h.get("id"), str), "BAD_DATA", "holding.id missing")
    if h.get("state") == "confirmed":
        a = _attested(cs, by=prof.meta["owner"])
        h["confirmed_by"], h["confirmed_on"] = a["by"], a["on"]
    else:
        _need(h.get("state") == "unconfirmed", "BAD_DATA", "set_holding accepts state confirmed or unconfirmed; use end_holding to end")
        h.pop("confirmed_by", None)
        h.pop("confirmed_on", None)
    store.files[store.path("holdings", h["id"], prof.name)] = h


def op_end_holding(store, cs):
    prof = _profile(store, cs)
    _need("target" in cs, "MISSING_TARGET", "target (holding id) is required")
    h = prof.holdings.get(cs["target"])
    _need(h is not None, "UNKNOWN_TARGET", "no holding %r in profile %s" % (cs["target"], prof.name))
    _need(h["state"] != "ended", "BAD_STATE", "holding already ended")
    _attested(cs, by=prof.meta["owner"])
    h["state"], h["valid_to"] = "ended", _data(cs, "ended_on", str)


def op_set_metric(store, cs):
    prof = _profile(store, cs)
    m = dict(_data(cs, "metric", dict))
    _need(isinstance(m.get("id"), str), "BAD_DATA", "metric.id missing")
    if m.get("state") == "confirmed":
        m["confirmed_by"] = _attested(cs, by=prof.meta["owner"])["by"]
    store.files[store.path("metrics", m["id"], prof.name)] = m


def op_record_discovery_run(store, cs):
    run = _data(cs, "run", dict)
    errs = Schema().validate(run, "discovery_run")
    _need(not errs, "SCHEMA", "; ".join(errs))
    _need(run["id"] not in store.discovery_runs, "ID_EXISTS", "run %r already recorded" % run["id"])
    store.files[store.path("discovery_runs", run["id"])] = run
    ledger = {"cells": dict(store.ledger["cells"])}
    for c in run["cells"]:
        for cid in c.get("candidates", []):
            _need(cid in store.candidates, "UNKNOWN_REFERENCE", "cell %s cites unknown candidate %r" % (c["cell"], cid))
        _need(c["outcome"] != "found" or c.get("candidates"), "BAD_DATA", "outcome 'found' must cite candidates")
        ledger["cells"][c["cell"]] = {"last_run": run["date"], "run": run["id"], "outcome": c["outcome"],
                                      "candidates": c.get("candidates", []), "note": c.get("note", "")}
    store.files[LEDGER_PATH] = ledger


def op_add_observation(store, cs):
    o = _data(cs, "observation", dict)
    _need(isinstance(o.get("id"), str), "BAD_DATA", "observation.id missing")
    _need(o["id"] not in store.observations, "ID_EXISTS", "observation %r exists" % o["id"])
    _need(str(o.get("valid_to", "")) >= cs["date"], "ALREADY_EXPIRED", "observation is already expired")
    if o.get("type") == "availability":
        o = dict(o, confirmed_by=_attested(cs)["by"])
    store.files[store.path("observations", o["id"])] = o


def op_prune_observations(store, cs):
    for o in list(store.observations.values()):
        if o["valid_to"] < cs["date"]:
            del store.files[store.path("observations", o["id"])]


HANDLERS = {name[3:]: fn for name, fn in list(globals().items()) if name.startswith("op_")}


# ---------------------------------------------------------------- pipeline
def stage(store, cs, applied_ids=(), previous=None):
    """Validate and apply to a copy. Returns a dict; never touches disk or the input store.

    previous: optional function(changeset_id) -> before-snapshot, needed only by revert_changeset.
    """
    def rejected(errs):
        return {"ok": False, "errors": errs, "changed": [], "impact": {}, "review_needed": False}

    errs = Schema().validate(cs, "changeset")
    if errs:
        return rejected(["SCHEMA: " + e for e in errs])
    pre = errors(store)
    if pre:
        return rejected(["STORE_ALREADY_INVALID: fix or escalate before applying changes: %s %s %s" % (i[1], i[2], i[3]) for i in pre[:5]])
    if cs["id"] in applied_ids:
        return rejected(["DUPLICATE_CHANGESET: %s was already applied" % cs["id"]])
    new = store.copy()
    try:
        if cs["op"] == "revert_changeset":
            op_revert_changeset(new, cs, previous)
        else:
            HANDLERS[cs["op"]](new, cs)
    except Reject as e:
        return rejected([str(e)])
    post = [i for i in lint(new) if i[0] == "ERROR"]
    if post:
        return rejected(["%s: %s: %s" % (i[1], i[2], i[3]) for i in post])
    impact, review_needed = {}, False
    for name in new.profile_names():
        if name not in store.profile_names():
            continue
        a, b = evaluate(store, name, cs["date"]), evaluate(new, name, cs["date"])
        changes, flags = diff(a, b), new_flags(a, b)
        if changes or flags:
            impact[name] = {"changes": changes, "new_flags": flags}
        # review is needed when something got weaker, or a review-severity flag appeared
        if any(RANK[c["after"]] < RANK[c["before"]] for c in changes) or any(f["severity"] == "review" for f in flags):
            review_needed = True
    return {"ok": True, "errors": [], "store": new, "changed": store.changed_paths(new),
            "impact": impact, "review_needed": review_needed}


def previous_loader(root):
    """Function returning the before-snapshot saved when a changeset was applied (or None)."""
    def load(cs_id):
        path = os.path.join(root, "data/audit/previous", "%s.json" % cs_id)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return load


def _entry(cs, out, before):
    meta = cs if isinstance(cs, dict) else {}
    return {"changeset": meta.get("id"), "op": meta.get("op"), "author": meta.get("author"), "date": meta.get("date"),
            "result": "applied" if out["ok"] else "rejected", "errors": out["errors"], "changed": out["changed"],
            "review_needed": out["review_needed"], "digest_before": before.digest()}


def apply_many(root, changesets, dry_run=False):
    """Apply a list of changesets in order, all or nothing.

    Every changeset is staged in memory on top of the previous one. Files are written only
    after the whole list has passed, so a failure anywhere leaves every record untouched.
    For each applied changeset three things are kept under data/audit/: the log line, a copy
    of the changeset, and a before-snapshot of every record it replaced (previous/<id>.json).
    """
    start = Store.load(root)
    applied = {e["changeset"] for e in read_audit(root) if e.get("result") == "applied"}
    loader, cur, staged = previous_loader(root), start, []
    for index, cs in enumerate(changesets):
        out = stage(cur, cs, applied, loader)
        if not out["ok"]:
            if not dry_run:
                append_audit(root, dict(_entry(cs, out, cur), batch_size=len(changesets), batch_index=index))
            return dict(out, results=[], failed_index=index, failed_id=cs.get("id") if isinstance(cs, dict) else None)
        staged.append((cs, cur, out))
        cur = out["store"]
        applied.add(cs["id"])
    results = [{"id": cs["id"], "op": cs["op"], "changed": out["changed"], "impact": out["impact"],
                "review_needed": out["review_needed"]} for cs, _b, out in staged]
    summary = {"ok": True, "errors": [], "results": results, "changed": start.changed_paths(cur),
               "review_needed": any(r["review_needed"] for r in results), "store": cur}
    if dry_run:
        return dict(summary, dry_run=True)
    extra = {}
    for cs, before, out in staged:
        extra["data/audit/changesets/%s.json" % cs["id"]] = cs
        extra["data/audit/previous/%s.json" % cs["id"]] = {
            "changeset": cs["id"],
            "records": {p: {"before": before.files.get(p), "after": _sha(out["store"].files.get(p))} for p in out["changed"]}}
    Store(dict(cur.files, **extra)).save(root, summary["changed"] + sorted(extra))
    for cs, before, out in staged:
        append_audit(root, dict(_entry(cs, out, before), digest_after=out["store"].digest()))
    return summary


def apply(root, cs, dry_run=False):
    """Apply one changeset. Same guarantees as apply_many."""
    many = apply_many(root, [cs], dry_run=dry_run)
    if not many["ok"]:
        out = {k: many[k] for k in ("ok", "errors", "changed", "impact", "review_needed")}
    else:
        one = many["results"][0]
        out = {"ok": True, "errors": [], "changed": one["changed"], "impact": one["impact"],
               "review_needed": one["review_needed"], "store": many["store"]}
    if dry_run:
        out["dry_run"] = True
    return out
