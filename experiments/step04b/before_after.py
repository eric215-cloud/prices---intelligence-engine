"""Step 04B before/after: the same invented Bilt cardholders on the baseline (88d1cdf) and on this branch.

    git worktree add /tmp/base88 88d1cdf1ab944ca028c97574f2b8902ce6b0392b
    python3 experiments/step04b/before_after.py /tmp/base88 .

Each checkout runs in its own subprocess, on a scratch copy of its own live store with the five governed candidates
promoted there. On the branch the six definitions are approved in the scratch copy too (column "branch"), and also
left unapproved (column "branch, unapproved"), so the A8 gate and the other repairs can be seen separately.
Every cardholder and date is invented. Nothing is written to either checkout.
"""
import json
import os
import subprocess
import sys

CASES = [
    # (finding, label, holdings, day)
    ("A1", "opened 2026-03-10 only, nothing else recorded", "window", "2027-05-11"),
    ("A1", "same, a year later", "window", "2028-01-01"),
    ("A1", "Legacy left 2027-09-05, no issuer anniversary: the $600", "exit-no-anniversary", "2028-06-01"),
    ("A1", "same with the issuer's anniversary (control)", "exit", "2028-06-01"),
    ("A2", "Legacy Election, no Flexible Bilt Cash record", "legacy-only", "2027-05-01"),
    ("A2", "Legacy Election while Housing-only was active", "tiered-then-legacy", "2027-05-01"),
    ("A2", "Legacy Election with Flexible Bilt Cash shown (control)", "legacy", "2027-05-01"),
    ("A3", "switch requested 06-10, effective 06-15 (cycle day 15): day 06-12", "a3-request", "2026-06-12"),
    ("A3", "same: day 06-15", "a3-request", "2026-06-15"),
    ("A3", "request day typed as the start (cycle day 15)", "a3-request-as-start", "2026-06-12"),
    ("A3", "exit recorded effective on its request day", "a3-exit-on-request-day", "2027-08-25"),
    ("ok-None", "Legacy Election with no start date", "undated", "2027-07-01"),
]

E = "election.bilt-palladium."
FLEX = {"id": "f1", "entity": E + "housing-flex-bilt-cash", "state": "confirmed", "valid_from": "2026-05-05"}


def acct(shown="2027-04-05", **extra):
    h = {"id": "h-card", "entity": "card.bilt-palladium", "state": "confirmed", "valid_from": "2026-03-10", "opened_on": "2026-03-10"}
    if shown:
        h["anniversary_on"] = shown
    h.update(extra)
    return h


def el(hid, opt, start=None, end=None, **extra):
    h = {"id": hid, "entity": E + opt, "state": "ended" if end else "confirmed"}
    if start:
        h["valid_from"] = start
    if end:
        h["valid_to"] = end
    h.update(extra)
    return h


PEOPLE = {
    "window": [acct(None)],
    "exit-no-anniversary": [acct(None), FLEX, el("e1", "legacy-election", "2026-11-20", "2027-09-04"), el("e2", "refreshed-arrangement", "2027-09-05")],
    "exit": [acct(), FLEX, el("e1", "legacy-election", "2026-11-20", "2027-09-04"), el("e2", "refreshed-arrangement", "2027-09-05")],
    "legacy-only": [acct(), el("e1", "legacy-election", "2026-11-20")],
    "tiered-then-legacy": [acct(), el("t1", "housing-tiered-points", "2026-03-10"), el("e1", "legacy-election", "2026-11-20")],
    "legacy": [acct(), FLEX, el("e1", "legacy-election", "2026-11-20")],
    "a3-request": [acct(billing_cycle_day=15), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-14"),
                   el("f1", "housing-flex-bilt-cash", "2026-06-15", requested_on="2026-06-10")],
    "a3-request-as-start": [acct(billing_cycle_day=15), el("t1", "housing-tiered-points", "2026-03-10", "2026-06-09"),
                            el("f1", "housing-flex-bilt-cash", "2026-06-10", requested_on="2026-06-10")],
    "a3-exit-on-request-day": [acct(billing_cycle_day=15), el("f1", "housing-flex-bilt-cash", "2026-05-15"),
                               el("e1", "legacy-election", "2026-11-20", "2027-08-19", exit_requested_on="2027-08-20"),
                               el("r1", "refreshed-arrangement", "2027-08-20")],
    "undated": [acct(), FLEX, el("e1", "legacy-election", confirmed_on="2027-06-01")],
}

CHILD = r'''
import json, os, shutil, sys, tempfile
root, approve, payload = sys.argv[1], sys.argv[2] == "1", json.loads(sys.stdin.read())
sys.path[:0] = [root, os.path.join(root, "fixtures")]
from condition_classes import scratch_real
from prices import changes
from prices.engine import evaluate
from prices.store import Store
FIVE = ("housing-tiered-points", "housing-flex-bilt-cash-legacy", "annual-bilt-cash-200-legacy", "hotel-credit-400-semiannual-legacy",
        "annual-bilt-cash-600-post2027")
tmp = tempfile.mkdtemp()
for sub in ("data", "profiles", "tables"):
    shutil.copytree(os.path.join(root, sub), os.path.join(tmp, sub))
rv = Store.load(tmp).vocab["promotion_reviewers"][0]
out = changes.apply_many(tmp, [{"id": "cs-20261115-ba-%d" % i, "op": "promote_candidate", "target": "c-cb.bilt-palladium." + k, "author": "ba",
      "date": "2026-11-15", "reason": "scratch", "attestation": {"by": rv, "on": "2026-11-15", "statement": "scratch"},
      "data": {"review_by": "2027-12-15", "conditions": scratch_real(Store.load(tmp).candidates["c-cb.bilt-palladium." + k], governed=True)}}
     for i, k in enumerate(FIVE)])
assert out["ok"], out["errors"]
if approve:
    from prices.elections import terms_digest
    s = Store.load(tmp)
    out = changes.apply_many(tmp, [{"id": "cs-20261120-ba-ap-%d" % i, "op": "approve_election", "target": o, "author": "ba reviewer",
          "date": "2026-11-20", "reason": "scratch", "data": {"terms": terms_digest(s.entities[o])},
          "attestation": {"by": "Bradley", "on": "2026-11-20", "statement": "scratch copy only: not a review"}}
         for i, o in enumerate(sorted(e for e in s.entities if e.startswith("election.bilt-palladium.")))])
    assert out["ok"], out["errors"]
for name, hs in payload["people"].items():
    d = os.path.join(tmp, "profiles", "syn-" + name, "holdings")
    os.makedirs(d)
    json.dump({"id": "syn-" + name, "label": "invented", "synthetic": True, "owner": "Invented " + name},
              open(os.path.join(tmp, "profiles", "syn-" + name, "profile.json"), "w"))
    for h in hs:
        h = dict(h, confirmed_by="Invented " + name)
        h.setdefault("confirmed_on", "2026-11-15")
        json.dump(h, open(os.path.join(d, h["id"] + ".json"), "w"))
s = Store.load(tmp)
res = {}
for _f, _l, who, day in payload["cases"]:
    r = evaluate(s, "syn-" + who, day)
    st = "".join({"ESTABLISHED": "E", "NOT_AVAILABLE": "-", "UNRESOLVED": "U"}.get(r.have("benefit.bilt-palladium." + k), "?") for k in FIVE)
    codes = sorted({f["code"] for f in r.flags if f["code"].startswith(("ELECTION", "ANNIVERSARY", "CONFLICT"))})
    res["%s@%s" % (who, day)] = [st, codes]
shutil.rmtree(tmp)
print(json.dumps(res))
'''


def run(root, approve):
    p = subprocess.run([sys.executable, "-I", "-c", CHILD, os.path.abspath(root), "1" if approve else "0"],
                       input=json.dumps({"people": PEOPLE, "cases": CASES}), capture_output=True, text=True)
    if p.returncode:
        sys.exit(p.stderr)
    return json.loads(p.stdout)


def main(base, branch):
    before, after, raw = run(base, False), run(branch, True), run(branch, False)
    print("Columns: tiered points, Flexible Bilt Cash, $200, $400, $600   (E established, - not available, U unresolved)\n")
    print("| Finding | Case | Day | 88d1cdf | branch | branch, unapproved | branch flags |")
    print("|---|---|---|---|---|---|---|")
    for f, label, who, day in CASES:
        k = "%s@%s" % (who, day)
        print("| %s | %s | %s | `%s` | `%s` | `%s` | %s |" % (f, label, day, before[k][0], after[k][0], raw[k][0], ", ".join(after[k][1]) or "-"))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
