"""Before/after demonstration of earned benefits (docs/operations/OP-11-earned-benefits.md) on a throwaway copy.

    python3 scripts/demo_earned.py

Prints every changeset file, every command and its output. Touches nothing in the project: it works
in a temp directory on a copy of fixtures/synthetic-earned. Everything is invented: the card, the
benefits, the person ("Casey (synthetic)") and every figure and date.

The story: Casey holds the invented Northwind Voyager card and missed the 75,000 threshold in 2026.
This run records Casey's 2027 year one fact at a time and shows, after each, what the program does
and does not conclude. Blake (another invented person, with no earned-benefit records) is checked
before and after to show that nothing about them changes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(prefix="prices-demo-earned-")
work = shutil.copytree(os.path.join(ROOT, "fixtures", "synthetic-earned"), os.path.join(tmp, "fx"))
os.mkdir(os.path.join(tmp, "changesets"))
CASEY, OWNER, ACCT, MEASURE = "synthetic-casey", "Casey (synthetic)", "h-card-northwind-voyager", "voyager.qualifying-spend"
STATUS = "status.orbit-concierge"
count = [0]


def sh(*args, expect=0, show=True):
    cmd = [sys.executable, "-m", "prices", "--root", work] + list(args)
    if show:
        print("\n$ python3 -m prices --root <copy> " + " ".join(a.replace(tmp, "<tmp>") for a in args))
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    out = (p.stdout + p.stderr).rstrip()
    if show:
        print(out)
    if p.returncode != expect:
        sys.exit("unexpected exit code %d (wanted %d)\n%s" % (p.returncode, expect, out))
    return out


def change(date, op, owner_says=None, expect=0, **body):
    """Write one changeset file, as a maintainer would, and apply it with the ordinary command."""
    count[0] += 1
    cs = dict({"id": "cs-%s-demo-%02d-%s" % (date.replace("-", ""), count[0], op.replace("_", "-")), "op": op,
               "author": "junior maintainer", "date": date, "reason": "Earned-benefit demonstration (invented data)", "profile": CASEY}, **body)
    if owner_says:
        cs["attestation"] = {"by": owner_says[0], "on": date, "statement": owner_says[1]}
    path = os.path.join(tmp, "changesets", cs["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cs, f, indent=2)
    print("\n--- changeset file %s.json" % cs["id"])
    print(json.dumps(cs, indent=2))
    sh("apply", path, expect=expect)
    return cs["id"]


def reading(rid, value, observed_on, state="confirmed", **extra):
    return {"account": ACCT, "measure": MEASURE, "cycle": "2027", "reading": dict({"id": rid, "value": value, "observed_on": observed_on, "state": state}, **extra)}


def earned(as_of, *more):
    sh("earned", "--profile", CASEY, "--as-of", as_of, "--cycle", "2027", *more)


print("=== 0. BEFORE: the rules are on offer; nothing is recorded for Casey's 2027; nothing is assumed")
sh("lint")
earned("2027-09-01")
blake_before = sh("--json", "status", "--profile", "synthetic-blake", "--as-of", "2027-12-10", show=False)
store_before = sh("--json", "status", "--profile", "synthetic-alex", "--as-of", "2027-12-10", show=False)

print("\n\n=== 1. Record progress that is still below the threshold")
change("2027-09-05", "record_progress", (OWNER, "August statement shows 52,000 in qualifying purchases this year."),
       data=reading("r-2027-08", 52000, "2027-08-31", basis="August statement"))
earned("2027-09-05")

print("\n\n=== 2. Four mistakes. Each is refused and no record changes")
print("\n(a) the maintainer, not the owner, tries to mark a figure confirmed")
change("2027-11-03", "record_progress", ("junior maintainer", "I am sure Casey has reached it."), expect=2,
       data=reading("r-2027-10", 79400, "2027-10-31"))
print("\n(b) a figure dated in the future")
change("2027-11-03", "record_progress", (OWNER, "I will have reached it by December."), expect=2,
       data=reading("r-2027-12", 90000, "2027-12-15"))
print("\n(c) the August figure typed in a second time under a new id")
change("2027-11-03", "record_progress", (OWNER, "August statement shows 52,000."), expect=2,
       data=reading("r-2027-08-again", 52000, "2027-08-31"))
print("\n(d) recording the status as held, with the dates left out")
change("2027-11-03", "record_entitlement", (OWNER, "I should have the status by now."), expect=2,
       data={"entitlement": {"id": "e-2027-concierge-status", "rule": "voyager.earn-concierge-status", "account": ACCT, "cycle": "2027", "state": "confirmed"}})

print("\n\n=== 3. Record the figure that reaches the threshold: Casey becomes ELIGIBLE. Nothing is held yet")
change("2027-11-03", "record_progress", (OWNER, "October statement shows 79,400 in qualifying purchases this year."),
       data=reading("r-2027-10", 79400, "2027-10-31", basis="October statement"))
earned("2027-11-03")
sh("explain", "--profile", CASEY, "--as-of", "2027-11-03", STATUS)
print("\n--- time travel: the same question asked for October 15, before the October 31 figure")
sh("explain", "--profile", CASEY, "--as-of", "2027-10-15", STATUS)
print("\n--- and for August 15, when the August 31 figure shows Casey was still below")
sh("explain", "--profile", CASEY, "--as-of", "2027-08-15", STATUS)

print("\n\n=== 4. Record what is actually on the account: the status and the credit, each with its own dates")
change("2027-11-12", "record_entitlement", (OWNER, "Account page shows Orbit Concierge status from November 10, 2027 through February 28, 2029."),
       data={"entitlement": {"id": "e-2027-concierge-status", "rule": "voyager.earn-concierge-status", "account": ACCT, "cycle": "2027",
                             "state": "confirmed", "effective_from": "2027-11-10", "expires_on": "2029-02-28", "basis": "Account page"}})
change("2027-11-12", "record_entitlement", (OWNER, "Account page shows a 300 travel credit, from November 10, 2027, good through December 31, 2028."),
       data={"entitlement": {"id": "e-2027-milestone-credit", "rule": "voyager.earn-milestone-credit", "account": ACCT, "cycle": "2027",
                             "state": "confirmed", "effective_from": "2027-11-10", "expires_on": "2028-12-31",
                             "allowance": {"amount": 300, "unit": "units"}, "basis": "Account page"}})
print("\n--- the suite night award needs its own activation step. That step has not been done, so the award stays 'eligible'")
earned("2027-11-12")

print("\n\n=== 5. Record a use of the credit: allowance, used and remaining stay three separate numbers")
change("2027-12-04", "record_usage", (OWNER, "Used 140 of the travel credit on December 2."), target="e-2027-milestone-credit",
       data={"usage": {"id": "u-2027-12-02", "amount": 140, "used_on": "2027-12-02", "state": "confirmed", "basis": "Airfare"}})
sh("earned", "--profile", CASEY, "--as-of", "2027-12-04", "--cycle", "2027", "--detail")
print("\n--- time travel: the day before that use, the full 300 was still there")
sh("status", "--profile", CASEY, "--as-of", "2027-12-01")
sh("status", "--profile", CASEY, "--as-of", "2027-12-04")

print("\n\n=== 6. A correction: the October figure was misread. The old entry is kept, marked superseded")
change("2027-12-10", "correct_entry", (OWNER, "I misread the October statement: it shows 74,400, not 79,400."),
       data={"record": "qualification", "id": "q-%s-%s-2027" % (ACCT, MEASURE), "entry": "r-2027-10",
             "replacement": {"id": "r-2027-10b", "value": 74400, "observed_on": "2027-10-31", "state": "confirmed", "basis": "October statement, re-read"}})
print("\n--- the account records stand on Casey's word, and the gap behind them is flagged, not hidden")
earned("2027-12-10", "--detail")

print("\n\n=== 7. The year-end figure settles it")
change("2028-01-05", "record_progress", (OWNER, "Year-end summary shows 88,000 in qualifying purchases for 2027."),
       data=reading("r-2027-final", 88000, "2027-12-31", final=True, basis="Year-end summary"))
earned("2028-01-05")

print("\n\n=== 8. AFTER: what the calendar does next, with no further input")
sh("timeline", "--profile", CASEY, "--as-of", "2028-01-05", "--until", "2029-06-01")
earned("2029-03-01")

print("\n\n=== 9. History: every change is in the log, with a copy of the changeset and the record as it was before")
sh("audit", "--last", "12")
prev = os.path.join(work, "data", "audit", "previous")
print("\nbefore-snapshots kept for this run: " + ", ".join(sorted(n[:-5] for n in os.listdir(prev) if "-demo-" in n)))
sh("lint")
sh("tables", "status")

print("\n\n=== 10. People with no new personal facts: unchanged, byte for byte")
blake_after = sh("--json", "status", "--profile", "synthetic-blake", "--as-of", "2027-12-10", show=False)
alex_after = sh("--json", "status", "--profile", "synthetic-alex", "--as-of", "2027-12-10", show=False)
print("synthetic-blake status report identical before and after: %s" % ("yes" if blake_before == blake_after else "NO"))
print("synthetic-alex  status report identical before and after: %s" % ("yes" if store_before == alex_after else "NO"))
if blake_before != blake_after or store_before != alex_after:
    sys.exit("another person's report changed")
print("\nDEMO COMPLETE (work copy: %s)" % work)
