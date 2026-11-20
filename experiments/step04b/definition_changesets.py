"""Step 04B: the changesets that revised the six Bilt Palladium election definitions (applied once, 2026-11-20).

    python3 experiments/step04b/definition_changesets.py --print     # show them
    python3 experiments/step04b/definition_changesets.py --apply     # apply to the project (already done; refused twice by id)

A1: anniversary_cycle_days 62 (an unpublished bound) is replaced by anniversary_from: first_billing_cycle_after_opening.
A2: the Legacy Election requires Flexible Bilt Cash to be the active Rewards Option (requires_active).
A3: Rewards Option changes, and leaving the Legacy Election, take effect on the first day of the next billing cycle.
The terms are recorded by engineering and attested by the builder identity ("Commissioning build"): they are NOT
independently approved, so the engine establishes nothing in these groups until a reviewer approves them (A8, OP-12).
"""
import copy
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from prices.store import Store            # noqa: E402

E = "election.bilt-palladium."
OLD = ("anniversary_cycle_days 62 is an engineering allowance for where that day can fall, NOT a published figure; "
       "anniversary_on on the holding replaces it.")
NEW = ("No published figure says how long after opening that billing cycle begins, so opened_on alone does not place the "
       "anniversary: record anniversary_on (as the Bilt app shows it) or first_billing_cycle_on on the card holding "
       "(Step 04B removed the former 62-day engineering allowance).")
EXTRA = {
    "legacy-election": {"requires_active": E + "housing-flex-bilt-cash", "exit_takes_effect": "next_billing_cycle"},
    "housing-flex-bilt-cash": {"takes_effect": "next_billing_cycle"},
    "housing-tiered-points": {"takes_effect": "next_billing_cycle"},
}
WHY = {
    "legacy-election": "A1 remove the unpublished 62-day bound; A2 the Legacy Election is open only to a cardholder whose active "
                       "Rewards Option is Flexible Bilt Cash; A3 leaving it takes effect on the first day of the next Billing Cycle.",
    "housing-flex-bilt-cash": "A1 remove the unpublished 62-day bound; A3 a Rewards Option change takes effect on the first day of "
                              "the next Billing Cycle.",
    "housing-tiered-points": "A1 remove the unpublished 62-day bound; A3 a Rewards Option change takes effect on the first day of "
                             "the next Billing Cycle.",
}


def changesets(store, day="2026-11-20"):
    out = []
    for n, key in enumerate(("legacy-election", "refreshed-arrangement", "housing-flex-bilt-cash", "housing-tiered-points",
                             "annual-credits-legacy", "annual-credits-600"), 1):
        e = store.entities[E + key]
        t = copy.deepcopy(e["election"])
        for k in ("anniversary_cycle_days", "terms_by", "approval"):
            t.pop(k, None)
        t["anniversary_from"] = "first_billing_cycle_after_opening"
        t.update(EXTRA.get(key, {}))
        if OLD in t.get("source_note", ""):
            t["source_note"] = t["source_note"].replace(OLD, NEW)
        out.append({"id": "cs-20261120-step04b-%02d-revise-entity-%s" % (n, key), "op": "revise_entity", "target": E + key,
                    "author": "Claude (engineering, Step 04B)", "date": day,
                    "reason": "Step 04B: " + WHY.get(key, "A1 remove the unpublished 62-day bound (anniversary_from replaces "
                                                          "anniversary_cycle_days)."),
                    "data": {"set": {"election": t}},
                    "attestation": {"by": "Commissioning build", "on": day,
                                    "statement": "Builder attestation only. These terms are NOT independently reviewed: the engine "
                                                 "establishes nothing in these groups until a reviewer approves them (approve_election)."}})
    return out


if __name__ == "__main__":
    s = Store.load(ROOT)
    css = changesets(s)
    if "--apply" in sys.argv:
        from prices import changes
        out = changes.apply_many(ROOT, css)
        print("APPLIED" if out["ok"] else "REFUSED: %s" % out["errors"])
        sys.exit(0 if out["ok"] else 1)
    print(json.dumps(css, indent=2))
