"""Turn the classification proposal for the live rules into changesets a reviewer can apply.

    python3 experiments/safety/proposal.py --list
    python3 experiments/safety/proposal.py --write-changesets <dir> --reviewer "<name>" --on YYYY-MM-DD --statement "<what you checked>"
    python3 -m prices apply <dir>/<file>          (one file per rule; OP-14)

This script never touches the project's data. `apply_to_copy` is for tests and experiments, on throwaway copies only.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load():
    with open(os.path.join(HERE, "live_rules_proposal.json"), encoding="utf-8") as f:
        return json.load(f)["rules"]


def changesets(reviewer, on, statement, author="classification proposal", tag="classify"):
    """One classify_conditions changeset per rule, in rule-id order."""
    out = []
    for n, (rule_id, items) in enumerate(sorted(load().items()), 1):
        out.append({"id": "cs-%s-%s-%02d-classify-conditions" % (on.replace("-", ""), tag, n), "op": "classify_conditions", "author": author, "date": on,
                    "reason": "Reviewer's classification of the restrictions and open questions on %s." % rule_id, "target": rule_id,
                    "data": {"items": items}, "attestation": {"by": reviewer, "on": on, "statement": statement}})
    return out


def apply_to_copy(root, on, statement="Scratch copy only: engineering's proposed classes, applied to show their effect. Not a content review."):
    """Apply the proposal in a THROWAWAY copy of the store, as its first listed reviewer. Refuses the project itself."""
    if os.path.realpath(root) == os.path.realpath(ROOT):
        raise RuntimeError("the proposal is not applied to the project: a reviewer does that (OP-14)")
    sys.path.insert(0, ROOT)
    from prices import changes
    from prices.store import Store
    reviewer = Store.load(root).vocab["promotion_reviewers"][0]
    for cs in changesets(reviewer, on, statement, author="scratch copy", tag="scratch"):
        out = changes.apply(root, cs)
        if not out["ok"]:
            raise RuntimeError("%s: %s" % (cs["target"], out["errors"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--write-changesets", metavar="DIR")
    ap.add_argument("--reviewer")
    ap.add_argument("--on")
    ap.add_argument("--statement")
    a = ap.parse_args(argv)
    if a.write_changesets:
        if not (a.reviewer and a.on and a.statement):
            ap.error("--write-changesets needs --reviewer, --on and --statement")
        os.makedirs(a.write_changesets, exist_ok=True)
        for cs in changesets(a.reviewer, a.on, a.statement, author=a.reviewer):
            path = os.path.join(a.write_changesets, cs["id"] + ".json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cs, f, indent=2)
            print(path)
        return 0
    for rule_id, items in sorted(load().items()):
        print(rule_id)
        for i in items:
            print("    %-20s %s%s" % (i["class"] + (" (" + i["enforced_by"] + ")" if "enforced_by" in i else ""), i["text"][:90], ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
