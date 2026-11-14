"""Human-editable tables (CSV) for card architecture and per-card benefits.

Authority
    The JSON store under data/ is the only system of record. Tables are
      - a generated view of the store (export), and
      - an authoring input: edited rows are compiled into ordinary changesets, which go
        through the same validation, lint, audit and all-or-nothing rules as any other change.
    Nothing is ever read from a table into the store except through that pipeline.

Protocol (docs/RELATIONAL_TABLES.md has the full version)
    export -> edit -> import, in one sitting.
    - Import refuses if the store changed after the export (TABLES_STALE): re-export, redo edits.
    - A row whose id is new is an addition. New benefit rows enter as candidates (quarantine).
    - A changed cell in an existing row is an update, if that column may be updated.
    - Rows are never deleted. Put `retire` (rules) or `withdraw` (candidates) in `_action`.
    - Columns starting with `=` and files starting with `view_` are read-only.
    - Any error anywhere: nothing is applied.
"""
import csv
import hashlib
import io
import json
import os

from . import changes
from .cards import card_pair, matrix
from .lint import ROLES, single_holds
from .store import Store

RULE_TAIL = ["summary", "restrictions", "valid_from", "valid_to", "evidence", "review_by",
             "=state", "=last_verified", "_action", "ended_on"]
COLUMNS = {
    "parties": ["id", "kind", "name", "network", "notes"],
    "benefits": ["id", "name", "notes"],
    "sources": ["id", "url", "title", "publisher", "source_type", "retrieved_on", "applies_to", "summary", "notes"],
    "cards": ["id", "name"] + list(ROLES) + ["annual_fee_usd", "sources", "notes"],
    "tier_baselines": ["id", "tier", "benefit", "=benefit_name"] + RULE_TAIL,
    "card_benefits": ["id", "card", "benefit", "=benefit_name", "applicability", "superseded_by"] + RULE_TAIL,
    "view_applicability": ["card", "card_name", "network_tier", "benefit", "benefit_name", "basis", "standing", "meaning", "detail"],
    "view_holdings": ["profile", "owner", "synthetic", "entity", "name", "kind", "state", "valid_from", "valid_to", "acquired_via", "quantity"],
}
AUTHORING = ("parties", "benefits", "sources", "cards", "tier_baselines", "card_benefits")
VIEWS = ("view_applicability", "view_holdings")
LOGIC = {"tier_baselines": ["tier", "benefit"], "card_benefits": ["card", "benefit", "applicability", "superseded_by"]}
MANIFEST = "MANIFEST.json"
SEP_IDS, SEP_TEXT = ";", " | "


def _ids(cell):
    return [x.strip() for x in cell.split(SEP_IDS) if x.strip()]


def _num(v):
    return "" if v is None else (str(int(v)) if float(v) == int(v) else str(v))


# ------------------------------------------------------------------ store -> rows
def _rule_row(table, rule, state, verification, evidence_ids, ents):
    row = {"id": rule["id"], "benefit": rule["output"], "=benefit_name": ents.get(rule["output"], {}).get("name", ""),
           "summary": rule["summary"], "restrictions": SEP_TEXT.join(rule.get("restrictions", [])),
           "valid_from": rule.get("valid_from", ""), "valid_to": rule.get("valid_to") or "",
           "evidence": SEP_IDS.join(evidence_ids), "review_by": verification.get("review_by", ""),
           "=state": state, "=last_verified": verification.get("last_verified", ""), "_action": "", "ended_on": ""}
    if table == "tier_baselines":
        row["tier"] = single_holds(rule["when"]) or ""
    else:
        row["card"] = single_holds(rule["when"]) or ""
        row["applicability"] = "confirmed" if rule["kind"] == "grants" else "excluded"
        row["superseded_by"] = rule.get("superseded_by", "")
    return row


def _table_of(rule, kind_of):
    if rule["kind"] == "baseline":
        return "tier_baselines"
    return "card_benefits" if card_pair(rule, kind_of) else None


def rows_from_store(store):
    """Every table as {table: {key: row}}; rows are dicts of strings. Also returns {rule id: candidate id}."""
    ents, out, cand_of = store.entities, {t: {} for t in COLUMNS}, {}
    for e in ents.values():
        if e["kind"] in ("organization", "network_tier"):
            out["parties"][e["id"]] = {"id": e["id"], "kind": e["kind"], "name": e["name"],
                                       "network": e.get("network", ""), "notes": e.get("notes", "")}
        elif e["kind"] == "benefit":
            out["benefits"][e["id"]] = {"id": e["id"], "name": e["name"], "notes": e.get("notes", "")}
        elif e["kind"] == "card":
            block = e.get("card", {})
            row = {"id": e["id"], "name": e["name"], "annual_fee_usd": _num(block.get("annual_fee_usd")),
                   "sources": SEP_IDS.join(e.get("sources", [])), "notes": e.get("notes", "")}
            for role in ROLES:
                row[role] = "" if role not in block else ("none" if block[role] is None else block[role])
            out["cards"][e["id"]] = row

    def source_row(ev):
        return {"id": ev["id"], "url": ev["url"], "title": ev["title"], "publisher": ev["publisher"],
                "source_type": ev["source_type"], "retrieved_on": ev["retrieved_on"],
                "applies_to": SEP_IDS.join(ev.get("applies_to", [])), "summary": ev["summary"], "notes": ev.get("notes", "")}
    for ev in store.evidence.values():
        out["sources"][ev["id"]] = source_row(ev)
    kind_of = lambda i: ents.get(i, {}).get("kind")   # noqa: E731
    for r in store.rules.values():
        t = _table_of(r, kind_of)
        if t:
            out[t][r["id"]] = _rule_row(t, r, r["verification"]["status"], r["verification"], r["evidence"], ents)
    for c in store.candidates.values():
        if c["status"] != "proposed":
            continue
        kinds = {e["id"]: e["kind"] for e in c.get("proposed_entities", [])}
        pr = c["proposed_rule"]
        t = _table_of(pr, lambda i: kind_of(i) or kinds.get(i))
        if t and pr["id"] not in out[t]:
            out[t][pr["id"]] = _rule_row(t, pr, "candidate", {}, [e["id"] for e in c["evidence"]], ents)
            cand_of[pr["id"]] = c["id"]
            for ev in c["evidence"]:
                out["sources"].setdefault(ev["id"], source_row(ev))
    for i, m in enumerate(matrix(store)):
        out["view_applicability"]["%04d" % i] = {k: m.get(k, "") for k in COLUMNS["view_applicability"]}
    n = 0
    for name in store.profile_names():
        prof = store.profile(name)
        for h in sorted(prof.holdings.values(), key=lambda h: h["id"]):
            e = ents.get(h["entity"], {})
            out["view_holdings"]["%04d" % n] = {
                "profile": name, "owner": prof.meta["owner"], "synthetic": "yes" if prof.meta["synthetic"] else "no",
                "entity": h["entity"], "name": e.get("name", ""), "kind": e.get("kind", ""), "state": h["state"],
                "valid_from": h.get("valid_from", ""), "valid_to": h.get("valid_to") or "",
                "acquired_via": h.get("acquired_via", ""), "quantity": _num(h.get("quantity"))}
            n += 1
    return out, cand_of


def render(table, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS[table])
    for key in sorted(rows):
        w.writerow([rows[key][c] for c in COLUMNS[table]])
    return buf.getvalue()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def generate(store):
    rows, _c = rows_from_store(store)
    return {t + ".csv": render(t, rows[t]) for t in COLUMNS}


# ------------------------------------------------------------------ export / status
def export(root, tdir="tables"):
    texts = generate(Store.load(root))
    full = os.path.join(root, tdir)
    os.makedirs(full, exist_ok=True)
    for name, text in texts.items():
        with open(os.path.join(full, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    manifest = {"format": 1, "files": {n: _sha(t) for n, t in sorted(texts.items())},
                "note": "Written by `python3 -m prices tables export`. Do not edit. The JSON store under data/ is the "
                        "system of record; these CSV files are a view of it and an input to `tables import`."}
    with open(os.path.join(full, MANIFEST), "w", encoding="utf-8") as f:
        f.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return sorted(texts)


def status(root, tdir="tables", store=None):
    """exists / stale (store moved on since export) / edited (files differ from what was exported)."""
    full = os.path.join(root, tdir)
    mpath = os.path.join(full, MANIFEST)
    if not os.path.exists(mpath):
        return {"exists": False, "stale": [], "edited": []}
    with open(mpath, encoding="utf-8") as f:
        recorded = json.load(f)["files"]
    fresh = generate(store or Store.load(root))
    stale = sorted(n for n, t in fresh.items() if recorded.get(n) != _sha(t))
    edited = []
    for n in sorted(fresh):
        path = os.path.join(full, n)
        if not os.path.exists(path):
            edited.append(n)
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            if _sha(f.read().replace("\r\n", "\n")) != recorded.get(n):
                edited.append(n)
    return {"exists": True, "stale": stale, "edited": edited}


def refresh_if_clean(root, tdir="tables"):
    """After a store change: re-export unless a person has unimported edits in the tables."""
    st = status(root, tdir)
    if not st["exists"] or not st["stale"]:
        return None
    if st["edited"]:
        return "tables/ has unimported edits (%s) and is now out of date; it was left untouched" % ", ".join(st["edited"])
    export(root, tdir)
    return "tables/ refreshed"


# ------------------------------------------------------------------ rows -> changesets
def _parse(full, table):
    path, errs, rows = os.path.join(full, table + ".csv"), [], {}
    if not os.path.exists(path):
        return {}, ["MISSING_FILE: %s.csv" % table]
    with open(path, encoding="utf-8-sig", newline="") as f:
        data = list(csv.reader(f))
    if not data or [h.strip() for h in data[0]] != COLUMNS[table]:
        return {}, ["BAD_HEADER: %s.csv must have exactly these columns in this order: %s" % (table, ",".join(COLUMNS[table]))]
    for n, cells in enumerate(data[1:], start=2):
        if not any(c.strip() for c in cells):
            continue
        if len(cells) != len(COLUMNS[table]):
            errs.append("BAD_ROW: %s.csv line %d has %d cells, expected %d" % (table, n, len(cells), len(COLUMNS[table])))
            continue
        row = {c: v.strip() for c, v in zip(COLUMNS[table], cells)}
        if not row["id"]:
            errs.append("MISSING_VALUE: %s.csv line %d has no id" % (table, n))
        elif row["id"] in rows:
            errs.append("DUPLICATE_ROW: %s.csv has id %r more than once (line %d)" % (table, row["id"], n))
        else:
            rows[row["id"]] = row
    return rows, errs


def plan(store, root, tdir, author, date):
    """Compile table edits into an ordered list of changesets. Never writes. Returns a dict."""
    full, errs = os.path.join(root, tdir), []

    def fail(e):
        return {"ok": False, "errors": e, "changesets": [], "origins": []}

    st = status(root, tdir, store)
    if not st["exists"]:
        return fail(["NO_EXPORT: %s/%s not found. Run `python3 -m prices tables export` first." % (tdir, MANIFEST)])
    if st["stale"]:
        return fail(["TABLES_STALE: the store changed after these tables were exported (%s). Nothing was imported. "
                     "Save your edits elsewhere, run `python3 -m prices tables export`, then redo them." % ", ".join(st["stale"])])
    for v in VIEWS:
        if v + ".csv" in st["edited"]:
            errs.append("READ_ONLY_VIEW: %s.csv is a generated view and cannot be edited" % v)
    base, cand_of = rows_from_store(store)
    edited = {}
    for t in AUTHORING:
        edited[t], e = _parse(full, t)
        errs += e
    if errs:
        return fail(errs)

    new, changed = {t: [] for t in AUTHORING}, {t: [] for t in AUTHORING}
    for t in AUTHORING:
        for rid in sorted(base[t]):
            if rid not in edited[t]:
                errs.append("ROW_DELETED: %s row %s is missing. Rows are never deleted and ids never change; "
                            "restore the row and use the _action column to retire it." % (t, rid))
        for rid in sorted(edited[t]):
            row, b = edited[t][rid], base[t].get(rid)
            ro = [c for c in COLUMNS[t] if c.startswith("=")]
            if b is None:
                errs += ["READ_ONLY_COLUMN: %s row %s: leave %s empty on a new row" % (t, rid, c) for c in ro if row[c]]
                new[t].append(row)
            elif row != b:
                errs += ["READ_ONLY_COLUMN: %s row %s: %s is read-only (was %r)" % (t, rid, c, b[c]) for c in ro if row[c] != b[c]]
                changed[t].append((b, row))

    # ---- sources: immutable once recorded; new ones travel with the row that cites them
    for b, row in changed["sources"]:
        errs.append("EVIDENCE_IMMUTABLE: sources row %s: a recorded source is never edited. Add a new source row instead." % row["id"])
    new_sources, used = {}, set()
    for row in new["sources"]:
        missing = [c for c in ("url", "title", "publisher", "source_type", "retrieved_on", "summary") if not row[c]]
        if missing:
            errs.append("MISSING_VALUE: sources row %s: %s required" % (row["id"], ", ".join(missing)))
        ev = {k: row[k] for k in ("id", "url", "title", "publisher", "source_type", "retrieved_on", "summary")}
        if row["applies_to"]:
            ev["applies_to"] = _ids(row["applies_to"])
        if row["notes"]:
            ev["notes"] = row["notes"]
        new_sources[row["id"]] = ev
    embedded = {e["id"]: e for c in store.candidates.values() if c["status"] == "proposed" for e in c["evidence"]}

    def source(sid, where):
        if sid in new_sources:
            used.add(sid)
            return new_sources[sid]
        got = store.evidence.get(sid) or embedded.get(sid)
        if got is None:
            errs.append("UNKNOWN_SOURCE: %s cites source %r, which is not a row in sources.csv" % (where, sid))
        return got

    out = []   # (changeset without id, origin text)

    def emit(op, origin, **kw):
        out.append((dict({"op": op, "author": author, "date": date, "reason": "tables import: " + origin}, **kw), origin))

    # ---- entities: parties (organizations before tiers), benefits, cards
    def opt(d, key, value):
        if value:
            d[key] = value
        return d

    for row in sorted(new["parties"], key=lambda r: (r["kind"] != "organization", r["id"])):
        if row["kind"] not in ("organization", "network_tier"):
            errs.append("BAD_VALUE: parties row %s: kind must be organization or network_tier" % row["id"])
            continue
        ent = opt(opt({"id": row["id"], "kind": row["kind"], "name": row["name"]}, "network", row["network"]), "notes", row["notes"])
        emit("add_entity", "parties row %s" % row["id"], data={"entity": ent})
    for row in new["benefits"]:
        emit("add_entity", "benefits row %s" % row["id"],
             data={"entity": opt({"id": row["id"], "kind": "benefit", "name": row["name"]}, "notes", row["notes"])})

    def card_block(row, where):
        block = {}
        for role in ROLES:
            if row[role]:
                block[role] = None if row[role].lower() == "none" else row[role]
        if row["annual_fee_usd"]:
            try:
                block["annual_fee_usd"] = float(row["annual_fee_usd"])
            except ValueError:
                errs.append("BAD_VALUE: %s: annual_fee_usd must be a number" % where)
        return block

    for row in new["cards"]:
        where = "cards row %s" % row["id"]
        srcs = _ids(row["sources"])
        evs = [e for e in (source(s, where) for s in srcs) if e is not None and e["id"] in new_sources]
        ent = opt({"id": row["id"], "kind": "card", "name": row["name"], "card": card_block(row, where)}, "notes", row["notes"])
        if srcs:
            ent["sources"] = srcs
        emit("add_entity", where, data={"entity": ent}, **({"evidence": evs} if evs else {}))

    for t in ("parties", "benefits", "cards"):
        for b, row in changed[t]:
            where, sets, evs = "%s row %s" % (t, row["id"]), {}, []
            if t == "parties" and row["kind"] != b["kind"]:
                errs.append("KIND_CHANGE: %s: an entity's kind never changes. Add a new row with a new id." % where)
                continue
            for col in ("name", "notes") + (("network",) if t == "parties" else ()):
                if row[col] != b[col]:
                    sets[col] = row[col] or None
            if t == "cards":
                if any(row[c] != b[c] for c in list(ROLES) + ["annual_fee_usd"]):
                    sets["card"] = card_block(row, where)
                if row["sources"] != b["sources"]:
                    gone = set(_ids(b["sources"])) - set(_ids(row["sources"]))
                    if gone:
                        errs.append("EVIDENCE_REMOVED: %s: sources are never removed (%s)" % (where, ", ".join(sorted(gone))))
                    sets["sources"] = _ids(row["sources"])
                    evs = [e for e in (source(s, where) for s in sets["sources"]) if e is not None and e["id"] in new_sources]
            if sets.get("name", "x") is None:
                errs.append("MISSING_VALUE: %s: name cannot be empty" % where)
            emit("revise_entity", where, target=row["id"], data={"set": sets}, **({"evidence": evs} if evs else {}))

    # ---- rule tables
    taken = {r["id"] for r in store.rules.values()} | {c["proposed_rule"]["id"] for c in store.candidates.values() if c["status"] == "proposed"}
    cand_ids = set(store.candidates)
    for t in ("tier_baselines", "card_benefits"):
        subject_col = "tier" if t == "tier_baselines" else "card"
        for row in new[t]:
            where = "%s row %s" % (t, row["id"])
            for col in ("_action", "ended_on", "review_by"):
                if row[col]:
                    errs.append("BAD_VALUE: %s: leave %s empty on a new row%s" % (where, col, " (the reviewer sets it at promotion)" if col == "review_by" else ""))
            if row["id"] in taken:
                errs.append("DUPLICATE_ID: %s: a rule or open candidate already uses this id" % where)
            for col in (subject_col, "benefit", "summary"):
                if not row[col]:
                    errs.append("MISSING_VALUE: %s: %s required" % (where, col))
            kind = "baseline"
            if t == "card_benefits":
                if row["applicability"] not in ("confirmed", "excluded"):
                    errs.append("BAD_VALUE: %s: applicability must be confirmed or excluded (leave the row out if unproven)" % where)
                if row["superseded_by"] and row["applicability"] != "excluded":
                    errs.append("BAD_VALUE: %s: superseded_by is only for excluded rows" % where)
                kind = "grants" if row["applicability"] == "confirmed" else "excludes"
            evs = [e for e in (source(s, where) for s in _ids(row["evidence"])) if e is not None]
            if not _ids(row["evidence"]):
                errs.append("MISSING_VALUE: %s: a new row needs at least one source id in the evidence column" % where)
            rule = {"id": row["id"], "kind": kind, "output": row["benefit"], "when": {"holds": row[subject_col]}, "summary": row["summary"]}
            if row["restrictions"]:
                rule["restrictions"] = [x.strip() for x in row["restrictions"].split("|") if x.strip()]
            for col in ("valid_from", "valid_to"):
                opt(rule, col, row[col])
            if t == "card_benefits":
                opt(rule, "superseded_by", row["superseded_by"])
            cid, n = "c-" + row["id"], 1
            while cid in cand_ids:
                n += 1
                cid = "c-%s-r%d" % (row["id"], n)
            cand_ids.add(cid)
            cand = {"id": cid, "status": "proposed", "created_on": date, "proposed_rule": rule, "evidence": evs,
                    "search_path": ["tables import (%s.csv)" % t], "open_questions": []}
            emit("add_candidate", where, data={"candidate": cand})

        for b, row in changed[t]:
            where, state, action = "%s row %s" % (t, row["id"]), b["=state"], row["_action"].lower()
            same = lambda cols: all(row[c] == b[c] for c in cols)   # noqa: E731
            if state == "retired":
                errs.append("ROW_READ_ONLY: %s is retired. Retired rows are history; add a new row with a new id instead." % where)
                continue
            if state == "candidate":
                if action == "withdraw" and same([c for c in COLUMNS[t] if c != "_action"]):
                    emit("reject_candidate", where, target=cand_of[row["id"]])
                else:
                    errs.append("CANDIDATE_READ_ONLY: %s is awaiting review and cannot be edited. To change it, put `withdraw` "
                                "in _action (changing nothing else), import, then add a corrected row under a new id." % where)
                continue
            if not same(LOGIC[t]):
                errs.append("LOGIC_CHANGE: %s: %s cannot be changed on an existing row. Retire this row (_action = retire) "
                            "and add a new row with a new id." % (where, ", ".join(c for c in LOGIC[t] if row[c] != b[c])))
                continue
            before, after = _ids(b["evidence"]), _ids(row["evidence"])
            if set(before) - set(after):
                errs.append("EVIDENCE_REMOVED: %s: evidence is never removed (%s)" % (where, ", ".join(sorted(set(before) - set(after)))))
                continue
            added = [e for e in (source(s, where) for s in after if s not in before) if e is not None]
            ev = {"evidence": added} if added else {}
            text_cols = ["summary", "restrictions", "valid_from", "valid_to"]
            if action == "retire":
                if not same(text_cols + ["review_by"]) or not row["ended_on"]:
                    errs.append("BAD_VALUE: %s: to retire, fill ended_on, add a source to evidence, and change nothing else" % where)
                else:
                    emit("retire_rule", where, target=row["id"], data={"ended_on": row["ended_on"]}, **ev)
            elif action == "confirm":
                if not same(text_cols) or row["ended_on"]:
                    errs.append("BAD_VALUE: %s: to confirm, set a new review_by, add a fresh source to evidence, and change nothing else" % where)
                else:
                    emit("confirm_rule", where, target=row["id"], data={"review_by": row["review_by"]}, **ev)
            elif action:
                errs.append("BAD_VALUE: %s: _action must be empty, retire or confirm (withdraw is for candidates)" % where)
            elif row["ended_on"]:
                errs.append("BAD_VALUE: %s: ended_on is only used together with _action = retire" % where)
            else:
                sets = {}
                if row["summary"] != b["summary"]:
                    sets["summary"] = row["summary"]
                if row["restrictions"] != b["restrictions"]:
                    sets["restrictions"] = [x.strip() for x in row["restrictions"].split("|") if x.strip()]
                if row["valid_from"] != b["valid_from"]:
                    if not row["valid_from"]:
                        errs.append("BAD_VALUE: %s: valid_from cannot be cleared once set" % where)
                    sets["valid_from"] = row["valid_from"]
                if row["valid_to"] != b["valid_to"]:
                    sets["valid_to"] = row["valid_to"] or None
                if row["review_by"] != b["review_by"]:
                    sets["review_by"] = row["review_by"]
                if sets:
                    emit("revise_rule", where, target=row["id"], data={"set": sets}, **ev)
                elif added:
                    emit("add_evidence", where, target=row["id"], **ev)

    errs += ["UNUSED_SOURCE: sources row %s is new but no row cites it. Cite it or remove it." % s
             for s in sorted(set(new_sources) - used)]
    if errs:
        return fail(errs)

    # ---- give ids, then prove the whole batch against the pipeline, in memory
    digest = hashlib.sha256(store.digest().encode())   # ids depend on the starting state and on the edits
    for t in AUTHORING:
        digest.update(render(t, edited[t]).encode("utf-8"))
    tag, sets, origins, cur = digest.hexdigest()[:8], [], [], store
    for n, (cs, origin) in enumerate(out, start=1):
        cs["id"] = "cs-%s-tbl-%s-%02d-%s" % (date.replace("-", ""), tag, n, cs["op"].replace("_", "-"))
        res = changes.stage(cur, cs)
        if not res["ok"]:
            return fail(["REJECTED: %s: %s" % (origin, e) for e in res["errors"]])
        cur = res["store"]
        sets.append(cs)
        origins.append(origin)
    return {"ok": True, "errors": [], "changesets": sets, "origins": origins}


def import_tables(root, tdir, author, date, dry_run=False):
    """Compile and apply table edits, all or nothing, then refresh the tables."""
    store = Store.load(root)
    p = plan(store, root, tdir, author, date)
    if not p["ok"]:
        return dict(p, applied=[])
    if dry_run or not p["changesets"]:
        return dict(p, applied=[], dry_run=dry_run)
    res = changes.apply_many(root, p["changesets"])
    if not res["ok"]:
        return {"ok": False, "errors": ["REJECTED: %s" % e for e in res["errors"]], "changesets": [], "origins": [], "applied": []}
    export(root, tdir)
    return dict(p, applied=[r["id"] for r in res["results"]], review_needed=res["review_needed"])
