"""Run the real-content experiment of ONE source tree and print what it found, as JSON. Used by before_after.py.

    python3 experiments/safety/scenario.py <tree>

<tree> is a checkout of this project: the current one, or an earlier commit unpacked somewhere. The code, the sheets
and the candidates all come from that tree, and everything happens in that tree's own throwaway copies.
"""
import contextlib
import io
import json
import os
import sys

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
sys.path.insert(0, os.path.join(tree, "experiments", "viability"))
import run                                             # noqa: E402
from lab import Lab, TODAY, load, status_of            # noqa: E402

with contextlib.redirect_stdout(io.StringIO()):
    p0, p1, bad = run.main()
lab = p1["lab"]
silver = lambda day: lab.js("explain", "--profile", "syn-devon", "--as-of", day, "united.silver")["status"]      # noqa: E731
out = {"checks": {c["check"].split(" ")[0]: [c["ok"], c["check"]] for c in run.checks}, "failed": [c["check"] for c in bad],
       "phase0": {k: v for k, v in p0.items() if k in ("established_despite_gate", "refused_unclassified", "promoted_without_conditions")},
       "silver_2027_at_6100_pqp": silver("2027-10-01"), "silver_2026": silver(TODAY)}

# a rule is retired: what happens to the answer for a day on which it was in force?  (TEST EDIT in a fresh copy)
spec = load("batch1.json")
lab2 = Lab()
with contextlib.redirect_stdout(io.StringIO()):
    run.select(lab2, spec)
    lab2.vocab({"spend_categories": spec["spend_categories"]})
    run.amend(lab2, spec, "batch1")
lab2.person("syn-casey", run.CASEY)
lyft = lambda day: lab2.js("earnings", "--profile", "syn-casey", "--as-of", day, "--category", "rideshare-lyft", "--amount", 60)["answers"][0].get("points")   # noqa: E731
rid = "cb.csr.lyft-5x-multiplier"
before = lyft("2026-11-01")
res = lab2.apply("retire_rule", "before-after", "retire", target=rid, data={"ended_on": "2026-11-10"}, evidence=lab2.evidence_of(rid))
out["retirement"] = {"accepted": res["ok"], "errors": res.get("errors", []), "points_2026_11_01_before": before, "points_2026_11_01_after": lyft("2026-11-01"),
                     "points_today_after": lyft(TODAY)}
rep = lab2.js("status", "--profile", "syn-casey", "--as-of", TODAY)
out["welcome_offer_with_this_trees_safeguards"] = status_of(rep, "benefit.csr.public-welcome-offer")
print(json.dumps(out))
