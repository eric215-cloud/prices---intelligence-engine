"""Deterministic eligibility engine.

Atoms
    have:<entity>      the person holds / is entitled to the entity on the as-of date
    can_get:<entity>   the person is eligible to ACQUIRE the entity (has not done so yet)

The same forward-chaining is run at four assumption levels. A level decides which
kinds of "assumption tokens" a derivation may contain:

    E  established   no assumptions          confirmed facts + verified rules only
    P  possible-now  unknowns                + unconfirmed facts, unverified rules
    C  achievable    actions, acquisitions   + things the person could go and do
    U  anything      all of the above

Status of an atom: ESTABLISHED if derivable at E, else CONDITIONAL if derivable at C,
else UNRESOLVED if derivable at U, else NOT_AVAILABLE.

Every derivation starts from base facts (holdings, metrics) and only grows upward,
so a cycle of rules can never establish anything by itself (least fixed point).
For each atom the engine keeps the derivation needing the fewest assumptions.
"""
import datetime

E, P, C, U = "E", "P", "C", "U"
LEVELS = (E, P, C, U)
ALLOWED = {E: (), P: ("unknown",), C: ("action", "acquire"), U: ("unknown", "action", "acquire")}
ESTABLISHED, CONDITIONAL, UNRESOLVED, NOT_AVAILABLE = "ESTABLISHED", "CONDITIONAL", "UNRESOLVED", "NOT_AVAILABLE"
NONE = frozenset()
# Rule kinds that record a sourced statement but never derive anything:
#   baseline  "network tier T advertises benefit B"   (says nothing about any particular card)
#   excludes  "card C does not carry benefit B"       (optionally superseded_by a better card benefit)
NON_DERIVING = ("baseline", "excludes")
# Rule kinds whose effect depends on a person's own dated records and is computed in earned.py:
#   earns     "reach a threshold on this card within a period and benefit X is on offer"
# The generic solver below never fires them; a threshold being met is never, by itself, a benefit held.
PERSONAL_KINDS = ("earns",)


def to_date(s):
    if isinstance(s, datetime.date):
        return s
    return datetime.date.fromisoformat(s) if s else None


def in_effect(rec, as_of):
    f, t = to_date(rec.get("valid_from")), to_date(rec.get("valid_to"))
    return (f is None or f <= as_of) and (t is None or as_of <= t)


def standing(rule):
    """The verification status a rule is evaluated with.

    A rule retired because the relationship ENDED keeps answering for dates up to its valid_to, with the status it
    had (verification.retired_from): retiring it must not erase what was true before. A rule retired as never true
    (no retired_from) answers for no date."""
    v = rule["verification"]
    if v["status"] == "retired" and v.get("retired_from") and rule.get("valid_to"):
        return v["retired_from"]
    return v["status"]


def leaves(cond, neg=False):
    """Yield (kind, id, negated) for every leaf of a condition."""
    if "holds" in cond:
        yield ("holds", cond["holds"], neg)
    elif "metric" in cond:
        yield ("metric", cond["metric"], neg)
    elif "not" in cond:
        yield ("holds", cond["not"]["holds"], True)
    else:
        for sub in cond.get("all") or cond.get("any") or []:
            for x in leaves(sub, neg):
                yield x


class Result:
    def __init__(self, store, profile, as_of):
        self.store, self.profile, self.as_of = store, profile, as_of
        self.best = {L: {} for L in LEVELS}   # level -> atom -> frozenset(tokens)
        self.via = {L: {} for L in LEVELS}    # level -> atom -> (rule_or_fact_id, [support atoms])
        self.rules = {}                       # internal rule id -> internal rule dict
        self.flags = []
        self.entities = store.entities

    # ----- construction helpers -----
    def flag(self, code, severity, subject, detail):
        f = {"code": code, "severity": severity, "subject": subject, "detail": detail}
        if f not in self.flags:
            self.flags.append(f)

    def _offer(self, atom, L, toks, via, sup):
        for t in toks:
            if t[0] not in ALLOWED[L]:
                return False
        cur = self.best[L].get(atom)
        if cur is None or len(toks) < len(cur):
            self.best[L][atom] = toks
            self.via[L][atom] = (via, list(sup))
            return True
        return False

    def _cond(self, c, L):
        """Return (tokens, supports) if the condition is satisfied at level L, else None."""
        if "holds" in c:
            a = "have:" + c["holds"]
            t = self.best[L].get(a)
            return None if t is None else (t, [a])
        if "metric" in c:
            key = c["metric"]
            m = self._metrics.get(key)
            if m is not None and to_date(m["as_of"]) > self.as_of:
                # an observation says nothing about dates before it was taken: unknown, never satisfied
                tok = ("unknown", "metric %s has no observation on or before %s (its reading is dated %s)" % (key, self.as_of, m["as_of"]))
            elif m is None:
                tok = ("unknown", "metric %s is not recorded" % key)
            elif m["value"] < c["gte"]:
                return None
            elif m["state"] == "confirmed":
                return (NONE, ["metric:" + key])
            else:
                tok = ("unknown", "metric %s is unconfirmed" % key)
            return (frozenset([tok]), ["metric:" + key]) if "unknown" in ALLOWED[L] else None
        if "not" in c:
            a = "have:" + c["not"]["holds"]
            ref = P if L in (E, C) else E   # strict levels need "definitely not held"
            return None if a in self.best[ref] else (NONE, ["not:" + a])
        if "all" in c:
            toks, sup = NONE, []
            for sub in c["all"]:
                got = self._cond(sub, L)
                if got is None:
                    return None
                toks, sup = toks | got[0], sup + got[1]
            return toks, sup
        if "any" in c:
            options = [g for g in (self._cond(sub, L) for sub in c["any"]) if g is not None]
            return min(options, key=lambda g: len(g[0])) if options else None
        return None

    def _solve(self, rules, L):
        changed = True
        while changed:
            changed = False
            for ru in rules:
                if L not in ru["levels"]:
                    continue
                got = self._cond(ru["when"], L)
                if got is None:
                    continue
                toks, sup = got[0] | ru["tokens"], got[1]
                out = ru["output"]
                if ru["kind"] == "acquire":
                    changed |= self._offer("can_get:" + out, L, toks, ru["id"], sup)
                    step = frozenset([("acquire", out, ru["id"])])
                    changed |= self._offer("have:" + out, L, toks | step, ru["id"], ["can_get:" + out])
                else:
                    changed |= self._offer("have:" + out, L, toks, ru["id"], sup)

    # ----- queries -----
    def level_of(self, atom):
        for L in (E, C, U):
            if atom in self.best[L]:
                return L
        return None

    def status(self, atom):
        return {E: ESTABLISHED, C: CONDITIONAL, U: UNRESOLVED, None: NOT_AVAILABLE}[self.level_of(atom)]

    def have(self, entity):
        return self.status("have:" + entity)

    def atoms(self):
        return sorted(set().union(*[set(self.best[L]) for L in LEVELS]))

    def tokens(self, atom):
        """Assumptions behind the atom's status: steps (things to do) and unknowns (things to confirm)."""
        L = self.level_of(atom)
        steps, unknowns = [], []
        for t in sorted(self.best[L][atom]) if L else []:
            if t[0] == "action":
                ent = self.entities.get(t[1], {})
                steps.append({"type": "action", "entity": t[1], "name": ent.get("name", t[1]), "how": ent.get("how", "")})
            elif t[0] == "acquire":
                ent = self.entities.get(t[1], {})
                steps.append({"type": "acquire", "entity": t[1], "name": ent.get("name", t[1]), "rule": t[2]})
            else:
                unknowns.append(t[1])
        return {"steps": steps, "unknowns": unknowns}

    def chain(self, atom):
        """Inspectable derivation tree for an atom, down to base facts."""
        return self._chain(atom, self.level_of(atom), set())

    def _chain(self, atom, L, seen):
        node = {"atom": atom, "status": self.status(atom) if atom.startswith(("have:", "can_get:")) else "CONDITION"}
        if not atom.startswith(("have:", "can_get:")) or L is None:
            return node
        if atom in seen:
            node["via"] = "(shown above)"
            return node
        seen.add(atom)
        lv = E if atom in self.via[E] else L
        if atom not in self.via[lv]:
            return node
        via, sup = self.via[lv][atom]
        node["via"] = via
        src = self.rules.get(via, {}).get("src")
        if src:
            node["rule_summary"] = src.get("summary", "")
            node["evidence"] = src.get("evidence", [])
        node["supports"] = [self._chain(s, lv, seen) for s in sup]
        return node

    def chain_atoms(self, atom):
        out, stack = set(), [self.chain(atom)]
        while stack:
            n = stack.pop()
            out.add(n["atom"])
            stack.extend(n.get("supports", []))
        return out

    def dependents(self, atom):
        """Atoms whose current derivation rests on the given atom (downstream consequences)."""
        return sorted(a for a in self.atoms() if a != atom and a.startswith(("have:", "can_get:"))
                      and atom in self.chain_atoms(a))

    def basis(self, atom):
        L = self.level_of(atom)
        via = self.via[L][atom][0] if L else ""
        return "personal" if via.startswith(("holding:", "retain:", "entitlement:", "election:", "election-default:", "election-link:")) else "derived"

    def report(self):
        """The four epistemic categories, kept apart."""
        from .conditions import blockers
        rep = {"profile": self.profile, "as_of": self.as_of.isoformat(),
               "synthetic": bool(self.store.profile(self.profile).meta.get("synthetic")),
               "sourced_rules": [], "personal_qualifications": [], "derived_entitlements": [],
               "eligible_to_acquire": [], "conditional": [], "unresolved": [], "flags": self.flags}
        for r in sorted(self.store.rules.values(), key=lambda r: r["id"]):
            rep["sourced_rules"].append({"id": r["id"], "kind": r["kind"], "output": r["output"],
                                         "verification": r["verification"]["status"],
                                         "in_effect": in_effect(r, self.as_of), "summary": r["summary"],
                                         "blocked_by": len(blockers(r))})
        for h in sorted(self.store.profile(self.profile).holdings.values(), key=lambda h: h["id"]):
            rep["personal_qualifications"].append({"holding": h["id"], "entity": h["entity"], "state": h["state"],
                                                   "valid_to": h.get("valid_to"), "effective": self.have(h["entity"])})
        for atom in self.atoms():
            kind, ent = atom.split(":", 1)
            st = self.status(atom)
            name = self.entities.get(ent, {}).get("name", ent)
            if self.entities.get(ent, {}).get("kind") in ("action", "election"):
                continue   # actions are steps; elections are reported per group below
            row = {"entity": ent, "name": name}
            row.update(self.tokens(atom))
            if kind == "can_get":
                if st == ESTABLISHED and self.have(ent) != ESTABLISHED:
                    row["rule"] = self.via[E][atom][0]
                    rep["eligible_to_acquire"].append(row)
                continue
            if st == ESTABLISHED and self.basis(atom) == "derived":
                row["via"] = self.via[E][atom][0]
                rep["derived_entitlements"].append(row)
            elif st == CONDITIONAL:
                rep["conditional"].append(row)
            elif st == UNRESOLVED:
                rep["unresolved"].append(row)
        if getattr(self, "elections", None):          # key exists only for people who hold a card with election groups
            rep["elections"] = [{"group": d["group"], "card_holding": d["card"], "established": d["established"],
                                 "unresolved": d["possible"], "reason": d["reason"]} for d in self.elections]
        if getattr(self, "earned", None) is not None:   # key exists only for people with earned-benefit records
            from .earned import summary_rows
            rep["earned_entitlements"] = summary_rows(self.earned)
        return rep


def evaluate(store, profile, as_of, include_candidates=False):
    as_of = to_date(as_of)
    prof = store.profile(profile)
    r = Result(store, profile, as_of)
    r._metrics = prof.metrics
    rules = []
    # cardholder elections: a governed rule also needs the person's election of its option (elections.py)
    from .elections import gate, governed
    from .conditions import tokens as condition_tokens
    gov = governed(store)

    # 1. sourced rules -> internal rules, with the levels at which each may be used
    for rule in sorted(store.rules.values(), key=lambda x: x["id"]):
        vs = standing(rule)
        if vs == "retired" or not in_effect(rule, as_of):
            continue
        if vs == "verified":
            levels, toks = LEVELS, NONE
            rb = to_date(rule["verification"].get("review_by"))
            if rb is not None and rb < as_of and rule["verification"]["status"] != "retired":
                r.flag("STALE_RULE", "review", rule["id"], "verified rule is past its review_by date %s; re-verify (OP-01)" % rb)
        else:
            levels, toks = (P, U), frozenset([("unknown", "rule %s is unverified" % rule["id"])])
        if rule["kind"] in NON_DERIVING or rule["kind"] in PERSONAL_KINDS:
            continue   # baseline/excludes: applicability matrix only (cards.py). earns: personal records only (earned.py)
        blocked = condition_tokens(rule)
        if blocked:
            # a restriction or open question on this rule is an unchecked condition, could change who is eligible, or has
            # no class from a reviewer (conditions.py). Text is not enforcement and silence is not approval: nothing is
            # established through this rule; it is at best a possibility, with each text as the reason
            levels, toks = (P, U), toks | blocked
        rules.append({"id": rule["id"], "kind": rule["kind"], "output": rule["output"], "when": gate(rule["id"], rule["when"], gov),
                      "levels": levels, "tokens": toks, "src": rule})
    if include_candidates:
        for c in sorted(store.candidates.values(), key=lambda x: x["id"]):
            if c["status"] != "proposed":
                continue
            pr = c["proposed_rule"]
            if pr["kind"] in NON_DERIVING or pr["kind"] in PERSONAL_KINDS:
                continue
            rules.append({"id": "candidate:" + c["id"], "kind": pr["kind"], "output": pr["output"], "when": gate(pr.get("id"), pr["when"], gov),
                          "levels": (U,), "tokens": frozenset([("unknown", "candidate %s is not promoted" % c["id"])]),
                          "src": pr})

    # 2. personal qualifications -> base facts (and retention rules for acquired holdings)
    by_entity = {}
    for h in sorted(prof.holdings.values(), key=lambda x: x["id"]):
        if h["state"] in ("ended", "withdrawn"):
            continue
        if store.entities.get(h["entity"], {}).get("kind") == "election":
            continue   # elections are decided per group in step 2c, never one holding at a time
        if not in_effect(h, as_of):
            vt = to_date(h.get("valid_to"))
            if vt is not None and vt < as_of:
                r.flag("EXPIRED_HOLDING", "review", h["id"], "%s expired on %s" % (h["entity"], vt))
            continue
        by_entity.setdefault(h["entity"], []).append(h)
    contested = []
    for ent, hs in sorted(by_entity.items()):
        atom = "have:" + ent
        states = {h["state"] for h in hs}
        if len(states) > 1:
            r.flag("CONFLICTING_HOLDINGS", "review", ent, "records disagree (%s); treated as unconfirmed"
                   % ", ".join(sorted(h["id"] + "=" + h["state"] for h in hs)))
        for h in hs:
            hid = "holding:" + h["id"]
            if h["state"] == "unconfirmed" or len(states) > 1:
                tok = frozenset([("unknown", "holding %s (%s) is not confirmed" % (h["id"], ent))])
                for L in (P, U):
                    r._offer(atom, L, tok, hid, [])
                if len(states) == 1:
                    r.flag("UNCONFIRMED_HOLDING", "review", h["id"], "%s is recorded but not confirmed" % ent)
                continue
            src = store.rules.get(h.get("acquired_via", ""))
            if h.get("acquired_via") and src is None:
                r.flag("ACQUISITION_RULE_MISSING", "review", h["id"],
                       "acquired_via %s is not in the rule base; holding stands on its own dates" % h["acquired_via"])
            mode = (src or {}).get("retention", {}).get("mode")
            if mode in (None, "fixed_term"):
                for L in LEVELS:
                    r._offer(atom, L, NONE, hid, [])
                if src is not None:
                    contested.append((h, src, mode))
            else:
                cond = src["retention"].get("retain_when") or src["when"]
                rid = "retain:" + h["id"]
                rules.append({"id": rid, "kind": "retain", "output": ent, "when": cond,
                              "levels": LEVELS, "tokens": NONE, "src": None})
                tok = frozenset([("unknown", "holding %s (%s): retention needs confirmation" % (h["id"], ent))])
                for L in (P, U):
                    r._offer(atom, L, tok, hid, [])
                contested.append((h, src, mode))

    # 2b. earned benefits: base facts from the person's own qualification and entitlement records
    if prof.qualifications or any(store.rules.get(e["rule"], {}).get("kind") != "grants" for e in prof.entitlements.values()):
        from . import earned
        earned.inject(r, store, prof, as_of)

    # 2c. cardholder elections: which option of each group is in effect on this date (never inferred from silence)
    if gov:
        from . import elections
        elections.inject(r, store, prof, as_of)

    # 3. actions are things the person could do: assumable at C and U
    for ent in sorted(store.entities.values(), key=lambda x: x["id"]):
        if ent["kind"] == "action":
            for L in (C, U):
                r._offer("have:" + ent["id"], L, frozenset([("action", ent["id"])]), "action:" + ent["id"], [])

    # 4. stratify on negation, then solve stratum by stratum
    strat, limit, bad = {}, len(rules) + 2, set()
    changed = True
    while changed:
        changed = False
        for ru in rules:
            if ru["id"] in bad:
                continue
            s = 0
            for kind, ident, neg in leaves(ru["when"]):
                if kind == "holds":
                    s = max(s, strat.get(ident, 0) + (1 if neg else 0))
            if s > strat.get(ru["output"], 0):
                if s > limit:
                    bad.add(ru["id"])
                    r.flag("NEGATIVE_CYCLE", "review", ru["id"], "rule negates something that depends on its own output; rule ignored")
                    continue
                strat[ru["output"]] = s
                changed = True
    for ru in rules:
        r.rules[ru["id"]] = ru
    usable = [ru for ru in rules if ru["id"] not in bad]
    for s in sorted({strat.get(ru["output"], 0) for ru in usable}):
        layer = [ru for ru in usable if strat.get(ru["output"], 0) == s]
        for L in LEVELS:
            r._solve(layer, L)

    # 5. retention findings for acquired holdings
    for h, src, mode in contested:
        atom = "have:" + h["entity"]
        if mode == "fixed_term":
            if r._cond(src["when"], E) is None:
                r.flag("SOURCE_LAPSED_FIXED_TERM", "info", h["id"],
                       "%s stands until %s under fixed-term retention, but the qualification used to acquire it "
                       "(rule %s) no longer holds; renewal will need another path" % (h["entity"], h.get("valid_to"), src["id"]))
            continue
        if atom in r.best[E]:
            continue
        code = "RETENTION_CONDITION_FAILED" if mode == "while_qualified" else "RETENTION_TERMS_UNKNOWN"
        r.flag(code, "review", h["id"],
               "%s was acquired via %s; its retention condition is not currently established (%s). "
               "Not terminated automatically: confirm actual account state (OP-07) and review dependents: %s"
               % (h["entity"], src["id"], "rule says status lasts only while qualified" if mode == "while_qualified"
                  else "retention terms are not known", ", ".join(r.dependents(atom)) or "none"))
    return r
