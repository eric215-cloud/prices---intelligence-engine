"""Whole-store validation. A store with any ERROR must never be written to disk.

Each issue is (severity, code, path, message). Codes are stable so maintainers and
tests can match on them.
"""
from .engine import NON_DERIVING, leaves
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


NOT_HOLDABLE = ("organization", "network_tier")
ROLES = ("cobrand_partner", "program_manager", "issuer", "capital_provider", "network", "network_tier")


def single_holds(cond):
    """The entity id if the condition is exactly {"holds": id}, else None."""
    return cond.get("holds") if set(cond) == {"holds"} else None


def shape_issues(rule, kind_of):
    """Structural checks shared by rules and candidates. kind_of(id) -> entity kind or None."""
    out = []
    subject, target = single_holds(rule["when"]), rule["output"]
    if rule["kind"] == "baseline":
        if kind_of(subject) != "network_tier" or kind_of(target) != "benefit":
            out.append(("BAD_BASELINE_SHAPE", "a baseline rule is exactly: when {\"holds\": <network_tier>} -> output <benefit>"))
    elif rule["kind"] == "excludes":
        if kind_of(subject) != "card" or kind_of(target) != "benefit":
            out.append(("BAD_EXCLUSION_SHAPE", "an excludes rule is exactly: when {\"holds\": <card>} -> output <benefit>"))
        sb = rule.get("superseded_by")
        if sb is not None and (kind_of(sb) != "benefit" or sb == target):
            out.append(("BAD_EXCLUSION_SHAPE", "superseded_by must be a different benefit entity"))
    else:
        refs = [i for k, i, _n in leaves(rule["when"]) if k == "holds"] + [target]
        refs += [i for k, i, _n in leaves(rule.get("retention", {}).get("retain_when", {"all": []})) if k == "holds"]
        bad = sorted({i for i in refs if kind_of(i) in NOT_HOLDABLE})
        if bad:
            out.append(("TIER_INHERITANCE", "%s: an organization or network tier never confers or receives an entitlement. "
                        "State the benefit for the specific card, with card-specific evidence" % ", ".join(bad)))
        if "superseded_by" in rule:
            out.append(("UNEXPECTED_FIELD", "superseded_by belongs only on excludes rules"))
    return out


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
        if "network" in e and (e["kind"] != "network_tier" or ents.get(e["network"], {}).get("kind") != "organization"):
            err("BAD_ROLE", p, "'network' belongs on a network_tier entity and must name an organization")
        for sid in e.get("sources", []):
            if sid not in evid:
                err("UNKNOWN_REFERENCE", p, "source %r is not an evidence record" % sid)
        if "card" in e:
            if e["kind"] != "card":
                err("BAD_ROLE", p, "a 'card' block is only allowed on entities of kind card")
            for role in ROLES:
                ref = e["card"].get(role)
                if ref is None:
                    continue   # missing = not recorded, null = recorded as none
                want = "network_tier" if role == "network_tier" else "organization"
                if ents.get(ref, {}).get("kind") != want:
                    err("BAD_ROLE", p, "%s %r must be an existing entity of kind %s" % (role, ref, want))
            tier, net = ents.get(e["card"].get("network_tier") or "", {}), e["card"].get("network")
            if tier.get("network") and net and tier["network"] != net:
                err("BAD_ROLE", p, "network_tier %s belongs to network %s, not %s" % (tier["id"], tier["network"], net))
            if any(e["card"].get(r) for r in ROLES) and not e.get("sources"):
                warn("CARD_WITHOUT_SOURCE", p, "card roles are recorded but the card lists no sources")
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
        for code, msg in shape_issues(r, lambda i: ents.get(i, {}).get("kind")):
            err(code, p, msg)
        if contradictory(r["when"]):
            err("CONTRADICTORY_CONDITION", p, "an 'all' both requires and excludes the same entity; rule can never apply")
        if r["kind"] == "acquire" and "retention" not in r:
            err("MISSING_RETENTION", p, "acquire rules must state retention (use mode 'unknown' if not established)")
        if r["kind"] != "acquire" and "retention" in r:
            err("UNEXPECTED_RETENTION", p, "only acquire rules have retention; grants/transfer last while the condition holds")
        if r["kind"] != "transfer" and "transfer" in r:
            err("UNEXPECTED_FIELD", p, "a 'transfer' block belongs only on transfer rules")
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
        if r["kind"] in NON_DERIVING:
            continue
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
            if ents.get(h["entity"], {}).get("kind") in NOT_HOLDABLE:
                err("NOT_HOLDABLE", p, "%s is an organization or network tier; a person holds cards, not tiers" % h["entity"])
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
        if c["status"] == "proposed":
            kinds = {e["id"]: e["kind"] for e in c.get("proposed_entities", [])}
            for code, msg in shape_issues(pr, lambda i: ents.get(i, {}).get("kind") or kinds.get(i)):
                err(code, p, msg)
        if pr["kind"] == "acquire" and "retention" not in pr:
            err("MISSING_RETENTION", p, "acquire rules must state retention (use mode 'unknown' if not established)")
        if c["status"] == "proposed" and not c["evidence"]:
            warn("CANDIDATE_WITHOUT_EVIDENCE", p, "candidate has no evidence yet")

    # 6b. evidence scope labels must point at real entities
    for e in evid.values():
        for ref in e.get("applies_to", []):
            if ref not in ents:
                err("UNKNOWN_REFERENCE", store.path("evidence", e["id"]), "applies_to %r is not an entity" % ref)

    # 6c. network-tier benefits apply to a card only on positive, card-specific evidence
    live = [r for r in rules.values() if r["verification"]["status"] != "retired"]
    baseline_benefits = {r["output"] for r in live if r["kind"] == "baseline"}

    def overlap(a, b):
        lo = max(a.get("valid_from") or "0000-00-00", b.get("valid_from") or "0000-00-00")
        hi = min(a.get("valid_to") or "9999-12-31", b.get("valid_to") or "9999-12-31")
        return lo <= hi

    stance = {}
    for r in live:
        p = store.path("rules", r["id"])
        subject = single_holds(r["when"])
        if r["kind"] in ("grants", "excludes") and ents.get(subject, {}).get("kind") == "card":
            for other in stance.get((subject, r["output"]), []):
                if other["kind"] != r["kind"] and overlap(other, r):
                    err("CONFLICTING_APPLICABILITY", p, "%s both grants and excludes %s for %s (see rule %s). Retire one"
                        % (subject, r["output"], subject, other["id"]))
            stance.setdefault((subject, r["output"]), []).append(r)
        if r["verification"]["status"] != "verified":
            continue
        if r["kind"] == "excludes":
            about = {subject}
        elif r["kind"] not in NON_DERIVING and r["output"] in baseline_benefits:
            about = {i for k, i, neg in leaves(r["when"]) if k == "holds" and not neg}
        else:
            continue
        specific = [evid[e] for e in r["evidence"] if e in evid and about & set(evid[e].get("applies_to", []))]
        if not evidence_ok(policy, specific):
            err("CARD_SPECIFIC_EVIDENCE_REQUIRED", p,
                "%s is a network-tier benefit or an exclusion: this rule needs evidence whose applies_to names %s "
                "(the card's own guide or terms). A network's general page, or the absence of an opt-out, proves nothing"
                % (r["output"], " or ".join(sorted(about))))
        if r["kind"] == "excludes" and r.get("superseded_by"):
            if not any(o["kind"] == "grants" and single_holds(o["when"]) == subject and o["output"] == r["superseded_by"] for o in live):
                warn("SUPERSEDING_BENEFIT_NOT_GRANTED", p, "%s is said to be superseded by %s, but no rule grants that to %s"
                     % (r["output"], r["superseded_by"], subject))

    # 7. observations are temporary by construction
    for o in store.observations.values():
        for t in o["tags"]:
            if t not in vocab["tags"]:
                err("UNKNOWN_TAG", store.path("observations", o["id"]), "tag %r is not in vocab" % t)
    return issues


def errors(store):
    return [i for i in lint(store) if i[0] == "ERROR"]
