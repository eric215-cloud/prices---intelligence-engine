"""Build the synthetic card fixture from its authored tables, through the normal pipeline.

    python3 fixtures/synthetic_cards.py <empty-or-new-directory>

Everything here is invented: banks, network, tier, cards, benefits, people and sources.
It exists to exercise the card tables and the applicability rules. The committed copy in
fixtures/synthetic-cards/ is the output of this script; a test checks they stay identical.

What the fixture shows
    (a) a card's own confirmed benefit                      voyager.travel-credit
    (b) network-tier baselines that establish nothing       lounge day pass (both cards), rental cover (Kestrel)
    (c) a card-specific exclusion and an upgraded term      kestrel.phone-protection-excluded; voyager primary rental cover
    (d) two people whose holdings stay separate             synthetic-alex (Voyager), synthetic-blake (Kestrel)
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from prices import changes, tables          # noqa: E402
from prices.store import Store, dumps       # noqa: E402
from condition_classes import invented     # noqa: E402

DATE = "2026-11-14"
AUTHOR = "fixture author (synthetic)"
REVIEWER = "Synthetic Reviewer"
PROMOTE_ORDER = ["baseline.orbit-summit.lounge-day-pass", "baseline.orbit-summit.phone-protection",
                 "baseline.orbit-summit.rental-cover", "voyager.travel-credit", "voyager.phone-protection",
                 "voyager.primary-rental-cover", "voyager.rental-cover-superseded", "kestrel.phone-protection-excluded"]
PEOPLE = [("synthetic-alex", "Alex (synthetic)", "card.northwind-voyager"),
          ("synthetic-blake", "Blake (synthetic)", "card.halcyon-kestrel")]


def _write(root, rel, obj):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(dumps(obj))


def _must(out, what):
    if not out["ok"]:
        raise SystemExit("fixture build failed at %s: %s" % (what, out["errors"]))
    return out


def build(dst):
    if os.path.exists(dst) and os.listdir(dst):
        raise SystemExit("refusing to build into a non-empty directory: %s" % dst)
    _write(dst, "data/kb/vocab.json", {
        "tags": {}, "questions": {}, "goal_research": [], "seeded_signatures": [], "watchlist": [],
        "evidence_policy": {"primary_types": ["official", "synthetic"], "secondary_types": ["reputable_secondary"], "secondary_min": 2},
        "promotion_reviewers": [REVIEWER]})
    for pid, owner, _card in PEOPLE:
        _write(dst, "profiles/%s/profile.json" % pid, {
            "id": pid, "label": "SYNTHETIC person for the card fixture - not a real person", "synthetic": True, "owner": owner})
    tables.export(dst)
    for name in tables.AUTHORING:   # the authored rows replace the empty exported tables
        shutil.copy(os.path.join(HERE, "synthetic-cards-input", name + ".csv"), os.path.join(dst, "tables", name + ".csv"))
    _must(tables.import_tables(dst, "tables", AUTHOR, DATE), "tables import")
    att = {"by": REVIEWER, "on": DATE, "statement": "Synthetic review: the cited synthetic source supports the row."}
    for n, rule_id in enumerate(PROMOTE_ORDER, start=1):
        _must(changes.apply(dst, {"id": "cs-20261114-fix-%02d-promote-candidate" % n, "op": "promote_candidate", "author": REVIEWER,
                                  "date": DATE, "reason": "Fixture promotion", "target": "c-" + rule_id,
                                  "data": {"review_by": "2027-05-14", "conditions": invented(Store.load(dst).candidates["c-" + rule_id])},
                                  "attestation": att}), rule_id)
    for n, (pid, owner, card) in enumerate(PEOPLE, start=1):
        _must(changes.apply(dst, {"id": "cs-20261114-fix-%02d-set-holding" % (20 + n), "op": "set_holding", "author": AUTHOR,
                                  "date": DATE, "reason": "Synthetic holding", "profile": pid,
                                  "data": {"holding": {"id": "h-" + card.replace(".", "-"), "entity": card, "state": "confirmed",
                                                       "valid_from": "2026-01-01"}},
                                  "attestation": {"by": owner, "on": DATE, "statement": "Invented holding for the fixture."}}), pid)
    tables.export(dst)
    return dst


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print("built synthetic card fixture at %s" % build(sys.argv[1]))
