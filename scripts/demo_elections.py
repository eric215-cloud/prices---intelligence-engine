"""Demonstration of cardholder elections (ENG-02, corrected by ENG-02B and Step 04B) on the real Bilt Palladium content, on a throwaway copy.

    python3 scripts/demo_elections.py

Touches nothing in the project. In a temp copy of the live store it:
  - promotes Argon's five election-governed Bilt candidates (THERE ONLY: the committed store keeps them proposed),
    because the hazard the elections guard against is what happens after promotion;
  - approves the six option definitions as a stand-in reviewer (THERE ONLY: the committed definitions await Eric or Bradley);
  - creates two invented cardholders (every name and date invented):
      "Bilt Holder (synthetic)"      account opened 2026-03-10, card anniversary shown by the issuer as April 5
      "New Bilt Holder (synthetic)"  account opened 2027-02-10
  - records the card, mistakes, a housing choice, a Legacy Election and leaving it, through changeset files and `prices apply`.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "fixtures")]
from condition_classes import scratch_real      # noqa: E402  (engineering's reading of the real restrictions, for scratch copies only)
tmp = tempfile.mkdtemp(prefix="prices-demo-elections-")
work = os.path.join(tmp, "store")
for d in ("data", "profiles", "tables"):
    shutil.copytree(os.path.join(ROOT, d), os.path.join(work, d))
os.mkdir(os.path.join(tmp, "changesets"))
P, OWNER = "synthetic-bilt", "Bilt Holder (synthetic)"
P2, OWNER2 = "synthetic-bilt-new", "New Bilt Holder (synthetic)"
B = "benefit.bilt-palladium."
E = "election.bilt-palladium."
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


def table(day, profile=P, want=None):
    """Print the five benefits for one day. `want`: the five expected statuses (E/U/-); the demo stops if they differ."""
    out = json.loads(sh("--json", "status", "--profile", profile, "--as-of", day, show=False))
    have = {}
    for key in ("derived_entitlements", "conditional", "unresolved"):
        for x in out[key]:
            have[x["entity"]] = {"derived_entitlements": "ESTABLISHED", "conditional": "CONDITIONAL", "unresolved": "UNRESOLVED"}[key]
    print("\n  %s" % day)
    for k in FIVE:
        print("    %-40s %s" % (k, have.get(B + k, "NOT_AVAILABLE")))
    for e in out.get("elections", []):
        print("    election %-33s %s" % (e["group"], ("IN EFFECT " + e["established"]) if e["established"] else "UNRESOLVED (%s)" % e["reason"]))
    got = "".join({"ESTABLISHED": "E", "UNRESOLVED": "U", "CONDITIONAL": "C"}.get(have.get(B + k), "-") for k in FIVE)
    if want is not None and got != want:
        sys.exit("demonstration stopped: on %s expected %s (tiered, flex, $200, $400, $600) but got %s" % (day, want, got))


def person(profile, owner, label):
    os.makedirs(os.path.join(work, "profiles", profile, "holdings"))
    with open(os.path.join(work, "profiles", profile, "profile.json"), "w", encoding="utf-8") as f:
        json.dump({"id": profile, "label": label, "synthetic": True, "owner": owner}, f, indent=2)


print("=== 0. Scratch setup: promote the five governed Bilt candidates (scratch copy only) and create two invented people")
reviewer = json.load(open(os.path.join(work, "data/kb/vocab.json")))["promotion_reviewers"][0]
for k in FIVE:
    change("2026-11-15", "promote_candidate", (reviewer, "Scratch-copy promotion for the election demonstration only."), show_file=False,
           target="c-cb.bilt-palladium." + k,
           data={"review_by": "2027-11-15", "conditions": scratch_real(json.load(open(os.path.join(work, "data/candidates/c-cb.bilt-palladium.%s.json" % k))), governed=True)})
person(P, OWNER, "Invented Bilt Palladium cardholder, account opened before 2027")
person(P2, OWNER2, "Invented Bilt Palladium cardholder, account opened in 2027")

print("\n--- Step 04B: the committed option definitions carry no independent approval, so nothing they decide is established yet.")
print("    In THIS scratch copy only, the first listed reviewer approves the exact terms (a demonstration stand-in, not a review);")
print("    in the project this is OP-12 section 8, done by Eric or Bradley, never by engineering.")
sys.path.insert(0, ROOT)
from prices.elections import terms_digest       # noqa: E402
from prices.store import Store                  # noqa: E402
for k in ("legacy-election", "refreshed-arrangement", "housing-flex-bilt-cash", "housing-tiered-points", "annual-credits-legacy", "annual-credits-600"):
    change("2026-11-15", "approve_election", (reviewer, "Scratch-copy approval for the election demonstration only; not a review."),
           show_file=(k == "legacy-election"), author="demo reviewer", target=E + k,
           data={"terms": terms_digest(Store.load(work).entities[E + k])})

print("\n\n=== 1. What the election definitions prevent")
print("    (without them every one of the five would be ESTABLISHED for any cardholder: both housing options at once, and both")
print("     the legacy benefits and the $600. tests/test_n_elections.py and tests/test_q_bilt_election_correction.py show this.)")

print("\n\n=== 2. Record the card: the opening date, and the card anniversary as the issuer shows it")
change("2026-11-15", "set_holding", (OWNER, "I hold Bilt Palladium; account opened March 10, 2026; the app shows my card anniversary as April 5."),
       profile=P, data={"holding": {"id": "h-bilt-palladium", "entity": "card.bilt-palladium", "state": "confirmed", "valid_from": "2026-03-10",
                                    "opened_on": "2026-03-10", "anniversary_on": "2027-04-05"}})
print("\n--- nothing else recorded. Before this account's transition anniversary (2027-04-05) the $200 Bilt Cash and the $400 hotel")
print("    credit apply automatically; the housing option is the cardholder's choice and is not known. From the anniversary on,")
print("    everything depends on whether a Legacy Election was made, and nothing is assumed either way.")
table("2026-11-15", want="UUEE-")
table("2027-04-04", want="UUEE-")
table("2027-04-05", want="UUUUU")
sh("explain", "--profile", P, "--as-of", "2026-11-15", B + "housing-tiered-points")

print("\n\n=== 3. Mistakes")
print("\n(a) the maintainer, not the owner, confirms a choice: refused")
change("2026-11-16", "set_holding", ("junior maintainer", "I think they chose tiered points."), expect=2, profile=P,
       data={"holding": {"id": "el-housing-1", "entity": E + "housing-tiered-points", "state": "confirmed", "valid_from": "2026-03-10"}})
print("\n(b) a rule that no longer needs the election cannot be slipped in: revising a definition needs a reviewer")
change("2026-11-16", "revise_entity", ("junior maintainer", "Simplify."), expect=2, target=E + "housing-tiered-points",
       data={"set": {"election": {"group": "bilt-palladium.housing-rewards", "card": "card.bilt-palladium", "governs": ["cb.bilt-palladium.base-2x-everyday"]}}})

print("\n\n=== 4. Record the owner's housing option: only that pathway applies, and the legacy benefits are untouched")
change("2026-11-16", "set_holding", (OWNER, "My housing rewards option has been housing-only tiered points since I opened the card."), profile=P,
       data={"holding": {"id": "el-housing-1", "entity": E + "housing-tiered-points", "state": "confirmed", "valid_from": "2026-03-10"}})
table("2026-11-16", want="E-EE-")

print("\n\n=== 5. A contradictory record: accepted with a warning, and NEITHER housing option is applied while it stands")
change("2026-11-20", "set_holding", None, profile=P,
       data={"holding": {"id": "el-housing-2", "entity": E + "housing-flex-bilt-cash", "state": "unconfirmed", "valid_from": "2026-11-01"}})
table("2026-11-20", want="UUEE-")
print("\n--- resolved: the owner says the Flex entry was a mistake. It is withdrawn: kept on file, never in effect on any date")
change("2026-11-21", "end_holding", (OWNER, "I never switched to Flex in November; that entry is wrong."), profile=P, target="el-housing-2",
       data={"withdrawn": True})
table("2026-11-21", want="E-EE-")

print("\n\n=== 6. Before the transition: switch the housing option (next billing cycle), then make the Legacy Election")
change("2026-12-05", "end_holding", (OWNER, "I switched to Flexible Bilt Cash; it took effect with the billing cycle that began December 5."),
       profile=P, target="el-housing-1", data={"ended_on": "2026-12-04"})
change("2026-12-05", "set_holding", (OWNER, "Flexible Bilt Cash from December 5, 2026."), profile=P,
       data={"holding": {"id": "el-housing-3", "entity": E + "housing-flex-bilt-cash", "state": "confirmed", "valid_from": "2026-12-05"}})
table("2026-12-04", want="E-EE-")
table("2026-12-05", want="-EEE-")
print("\n--- the annual benefits cannot be recorded as a choice of their own: the record is reported and not used")
change("2026-12-08", "set_holding", (OWNER, "I want the $600 instead."), profile=P,
       data={"holding": {"id": "el-credits-1", "entity": E + "annual-credits-600", "state": "confirmed", "valid_from": "2026-12-08"}})
table("2026-12-08", want="-EEE-")
change("2026-12-09", "end_holding", (OWNER, "That entry was wrong."), profile=P, target="el-credits-1", data={"withdrawn": True})
print("\n--- the Legacy Election: ONE record keeps Flexible Bilt Cash, the $200 Bilt Cash and the $400 hotel credit together")
change("2026-12-10", "set_holding", (OWNER, "I made the Legacy Election in the Bilt app on December 10, 2026."), profile=P,
       data={"holding": {"id": "el-legacy-1", "entity": E + "legacy-election", "state": "confirmed", "valid_from": "2026-12-10"}})
table("2027-04-04", want="-EEE-")
table("2027-04-05", want="-EEE-")
table("2027-08-01", want="-EEE-")

print("\n\n=== 7. Leaving the legacy arrangement is permanent")
change("2027-09-05", "end_holding", (OWNER, "I moved to the updated rewards; it took effect with the billing cycle that began September 5, 2027."),
       profile=P, target="el-legacy-1", data={"ended_on": "2027-09-04"})
change("2027-09-05", "set_holding", (OWNER, "On the refreshed arrangement from September 5, 2027."), profile=P,
       data={"holding": {"id": "el-refreshed-1", "entity": E + "refreshed-arrangement", "state": "confirmed", "valid_from": "2027-09-05"}})
print("\n--- the legacy benefits stop that day; Housing-only applies; the $600 starts at the next card anniversary")
table("2027-09-04", want="-EEE-")
table("2027-09-05", want="E----")
table("2028-04-04", want="E----")
table("2028-04-05", want="E---E")
print("\n--- an attempt to go back is accepted as a record, reported, and never applied")
change("2028-05-01", "set_holding", (OWNER, "I want the Legacy Election again from May 1, 2028."), profile=P,
       data={"holding": {"id": "el-legacy-2", "entity": E + "legacy-election", "state": "confirmed", "valid_from": "2028-05-01"}})
table("2028-05-02", want="U---U")      # the legacy side is not even possible any more; the contradiction is flagged
change("2028-05-03", "end_holding", (OWNER, "Withdrawn: the Legacy Election cannot be made again."), profile=P, target="el-legacy-2",
       data={"withdrawn": True})
table("2028-05-03", want="E---E")

print("\n\n=== 8. An account opened in 2027: refreshed from the day it opens, with nothing to elect and nothing to record")
change("2027-02-10", "set_holding", (OWNER2, "I hold Bilt Palladium; account opened February 10, 2027."), profile=P2,
       data={"holding": {"id": "h-bilt-palladium", "entity": "card.bilt-palladium", "state": "confirmed", "valid_from": "2027-02-10",
                         "opened_on": "2027-02-10"}})
table("2027-02-10", P2, want="E---E")
table("2027-12-01", P2, want="E---E")

print("\n\n=== 9. The timeline shows every change on its day")
sh("timeline", "--profile", P, "--as-of", "2026-11-15", "--until", "2028-06-30")
sh("lint")
sh("tables", "status")
print("\nDEMO COMPLETE (work copy: %s)" % work)
