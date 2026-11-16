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
ENTITY_REVISABLE = ("name", "notes", "tags", "how", "economics", "program", "network", "card", "sources", "election")
REVISABLE = ("valid_from", "valid_to", "restrictions", "open_questions", "value_note", "summary", "review_by", "retention_note",
             "unchecked", "earning")
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


def op_set_credit_terms(store, cs):
    """Set, correct or remove the structured credit terms of a card-benefit rule, or of a candidate still awaiting review.

    The rule's id, condition and output are untouched, so nothing that refers to it (elections, personal records) breaks.
    data.credit is the complete block and replaces the old one: a key left out means "the source does not say"."""
    from .credits import find
    _need("target" in cs, "MISSING_TARGET", "target (the rule id, also for a candidate's proposed rule) is required")
    owner, r, where = find(store, cs["target"])
    _need(r is not None, "UNKNOWN_TARGET", "no rule, and no candidate awaiting review, has the rule id %r" % cs["target"])
    data = cs.get("data") or {}
    remove = data.get("remove") is True
    _need(remove != ("credit" in data), "BAD_DATA", "give data.credit (the complete terms) or data.remove: true, not both and not neither")
    if where == "rule":
        _need(r["verification"]["status"] != "retired", "RETIRED", "retired rules are history; they are not revised")
        _need(cs.get("evidence"), "EVIDENCE_REQUIRED", "changing the published terms of a rule in force needs evidence: "
                                                       "the source they come from, retrieved again or new")
        _need(evidence_ok(store.vocab["evidence_policy"], cs["evidence"]), "INSUFFICIENT_EVIDENCE",
              "the evidence must satisfy the evidence policy")
        _add_evidence(store, cs, r)
    else:
        for e in cs.get("evidence", []):          # a candidate keeps its sources with it; more may be added, never replaced
            old = next((x for x in owner["evidence"] if x["id"] == e["id"]), None)
            _need(old is None or old == e, "EVIDENCE_ID_EXISTS", "evidence id %r already exists with different content" % e["id"])
            _need(e["retrieved_on"] <= cs["date"], "BAD_DATES", "evidence %r retrieved after the changeset date" % e["id"])
            if old is None:
                owner["evidence"].append(e)
    if remove:
        _need("credit" in r, "BAD_STATE", "%s has no credit terms to remove" % cs["target"])
        del r["credit"]
    else:
        _need(isinstance(data["credit"], dict), "BAD_DATA", "data.credit must be an object")
        _need(r.get("credit") != data["credit"], "NO_CHANGE", "%s already has exactly these credit terms" % cs["target"])
        r["credit"] = dict(data["credit"])
    # last_verified is left alone: recording the credit terms is not a re-verification of the whole rule (that is confirm_rule, OP-01)


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
        if k == "election":
            # changing which rules an option governs, or its dates, changes who can be granted what: a reviewer decides
            _need(e["kind"] == "election", "BAD_DATA", "only an election entity has an 'election' block")
            _reviewer(store, _attested(cs))
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
    _need(h["state"] not in ("ended", "withdrawn"), "BAD_STATE", "holding already %s" % h["state"])
    if cs.get("data", {}).get("withdrawn") is True:
        # entered by mistake: kept on file, never in effect on any date. A confirmed record needs its owner to say so;
        # a record nobody confirmed may be withdrawn by a maintainer.
        if h["state"] == "confirmed":
            _attested(cs, by=prof.meta["owner"])
        h["state"], h["withdrawn_on"] = "withdrawn", cs["date"]
        return
    _attested(cs, by=prof.meta["owner"])
    h["state"], h["valid_to"] = "ended", _data(cs, "ended_on", str)


def op_set_metric(store, cs):
    prof = _profile(store, cs)
    m = dict(_data(cs, "metric", dict))
    _need(isinstance(m.get("id"), str), "BAD_DATA", "metric.id missing")
    if m.get("state") == "confirmed":
        m["confirmed_by"] = _attested(cs, by=prof.meta["owner"])["by"]
    store.files[store.path("metrics", m["id"], prof.name)] = m


# ---------------------------------------------------------------- earned benefits (personal, account- and cycle-scoped)
def _owner_confirms(cs, prof, rec, what, always=False):
    """`confirmed` is only ever set from the profile owner's own attestation. Maintainers may record `unconfirmed`."""
    if rec.get("state") == "confirmed" or always:
        a = _attested(cs, by=prof.meta["owner"])
        _need(a["on"] <= cs["date"], "BAD_DATES", "attestation is dated after the changeset")
        if rec.get("state") == "confirmed":
            rec["confirmed_by"], rec["confirmed_on"] = a["by"], a["on"]
    if rec.get("state") != "confirmed":
        _need(rec.get("state") in ("unconfirmed", "superseded"), "BAD_DATA",
              "%s: state must be confirmed (with the owner's attestation) or unconfirmed" % what)
        rec.pop("confirmed_by", None)
        rec.pop("confirmed_on", None)


def _own_account(prof, account):
    h = prof.holdings.get(account)
    _need(h is not None, "UNKNOWN_ACCOUNT",
          "account %r is not a holding in profile %s. Personal progress and earned benefits are recorded only against "
          "that person's own account; record the card with set_holding first (OP-07)" % (account, prof.name))
    return h


def _when(value, what, cs, lo=None, hi=None, code="OUT_OF_CYCLE"):
    """A date field that may be the word unknown. Never in the future; optionally inside a range."""
    from .schema import is_date
    _need(isinstance(value, str) and (value == "unknown" or is_date(value)), "BAD_DATES",
          "%s must be a YYYY-MM-DD date or the word unknown (never a guess)" % what)
    if value != "unknown":
        _need(value <= cs["date"], "FUTURE_DATE", "%s (%s) is after the changeset date %s" % (what, value, cs["date"]))
        _need((lo is None or lo <= value) and (hi is None or value <= hi), code,
              "%s (%s) must fall between %s and %s" % (what, value, lo, hi))
    return value


def _new_reading(cs, prof, qual, reading, period):
    from .earned import cycle_bounds
    start, end = [d.isoformat() for d in cycle_bounds(period, qual["cycle"])]
    r = dict(reading)
    _need(isinstance(r.get("id"), str), "BAD_DATA", "reading.id missing")
    _need(all(x["id"] != r["id"] for x in qual["readings"]), "ID_EXISTS", "reading %r already exists in %s" % (r["id"], qual["id"]))
    _need(isinstance(r.get("value"), (int, float)) and not isinstance(r.get("value"), bool) and r["value"] >= 0, "BAD_VALUE",
          "reading.value must be a number, zero or more")
    if r.get("final"):
        r.setdefault("observed_on", end)
        _need(r["observed_on"] == end and r.get("value_kind", "exact") == "exact", "BAD_READING",
              "a final figure is exact and dated the last day of the cycle (%s)" % end)
        _need(cs["date"] > end, "FINAL_BEFORE_PERIOD_END", "cycle %s does not end until %s; a figure recorded now cannot be final" % (qual["cycle"], end))
    _need("observed_on" in r, "MISSING_DATA", "reading.observed_on is required: the date the figure refers to, or the word unknown")
    _when(r["observed_on"], "reading.observed_on", cs, start, end)
    if r["observed_on"] == "unknown":
        _need(r.get("value_kind") == "at_least", "BAD_READING",
              "a reading with no date can only say 'at least this much': set value_kind to at_least")
    _owner_confirms(cs, prof, r, "reading")
    same = [x["id"] for x in qual["readings"] if x["state"] != "superseded" and x["observed_on"] == r["observed_on"]
            and x["value"] == r["value"] and x.get("value_kind", "exact") == r.get("value_kind", "exact")]
    _need(not same, "DUPLICATE_READING", "reading %s already records %s on %s" % (same[0] if same else "", r["value"], r["observed_on"]))
    r["changeset"] = cs["id"]
    qual["readings"].append(r)
    return r


def op_record_progress(store, cs):
    """Add one dated reading of a person's progress on one of their own accounts in one qualifying cycle."""
    prof = _profile(store, cs)
    account, measure, cycle = _data(cs, "account", str), _data(cs, "measure", str), _data(cs, "cycle", str)
    h = _own_account(prof, account)
    rules = [r for r in store.rules.values() if r["kind"] == "earns" and r["when"].get("holds") == h["entity"]
             and r.get("earn", {}).get("measure") == measure]
    _need(rules, "UNKNOWN_MEASURE", "no earns rule measures %r on %s. Progress is recorded only for a sourced rule" % (measure, h["entity"]))
    _need(len(cycle) == 4 and cycle.isdigit(), "BAD_DATA", "cycle must be a four-digit qualifying year, e.g. 2026")
    qual = next((q for q in prof.qualifications.values() if (q["account"], q["measure"], q["cycle"]) == (account, measure, cycle)), None)
    if qual is None:
        qual = {"id": "q-%s-%s-%s" % (account, measure, cycle), "account": account, "measure": measure, "cycle": cycle, "readings": []}
    _new_reading(cs, prof, qual, _data(cs, "reading", dict), rules[0]["earn"]["period"])
    store.files[store.path("qualifications", qual["id"], prof.name)] = qual


def op_record_entitlement(store, cs):
    """Record that an earned benefit is actually on the person's account, with its own dates. Not implied by progress."""
    prof = _profile(store, cs)
    e = dict(_data(cs, "entitlement", dict))
    _need(isinstance(e.get("id"), str), "BAD_DATA", "entitlement.id missing")
    _need(e["id"] not in prof.entitlements, "ID_EXISTS", "entitlement %r already exists; use revise_entitlement to change it" % e["id"])
    from .credits import is_credit_rule, label_ok
    rule = store.rules.get(e.get("rule", ""))
    recurring = is_credit_rule(rule)      # one allowance period of a recurring card credit, as the account shows it
    _need(rule is not None and (rule["kind"] == "earns" or recurring), "UNKNOWN_RULE",
          "entitlement.rule must name an earns rule, or a rule in force that has credit terms (a candidate is not in force)")
    h = _own_account(prof, e.get("account", ""))
    _need(h["entity"] == rule["when"].get("holds"), "ACCOUNT_MISMATCH",
          "account %s is a %s; rule %s is about %s" % (h["id"], h["entity"], rule["id"], rule["when"].get("holds")))
    _need(e.setdefault("entity", rule["output"]) == rule["output"], "ENTITY_MISMATCH", "rule %s offers %s" % (rule["id"], rule["output"]))
    if recurring:
        _need(isinstance(e.get("cycle"), str) and label_ok(rule["credit"], e["cycle"]), "BAD_PERIOD",
              "cycle must name the allowance period of this %s credit (examples: 2027, 2027-H1, 2027-Q3, 2027-07; for an "
              "anniversary or multi-year period, the year in which it starts)" % rule["credit"]["cycle"])
        _need(isinstance(e.get("allowance"), dict), "MISSING_ALLOWANCE",
              "record the allowance the account shows for this period. Do not copy it from the rule without the owner's word")
    else:
        _need(isinstance(e.get("cycle"), str) and len(e["cycle"]) == 4 and e["cycle"].isdigit(), "BAD_DATA", "cycle must be a four-digit qualifying year")
    for field in ("effective_from", "expires_on"):
        _need(field in e, "MISSING_DATA", "entitlement.%s is required. If it is not known, write the word unknown; do not leave it out "
                                          "and do not copy the rule's general term" % field)
    _need(not e.get("usage"), "BAD_DATA", "record use separately with record_usage")
    same = [o["id"] for o in prof.entitlements.values() if o["state"] != "superseded"
            and (o["rule"], o["account"], o["cycle"]) == (e["rule"], e["account"], e["cycle"])]
    _need(not same, "DUPLICATE_INSTANCE", "%s already records this benefit for this account and cycle; use revise_entitlement" % (same[0] if same else ""))
    _owner_confirms(cs, prof, e, "entitlement")
    store.files[store.path("entitlements", e["id"], prof.name)] = e


ENTITLEMENT_REVISABLE = ("effective_from", "expires_on", "ended_on", "end_reason", "allowance", "basis", "notes", "state")


def op_revise_entitlement(store, cs):
    """Correct or end an earned benefit record. The earlier version is kept in data/audit/previous/."""
    prof = _profile(store, cs)
    _need("target" in cs, "MISSING_TARGET", "target (entitlement id) is required")
    e = prof.entitlements.get(cs["target"])
    _need(e is not None, "UNKNOWN_TARGET", "no entitlement %r in profile %s" % (cs["target"], prof.name))
    changes = _data(cs, "set", dict)
    _need(changes, "MISSING_DATA", "data.set is empty")
    was_confirmed = e["state"] == "confirmed"
    for k, v in changes.items():
        _need(k in ENTITLEMENT_REVISABLE, "FIELD_NOT_REVISABLE",
              "%r cannot be revised (allowed: %s). The rule, account and cycle of a record never change: "
              "withdraw it (state: superseded) and record a new one." % (k, ", ".join(ENTITLEMENT_REVISABLE)))
        if v is None:
            e.pop(k, None)
        else:
            e[k] = v
    _owner_confirms(cs, prof, e, "entitlement", always=was_confirmed)
    if was_confirmed and e["state"] == "confirmed":
        e["confirmed_on"] = cs["attestation"]["on"]     # the owner has re-confirmed the record as it now stands


def _transaction_cap(store, e):
    c = store.rules.get(e["rule"], {}).get("credit") or {}
    return c["max_per_transaction"] if isinstance(c.get("max_per_transaction"), (int, float)) else None


def _new_usage(cs, prof, e, usage, cap=None):
    u = dict(usage)
    _need("allowance" in e, "NO_ALLOWANCE", "%s has no consumable allowance; use cannot be recorded against it" % e["id"])
    _need(e["state"] != "superseded", "BAD_STATE", "entitlement %s was withdrawn" % e["id"])
    _need(isinstance(u.get("id"), str), "BAD_DATA", "usage.id missing")
    _need(all(x["id"] != u["id"] for x in e.get("usage", [])), "ID_EXISTS", "usage %r already exists on %s" % (u["id"], e["id"]))
    _need(isinstance(u.get("amount"), (int, float)) and not isinstance(u.get("amount"), bool) and u["amount"] > 0, "BAD_VALUE",
          "usage.amount must be a number greater than zero")
    _need(cap is None or u["amount"] <= cap, "USE_EXCEEDS_TRANSACTION_CAP",
          "one use of %s is more than the published maximum of %s per transaction. Record each transaction separately; "
          "if the account really shows one credit above the maximum, escalate" % (u.get("amount"), cap))
    _need("used_on" in u, "MISSING_DATA", "usage.used_on is required: the date of use, or the word unknown")
    _when(u["used_on"], "usage.used_on", cs)
    _owner_confirms(cs, prof, u, "usage")
    live = [x for x in e.get("usage", []) if x["state"] != "superseded"]
    same = [x["id"] for x in live if (x["amount"], x["used_on"], x.get("basis", "")) == (u["amount"], u["used_on"], u.get("basis", ""))]
    _need(not same, "DUPLICATE_USAGE", "usage %s already records %s on %s. If this is a second, separate use, say so in 'basis'"
          % (same[0] if same else "", u["amount"], u["used_on"]))
    total = sum(x["amount"] for x in live if x["state"] == "confirmed") + (u["amount"] if u["state"] == "confirmed" else 0)
    _need(total <= e["allowance"]["amount"], "USAGE_EXCEEDS_ALLOWANCE",
          "confirmed use would total %s against an allowance of %s. Check the amounts, or correct the allowance first"
          % (total, e["allowance"]["amount"]))
    u["changeset"] = cs["id"]
    e.setdefault("usage", []).append(u)
    return u


def op_record_usage(store, cs):
    """Record one use of a consumable benefit. Allowance, used and remaining stay separate; remaining is computed."""
    prof = _profile(store, cs)
    _need("target" in cs, "MISSING_TARGET", "target (entitlement id) is required")
    e = prof.entitlements.get(cs["target"])
    _need(e is not None, "UNKNOWN_TARGET", "no entitlement %r in profile %s" % (cs["target"], prof.name))
    _new_usage(cs, prof, e, _data(cs, "usage", dict), _transaction_cap(store, e))


def op_correct_entry(store, cs):
    """Withdraw one reading or one usage entry, optionally replacing it. The old entry stays, marked superseded."""
    prof = _profile(store, cs)
    kind, rec_id, entry_id = _data(cs, "record", str), _data(cs, "id", str), _data(cs, "entry", str)
    _need(kind in ("qualification", "entitlement"), "BAD_DATA", "data.record must be qualification or entitlement")
    rec = (prof.qualifications if kind == "qualification" else prof.entitlements).get(rec_id)
    _need(rec is not None, "UNKNOWN_TARGET", "no %s %r in profile %s" % (kind, rec_id, prof.name))
    entries = rec["readings"] if kind == "qualification" else rec.get("usage", [])
    old = next((x for x in entries if x["id"] == entry_id), None)
    _need(old is not None, "UNKNOWN_TARGET", "no entry %r in %s" % (entry_id, rec_id))
    _need(old["state"] != "superseded", "BAD_STATE", "entry %s was already superseded" % entry_id)
    if old["state"] == "confirmed":
        _attested(cs, by=prof.meta["owner"])    # undoing an owner-confirmed fact needs the owner
    old["state"] = "superseded"
    new = cs.get("data", {}).get("replacement")
    if new is not None:
        if kind == "qualification":
            rule = next(r for r in store.rules.values() if r["kind"] == "earns" and r.get("earn", {}).get("measure") == rec["measure"])
            added = _new_reading(cs, prof, rec, new, rule["earn"]["period"])
        else:
            added = _new_usage(cs, prof, rec, new, _transaction_cap(store, rec))
        old["superseded_by"] = added["id"]


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
