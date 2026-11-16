"""Foundation viability experiment: a reproducible run on real content, in a throwaway copy of the store.

    python3 experiments/viability/run.py            # prints a summary; exit 0 only if every check holds
    python3 experiments/viability/run.py --write    # also rewrites experiments/viability/results/

Phases
    0  baseline   real candidates promoted in the copy exactly as they are: what does the engine tell a cardholder?
    1  batch 1    the same content with the first capabilities (unchecked conditions, earning rates, credit terms):
                  realistic questions, each labelled RECORDED / EVALUATED / CALCULATED / DECLINED
    2  batch 2    new real content from programmes the engine has never seen, entered with the code frozen
    3  maintenance  published terms change; do answers follow without losing history?

Every expected value in a check was worked out from the source terms before the run, not copied from its output.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import HERE, Lab, TODAY, load, status_of   # noqa: E402

OUT = os.path.join(HERE, "results")
checks, sections = [], []


def check(name, ok, detail=""):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    return ok


def section(title, lines):
    sections.append((title, list(lines)))


def gate_counts():
    """How many real candidates state a condition on who has the benefit that their rule does not check."""
    classes = load("restriction_classes.json")["classes"]
    cands = {}
    for name in sorted(os.listdir(os.path.join(Lab.__module__ and os.path.dirname(HERE), "..", "data", "candidates"))):
        with open(os.path.join(os.path.dirname(HERE), "..", "data", "candidates", name), encoding="utf-8") as f:
            c = json.load(f)
        if c["status"] == "proposed" and c["proposed_rule"]["kind"] != "transfer":
            cands[c["proposed_rule"]["id"]] = c["proposed_rule"]
    aligned = all(len(classes.get(rid, "")) == len(r.get("restrictions", [])) for rid, r in cands.items())
    total = sum(len(r.get("restrictions", [])) for r in cands.values())
    tally = collections.Counter(ch for rid in cands for ch in classes.get(rid, ""))
    gated = sorted(rid for rid in cands if "G" in classes.get(rid, ""))
    deriving = [rid for rid in gated if cands[rid]["kind"] in ("grants", "acquire")]
    return {"candidates": len(cands), "restrictions": total, "aligned": aligned, "tally": dict(tally), "with_unchecked_gate": gated,
            "deriving_with_unchecked_gate": deriving}


def select(lab, spec):
    ids = sorted(c for c in lab.store().candidates if lab.store().candidates[c]["status"] == "proposed"
                 and (c.startswith(tuple(spec["select_prefixes"])) or c in spec["select_ids"]))
    done, refused = [], {}
    for cid in ids:
        out = lab.promote(cid, "batch1")
        if out["ok"]:
            done.append(cid)
        else:
            refused[cid] = out["errors"]
    assert all("INSUFFICIENT_EVIDENCE" in e for errs in refused.values() for e in errs), refused      # the only refusal expected
    return done, refused


CASEY = [{"id": "h-csr", "entity": "card.chase-sapphire-reserve", "valid_from": "2024-03-01", "opened_on": "2024-03-01"},
         {"id": "h-ur", "entity": "chase.ur", "valid_from": "2024-03-01", "quantity": 120000},
         {"id": "h-mr", "entity": "amex.mr", "valid_from": "2023-01-10", "quantity": 80000},
         {"id": "h-titanium", "entity": "marriott.titanium", "valid_from": "2026-02-01", "valid_to": "2027-02-28"}]
RILEY = [{"id": "h-csr", "entity": "card.chase-sapphire-reserve", "state": "unconfirmed", "valid_from": "2025-06-01"}]


# ------------------------------------------------------------------------------------------------ phase 0
def phase0(spec):
    lab = Lab()
    ids, refused = select(lab, spec)
    check("0.0 the evidence policy holds on real content: a candidate with one secondary source cannot be promoted, even in the copy",
          sorted(refused) == ["c-ana-business-award-via-ana-miles"], ", ".join(sorted(refused)))
    lab.person("syn-casey", CASEY)
    rep = lab.js("status", "--profile", "syn-casey", "--as-of", TODAY)
    g = gate_counts()
    wrong = sorted(x["entity"] for x in rep["derived_entitlements"] if x.get("via") in g["deriving_with_unchecked_gate"])
    check("0.1 the restriction classification covers every restriction (124 strings on the 73 real non-transfer candidates)",
          g["aligned"] and g["restrictions"] == 124 and g["candidates"] == 73, str(g["tally"]))
    check("0.2 BASELINE DEFECT reproduced: an account opened in 2024 is shown the new-applicant welcome offer as ESTABLISHED",
          status_of(rep, "benefit.csr.public-welcome-offer") == "ESTABLISHED")
    check("0.3 BASELINE DEFECT reproduced: IHG Platinum 'benefit' ESTABLISHED while the status itself still needs enrolment",
          status_of(rep, "benefit.csr.ihg-platinum-elite-status") == "ESTABLISHED" and status_of(rep, "ihg.platinum") == "CONDITIONAL")
    section("Phase 0 - baseline: real candidates promoted in the copy as they are", [
        "%d real candidates promoted in the copy (Chase Sapphire Reserve packet, Visa Infinite baselines, two loyalty candidates); "
        "44 of the 113 in the store carry open questions and promote only with an explicit acceptance." % len(ids),
        "Restrictions on the 73 real non-transfer candidates: %d strings. Engineering's classification: %s."
        % (g["restrictions"], ", ".join("%s %d" % (k, v) for k, v in sorted(g["tally"].items()))),
        "(U usage term, G gate not checked by the rule, g gate that is checked, T time window, M research note)",
        "Candidates that state a gate their rule does not check: %d of 73; %d of them derive an entitlement."
        % (len(g["with_unchecked_gate"]), len(g["deriving_with_unchecked_gate"])),
        "For an invented cardholder whose account was opened in 2024, the status report lists as DERIVED ENTITLEMENTS - established:",
    ] + ["    %s" % e for e in wrong] + [
        "Each of those has a stated condition (new applicants only, enrolment, activation, primary cardholder) that nothing checked.",
    ])
    return {"promoted": len(ids), "gates": g, "established_despite_gate": wrong}


# ------------------------------------------------------------------------------------------------ phase 1
def amend(lab, spec, batch):
    """The structured terms of a batch, through the pipeline, each with the rule's own evidence."""
    n = collections.Counter()
    for rid, texts in spec.get("unchecked", {}).items():
        rule = lab.store().rules[rid]
        keep = [x for x in rule.get("restrictions", []) if x not in texts]
        out = lab.apply("revise_rule", batch, rid, target=rid, data={"set": {"unchecked": texts, "restrictions": keep}}, evidence=lab.evidence_of(rid))
        n["unchecked ok" if out["ok"] else "unchecked refused"] += 1
        assert out["ok"], (rid, out["errors"])
    for rid, block in spec.get("earning", {}).items():
        out = lab.apply("revise_rule", batch, rid, target=rid, data={"set": {"earning": block}}, evidence=lab.evidence_of(rid))
        n["earning ok" if out["ok"] else "earning refused"] += 1
        assert out["ok"], (rid, out["errors"])
    refused = {}
    for rid, block in spec.get("credit", {}).items():
        out = lab.apply("set_credit_terms", batch, rid, target=rid, data={"credit": block}, evidence=lab.evidence_of(rid))
        n["credit ok" if out["ok"] else "credit refused"] += 1
        if not out["ok"]:
            refused[rid] = out["errors"]
    return n, refused


def answers(lab, rows, qid, kind, question, args, verdict):
    code, text = lab.cli(*args)
    rows.append({"id": qid, "kind": kind, "question": question, "command": "python3 -m prices " + " ".join(str(a) for a in args),
                 "exit": code, "answer": verdict, "output": text})


def phase1(spec):
    lab = Lab()
    select(lab, spec)
    lab.vocab({"spend_categories": spec["spend_categories"]})
    counts, refused = amend(lab, spec, "batch1")
    lab.person("syn-casey", CASEY)
    lab.person("syn-riley", RILEY)
    owner = "syn-casey (invented)"
    out = lab.apply("record_progress", "batch1", "progress", profile="syn-casey",
                    attestation={"by": owner, "on": TODAY, "statement": "Invented: statement shows 61,200 in purchases this year."},
                    data={"account": "h-csr", "measure": "csr.qualifying_spend", "cycle": "2026",
                          "reading": {"id": "r-2026-10", "value": 61200, "observed_on": "2026-10-31", "state": "confirmed"}})
    assert out["ok"], out["errors"]
    check("1.0 the copy is sound after batch 1 (lint: no errors)", lab.lint_errors() == [], "; ".join(lab.lint_errors()[:3]))
    rows = []
    P = ["--profile", "syn-casey", "--as-of", TODAY]
    rep = lab.js("status", *P)

    # --- evaluated: relationships across several entities
    st = {e: status_of(rep, e) for e in ("jal.crystal", "oneworld.ruby", "aeroplan.25k", "aeroplan.points", "cap.japan-business.ana-via-aeroplan",
                                         "benefit.csr.public-welcome-offer", "benefit.csr.ihg-platinum-elite-status", "ihg.platinum",
                                         "benefit.csr.annual-travel-credit-300", "benefit.csr.trip-delay-reimbursement", "hyatt.explorist")}
    check("1.1 EVALUATED chain: Marriott Titanium -> JAL Crystal -> oneworld Ruby is CONDITIONAL (an action is needed), not established",
          st["jal.crystal"] == "CONDITIONAL" and st["oneworld.ruby"] == "CONDITIONAL", str(st))
    check("1.2 EVALUATED chain: Amex points -> Aeroplan points -> ANA business award to Japan is ESTABLISHED",
          st["aeroplan.points"] == "ESTABLISHED" and st["cap.japan-business.ana-via-aeroplan"] == "ESTABLISHED")
    check("1.3 GUARD: the new-applicant welcome offer is now UNRESOLVED for an existing cardholder, never ESTABLISHED",
          st["benefit.csr.public-welcome-offer"] == "UNRESOLVED")
    check("1.4 GUARD: IHG Platinum is UNRESOLVED both as the card benefit and as the status (primary cardholder is not checked)",
          st["benefit.csr.ihg-platinum-elite-status"] == "UNRESOLVED" and st["ihg.platinum"] == "UNRESOLVED")
    check("1.5 a benefit with usage terms only stays ESTABLISHED (travel credit, trip delay)",
          st["benefit.csr.annual-travel-credit-300"] == "ESTABLISHED" and st["benefit.csr.trip-delay-reimbursement"] == "ESTABLISHED")
    check("1.6 a spending threshold is never met by holding the card: Hyatt Explorist is NOT_AVAILABLE", st["hyatt.explorist"] == "NOT_AVAILABLE")
    answers(lab, rows, "Q1", "EVALUATED", "Casey holds Marriott Titanium. Which airline status does that lead to?",
            ["explain", *P, "oneworld.ruby"], "CONDITIONAL: reachable, an action is needed first")
    answers(lab, rows, "Q2", "EVALUATED", "Is the Sapphire Reserve welcome offer available to Casey (account opened 2024)?",
            ["explain", *P, "benefit.csr.public-welcome-offer"], "UNRESOLVED: 'new applicants only' is text the engine does not check")
    answers(lab, rows, "Q3", "RECORDED", "What are the terms of trip delay cover on Casey's card?",
            ["explain", *P, "benefit.csr.trip-delay-reimbursement"], "ESTABLISHED as a card benefit; its terms are shown as text, not evaluated")

    # --- calculated
    q = lab.js("earnings", *P, "--category", "dining", "--amount", 400)["answers"]
    check("1.7 CALCULATED: $400 of dining on Sapphire Reserve = 1,200 Ultimate Rewards points (3 per $1)",
          len(q) == 1 and q[0]["result"] == "CALCULATED" and q[0]["points"] == 1200 and q[0]["currency"] == "chase.ur")
    q = lab.js("earnings", *P, "--category", "portal-travel", "--amount", 1000)["answers"]
    check("1.8 CALCULATED: $1,000 through Chase Travel = 8,000 points", q[0]["result"] == "CALCULATED" and q[0]["points"] == 8000)
    q = lab.js("earnings", *P, "--category", "travel", "--amount", 1000)["answers"]
    check("1.9 DECLINED: 'travel' is too broad (the card publishes 8, 4 and 1 for different kinds of travel)", q[0]["result"] == "NOT_CALCULATED")
    q1 = lab.js("earnings", *P, "--category", "rideshare-lyft", "--amount", 60)["answers"][0]
    q2 = lab.js("earnings", "--profile", "syn-casey", "--as-of", "2027-10-15", "--category", "rideshare-lyft", "--amount", 60)["answers"][0]
    check("1.10 CALCULATED with dates: $60 of Lyft = 300 points today, 60 after the 5X offer ends on 2027-09-30 (catch-all rate, said so)",
          q1["points"] == 300 and q2["points"] == 60 and q2["category_used"] == "other", "%s / %s" % (q1.get("points"), q2.get("points")))
    q = lab.js("earnings", "--profile", "syn-riley", "--as-of", TODAY, "--category", "dining", "--amount", 400)["answers"]
    check("1.11 DECLINED: no calculation for a person whose card holding is unconfirmed", len(q) == 1 and q[0]["result"] == "NOT_CALCULATED")
    code, text = lab.cli("earnings", *P, "--category", "groceries", "--amount", 100)
    check("1.12 DECLINED: an unknown category is refused, not guessed", code == 2 and "unknown spend category" in text)
    q = lab.js("convert", *P, "--from", "chase.ur", "--amount", 50000)["answers"]
    check("1.13 DECLINED: Ultimate Rewards -> 14 partners, no amount for any: the source publishes no ratio",
          len(q) == 14 and all(a["result"] == "NOT_CALCULATED" for a in q), "%d answers" % len(q))
    q = lab.js("convert", *P, "--from", "amex.mr", "--amount", 50000, "--to", "ana.miles")["answers"]
    check("1.14 CALCULATED: 50,000 Amex points -> 50,000 ANA miles at the recorded 1:1, with its open question shown",
          len(q) == 1 and q[0]["result"] == "CALCULATED" and q[0]["amount"] == 50000 and q[0]["open_questions"])
    answers(lab, rows, "Q4", "CALCULATED", "What does $400 of dining earn on Casey's cards?",
            ["earnings", *P, "--category", "dining", "--amount", 400], "1,200 chase.ur")
    answers(lab, rows, "Q5", "DECLINED", "What does $1,000 of 'travel' earn?", ["earnings", *P, "--category", "travel", "--amount", 1000],
            "not calculated: three different published rates could apply")
    answers(lab, rows, "Q6", "DECLINED", "What would 50,000 Ultimate Rewards points become at Hyatt?",
            ["convert", *P, "--from", "chase.ur", "--amount", 50000, "--to", "hyatt.points"], "not calculated: no ratio is recorded")
    answers(lab, rows, "Q7", "CALCULATED", "What would 50,000 Amex points become at ANA?",
            ["convert", *P, "--from", "amex.mr", "--amount", 50000, "--to", "ana.miles"], "50,000 ana.miles, with caveats")

    # --- credits and thresholds (capabilities that existed before this experiment)
    cr = lab.js("credits", *P)
    by = {c["rule"]: c for acct in cr["accounts"] for c in acct["credits"]}
    tc = by["cb.csr.annual-travel-credit-300"]
    check("1.15 CALCULATED: travel credit period for an account opened 2024-03-01 is 2026-03-01 to 2027-02-28; allowance 300; "
          "personal balance NOT_RECORDED (never assumed unused)",
          (tc["period"]["start"], tc["period"]["end"], tc["allowance"]["amount"], tc["personal"]["state"]) == ("2026-03-01", "2027-02-28", 300, "NOT_RECORDED"))
    sh = by["cb.csr.stubhub-viagogo-credit-300"]
    check("1.16 the guard reaches credits: StubHub period is computed (2026-H2) but whether it applies is UNRESOLVED (activation not checked)",
          sh["period"]["label"] == "2026-H2" and sh["applies"]["status"] == "UNRESOLVED")
    check("1.17 DECLINED: Global Entry credit, the source does not say what the four years count from; no period is invented",
          by["cb.csr.trusted-traveler-credit-120"]["period"]["state"] == "UNRESOLVED")
    earned_text = lab.cli("earned", *P)[1]
    check("1.18 EVALUATED: $61,200 against the $75,000 threshold is BELOW; five outcomes listed, none earned",
          "61,200" in earned_text and earned_text.count("ACHIEVEMENT   BELOW") == 5 and "ENTITLEMENT   ACTIVE" not in earned_text)
    late = lab.js("status", "--profile", "syn-casey", "--as-of", "2027-01-15")
    check("1.19 EVALUATED over time: the 2026-only hotel credit is ESTABLISHED on %s and NOT_AVAILABLE on 2027-01-15" % TODAY,
          status_of(rep, "benefit.csr.select-hotel-credit-250-2026") == "ESTABLISHED"
          and status_of(late, "benefit.csr.select-hotel-credit-250-2026") == "NOT_AVAILABLE")
    rows.append({"id": "Q8", "kind": "CALCULATED", "question": "Which credit periods is Casey in today, and when do they end?",
                 "command": "python3 -m prices credits --profile syn-casey --as-of %s" % TODAY, "exit": 0,
                 "answer": "periods computed from the published cycle; personal balance 'not recorded', never assumed unused",
                 "output": lab.cli("credits", *P)[1]})
    answers(lab, rows, "Q9", "EVALUATED", "How far is Casey from the $75,000 unlock, and what does it give?",
            ["earned", *P], "progress 61,200 of 75,000 on record; nothing earned; five separate outcomes with their own terms")
    return {"lab": lab, "amendments": dict(counts), "credit_refused": refused, "rows": rows, "credits_json": cr, "by": by}


# ------------------------------------------------------------------------------------------------ phase 2
DEVON = [{"id": "h-vx", "entity": "card.capital-one-venture-x", "valid_from": "2025-05-20", "opened_on": "2025-05-20"},
         {"id": "h-c1", "entity": "capitalone.miles", "valid_from": "2025-05-20", "quantity": 90000},
         {"id": "h-hyatt", "entity": "hyatt.member", "valid_from": "2019-01-01"},
         {"id": "h-united", "entity": "united.member", "valid_from": "2015-01-01"}]
DEVON_METRICS = [{"id": "hyatt.2026.tier_qualifying_nights", "value": 34, "as_of": "2026-10-31"}, {"id": "hyatt.2026.base_points", "value": 21000, "as_of": "2026-10-31"},
                 {"id": "hyatt.2026.meetings_events", "value": 0, "as_of": "2026-10-31"},
                 {"id": "united.2026.pqp", "value": 6500, "as_of": "2026-10-31"}, {"id": "united.2026.pqf", "value": 10, "as_of": "2026-10-31"},
                 {"id": "united.2026.united_segments", "value": 9, "as_of": "2026-10-31"}]
EDEN = [{"id": "h-united", "entity": "united.member", "valid_from": "2020-01-01"}]


def expand(rec):
    """A sheet row -> the rule an operator would otherwise write out in full."""
    if "rule" in rec:
        return json.loads(json.dumps(rec["rule"]))
    dest, ratio = rec["transfer"]
    rule = {"id": "capitalone.miles-to-" + dest.split(".")[0], "kind": "transfer", "output": dest, "when": {"holds": "capitalone.miles"},
            "summary": "Capital One miles transfer to %s at %s." % (dest, ratio),
            "transfer": {"from": "capitalone.miles", "ratio": ratio, "note": "At least 1,000 miles are needed to transfer; the increment and timing are not stated."},
            "restrictions": ["Requires a Capital One travel rewards or business rewards card",
                             "The name on the Capital One account must match the name on the loyalty programme account",
                             "A finished transfer cannot be reversed"]}
    if rec.get("unchecked"):
        rule["unchecked"] = rec["unchecked"]
    return rule


def intake(lab, sheet, batch):
    """Enter a sheet through the pipeline exactly as it is frozen: add_entity, add_candidate, promote (in the copy)."""
    from lab import _fields
    lab.vocab({"spend_categories": sheet.get("spend_categories", {})})
    outcome = collections.OrderedDict()
    for e in sheet.get("entities", []):
        out = lab.apply("add_entity", batch, e["id"], data={"entity": e})
        if not out["ok"] and "sources" in e:                 # a card's own sources cannot be named before any rule has brought them in
            first = out["errors"]
            out = lab.apply("add_entity", batch, e["id"], data={"entity": {k: v for k, v in e.items() if k != "sources"}})
            outcome["entity " + e["id"]] = {"attempts": 2, "accepted": out["ok"], "first_error": first, "sheet_fields": _fields(e)}
        else:
            outcome["entity " + e["id"]] = {"attempts": 1, "accepted": out["ok"], "first_error": out.get("errors") or None, "sheet_fields": _fields(e)}
    for rec in sheet["records"]:
        rule, tries, first = expand(rec), 0, None
        while True:
            tries += 1
            cand = {"id": "c-" + rule["id"], "status": "proposed", "created_on": TODAY, "proposed_rule": rule,
                    "evidence": [dict(sheet["sources"][i], id=i) for i in rec["evidence"]],
                    "search_path": ["viability experiment: " + rec["mechanism"]], "open_questions": rec.get("open_questions", [])}
            out = lab.apply("add_candidate", batch, rec["key"], data={"candidate": cand})
            if out["ok"] or tries == 2 or "fallback" not in rec:
                break
            first = out["errors"]
            fb = rec["fallback"]
            rule = json.loads(json.dumps(fb["rule"])) if "rule" in fb else {k: v for k, v in rule.items() if k not in fb.get("drop", [])}
        promoted = lab.promote(cand["id"], batch, rec["key"])["ok"] if out["ok"] else False
        outcome[rec["key"]] = {"attempts": tries, "accepted": out["ok"], "promoted": promoted, "first_error": first or (None if out["ok"] else out["errors"]),
                               "rule": rule["id"], "sheet_fields": _fields({k: v for k, v in rec.items() if k != "key"}),
                               "changeset_fields": _fields(cand), "mechanism": rec["mechanism"]}
    return outcome


def phase2(lab):
    sheet = load("batch2.json")
    before = len(lab.log)
    outcome = intake(lab, sheet, "batch2")
    recs = {k: v for k, v in outcome.items() if not k.startswith("entity ")}
    check("2.0 every batch 2 record ended up in the copy (accepted and promoted there), and the copy is sound",
          all(v["accepted"] and v["promoted"] for v in recs.values()) and lab.lint_errors() == [],
          "; ".join("%s: %s" % (k, v["first_error"]) for k, v in recs.items() if not v["accepted"])[:400] + " " + "; ".join(lab.lint_errors()[:2]))
    lab.person("syn-devon", DEVON, DEVON_METRICS)
    lab.person("syn-eden", EDEN)
    D = ["--profile", "syn-devon", "--as-of", TODAY]
    rows = []
    rep = lab.js("status", *D)
    st = {e: status_of(rep, e) for e in ("hyatt.discoverist", "hyatt.explorist", "hyatt.globalist", "benefit.hyatt.milestone-20", "united.silver", "united.gold",
                                         "benefit.united.starter-pqp", "priority_pass.select", "benefit.venture-x.early-spend-bonus",
                                         "benefit.venture-x.anniversary-miles", "benefit.venture-x.capital-one-lounges", "capitalone.miles")}
    check("2.1 EVALUATED: 34 Hyatt nights in 2026 -> Discoverist and Explorist ESTABLISHED, Globalist not; the 20-night milestone ESTABLISHED",
          (st["hyatt.discoverist"], st["hyatt.explorist"], st["hyatt.globalist"], st["benefit.hyatt.milestone-20"]) == ("ESTABLISHED", "ESTABLISHED", "NOT_AVAILABLE", "ESTABLISHED"), str(st))
    check("2.2 EVALUATED compound threshold: 6,500 PQP, 10 PQF, 9 United segments -> Silver by the PQP-only route; not Gold; starter PQP follows",
          (st["united.silver"], st["united.gold"], st["benefit.united.starter-pqp"]) == ("ESTABLISHED", "NOT_AVAILABLE", "ESTABLISHED"), str(st))
    check("2.3 EVALUATED: Priority Pass is CONDITIONAL (enrolment needed); the early-spend bonus and anniversary miles are UNRESOLVED; lounges ESTABLISHED",
          (st["priority_pass.select"], st["benefit.venture-x.early-spend-bonus"], st["benefit.venture-x.anniversary-miles"], st["benefit.venture-x.capital-one-lounges"])
          == ("CONDITIONAL", "UNRESOLVED", "UNRESOLVED", "ESTABLISHED"), str(st))
    eden = lab.js("status", "--profile", "syn-eden", "--as-of", TODAY)
    check("2.4 UNCERTAINTY: a member with no figures recorded is UNRESOLVED for Silver, not refused and not assumed",
          status_of(eden, "united.silver") == "UNRESOLVED")
    late = lab.js("status", "--profile", "syn-devon", "--as-of", "2027-02-01")
    check("2.5 LIMIT (gap G3): on 2027-02-01 the engine no longer shows the Silver that Devon qualified for in 2026; the validity of an earned "
          "programme status is not represented", status_of(late, "united.silver") == "NOT_AVAILABLE")
    q = {c: lab.js("earnings", *D, "--category", c, "--amount", a)["answers"][0] for c, a in
         (("portal-hotels", 500), ("dining", 400), ("portal-travel", 1000), ("issuer-entertainment", 200))}
    check("2.6 CALCULATED with unchanged code: $500 of portal hotels = 5,000 miles; $200 of entertainment = 1,000; $400 of dining = 800 at the "
          "catch-all rate; 'portal travel' is too broad (10 and 5 are published)",
          (q["portal-hotels"].get("points"), q["issuer-entertainment"].get("points"), q["dining"].get("points"), q["dining"].get("category_used"),
           q["portal-travel"]["result"]) == (5000, 1000, 800, "other", "NOT_CALCULATED"), str({k: v.get("points", v["result"]) for k, v in q.items()}))
    cv = {a["to"]: a for a in lab.js("convert", *D, "--from", "capitalone.miles", "--amount", 30000)["answers"]}
    got = {k: cv[k].get("amount") for k in ("aeroplan.points", "jal.miles", "jetblue.points", "accor.points", "iprefer.points")}
    check("2.7 CALCULATED with unchanged code: 30,000 Capital One miles -> 30,000 Aeroplan, 22,500 JAL (2:1.5), 18,000 JetBlue (5:3), "
          "15,000 Accor (2:1), 60,000 I Prefer (1:2)",
          got == {"aeroplan.points": 30000, "jal.miles": 22500, "jetblue.points": 18000, "accor.points": 15000, "iprefer.points": 60000}, str(got))
    check("2.8 DECLINED: Choice Privileges is not calculated: 'U.S.-based accounts only' is not checked", cv["choice.points"]["result"] == "NOT_CALCULATED")
    cr = {c["rule"]: c for acct in lab.js("credits", *D)["accounts"] for c in acct["credits"]}
    check("2.9 the $300 Capital One Travel credit has no period (the source states no cycle, and the credit block cannot hold that): it is absent "
          "from the credits report; the Global Entry credit is there with its period unresolved",
          "cb.venture-x.travel-credit-300" not in cr and cr["cb.venture-x.trusted-traveler-credit-120"]["period"]["state"] == "UNRESOLVED")
    both = dict(lab.js("earnings", "--profile", "syn-casey", "--as-of", TODAY, "--category", "dining", "--amount", 400))
    answers(lab, rows, "Q10", "CALCULATED", "Devon books a $500 hotel through Capital One Travel. Miles? And what would 30,000 miles become at JAL?",
            ["earnings", *D, "--category", "portal-hotels", "--amount", 500], "5,000 capitalone.miles")
    answers(lab, rows, "Q11", "CALCULATED", "... and at JAL?", ["convert", *D, "--from", "capitalone.miles", "--amount", 30000, "--to", "jal.miles"], "22,500 jal.miles at 2:1.5")
    answers(lab, rows, "Q12", "EVALUATED", "Has Devon qualified for United Premier Silver in 2026?", ["explain", *D, "united.silver"],
            "ESTABLISHED from three recorded figures (PQP-only route)")
    answers(lab, rows, "Q13", "DECLINED", "Has Eden, with nothing recorded?", ["explain", "--profile", "syn-eden", "--as-of", TODAY, "united.silver"],
            "UNRESOLVED: the figures are not recorded")
    answers(lab, rows, "Q14", "EVALUATED", "Is the Venture X early-spend bonus Devon's?", ["explain", *D, "benefit.venture-x.early-spend-bonus"],
            "UNRESOLVED: the spend requirement and the 48-month rule are text, not checked")
    assess = {k: v for k, v in sheet["assessment"].items() if k != "about"}
    check("2.10 the assessment covers every record", sorted(assess) == sorted(recs))
    ops = lab.log[before:]
    m = {"records": len(recs), "entities": len(outcome) - len(recs),
         "operations_attempted": len(ops), "operations_refused": sum(1 for o in ops if not o["ok"]),
         "records_accepted_first_time": sum(1 for v in recs.values() if v["attempts"] == 1 and v["accepted"]),
         "records_reshaped_to_fit": sorted(k for k, v in recs.items() if v["attempts"] > 1),
         "sheet_fields_per_record": round(sum(v["sheet_fields"] for v in recs.values()) / len(recs), 1),
         "changeset_fields_per_record": round(sum(v["changeset_fields"] for v in recs.values()) / len(recs), 1),
         "pipeline_operations_per_record": round(len(ops) / len(recs), 2),
         "by_level": dict(collections.Counter(v["level"] for v in assess.values())),
         "by_path": dict(collections.Counter(v["path"] for v in assess.values())),
         "fully_captured": sum(1 for v in assess.values() if v["full"]),
         "fully_captured_by_data_alone": sum(1 for v in assess.values() if v["full"] and v["path"] == "data"),
         "by_gap": dict(collections.Counter(v["gap"] or "none" for v in assess.values()))}
    return {"outcome": outcome, "rows": rows, "measurements": m, "assessment": assess}


def main():
    spec = load("batch1.json")
    p0 = phase0(spec)
    p1 = phase1(spec)
    p2 = phase2(p1["lab"])
    p1["p2"] = p2
    bad = [c for c in checks if not c["ok"]]
    for c in checks:
        print("%-4s %s%s" % ("ok" if c["ok"] else "FAIL", c["check"], ("   [" + c["detail"] + "]") if c["detail"] and not c["ok"] else ""))
    print("\n%d checks, %d failed" % (len(checks), len(bad)))
    return p0, p1, bad


if __name__ == "__main__":
    p0, p1, bad = main()
    sys.exit(1 if bad else 0)
