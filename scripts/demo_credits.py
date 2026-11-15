"""Before/after demonstration of recurring-credit maintenance (docs/operations/OP-13-recurring-credits.md) on a throwaway copy.

    python3 scripts/demo_credits.py

Prints every table edit, changeset file, command and its output. Touches nothing in the project: it works in a temp
directory on a copy of fixtures/synthetic-credits. Everything is invented: the card, the credits, the people
("Erin (synthetic)", "Finn (synthetic)") and every figure and date.

The story: a maintainer corrects a published term, adds a new credit, makes some mistakes that are refused, and
records what two cardholders say about their own accounts. Blake (another invented person, whose card has no credit
terms) is checked before and after to show that nothing about them changes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "fixtures"))
sys.path.insert(0, ROOT)
from synthetic_credits import edit_table  # noqa: E402

tmp = tempfile.mkdtemp(prefix="prices-demo-credits-")
work = shutil.copytree(os.path.join(ROOT, "fixtures", "synthetic-credits"), os.path.join(tmp, "fx"))
os.mkdir(os.path.join(tmp, "changesets"))
CARD, ACCT = "card.northwind-voyager", "h-card-northwind-voyager"
ERIN, FINN = "synthetic-erin", "synthetic-finn"
OWNER = {ERIN: "Erin (synthetic)", FINN: "Finn (synthetic)"}
count = [0]


def sh(*args, expect=0, show=True, keep=None):
    """Run a prices command. keep: only print lines containing one of these strings (the full output is long)."""
    if show:
        print("\n$ python3 -m prices --root <copy> " + " ".join(a.replace(tmp, "<tmp>") for a in args))
    p = subprocess.run([sys.executable, "-m", "prices", "--root", work] + list(args), cwd=ROOT, capture_output=True, text=True)
    out = (p.stdout + p.stderr).rstrip()
    if show:
        lines = out.splitlines()
        if keep:
            lines = [ln for ln in lines if any(k in ln for k in keep)]
        print("\n".join(lines))
    if p.returncode != expect:
        sys.exit("unexpected exit code %d (wanted %d)\n%s" % (p.returncode, expect, out))
    return out


def table(name, note, **kw):
    print("\n--- edit tables/%s.csv: %s" % (name, note))
    edit_table(work, name, **kw)


def change(date, op, person=None, owner_says=None, expect=0, **body):
    count[0] += 1
    cs = dict({"id": "cs-%s-demo-%02d-%s" % (date.replace("-", ""), count[0], op.replace("_", "-")), "op": op,
               "author": "junior maintainer", "date": date, "reason": "Recurring-credit demonstration (invented data)"}, **body)
    if person:
        cs["profile"] = person
    if owner_says:
        cs["attestation"] = {"by": owner_says[0], "on": date, "statement": owner_says[1]}
    path = os.path.join(tmp, "changesets", cs["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cs, f, indent=2)
    print("\n--- changeset file %s.json" % cs["id"])
    print(json.dumps(cs, indent=2))
    sh("apply", path, expect=expect)


def source(sid, text):
    return {"id": sid, "url": "https://example.invalid/northwind/" + sid, "title": "Northwind Voyager credit terms", "publisher": "Northwind Bank (synthetic)",
            "source_type": "synthetic", "retrieved_on": "2027-07-10", "applies_to": CARD, "summary": text, "notes": "Invented for the demonstration."}


HOTEL = ["curated hotel credit", "PUBLISHED   voyager.curated-hotel", "per transaction: maximum 250", "per transaction: maximum 200"]
blake_before = sh("--json", "status", "--profile", "synthetic-blake", "--as-of", "2027-07-10", show=False)

print("=== 0. BEFORE: the published terms, and one cardholder's view")
sh("lint")
out = sh("credits", "--as-of", "2027-07-10", "--card", CARD, show=False)
print("\n$ python3 -m prices --root <copy> credits --as-of 2027-07-10 --card %s      (8 credits; one shown)" % CARD)
block = out[out.index("Northwind Voyager curated hotel credit"):]
print(block[:block.index("\n\n")])

print("\n\n=== 1. Correct a published term. The source, read again, says 200 per booking, not 250")
table("credits", "voyager.curated-hotel-credit: max_per_transaction 250 -> 200 (no source named yet)",
      change={"voyager.curated-hotel-credit": {"max_per_transaction": "200"}})
sh("tables", "import", "--author", "junior maintainer", "--date", "2027-07-10", expect=2)
print("\n(refused: a rule in force is never changed without naming the source. Nothing was applied.)")
table("sources", "add the source that was re-read", add=[source("ev-demo-hotel-terms-2027-07", "Curated hotel credit: 500 per calendar year, 200 per booking, two-night minimum.")])
table("credits", "name it in _evidence", change={"voyager.curated-hotel-credit": {"_evidence": "ev-demo-hotel-terms-2027-07"}})
sh("tables", "import", "--author", "junior maintainer", "--date", "2027-07-10")
sh("credits", "--profile", ERIN, "--as-of", "2027-07-10", keep=HOTEL)
print("\n--- the record as it was is kept (before-snapshot), and the change is in the log")
prev = [n for n in sorted(os.listdir(os.path.join(work, "data", "audit", "previous"))) if "set-credit-terms" in n and "20270710" in n][-1]
with open(os.path.join(work, "data", "audit", "previous", prev), encoding="utf-8") as f:
    before = json.load(f)["records"]["data/kb/rules/voyager.curated-hotel-credit.json"]["before"]["credit"]
print("before: %s" % json.dumps(before, sort_keys=True))
with open(os.path.join(work, "data", "kb", "rules", "voyager.curated-hotel-credit.json"), encoding="utf-8") as f:
    print("after:  %s" % json.dumps(json.load(f)["credit"], sort_keys=True))
sh("audit", "--last", "1")

print("\n\n=== 2. Add a new credit in the tables. It enters as a candidate and establishes nothing until a reviewer promotes it")
table("benefits", "new benefit", add=[{"id": "benefit.voyager.spa-credit", "name": "Northwind Voyager spa credit (synthetic)"}])
table("sources", "its source", add=[source("ev-demo-spa-terms", "Spa credit: 50 per calendar quarter; the terms do not say whether it carries over.")])
table("card_benefits", "the card carries it", add=[{"id": "voyager.spa-credit", "card": CARD, "benefit": "benefit.voyager.spa-credit", "applicability": "confirmed",
                                                 "summary": "50 spa credit each calendar quarter.", "evidence": "ev-demo-spa-terms"}])
table("credits", "its terms; rollover is left empty because the source does not say",
      add=[{"id": "voyager.spa-credit", "amount": "50", "unit": "USD", "cycle": "calendar_quarter"}])
sh("tables", "import", "--author", "junior maintainer", "--date", "2027-07-10")
SPA = ["spa credit", "voyager.spa-credit", "APPLIES", "rollover:"]
print("\n--- not in the ordinary report (quarantined):")
sh("credits", "--profile", ERIN, "--as-of", "2027-07-10", keep=["spa"])
print("\n--- visible on request, and never established:")
out = sh("credits", "--profile", ERIN, "--as-of", "2027-07-10", "--candidates", show=False)
block = out[out.index("  Northwind Voyager spa credit"):]
print(block[:block.index("\n\n")])
change("2027-07-12", "promote_candidate", owner_says=("Synthetic Reviewer", "Reviewed against the cited source."), target="c-voyager.spa-credit",
       data={"review_by": "2028-07-12"})
out = sh("credits", "--profile", ERIN, "--as-of", "2027-07-12", show=False)
block = out[out.index("  Northwind Voyager spa credit"):]
print(block[:block.index("\n\n")])

print("\n\n=== 3. Mistakes. Each is refused and no record changes")
print("\n(a) an amount that is not a number")
table("credits", "voyager.dining-credit amount -> 'lots'", change={"voyager.dining-credit": {"amount": "lots", "_evidence": "ev-demo-spa-terms"}})
sh("tables", "import", "--author", "junior maintainer", "--date", "2027-07-12", expect=2)
print("\n(b) a cycle the program does not know (it does not guess the nearest one)")
table("credits", "voyager.dining-credit amount back to 150; cycle -> 'fortnightly'", change={"voyager.dining-credit": {"amount": "150", "cycle": "fortnightly"}})
sh("tables", "import", "--author", "junior maintainer", "--date", "2027-07-12", expect=2)
sh("tables", "export", show=False)                       # discard the bad edits
print("\n(c) changing a rule in force by changeset without evidence")
change("2027-07-12", "set_credit_terms", expect=2, target="voyager.ride-credit", data={"credit": {"amount": 15, "unit": "USD", "cycle": "calendar_month"}})
print("\n(d) writing 0 where the source gives no cap (leave the key out instead)")
change("2027-07-12", "set_credit_terms", expect=2, target="voyager.spa-credit", evidence=[dict(source("ev-demo-spa-terms-2", "Spa credit terms, re-read."), applies_to=[CARD], retrieved_on="2027-07-12")],
       data={"credit": {"amount": 50, "unit": "USD", "cycle": "calendar_quarter", "max_per_transaction": 0}})

print("\n\n=== 4. A cardholder whose opening date is not on file: the anniversary period is unresolved, not guessed")
TRAVEL = ["ACCOUNT", "annual travel credit", "PERIOD      UNRESOLVED - the opening", "PERIOD      2027  2027-05", "CREDIT_PERIOD_UNRESOLVED h-card-northwind-voyager: benefit.voyager.travel"]
sh("credits", "--profile", FINN, "--as-of", "2027-07-12", keep=TRAVEL)
change("2027-07-13", "set_holding", FINN, (OWNER[FINN], "My Voyager account was opened on May 1, 2026."),
       data={"holding": {"id": ACCT, "entity": CARD, "state": "confirmed", "valid_from": "2026-05-01", "opened_on": "2026-05-01"}})
sh("credits", "--profile", FINN, "--as-of", "2027-07-13", keep=TRAVEL)

print("\n\n=== 5. What a cardholder's own account shows: a period record and its uses")
DINING = ["dining credit", "PERIOD      2027-H", "ALLOWANCE   150", "record e-dining", "allowance 150 USD", "PERSONAL    NOT RECORDED - nothing is recorded for this account and period"]
print("\n--- before: the card publishes 150 for July-December; nothing says what Erin has left")
out = sh("credits", "--profile", ERIN, "--as-of", "2027-07-13", show=False)
block = out[out.index("  Northwind Voyager dining credit"):]
print(block[:block.index("\n\n")])
change("2027-08-02", "record_entitlement", ERIN, (OWNER[ERIN], "My account shows the 150 dining credit for July to December 2027."),
       data={"entitlement": {"id": "e-dining-2027-h2", "rule": "voyager.dining-credit", "account": ACCT, "cycle": "2027-H2", "state": "confirmed",
                             "effective_from": "2027-07-01", "expires_on": "2027-12-31", "allowance": {"amount": 150, "unit": "USD"},
                             "basis": "Credit tracker on the account page"}})
change("2027-08-02", "record_usage", ERIN, (OWNER[ERIN], "40 of it was applied to a dinner on July 30."), target="e-dining-2027-h2",
       data={"usage": {"id": "u-2027-07-30", "amount": 40, "used_on": "2027-07-30", "state": "confirmed", "basis": "Dinner"}})
out = sh("credits", "--profile", ERIN, "--as-of", "2027-08-02", show=False)
block = out[out.index("  Northwind Voyager dining credit"):]
print(block[:block.index("\n\n")])
print("\n--- a single use above the published per-booking maximum (now 200) is refused")
change("2027-08-02", "record_entitlement", ERIN, (OWNER[ERIN], "My account shows the 500 hotel credit for 2027."),
       data={"entitlement": {"id": "e-hotel-2027", "rule": "voyager.curated-hotel-credit", "account": ACCT, "cycle": "2027", "state": "confirmed",
                             "effective_from": "2027-01-01", "expires_on": "2027-12-31", "allowance": {"amount": 500, "unit": "USD"}}})
change("2027-08-02", "record_usage", ERIN, (OWNER[ERIN], "I used 230 on one booking."), expect=2, target="e-hotel-2027",
       data={"usage": {"id": "u-2027-07-20", "amount": 230, "used_on": "2027-07-20", "state": "confirmed"}})
print("\n--- time travel: on January 1 the half-year credit resets. The published 150 is back; Erin's balance for the new period is NOT assumed")
out = sh("credits", "--profile", ERIN, "--as-of", "2028-01-01", show=False)
block = out[out.index("  Northwind Voyager dining credit"):]
print(block[:block.index("\n\n")])

print("\n\n=== 6. Two credits the cardholder chooses between: with no election on file, neither is established (ENG-02)")
PERK = ["lifestyle credit (synthetic)  [", "wellness credit (synthetic)  [", "APPLIES", "only under election"]
out = sh("credits", "--profile", ERIN, "--as-of", "2027-08-02", show=False)
for name in ("lifestyle", "wellness"):
    block = out[out.index("  Northwind Voyager %s credit" % name):]
    print("\n".join(ln for ln in block[:block.index("\n\n")].splitlines() if any(k in ln for k in PERK)))
change("2027-08-03", "set_holding", ERIN, (OWNER[ERIN], "I chose the wellness credit when I opened the account."),
       data={"holding": {"id": "el-annual-perk", "entity": "election.voyager.wellness-credit", "state": "confirmed", "valid_from": "2024-11-02"}})
out = sh("credits", "--profile", ERIN, "--as-of", "2027-08-03", show=False)
for name in ("lifestyle", "wellness"):
    block = out[out.index("  Northwind Voyager %s credit" % name):]
    print("\n".join(ln for ln in block[:block.index("\n\n")].splitlines() if any(k in ln for k in PERK + ["ALLOWANCE"])))

print("\n\n=== 7. AFTER: what the calendar does next (period ends, resets and the end of an offer)")
sh("review", "--profile", ERIN, "--from", "2027-09-15", "--to", "2027-11-05")
sh("lint")
print("(the warning is a consequence of step 1: once the published maximum became 200, Alex's earlier recorded use of 250 on one booking\n"
      " no longer fits the terms. It is surfaced for a person to look at; the owner's record is not altered.)")
sh("tables", "status")

print("\n\n=== 8. People whose card has no credit terms: unchanged, byte for byte")
blake_after = sh("--json", "status", "--profile", "synthetic-blake", "--as-of", "2027-07-10", show=False)
same = json.loads(blake_before) == json.loads(blake_after) or {k: v for k, v in json.loads(blake_before).items() if k != "sourced_rules"} == \
    {k: v for k, v in json.loads(blake_after).items() if k != "sourced_rules"}
print("synthetic-blake status report identical before and after (apart from the list of public rules, which gained one): %s" % ("yes" if same else "NO"))
if not same:
    sys.exit("another person's report changed")
print("\nDEMO COMPLETE (work copy: %s)" % work)
