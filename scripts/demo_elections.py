"""Before/after demonstration of cardholder elections (ENG-02) on the real Bilt Palladium content, on a throwaway copy.

    python3 scripts/demo_elections.py

Touches nothing in the project. In a temp copy of the live store it:
  - promotes Argon's five election-governed Bilt candidates (THERE ONLY: the committed store keeps them proposed),
    because the hazard ENG-02 guards against is what happens after promotion;
  - creates one invented cardholder ("Bilt Holder (synthetic)", account opened 2025-06-01; every date invented);
  - records the card, mistakes, an election and a change of election through changeset files and `prices apply`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(prefix="prices-demo-elections-")
work = os.path.join(tmp, "store")
for d in ("data", "profiles", "tables"):
    shutil.copytree(os.path.join(ROOT, d), os.path.join(work, d))
os.mkdir(os.path.join(tmp, "changesets"))
P, OWNER = "synthetic-bilt", "Bilt Holder (synthetic)"
B = "benefit.bilt-palladium."
FIVE = ["housing-tiered-points", "housing-flex-bilt-cash-legacy", "annual-bilt-cash-200-legacy", "hotel-credit-400-semiannual-legacy",
        "annual-bilt-cash-600-post2027"]
n = [0]


def sh(*args, expect=0, show=True):
    if show:
        print("\n$ python3 -m prices --root <copy> " + " ".join(a.replace(tmp, "<tmp>") for a in args))
    p = subprocess.run([sys.executable, "-m", "prices", "--root", work] + list(args), cwd=ROOT, capture_output=True, text=True)
    out = (p.stdout + p.stderr).rstrip()
    if show:
        print(out)
    if p.returncode != expect:
        sys.exit("unexpected exit code %d (wanted %d)\n%s" % (p.returncode, expect, out))
    return out


def change(date, op, by=None, expect=0, show_file=True, **body):
    n[0] += 1
    cs = dict({"id": "cs-%s-demo-el-%02d-%s" % (date.replace("-", ""), n[0], op.replace("_", "-")), "op": op, "author": "junior maintainer",
               "date": date, "reason": "Election demonstration (invented data)"}, **body)
    if by:
        cs["attestation"] = {"by": by[0], "on": date, "statement": by[1]}
    path = os.path.join(tmp, "changesets", cs["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cs, f, indent=2)
    if show_file:
        print("\n--- changeset file %s.json" % cs["id"])
        print(json.dumps(cs, indent=2))
    sh("apply", path, expect=expect)


def table(day):
    out = json.loads(sh("--json", "status", "--profile", P, "--as-of", day, show=False))
    have = {}
    for key in ("derived_entitlements", "conditional", "unresolved"):
        for x in out[key]:
            have[x["entity"]] = {"derived_entitlements": "ESTABLISHED", "conditional": "CONDITIONAL", "unresolved": "UNRESOLVED"}[key]
    print("\n  %s" % day)
    for k in FIVE:
        print("    %-40s %s" % (k, have.get(B + k, "NOT_AVAILABLE")))
    for e in out.get("elections", []):
        print("    election %-33s %s" % (e["group"], ("IN EFFECT " + e["established"]) if e["established"] else "UNRESOLVED (%s)" % e["reason"]))


print("=== 0. Scratch setup: promote the five governed Bilt candidates (scratch copy only) and create one invented person")
reviewer = json.load(open(os.path.join(work, "data/kb/vocab.json")))["promotion_reviewers"][0]
for k in FIVE:
    change("2026-11-15", "promote_candidate", (reviewer, "Scratch-copy promotion for the ENG-02 demonstration only."), show_file=False,
           target="c-cb.bilt-palladium." + k, data={"review_by": "2027-11-15"})
os.makedirs(os.path.join(work, "profiles", P, "holdings"))
with open(os.path.join(work, "profiles", P, "profile.json"), "w", encoding="utf-8") as f:
    json.dump({"id": P, "label": "Invented Bilt Palladium cardholder", "synthetic": True, "owner": OWNER}, f, indent=2)

print("\n\n=== 1. BEFORE ENG-02 would have mattered: what the same rules would grant with no election check")
print("    (without the election definitions every one of the five would be ESTABLISHED for any cardholder: both housing")
print("     options at once, and both the legacy credits and the $600 from 2027 on. tests/test_n_elections.py shows this.)")

print("\n\n=== 2. Record the card, with the opening date the anniversary comes from")
change("2026-11-15", "set_holding", (OWNER, "I hold Bilt Palladium; account opened June 1, 2025."), profile=P,
       data={"holding": {"id": "h-bilt-palladium", "entity": "card.bilt-palladium", "state": "confirmed", "valid_from": "2025-06-01",
                         "opened_on": "2025-06-01"}})
print("\n--- no election recorded: housing options UNRESOLVED; legacy credits apply by default until this account's 2027 anniversary")
for day in ("2026-11-15", "2027-05-31", "2027-06-01"):
    table(day)
sh("explain", "--profile", P, "--as-of", "2026-11-15", B + "housing-tiered-points")

print("\n\n=== 3. Mistakes")
print("\n(a) the maintainer, not the owner, confirms an election: refused")
change("2026-11-16", "set_holding", ("junior maintainer", "I think they chose tiered points."), expect=2, profile=P,
       data={"holding": {"id": "el-housing-1", "entity": "election.bilt-palladium.housing-tiered-points", "state": "confirmed", "valid_from": "2025-06-01"}})
print("\n(b) a rule that no longer needs the election cannot be slipped in: revising a definition needs a reviewer")
change("2026-11-16", "revise_entity", ("junior maintainer", "Simplify."), expect=2, target="election.bilt-palladium.housing-tiered-points",
       data={"set": {"election": {"group": "bilt-palladium.housing-rewards", "card": "card.bilt-palladium", "governs": ["cb.bilt-palladium.base-2x-everyday"]}}})

print("\n\n=== 4. Record the owner's housing election: only that pathway applies")
change("2026-11-16", "set_holding", (OWNER, "My housing rewards option has been housing-only tiered points since I opened the card."), profile=P,
       data={"holding": {"id": "el-housing-1", "entity": "election.bilt-palladium.housing-tiered-points", "state": "confirmed", "valid_from": "2025-06-01"}})
table("2026-11-16")

print("\n\n=== 5. A contradictory record: accepted with a warning, and NEITHER housing option is applied while it stands")
change("2026-11-20", "set_holding", None, profile=P,
       data={"holding": {"id": "el-housing-2", "entity": "election.bilt-palladium.housing-flex-bilt-cash", "state": "unconfirmed", "valid_from": "2026-11-01"}})
table("2026-11-20")
print("\n--- resolved: the owner says the Flex entry was a mistake. It is withdrawn: kept on file, never in effect on any date")
change("2026-11-21", "end_holding", (OWNER, "I never switched to Flex; that entry is wrong."), profile=P, target="el-housing-2",
       data={"withdrawn": True})
table("2026-11-21")

print("\n\n=== 6. The 2027 transition: the owner keeps the legacy credits, then later switches housing to Flex")
change("2026-12-10", "set_holding", (OWNER, "I elected to keep the legacy $200 Bilt Cash + $400 hotel credit structure."), profile=P,
       data={"holding": {"id": "el-credits-1", "entity": "election.bilt-palladium.annual-credits-legacy", "state": "confirmed", "valid_from": "2026-12-10"}})
change("2027-03-01", "end_holding", (OWNER, "I switched housing rewards to Flexible Bilt Cash from March 1."), profile=P, target="el-housing-1",
       data={"ended_on": "2027-02-28"})
change("2027-03-01", "set_holding", (OWNER, "Flexible Bilt Cash from March 1, 2027."), profile=P,
       data={"holding": {"id": "el-housing-3", "entity": "election.bilt-palladium.housing-flex-bilt-cash", "state": "confirmed", "valid_from": "2027-03-01"}})
for day in ("2027-02-28", "2027-03-01", "2027-06-01"):
    table(day)
print("\n--- Flex was elected before this account's first 2027 anniversary (June 1), as its terms require. A Flex election")
print("    recorded for after that date would be flagged ELECTION_NOT_PERMITTED and applied as neither option.")

print("\n\n=== 7. AFTER: the timeline shows every change on its day")
sh("timeline", "--profile", P, "--as-of", "2026-11-15", "--until", "2027-12-31")
sh("lint")
sh("tables", "status")
print("\nDEMO COMPLETE (work copy: %s)" % work)
