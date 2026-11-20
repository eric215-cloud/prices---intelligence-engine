"""Build the synthetic recurring-credit fixture on top of the synthetic card fixture, through the normal pipeline.

    python3 fixtures/synthetic_credits.py <empty-or-new-directory>

Everything here is invented: card, credits, amounts, people, dates and sources. Nothing describes a real
product or a real person. The committed copy in fixtures/synthetic-credits/ is the output of this script;
a test checks they stay identical.

Published side (all on the invented Northwind Voyager card; authored through the CSV tables, then promoted):

    A  travel credit          300 USD each card-anniversary year. The card fixture had it as prose only ("200 ...");
                              here the row is corrected and given structured terms, with a new source.
    B  curated hotel credit   500 USD each calendar year; at most 250 per booking; minimum stay 2 nights; no rollover
    C  dining credit          150 USD each calendar half (January-June, July-December), separately; no rollover
    D  ride credit            10 USD each calendar month; no rollover; the offer ends 2027-09-30
       traveler fee credit    120 USD once every 4 years, counted from the last use
       streaming credit       20 USD each calendar quarter; unused rolls over, up to 20
    G  lifestyle credit       200 USD each calendar year     } the cardholder elects ONE of these two
       wellness credit        25 USD each calendar month     } (election group voyager.annual-perk)

People (each holds their own Voyager account):

    synthetic-alex   account opened 2025-03-15. Elected the lifestyle credit. Records on file for the hotel credit 2027
                     (250 used, 180 more unconfirmed), the dining credit 2027-H1 (used up), and the traveler fee credit
                     (used 2025-09-10).
    synthetic-erin   account opened 2024-11-02 (a different anniversary). No election recorded. A record for the travel
                     credit's anniversary year that began 2026-11-02 (120 used).
    synthetic-finn   holds the card; the opening date is NOT recorded. Elected the wellness credit. Nothing else on file.
    synthetic-blake  holds a different card with no credit terms. Unaffected.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import synthetic_cards                       # noqa: E402
from prices import changes, tables           # noqa: E402
from prices.store import Store, dumps        # noqa: E402
from prices.elections import terms_digest     # noqa: E402
from condition_classes import invented                  # noqa: E402

CARD, ACCOUNT = "card.northwind-voyager", "h-card-northwind-voyager"
AUTHOR, REVIEWER, DATE = "fixture author (synthetic)", "Synthetic Reviewer", "2026-11-15"
OWNERS = {"synthetic-alex": "Alex (synthetic)", "synthetic-erin": "Erin (synthetic)", "synthetic-finn": "Finn (synthetic)"}
SOURCE = "ev-syn-voyager-credit-terms"
APPROVED = "2027-06-22"                  # Step 04B: the synthetic reviewer approves the election terms
GROUP = "voyager.annual-perk"

# id suffix, name, summary, restrictions, valid_to, credit cells
CREDITS = [
    ("curated-hotel-credit", "Northwind Voyager curated hotel credit (synthetic)",
     "Up to 500 in statement credits each calendar year on prepaid stays of two nights or more at curated hotels, at most 250 per booking.",
     "Prepaid bookings through the (invented) Northwind travel desk only", "",
     dict(amount="500", unit="USD", cycle="calendar_year", max_per_transaction="250", min_stay_nights="2", rollover="none")),
    ("dining-credit", "Northwind Voyager dining credit (synthetic)",
     "Up to 150 in dining statement credits from January to June and up to 150 from July to December.",
     "The two halves are separate; an unused amount does not carry over", "",
     dict(amount="150", unit="USD", cycle="calendar_half", rollover="none")),
    ("ride-credit", "Northwind Voyager ride credit (synthetic)",
     "10 in ride credit each calendar month through September 30, 2027.", "Unused monthly credit expires at the end of the month", "2027-09-30",
     dict(amount="10", unit="USD", cycle="calendar_month", rollover="none")),
    ("traveler-fee-credit", "Northwind Voyager trusted-traveler fee credit (synthetic)",
     "One statement credit of up to 120 every four years for a trusted-traveler application fee.",
     "The four years run from the date the credit was last applied", "",
     dict(amount="120", unit="USD", cycle="multi_year", years="4", anchor="last_use")),
    ("streaming-credit", "Northwind Voyager streaming credit (synthetic)",
     "20 in streaming credit each calendar quarter; an unused amount carries into the next quarter, up to 20.", "", "",
     dict(amount="20", unit="USD", cycle="calendar_quarter", rollover="allowed", rollover_max="20")),
    ("lifestyle-credit", "Northwind Voyager lifestyle credit (synthetic)",
     "200 lifestyle credit each calendar year, for cardholders who chose the lifestyle option.",
     "Cardholders choose either the lifestyle credit or the wellness credit, not both", "",
     dict(amount="200", unit="USD", cycle="calendar_year")),
    ("wellness-credit", "Northwind Voyager wellness credit (synthetic)",
     "25 wellness credit each calendar month, for cardholders who chose the wellness option.",
     "Cardholders choose either the lifestyle credit or the wellness credit, not both", "",
     dict(amount="25", unit="USD", cycle="calendar_month", rollover="none")),
]


def edit_table(root, table, add=(), change=None):
    """Append rows to a table, and/or change cells of existing rows ({row id: {column: value}}), as a person would in a spreadsheet."""
    path = os.path.join(root, "tables", table + ".csv")
    with open(path, encoding="utf-8", newline="") as f:
        data = list(csv.reader(f))
    cols = tables.COLUMNS[table]
    for row in data[1:]:
        for col, value in (change or {}).get(row[0], {}).items():
            row[cols.index(col)] = value
    data += [[r.get(c, "") for c in cols] for r in add]
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(data)


class Builder:
    def __init__(self, root):
        self.root, self.n = root, 0

    def apply(self, date, op, person=None, confirm=True, **kw):
        self.n += 1
        cs = dict({"id": "cs-%s-credit-%02d-%s" % (date.replace("-", ""), self.n, op.replace("_", "-")), "op": op,
                   "author": AUTHOR, "date": date, "reason": "Synthetic recurring-credit fixture"}, **kw)
        if person:
            cs["profile"] = person
            if confirm:
                cs["attestation"] = {"by": OWNERS[person], "on": date, "statement": "Invented statement for the fixture."}
        out = changes.apply(self.root, cs)
        if not out["ok"]:
            raise SystemExit("fixture build failed at %s: %s" % (cs["id"], out["errors"]))

    def period(self, date, person, eid, rule, cycle, start, end, amount, **extra):
        self.apply(date, "record_entitlement", person, data={"entitlement": dict(
            {"id": eid, "rule": rule, "account": ACCOUNT, "cycle": cycle, "state": "confirmed", "effective_from": start, "expires_on": end,
             "allowance": {"amount": amount, "unit": "USD"}}, **extra)})

    def use(self, date, person, eid, uid, amount, used_on, confirm=True, **extra):
        self.apply(date, "record_usage", person, confirm=confirm, target=eid, data={"usage": dict(
            {"id": uid, "amount": amount, "used_on": used_on, "state": "confirmed" if confirm else "unconfirmed"}, **extra)})


def build(dst):
    synthetic_cards.build(dst)
    # ---- published side, authored in the tables in one sitting, as a maintainer would (OP-10, OP-13)
    edit_table(dst, "sources", add=[{
        "id": SOURCE, "url": "https://example.invalid/northwind/voyager-credit-terms", "title": "Northwind Voyager statement credit terms",
        "publisher": "Northwind Bank (synthetic)", "source_type": "synthetic", "retrieved_on": DATE, "applies_to": CARD,
        "summary": "The card's own credit terms: 300 travel credit per cardmember year, resetting on the account anniversary; curated hotel "
                   "credit 500 per calendar year, 250 per booking, two-night minimum; dining credit 150 per half year; ride credit 10 per "
                   "month through September 30, 2027; trusted-traveler fee credit 120 every four years from the last use; streaming credit "
                   "20 per quarter with carry-over up to 20; and a choice between a 200 yearly lifestyle credit and a 25 monthly wellness credit.",
        "notes": "Invented for testing."}])
    edit_table(dst, "benefits", add=[{"id": "benefit.voyager." + s, "name": name} for s, name, *_rest in CREDITS])
    edit_table(dst, "card_benefits",
               add=[{"id": "voyager." + s, "card": CARD, "benefit": "benefit.voyager." + s, "applicability": "confirmed", "summary": summary,
                     "restrictions": restr, "valid_to": valid_to, "evidence": SOURCE} for s, _n, summary, restr, valid_to, _c in CREDITS],
               change={"voyager.travel-credit": {"summary": "300 annual travel credit per cardmember year.", "_action": "correct",
                                                 "evidence": "ev-syn-voyager-guide;" + SOURCE}})     # a corrected wording, declared as one
    edit_table(dst, "credits",
               add=[dict(c, id="voyager." + s) for s, _n, _s, _r, _v, c in CREDITS] +
                   [dict(id="voyager.travel-credit", amount="300", unit="USD", cycle="anniversary_year", _evidence=SOURCE)])
    out = tables.import_tables(dst, "tables", AUTHOR, DATE)
    if not out["ok"]:
        raise SystemExit("fixture build failed at tables import: %s" % out["errors"])
    b = Builder(dst)
    review = {"by": REVIEWER, "on": DATE, "statement": "Synthetic review: the cited synthetic source supports the row and its credit terms."}
    for s, *_rest in CREDITS:
        b.apply(DATE, "promote_candidate", target="c-voyager." + s, attestation=review,
                data={"review_by": "2027-11-15", "conditions": invented(Store.load(b.root).candidates["c-voyager." + s])})
    # ---- the two credits a cardholder chooses between (ENG-02 election options)
    for s in ("lifestyle-credit", "wellness-credit"):
        b.apply(DATE, "add_entity", data={"entity": {
            "id": "election.voyager." + s, "kind": "election", "name": "Northwind Voyager annual perk choice: %s (synthetic)" % s.replace("-", " "),
            "election": {"group": GROUP, "card": CARD, "governs": ["voyager." + s],
                         "source_note": "Invented: cardholders choose either the lifestyle credit or the wellness credit."}}})
    # ---- people
    b.apply(DATE, "set_holding", "synthetic-alex", data={"holding": {
        "id": ACCOUNT, "entity": CARD, "state": "confirmed", "valid_from": "2026-01-01", "opened_on": "2025-03-15"}})
    for person, held in (("synthetic-erin", {"valid_from": "2024-11-02", "opened_on": "2024-11-02"}), ("synthetic-finn", {"valid_from": "2026-05-01"})):
        path = os.path.join(dst, "profiles", person, "profile.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(dumps({"id": person, "label": "SYNTHETIC person for the recurring-credit fixture - not a real person",
                           "synthetic": True, "owner": OWNERS[person]}))
        b.apply(DATE, "set_holding", person, data={"holding": dict({"id": ACCOUNT, "entity": CARD, "state": "confirmed"}, **held)})
    b.apply(DATE, "set_holding", "synthetic-alex", data={"holding": {
        "id": "el-annual-perk", "entity": "election.voyager.lifestyle-credit", "state": "confirmed", "valid_from": "2026-01-01"}})
    b.apply(DATE, "set_holding", "synthetic-finn", data={"holding": {
        "id": "el-annual-perk", "entity": "election.voyager.wellness-credit", "state": "confirmed", "valid_from": "2026-05-01"}})
    # ---- what the owners' accounts show (period records and uses; the same operations as earned benefits)
    b.period(DATE, "synthetic-alex", "e-traveler-fee-2025", "voyager.traveler-fee-credit", "2025", "2025-09-10", "2029-09-09", 120,
             basis="Statement credit for the application fee, September 2025")
    b.use(DATE, "synthetic-alex", "e-traveler-fee-2025", "u-2025-09-10", 120, "2025-09-10", basis="Application fee")
    b.period("2026-12-16", "synthetic-erin", "e-travel-2026", "voyager.travel-credit", "2026", "2026-11-02", "2027-11-01", 300,
             basis="Credit tracker on the account page")
    b.use("2026-12-16", "synthetic-erin", "e-travel-2026", "u-2026-12-15", 120, "2026-12-15", basis="Rail tickets")
    b.period("2027-02-11", "synthetic-alex", "e-hotel-2027", "voyager.curated-hotel-credit", "2027", "2027-01-01", "2027-12-31", 500,
             basis="Credit tracker on the account page")
    b.use("2027-02-11", "synthetic-alex", "e-hotel-2027", "u-2027-02-10", 250, "2027-02-10", basis="Two nights, first booking")
    b.period("2027-03-06", "synthetic-alex", "e-dining-2027-h1", "voyager.dining-credit", "2027-H1", "2027-01-01", "2027-06-30", 150,
             basis="Credit tracker on the account page")
    b.use("2027-03-06", "synthetic-alex", "e-dining-2027-h1", "u-2027-03-05", 150, "2027-03-05", basis="Dinner")
    b.use("2027-06-21", "synthetic-alex", "e-hotel-2027", "u-2027-06-20", 180, "2027-06-20", confirm=False,
          basis="Entered by a maintainer from an email; not yet confirmed by the owner")
    # Step 04B (A8): election terms establish nothing until a reviewer other than their author approves them, as read.
    # Applied last so that every earlier changeset keeps the id it had before Step 04B
    for s in ("lifestyle-credit", "wellness-credit"):
        b.apply(APPROVED, "approve_election", target="election.voyager." + s, author=REVIEWER,
                attestation={"by": REVIEWER, "on": APPROVED, "statement": "Synthetic review: the election terms match the cited synthetic source."},
                data={"terms": terms_digest(Store.load(b.root).entities["election.voyager." + s])})
    tables.export(dst)
    return dst


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print("built synthetic recurring-credit fixture at %s" % build(sys.argv[1]))
