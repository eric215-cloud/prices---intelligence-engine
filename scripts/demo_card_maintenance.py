"""Run the junior-maintainer card task (docs/operations/OP-10-tables.md) on a throwaway copy of the synthetic fixture.

    python3 scripts/demo_card_maintenance.py

Prints every command and its output. Touches nothing in the project: it works in a temp directory.
The cell edits are made by code here only so the run can be repeated; a person would make the
same edits in a spreadsheet or text editor.
"""
import csv
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from prices.tables import COLUMNS  # noqa: E402

work = os.path.join(tempfile.mkdtemp(prefix="prices-demo-"), "fx")
shutil.copytree(os.path.join(ROOT, "fixtures", "synthetic-cards"), work)
VOYAGER, KESTREL = "card.northwind-voyager", "card.halcyon-kestrel"


def sh(*args, expect=0):
    cmd = [sys.executable, "-m", "prices", "--root", work] + list(args)
    print("\n$ python3 -m prices --root <copy> " + " ".join(args))
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print((p.stdout + p.stderr).rstrip())
    if p.returncode != expect:
        sys.exit("unexpected exit code %d (wanted %d)" % (p.returncode, expect))


def cells(table, rid=None, **values):
    path = os.path.join(work, "tables", table + ".csv")
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if rid is None:
        rows.append(values)
        print("  edit: %s.csv  + new row %s" % (table, values["id"]))
    else:
        row = [r for r in rows if r["id"] == rid][0]
        row.update(values)
        print("  edit: %s.csv  row %s  set %s" % (table, rid, ", ".join(sorted(values))))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS[table])
        for r in rows:
            w.writerow([r.get(c, "") for c in COLUMNS[table]])


def src(sid, card, day, summary):
    return dict(id=sid, url="https://example.invalid/" + sid, title="Synthetic document " + sid, publisher="Synthetic Bank",
                source_type="synthetic", retrieved_on=day, applies_to=card, summary=summary)


print("=== 0. Starting point")
sh("tables", "export")
sh("tables", "status")
sh("cards", "--profile", "synthetic-alex", "--as-of", "2026-12-01")

print("\n=== 1. The 2027 guide changes a benefit's terms. Writing the new terms over the old ones is refused")
cells("sources", **src("ev-voyager-2027", VOYAGER, "2026-12-01", "2027 guide: from January 1, 2027 the travel credit is 250 and excludes rail; phone protection ends June 30, 2027."))
cells("card_benefits", "voyager.travel-credit", summary="250 annual travel credit per cardmember year.",
      restrictions="Travel purchases only | Rail fares excluded | Resets on the account anniversary",
      evidence="ev-syn-voyager-guide;ev-voyager-2027")
sh("tables", "import", "--author", "junior maintainer", "--date", "2026-12-01", expect=2)
print("\n(refused: that edit would also change what the engine says about 2026. Nothing was applied.)")
sh("tables", "export")                                    # discard the edit

print("\n=== 1b. The right way: end the old terms on their last day and add the new terms from the next day")
cells("sources", **src("ev-voyager-2027", VOYAGER, "2026-12-01", "2027 guide: from January 1, 2027 the travel credit is 250 and excludes rail; phone protection ends June 30, 2027."))
cells("card_benefits", "voyager.travel-credit", valid_to="2026-12-31", evidence="ev-syn-voyager-guide;ev-voyager-2027")
sh("tables", "import", "--author", "junior maintainer", "--date", "2026-12-01")
print("\n(first import: the old terms now end on 2026-12-31. Second import: the new terms, and the other edits.)")
cells("card_benefits", id="voyager.travel-credit-2027", card=VOYAGER, benefit="benefit.voyager.travel-credit", applicability="confirmed",
      summary="250 annual travel credit per cardmember year.", restrictions="Travel purchases only | Rail fares excluded | Resets on the account anniversary",
      valid_from="2027-01-01", evidence="ev-voyager-2027")
cells("card_benefits", "voyager.phone-protection", valid_to="2027-06-30", evidence="ev-syn-voyager-guide;ev-voyager-2027")
cells("sources", **src("ev-kestrel-2027", KESTREL, "2026-12-01", "2027 guide lists one lounge day pass a year for this card."))
cells("card_benefits", id="kestrel.lounge-day-pass", card=KESTREL, benefit="benefit.orbit-summit.lounge-day-pass", applicability="confirmed",
      summary="2027 guide confirms one lounge day pass a year on this card.", evidence="ev-kestrel-2027")
sh("tables", "plan", "--author", "junior maintainer", "--date", "2026-12-01")
sh("tables", "import", "--author", "junior maintainer", "--date", "2026-12-01")
sh("lint")
sh("tables", "import", "--author", "junior maintainer", "--date", "2026-12-01")
print("\n(The new rows are candidates: they establish nothing until a reviewer promotes them and classes their restrictions, OP-14.)")

print("\n=== 2. A mistake: trying to flip applicability in place is refused, and nothing changes")
cells("card_benefits", "voyager.phone-protection", applicability="excluded")
sh("tables", "import", "--author", "junior maintainer", "--date", "2026-12-01", expect=2)
sh("tables", "export")

print("\n=== 3. Retire a benefit, keeping its history")
cells("sources", **src("ev-voyager-notice", VOYAGER, "2026-12-15", "Notice: primary rental car cover is discontinued after December 14, 2026."))
cells("card_benefits", "voyager.primary-rental-cover", _action="retire", ended_on="2026-12-14", evidence="ev-syn-voyager-guide;ev-voyager-notice")
sh("tables", "import", "--author", "junior maintainer", "--date", "2026-12-15")
sh("lint")
sh("cards", "--profile", "synthetic-alex", "--as-of", "2026-12-15")
print("\n--- and the day before it ended is still answered as it was:")
sh("cards", "--profile", "synthetic-alex", "--as-of", "2026-12-14")
sh("cards", "--profile", "synthetic-blake", "--as-of", "2026-12-15")
sh("audit", "--last", "5")
with open(os.path.join(work, "tables", "card_benefits.csv"), encoding="utf-8", newline="") as f:
    print("\ncard_benefits.csv after the task (id, applicability, state, valid_to):")
    for r in csv.DictReader(f):
        print("  %-34s %-10s %-10s %s" % (r["id"], r["applicability"], r["=state"], r["valid_to"]))
print("\nprevious values kept for: " + ", ".join(sorted(os.listdir(os.path.join(work, "data/audit/previous")))[-4:]))
print("\nDEMO COMPLETE (work copy: %s)" % work)
