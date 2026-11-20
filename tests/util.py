"""Builders for small in-memory stores. All test data is synthetic and lives only in tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(1, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures"))

from prices.store import Store  # noqa: E402

TEST_VOCAB = {
    "evidence_policy": {"primary_types": ["official", "synthetic"], "secondary_types": ["reputable_secondary"], "secondary_min": 2},
    "tags": {"region:japan": {"keywords": ["japan", "tokyo"]}, "cabin:business": {"keywords": ["business class"]},
             "cabin:economy": {"keywords": ["economy"]}, "type:flight": {"keywords": ["fly", "flight"]}},
    "questions": {
        "status_match_out": {"modes": ["forward"], "applies_to": ["status"], "ask": "What does {name} unlock elsewhere?", "queries": ["{name} status match"]},
        "card_benefits": {"modes": ["forward"], "applies_to": ["card"], "ask": "What statuses does {name} confer?", "queries": ["{name} elite status benefit"]},
        "inbound_paths": {"modes": ["backward", "exploratory"], "applies_to": ["status", "benefit", "capability"], "ask": "How can {name} be obtained?", "queries": ["how to get {name}"]},
        "combined_with": {"modes": ["bridge"], "applies_to": ["pair"], "ask": "Do {a} and {b} combine?", "queries": ["{a} {b} together"]},
        "identify": {"modes": ["exploratory"], "applies_to": [], "ask": "What is {name}?", "queries": ["{name} loyalty program"]},
    },
    "goal_research": [{"id": "check-award-space", "applies_dims": ["region", "cabin"], "ask": "Check live award space.", "record_as": "observation(availability)"}],
    "seeded_signatures": [],
}


def H(x):
    return {"holds": x}


def ent(id, kind="status", **kw):
    return dict({"id": id, "kind": kind, "name": kw.pop("name", id)}, **kw)


def ev(id="ev1", source_type="synthetic", publisher="Test Fixture", retrieved_on="2026-01-01"):
    return {"id": id, "url": "https://example.invalid/" + id, "title": "fixture " + id, "publisher": publisher,
            "source_type": source_type, "retrieved_on": retrieved_on, "summary": "synthetic test evidence"}


def rule(id, kind, output, when, status="verified", evidence=("ev1",), **kw):
    r = {"id": id, "kind": kind, "output": output, "when": when, "summary": "rule " + id,
         "evidence": list(evidence), "verification": {"status": status}}
    if status == "verified":
        r["verification"].update({"last_verified": "2026-01-01", "review_by": kw.pop("review_by", "2029-01-01")})
    reviewed = kw.pop("reviewed", True)
    r.update(kw)
    if reviewed and "condition_review" not in r and (r.get("restrictions") or r.get("open_questions")):
        # Fixture rules stand for REVIEWED rules, as status="verified" stands for verified ones: every restriction is
        # taken as a usage term and every open question as informational. Pass reviewed=False for a rule nobody has
        # classified, or condition_review=... for a specific classification (prices/conditions.py).
        r["condition_review"] = {"by": "Test Owner", "on": "2026-01-01",
                                 "items": [{"text": t, "class": "usage"} for t in r.get("restrictions") or []]
                                 + [{"text": t, "class": "informational"} for t in r.get("open_questions") or []]}
    return r


def review(*items, by="Test Owner", on="2026-01-01"):
    """A reviewer's classification for a fixture rule: review(("New applicants only", "unchecked"), ("Ends in June", "enforced", "dates"))."""
    return {"by": by, "on": on, "items": [dict({"text": i[0], "class": i[1]}, **({"enforced_by": i[2]} if len(i) > 2 else {})) for i in items]}


def holding(id, entity, state="confirmed", **kw):
    h = {"id": id, "entity": entity, "state": state}
    if state == "confirmed":
        h.update({"confirmed_on": "2026-01-01", "confirmed_by": "synthetic"})
    h.update(kw)
    return h


def metric(id, value, state="confirmed"):
    m = {"id": id, "value": value, "as_of": "2026-01-01", "state": state}
    if state == "confirmed":
        m["confirmed_by"] = "synthetic"
    return m


def approve(option, by="Test Reviewer"):
    """An invented election option, stamped as independently approved exactly as its terms stand (Step 04B, A8)."""
    from prices.elections import terms_digest
    option = dict(option, election=dict(option["election"]))
    option["election"].pop("approval", None)
    option["election"]["approval"] = {"by": by, "on": "2026-01-01", "changeset": "fixture", "terms": terms_digest(option)}
    return option


def make_store(entities=(), rules=(), holdings=(), metrics=(), evidence=None, candidates=(), observations=(),
               profile="t", vocab=None, owner="Test Owner", approve_elections=True):
    """approve_elections: invented election options stand for approved definitions unless a test says otherwise
    (pass False, or give the option its own `approval`)."""
    f = {"data/kb/vocab.json": vocab or TEST_VOCAB,
         "profiles/%s/profile.json" % profile: {"id": profile, "label": "test", "synthetic": True, "owner": owner}}
    for e in entities:
        if approve_elections and e.get("kind") == "election" and isinstance(e.get("election"), dict) and "approval" not in e["election"]:
            e = approve(e)
        f[Store.path("entities", e["id"])] = e
    for r in rules:
        f[Store.path("rules", r["id"])] = r
    for e in (evidence if evidence is not None else [ev()]):
        f[Store.path("evidence", e["id"])] = e
    for h in holdings:
        f[Store.path("holdings", h["id"], profile)] = h
    for m in metrics:
        f[Store.path("metrics", m["id"], profile)] = m
    for c in candidates:
        f[Store.path("candidates", c["id"])] = c
    for o in observations:
        f[Store.path("observations", o["id"])] = o
    return Store(f)


def approve_elections_on_disk(root, by="Bradley", day="2026-11-20"):
    """SCRATCH COPIES ONLY: approve every election option on disk, as a reviewer independent of the terms' author.
    Refuses to touch the project itself."""
    import os
    from prices import changes
    from prices.elections import terms_digest
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.realpath(root) != os.path.realpath(here), "the project's election definitions are approved by a reviewer, not by tests"
    s = Store.load(root)
    css = [{"id": "cs-%s-scratch-approve-%02d" % (day.replace("-", ""), n), "op": "approve_election", "target": o["id"], "author": "scratch",
            "date": day, "reason": "scratch copy only", "data": {"terms": terms_digest(o)},
            "attestation": {"by": by, "on": day, "statement": "scratch copy only: not a review"}}
           for n, o in enumerate(sorted((e for e in s.entities.values() if e["kind"] == "election"), key=lambda e: e["id"]), 1)]
    out = changes.apply_many(root, css)
    assert out["ok"], out["errors"]


def write_store(store, root):
    store.save(root, sorted(store.files))


def codes(issues):
    return {i[1] for i in issues if i[0] == "ERROR"}


def flag_codes(result):
    return {f["code"] for f in result.flags}
