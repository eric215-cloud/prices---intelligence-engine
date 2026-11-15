"""Build the synthetic earned-benefits fixture on top of the synthetic card fixture, through the normal pipeline.

    python3 fixtures/synthetic_earned.py <empty-or-new-directory>

Everything here is invented: card, benefits, people, spending figures, dates and sources. Nothing
describes a real product or a real person. The committed copy in fixtures/synthetic-earned/ is the
output of this script; a test checks they stay identical.

The invented rule: spend 75,000 units on the Northwind Voyager card in one calendar year and four things
are on offer, each with its own terms.

    status    Orbit Concierge status        lasts through the end of February two years later   automatic
    fare      companion fare                lasts through December 31 of the following year     automatic; offer ends with 2026
    award     suite night award             lasts through December 31 of the following year     needs a separate activation step
    credit    milestone travel credit, 300  lasts through December 31 of the following year     automatic; consumable

The invented people (each holds their own Voyager account):

    synthetic-alex    2026: below in June, at/above by October 31, final 91,250. Status, fare and credit confirmed on
                      the account; award activated only in January 2027; credit partly used.
                      2027: a second, independent cycle; reaches the threshold by September 30.
    synthetic-casey   2026: 41,000 in August, final 61,300. Did not qualify. Nothing earned.
    synthetic-devon   2026: says only "I reached it in 2026" (no date), and that the status is on the account
                      (start date not known). Nothing is inferred beyond that.
    synthetic-blake   holds a different card with no earned-benefit rule. Unaffected.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import synthetic_cards                       # noqa: E402
from prices import changes, tables           # noqa: E402
from prices.store import dumps               # noqa: E402

CARD, ACCOUNT, MEASURE = "card.northwind-voyager", "h-card-northwind-voyager", "voyager.qualifying-spend"
AUTHOR, REVIEWER = "fixture author (synthetic)", "Synthetic Reviewer"
OWNERS = {"synthetic-alex": "Alex (synthetic)", "synthetic-casey": "Casey (synthetic)", "synthetic-devon": "Devon (synthetic)"}
SOURCE = {"id": "ev-syn-voyager-milestones", "url": "https://example.invalid/northwind/voyager-milestone-terms",
          "title": "Northwind Voyager milestone benefit terms", "publisher": "Northwind Bank (synthetic)", "source_type": "synthetic",
          "retrieved_on": "2026-11-14", "applies_to": [CARD],
          "summary": "The card's own milestone terms. 75,000 in qualifying purchases on this card account in a calendar year earns: "
                     "Orbit Concierge status through the end of February two years later; a companion fare and a suite night award, "
                     "each through December 31 of the following year; and a 300 travel credit through December 31 of the following "
                     "year. The suite night award must be activated in the rewards portal. The companion fare is offered for "
                     "qualifying years up to and including 2026.",
          "notes": "Invented for testing."}
ENTITIES = [
    {"id": "status.orbit-concierge", "kind": "status", "name": "Orbit Concierge status (synthetic)"},
    {"id": "benefit.voyager.companion-fare", "kind": "benefit", "name": "Northwind Voyager companion fare (synthetic)"},
    {"id": "benefit.voyager.suite-award", "kind": "benefit", "name": "Northwind Voyager suite night award (synthetic)"},
    {"id": "benefit.voyager.milestone-credit", "kind": "benefit", "name": "Northwind Voyager milestone travel credit (synthetic)"},
    {"id": "benefit.orbit-concierge.priority-line", "kind": "benefit", "name": "Orbit Concierge priority phone line (synthetic)"},
    {"id": "action.voyager.activate-suite-award", "kind": "action", "name": "Activate the suite night award in the Northwind rewards portal",
     "how": "Sign in to the (invented) Northwind rewards portal, choose the suite night award and link the hotel account. "
            "Reaching the spending threshold does not do this for you."},
]


def _earn(term, activation="automatic", **extra):
    return dict({"measure": MEASURE, "period": "calendar_year", "threshold": 75000, "unit": "units", "activation": activation, "term": term}, **extra)


DEC_NEXT = {"ends": "fixed", "year_offset": 1, "month": 12, "day": 31}
RULES = [
    {"id": "voyager.earn-concierge-status", "kind": "earns", "output": "status.orbit-concierge", "when": {"holds": CARD},
     "summary": "75,000 in qualifying purchases in a calendar year earns Orbit Concierge status through the end of February two years later.",
     "earn": _earn({"ends": "fixed", "year_offset": 2, "month": 2, "month_end": True})},
    {"id": "voyager.earn-companion-fare", "kind": "earns", "output": "benefit.voyager.companion-fare", "when": {"holds": CARD},
     "summary": "75,000 in qualifying purchases in a calendar year earns one companion fare, usable through December 31 of the following year.",
     "valid_to": "2026-12-31", "restrictions": ["Offered for qualifying years up to and including 2026"],
     "earn": _earn(DEC_NEXT)},
    {"id": "voyager.earn-suite-award", "kind": "earns", "output": "benefit.voyager.suite-award", "when": {"holds": CARD},
     "summary": "75,000 in qualifying purchases in a calendar year makes one suite night award available; it must be activated in the rewards portal.",
     "earn": _earn(DEC_NEXT, "required", activation_action="action.voyager.activate-suite-award")},
    {"id": "voyager.earn-milestone-credit", "kind": "earns", "output": "benefit.voyager.milestone-credit", "when": {"holds": CARD},
     "summary": "75,000 in qualifying purchases in a calendar year earns a 300 travel credit, usable through December 31 of the following year.",
     "earn": _earn(DEC_NEXT, allowance={"amount": 300, "unit": "units"})},
    {"id": "concierge.priority-line", "kind": "grants", "output": "benefit.orbit-concierge.priority-line", "when": {"holds": "status.orbit-concierge"},
     "summary": "Orbit Concierge members may use the priority phone line."},
]


class Builder:
    def __init__(self, root):
        self.root, self.n = root, 0

    def apply(self, date, op, person=None, confirm=True, **kw):
        self.n += 1
        cs = dict({"id": "cs-%s-earn-%02d-%s" % (date.replace("-", ""), self.n, op.replace("_", "-")), "op": op,
                   "author": AUTHOR, "date": date, "reason": "Synthetic earned-benefit fixture"}, **kw)
        if person:
            cs["profile"] = person
            if confirm:
                cs["attestation"] = {"by": OWNERS[person], "on": date, "statement": "Invented statement for the fixture."}
        out = changes.apply(self.root, cs)
        if not out["ok"]:
            raise SystemExit("fixture build failed at %s: %s" % (cs["id"], out["errors"]))

    def reading(self, date, person, cycle, rid, value, observed_on, **extra):
        self.apply(date, "record_progress", person, data={"account": ACCOUNT, "measure": MEASURE, "cycle": cycle,
                   "reading": dict({"id": rid, "value": value, "observed_on": observed_on, "state": "confirmed"}, **extra)})

    def instance(self, date, person, cycle, eid, rule, start, end, **extra):
        self.apply(date, "record_entitlement", person, data={"entitlement": dict(
            {"id": eid, "rule": rule, "account": ACCOUNT, "cycle": cycle, "state": "confirmed", "effective_from": start, "expires_on": end}, **extra)})


def build(dst):
    synthetic_cards.build(dst)
    b = Builder(dst)
    # ---- public side: entities, then the earn rules as candidates, promoted by the (synthetic) reviewer
    for e in ENTITIES:
        b.apply("2026-11-14", "add_entity", data={"entity": e})
    review = {"by": REVIEWER, "on": "2026-11-14", "statement": "Synthetic review: the cited synthetic source supports the rule."}
    for r in RULES:
        cand = {"id": "c-" + r["id"], "status": "proposed", "created_on": "2026-11-14", "proposed_rule": r, "evidence": [SOURCE],
                "search_path": ["fixture"], "open_questions": []}
        b.apply("2026-11-14", "add_candidate", data={"candidate": cand})
        b.apply("2026-11-14", "promote_candidate", target=cand["id"], data={"review_by": "2027-11-14"}, attestation=review)
    # ---- two more invented people, each with their own Voyager account
    for person in ("synthetic-casey", "synthetic-devon"):
        path = os.path.join(dst, "profiles", person, "profile.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(dumps({"id": person, "label": "SYNTHETIC person for the earned-benefit fixture - not a real person",
                           "synthetic": True, "owner": OWNERS[person]}))
        b.apply("2026-11-14", "set_holding", person, data={"holding": {"id": ACCOUNT, "entity": CARD, "state": "confirmed", "valid_from": "2026-01-01"}})

    # ---- Alex, qualifying year 2026
    b.reading("2026-11-14", "synthetic-alex", "2026", "r-2026-06", 38400, "2026-06-30", basis="June statement")
    b.reading("2026-11-14", "synthetic-alex", "2026", "r-2026-10", 76900, "2026-10-31", basis="October statement")
    b.instance("2026-11-14", "synthetic-alex", "2026", "e-2026-concierge-status", "voyager.earn-concierge-status", "2026-11-08", "2028-02-29",
               basis="Status shown on the account page")
    b.instance("2026-11-14", "synthetic-alex", "2026", "e-2026-companion-fare", "voyager.earn-companion-fare", "2026-11-08", "2027-12-31",
               basis="Certificate shown on the account page")
    b.instance("2026-11-14", "synthetic-alex", "2026", "e-2026-milestone-credit", "voyager.earn-milestone-credit", "2026-11-08", "2027-12-31",
               allowance={"amount": 300, "unit": "units"}, basis="Credit shown on the account page")
    b.reading("2026-11-14", "synthetic-casey", "2026", "r-2026-08", 41000, "2026-08-31", basis="August statement")
    b.apply("2026-12-05", "record_usage", "synthetic-alex", target="e-2026-milestone-credit",
            data={"usage": {"id": "u-2026-12-03", "amount": 120, "used_on": "2026-12-03", "state": "confirmed", "basis": "Airfare"}})
    # ---- year end
    b.reading("2027-01-04", "synthetic-alex", "2026", "r-2026-final", 91250, "2026-12-31", final=True, basis="Year-end summary")
    b.reading("2027-01-04", "synthetic-casey", "2026", "r-2026-final", 61300, "2026-12-31", final=True, basis="Year-end summary")
    # ---- the award is activated only now; reaching the threshold in October did not do it
    b.instance("2027-01-16", "synthetic-alex", "2026", "e-2026-suite-award", "voyager.earn-suite-award", "2027-01-15", "2027-12-31",
               basis="Activated in the portal on January 15")
    # ---- Devon: a year-only statement and a status whose start date is not known
    b.reading("2027-01-20", "synthetic-devon", "2026", "r-2026-year-only", 75000, "unknown", value_kind="at_least",
              basis="Owner says the threshold was reached during 2026; no statement to hand")
    b.instance("2027-01-20", "synthetic-devon", "2026", "e-2026-concierge-status", "voyager.earn-concierge-status", "unknown", "2028-02-29",
               basis="Status shown on the account page today; start date not shown")
    b.apply("2027-02-11", "record_usage", "synthetic-alex", target="e-2026-milestone-credit",
            data={"usage": {"id": "u-2027-02-10", "amount": 80, "used_on": "2027-02-10", "state": "confirmed", "basis": "Hotel"}})
    b.apply("2027-03-03", "record_usage", "synthetic-alex", confirm=False, target="e-2026-milestone-credit",
            data={"usage": {"id": "u-2027-03-02", "amount": 60, "used_on": "2027-03-02", "state": "unconfirmed",
                            "basis": "Entered by a maintainer from an email; not yet confirmed by the owner"}})
    # ---- Alex, qualifying year 2027: separate progress, separate achievement, separate instances
    b.reading("2027-05-02", "synthetic-alex", "2027", "r-2027-04", 29000, "2027-04-30", basis="April statement")
    b.reading("2027-10-02", "synthetic-alex", "2027", "r-2027-09", 78300, "2027-09-30", basis="September statement")
    b.instance("2027-10-08", "synthetic-alex", "2027", "e-2027-concierge-status", "voyager.earn-concierge-status", "2027-10-06", "2029-02-28",
               basis="Status renewal shown on the account page")
    b.instance("2027-10-08", "synthetic-alex", "2027", "e-2027-milestone-credit", "voyager.earn-milestone-credit", "2027-10-06", "2028-12-31",
               allowance={"amount": 300, "unit": "units"}, basis="Second credit shown on the account page")
    tables.export(dst)
    return dst


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print("built synthetic earned-benefit fixture at %s" % build(sys.argv[1]))
