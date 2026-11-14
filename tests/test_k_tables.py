"""Relational foundation, part 2: CSV tables as a view of the store and as validated authoring input.

Every test builds the synthetic card fixture in a temporary directory (through the normal
pipeline), edits its CSV files the way a maintainer would, and checks what the import did.
"""
import contextlib
import csv
import filecmp
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

import util  # noqa: F401  (sets sys.path)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "fixtures"))

import synthetic_cards  # noqa: E402
from prices import changes, tables  # noqa: E402
from prices.cards import CONFIRMED, PENDING, UNPROVEN, matrix  # noqa: E402
from prices.cli import main  # noqa: E402
from prices.engine import ESTABLISHED, NOT_AVAILABLE, evaluate  # noqa: E402
from prices.lint import lint  # noqa: E402
from prices.store import Store, read_audit  # noqa: E402

D = "2026-12-01"
WHO = "test maintainer"
REVIEW = {"by": "Synthetic Reviewer", "on": D, "statement": "Checked against the cited synthetic source."}
VOYAGER, KESTREL = "card.northwind-voyager", "card.halcyon-kestrel"


def slurp(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def spit(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def table_files(root):
    d = os.path.join(root, "tables")
    return {n: slurp(os.path.join(d, n)) for n in sorted(os.listdir(d))}


def read(root, table):
    with open(os.path.join(root, "tables", table + ".csv"), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(root, table, rows):
    with open(os.path.join(root, "tables", table + ".csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(tables.COLUMNS[table])
        for r in rows:
            w.writerow([r.get(c, "") for c in tables.COLUMNS[table]])


def edit(root, table, rid, **cells):
    rows = read(root, table)
    hit = [r for r in rows if r["id"] == rid]
    assert len(hit) == 1, (table, rid)
    hit[0].update({k.replace("EQ_", "="): v for k, v in cells.items()})
    write(root, table, rows)


def add(root, table, **row):
    write(root, table, read(root, table) + [row])


def source(sid, card, summary="Synthetic 2027 guide."):
    return {"id": sid, "url": "https://example.invalid/" + sid, "title": "Synthetic guide " + sid, "publisher": "Synthetic Bank",
            "source_type": "synthetic", "retrieved_on": D, "applies_to": card, "summary": summary}


def imp(root, dry_run=False):
    return tables.import_tables(root, "tables", WHO, D, dry_run=dry_run)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prices-tables-")
        self.root = synthetic_cards.build(os.path.join(self.tmp, "fx"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def store(self):
        return Store.load(self.root)

    def have(self, person, entity, day=D):
        return evaluate(self.store(), person, day).have(entity)

    def rejected(self, code):
        before, log = self.store().digest(), len(read_audit(self.root))
        csv_before = table_files(self.root)
        out = imp(self.root)
        self.assertFalse(out["ok"], "import should have been rejected")
        self.assertTrue(any(code in e for e in out["errors"]), out["errors"])
        self.assertEqual(self.store().digest(), before, "a rejected import must not change any record")
        self.assertEqual(len(read_audit(self.root)), log, "a rejected import applies no changeset")
        self.assertEqual(table_files(self.root), csv_before, "the maintainer's files are left as they were")
        return out


class TestFixtureAndExport(Base):
    def test_committed_fixture_is_exactly_what_the_builder_produces(self):
        committed = os.path.join(ROOT, "fixtures", "synthetic-cards")

        def tree(base):
            return sorted(os.path.relpath(os.path.join(d, n), base) for d, _s, names in os.walk(base) for n in names)
        self.assertEqual(tree(committed), tree(self.root))
        _same, diff, errs = filecmp.cmpfiles(committed, self.root, tree(committed), shallow=False)
        self.assertEqual((diff, errs), ([], []))

    def test_fixture_is_valid_and_shows_the_four_required_cases(self):
        s = self.store()
        self.assertEqual(lint(s), [])
        st = {(m["card"], m["benefit"]): m["standing"] for m in matrix(s, D)}
        self.assertEqual(st[(VOYAGER, "benefit.voyager.travel-credit")], CONFIRMED)                 # (a) card's own benefit
        self.assertEqual(st[(VOYAGER, "benefit.orbit-summit.lounge-day-pass")], UNPROVEN)          # (b) baseline, no card evidence
        self.assertEqual(st[(KESTREL, "benefit.orbit-summit.rental-cover")], UNPROVEN)
        self.assertEqual(st[(KESTREL, "benefit.orbit-summit.phone-protection")], "EXCLUDED")       # (c) exclusion
        self.assertEqual(st[(VOYAGER, "benefit.orbit-summit.rental-cover")], "SUPERSEDED")         # (c) upgrade
        alex, blake = evaluate(s, "synthetic-alex", D), evaluate(s, "synthetic-blake", D)          # (d) two people
        got = lambda r: sorted(a[5:] for a in r.best["E"] if a.startswith("have:benefit."))        # noqa: E731
        self.assertEqual(got(alex), ["benefit.orbit-summit.phone-protection", "benefit.voyager.primary-rental-cover", "benefit.voyager.travel-credit"])
        self.assertEqual(got(blake), [])
        self.assertEqual((alex.have(KESTREL), blake.have(VOYAGER)), (NOT_AVAILABLE, NOT_AVAILABLE))
        self.assertEqual(alex.have("benefit.orbit-summit.lounge-day-pass"), NOT_AVAILABLE)

    def test_every_fixture_record_is_labelled_synthetic(self):
        s = self.store()
        self.assertTrue(all(e["source_type"] == "synthetic" and "example.invalid" in e["url"] for e in s.evidence.values()))
        self.assertTrue(all(s.profile(p).meta["synthetic"] for p in s.profile_names()))
        self.assertTrue(all("synthetic" in e["name"].lower() or e["kind"] == "benefit" for e in s.entities.values()))

    def test_export_is_deterministic_and_import_of_untouched_tables_does_nothing(self):
        before = table_files(self.root)
        tables.export(self.root)
        self.assertEqual(before, table_files(self.root))
        self.assertEqual(tables.status(self.root), {"exists": True, "stale": [], "edited": []})
        digest, log = self.store().digest(), len(read_audit(self.root))
        for _ in range(2):
            out = imp(self.root)
            self.assertTrue(out["ok"])
            self.assertEqual((out["changesets"], out["applied"]), ([], []))
        self.assertEqual((self.store().digest(), len(read_audit(self.root))), (digest, log))

    def test_spreadsheet_style_file_with_bom_and_crlf_is_read_the_same(self):
        path = os.path.join(self.root, "tables", "card_benefits.csv")
        text = slurp(path)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(text.replace("\n", "\r\n"))
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(out["changesets"], [])

    def test_tables_carry_no_holder_column_and_import_never_touches_profiles(self):
        self.assertFalse([c for t in tables.AUTHORING for c in tables.COLUMNS[t] if c in ("holder", "cardholder", "owner", "profile")])
        prof = {p: v for p, v in self.store().files.items() if p.startswith("profiles/")}
        edit(self.root, "cards", KESTREL, annual_fee_usd="99", sources="ev-syn-kestrel-terms;ev-fee")
        add(self.root, "sources", **source("ev-fee", KESTREL, "Fee changed to 99."))
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual({p: v for p, v in self.store().files.items() if p.startswith("profiles/")}, prof)
        self.assertEqual({cs["op"] for cs in out["changesets"]} & {"set_holding", "end_holding", "set_metric"}, set())


class TestAuthoring(Base):
    def add_kestrel_lounge(self, evidence="ev-kestrel-2027"):
        add(self.root, "card_benefits", id="kestrel.lounge-day-pass", card=KESTREL, benefit="benefit.orbit-summit.lounge-day-pass",
            applicability="confirmed", summary="2027 guide confirms one lounge day pass a year on this card.", evidence=evidence)
        if evidence == "ev-kestrel-2027":
            add(self.root, "sources", **source("ev-kestrel-2027", KESTREL, "2027 guide lists the lounge day pass for this card."))

    def test_new_benefit_row_is_quarantined_until_a_reviewer_promotes_it(self):
        rules_before = set(self.store().rules)
        self.add_kestrel_lounge()
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual([cs["op"] for cs in out["changesets"]], ["add_candidate"])
        s = self.store()
        self.assertEqual(set(s.rules), rules_before)                                          # no rule was created
        self.assertEqual(s.candidates["c-kestrel.lounge-day-pass"]["status"], "proposed")
        self.assertEqual(self.have("synthetic-blake", "benefit.orbit-summit.lounge-day-pass"), NOT_AVAILABLE)
        st = {(m["card"], m["benefit"]): m["standing"] for m in matrix(s, D)}
        self.assertEqual(st[(KESTREL, "benefit.orbit-summit.lounge-day-pass")], PENDING)
        row = [r for r in read(self.root, "card_benefits") if r["id"] == "kestrel.lounge-day-pass"][0]
        self.assertEqual(row["=state"], "candidate")                                          # refreshed table shows where it stands
        self.assertEqual(tables.status(self.root)["stale"], [])
        # a maintainer cannot promote; a named reviewer can
        cs = {"id": "cs-p1", "op": "promote_candidate", "author": WHO, "date": D, "reason": "r", "target": "c-kestrel.lounge-day-pass",
              "data": {"review_by": "2027-06-01"}, "attestation": {"by": WHO, "on": D, "statement": "looks fine"}}
        self.assertTrue(changes.apply(self.root, cs)["errors"][0].startswith("REVIEWER_NOT_AUTHORIZED"))
        ok = changes.apply(self.root, dict(cs, id="cs-p2", attestation=REVIEW))
        self.assertTrue(ok["ok"], ok["errors"])
        self.assertEqual(self.have("synthetic-blake", "benefit.orbit-summit.lounge-day-pass"), ESTABLISHED)
        self.assertEqual(self.have("synthetic-alex", "benefit.orbit-summit.lounge-day-pass"), NOT_AVAILABLE)   # other card, other person

    def test_network_page_cannot_get_a_tier_benefit_confirmed_for_a_card(self):
        self.add_kestrel_lounge(evidence="ev-syn-orbit-summit-benefits")      # cites only the network's marketing page
        self.assertTrue(imp(self.root)["ok"])                                  # may wait in quarantine...
        out = changes.apply(self.root, {"id": "cs-p", "op": "promote_candidate", "author": "r", "date": D, "reason": "r",
                                        "target": "c-kestrel.lounge-day-pass", "data": {"review_by": "2027-06-01"}, "attestation": REVIEW})
        self.assertFalse(out["ok"])                                            # ...but can never become a rule
        self.assertTrue(out["errors"][0].startswith("CARD_SPECIFIC_EVIDENCE_REQUIRED"), out["errors"])
        self.assertEqual(self.have("synthetic-blake", "benefit.orbit-summit.lounge-day-pass"), NOT_AVAILABLE)

    def test_candidate_rows_can_only_be_withdrawn(self):
        self.add_kestrel_lounge()
        self.assertTrue(imp(self.root)["ok"])
        edit(self.root, "card_benefits", "kestrel.lounge-day-pass", summary="Changed my mind about the wording.")
        self.rejected("CANDIDATE_READ_ONLY")
        tables.export(self.root)
        edit(self.root, "card_benefits", "kestrel.lounge-day-pass", _action="withdraw")
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(self.store().candidates["c-kestrel.lounge-day-pass"]["status"], "rejected")   # kept as history
        self.assertNotIn("kestrel.lounge-day-pass", [r["id"] for r in read(self.root, "card_benefits")])
        self.add_kestrel_lounge(evidence="ev-kestrel-2027")                    # the same id may be proposed again
        again = imp(self.root)
        self.assertTrue(again["ok"], again["errors"])
        self.assertIn("c-kestrel.lounge-day-pass-r2", self.store().candidates)

    def test_new_card_with_its_parties_and_sources_in_one_import(self):
        add(self.root, "parties", id="org.quay-bank", kind="organization", name="Quay Bank (synthetic)")
        add(self.root, "sources", **source("ev-quay-terms", "card.quay-one", "Names issuer and network."))
        add(self.root, "cards", id="card.quay-one", name="Quay One (synthetic)", issuer="org.quay-bank", network="org.orbit",
            cobrand_partner="none", sources="ev-quay-terms")
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual([cs["op"] for cs in out["changesets"]], ["add_entity", "add_entity"])
        card = self.store().entities["card.quay-one"]
        self.assertEqual(card["card"], {"issuer": "org.quay-bank", "network": "org.orbit", "cobrand_partner": None})
        self.assertNotIn("network_tier", card["card"])                          # left blank = not recorded, and nothing is assumed
        self.assertEqual([m for m in matrix(self.store(), D) if m["card"] == "card.quay-one"], [])
        self.assertEqual(lint(self.store()), [])

    def test_role_change_keeps_the_previous_value(self):
        add(self.root, "parties", id="org.new-manager", kind="organization", name="New Manager (synthetic)")
        add(self.root, "sources", **source("ev-kestrel-notice", KESTREL, "Servicing moved to New Manager."))
        edit(self.root, "cards", KESTREL, program_manager="org.new-manager", sources="ev-syn-kestrel-terms;ev-kestrel-notice")
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(self.store().entities[KESTREL]["card"]["program_manager"], "org.new-manager")
        rev = [cs["id"] for cs in out["changesets"] if cs["op"] == "revise_entity"][0]
        snap = json.loads(slurp(os.path.join(self.root, "data/audit/previous", rev + ".json")))
        self.assertEqual(snap["records"]["data/kb/entities/%s.json" % KESTREL]["before"]["card"]["program_manager"], "org.ledgerline")
        self.assertEqual({(self.have("synthetic-blake", KESTREL))}, {ESTABLISHED})


class TestMaintenance(Base):
    """The junior-maintainer task of docs/operations/OP-10-tables.md, step for step."""

    def test_change_one_benefit_and_its_evidence(self):
        add(self.root, "sources", **source("ev-voyager-2027", VOYAGER, "2027 guide: travel credit is now 250 and excludes rail."))
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="250 annual travel credit per cardmember year.",
             restrictions="Travel purchases only | Rail fares excluded | Resets on the account anniversary",
             evidence="ev-syn-voyager-guide;ev-voyager-2027")
        plan = imp(self.root, dry_run=True)
        self.assertEqual([cs["op"] for cs in plan["changesets"]], ["revise_rule"])
        self.assertEqual(self.store().rules["voyager.travel-credit"]["summary"], "200 annual travel credit per cardmember year.")   # dry run wrote nothing
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        r = self.store().rules["voyager.travel-credit"]
        self.assertEqual(r["summary"], "250 annual travel credit per cardmember year.")
        self.assertEqual(r["restrictions"], ["Travel purchases only", "Rail fares excluded", "Resets on the account anniversary"])
        self.assertEqual(r["evidence"], ["ev-syn-voyager-guide", "ev-voyager-2027"])            # old evidence kept, new appended
        self.assertEqual(r["verification"]["last_verified"], D)
        self.assertEqual(r["when"], {"holds": VOYAGER})                                         # logic untouched
        snap = json.loads(slurp(os.path.join(self.root, "data/audit/previous", out["applied"][0] + ".json")))
        old = snap["records"]["data/kb/rules/voyager.travel-credit.json"]["before"]
        self.assertEqual(old["summary"], "200 annual travel credit per cardmember year.")       # previous value preserved
        self.assertEqual(lint(self.store()), [])
        self.assertEqual(self.have("synthetic-alex", "benefit.voyager.travel-credit"), ESTABLISHED)
        self.assertEqual(self.have("synthetic-blake", "benefit.voyager.travel-credit"), NOT_AVAILABLE)
        self.assertEqual(imp(self.root)["changesets"], [])                                      # second import: nothing to do
        self.assertEqual(read_audit(self.root)[-1]["author"], WHO)

    def test_change_without_new_evidence_is_refused(self):
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="250 annual travel credit per cardmember year.")
        self.rejected("EVIDENCE_REQUIRED")

    def test_update_expiration(self):
        add(self.root, "sources", **source("ev-voyager-2027", VOYAGER, "Phone protection ends June 30, 2027."))
        edit(self.root, "card_benefits", "voyager.phone-protection", valid_to="2027-06-30", evidence="ev-syn-voyager-guide;ev-voyager-2027")
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertFalse(out["review_needed"])                                                  # still in effect today
        self.assertEqual(self.have("synthetic-alex", "benefit.orbit-summit.phone-protection", "2027-06-30"), ESTABLISHED)
        self.assertEqual(self.have("synthetic-alex", "benefit.orbit-summit.phone-protection", "2027-07-01"), NOT_AVAILABLE)
        st = {(m["card"], m["benefit"]): m["standing"] for m in matrix(self.store(), "2027-07-01")}
        self.assertEqual(st[(VOYAGER, "benefit.orbit-summit.phone-protection")], UNPROVEN)      # falls back to unproven, never to "inherited"

    def test_change_applicability_means_retire_and_add(self):
        edit(self.root, "card_benefits", "voyager.phone-protection", applicability="excluded")
        self.rejected("LOGIC_CHANGE")

    def test_retire_a_benefit_and_keep_its_history(self):
        add(self.root, "sources", **source("ev-voyager-2027", VOYAGER, "Travel credit discontinued on November 30, 2026."))
        edit(self.root, "card_benefits", "voyager.travel-credit", _action="retire", ended_on="2026-11-30",
             evidence="ev-syn-voyager-guide;ev-voyager-2027")
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual([cs["op"] for cs in out["changesets"]], ["retire_rule"])
        self.assertTrue(out["review_needed"])                                                   # a person lost something: review is flagged
        r = self.store().rules["voyager.travel-credit"]                                         # record still exists
        self.assertEqual((r["verification"]["status"], r["valid_to"]), ("retired", "2026-11-30"))
        self.assertEqual(r["summary"], "200 annual travel credit per cardmember year.")
        self.assertEqual(self.have("synthetic-alex", "benefit.voyager.travel-credit"), NOT_AVAILABLE)
        row = [x for x in read(self.root, "card_benefits") if x["id"] == "voyager.travel-credit"][0]
        self.assertEqual((row["=state"], row["valid_to"], row["_action"]), ("retired", "2026-11-30", ""))   # history stays visible in the table
        self.assertEqual(lint(self.store()), [])
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="Trying to edit history.")
        self.rejected("ROW_READ_ONLY")

    def test_retire_needs_a_date_and_a_source(self):
        edit(self.root, "card_benefits", "voyager.travel-credit", _action="retire")
        self.rejected("BAD_VALUE")
        tables.export(self.root)
        edit(self.root, "card_benefits", "voyager.travel-credit", _action="retire", ended_on="2026-11-30")
        self.rejected("EVIDENCE_REQUIRED")

    def test_confirm_a_row_after_rechecking_its_source(self):
        add(self.root, "sources", **source("ev-kestrel-recheck", KESTREL, "Guide re-read: phone protection still not offered."))
        edit(self.root, "card_benefits", "kestrel.phone-protection-excluded", _action="confirm", review_by="2027-11-30",
             evidence="ev-syn-kestrel-guide;ev-kestrel-recheck")
        out = imp(self.root)
        self.assertTrue(out["ok"], out["errors"])
        v = self.store().rules["kestrel.phone-protection-excluded"]["verification"]
        self.assertEqual((v["last_verified"], v["review_by"]), (D, "2027-11-30"))

    def test_revert_restores_the_previous_record_exactly(self):
        before = self.store().rules["voyager.travel-credit"]
        add(self.root, "sources", **source("ev-voyager-2027", VOYAGER))
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="Wrong summary entered by mistake.", evidence="ev-syn-voyager-guide;ev-voyager-2027")
        applied = imp(self.root)["applied"][0]
        cs = {"id": "cs-revert-1", "op": "revert_changeset", "author": WHO, "date": D, "reason": "Entered in error",
              "data": {"changeset": applied}, "attestation": {"by": WHO, "on": D, "statement": "undo"}}
        self.assertTrue(changes.apply(self.root, cs)["errors"][0].startswith("REVIEWER_NOT_AUTHORIZED"))
        out = changes.apply(self.root, dict(cs, id="cs-revert-2", attestation=REVIEW))
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(self.store().rules["voyager.travel-credit"], before)
        self.assertNotIn("ev-voyager-2027", self.store().evidence)
        self.assertEqual(lint(self.store()), [])
        log = [(e["op"], e["result"]) for e in read_audit(self.root)][-3:]                       # everything stays in the log
        self.assertEqual(log, [("revise_rule", "applied"), ("revert_changeset", "rejected"), ("revert_changeset", "applied")])

    def test_revert_is_refused_once_the_record_has_moved_on(self):
        add(self.root, "sources", **source("ev-v1", VOYAGER))
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="First change.", evidence="ev-syn-voyager-guide;ev-v1")
        first = imp(self.root)["applied"][0]
        add(self.root, "sources", **source("ev-v2", VOYAGER))
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="Second change.", evidence="ev-syn-voyager-guide;ev-v1;ev-v2")
        self.assertTrue(imp(self.root)["ok"])
        out = changes.apply(self.root, {"id": "cs-revert-3", "op": "revert_changeset", "author": WHO, "date": D, "reason": "r",
                                        "data": {"changeset": first}, "attestation": REVIEW})
        self.assertFalse(out["ok"])
        self.assertTrue(out["errors"][0].startswith("LATER_CHANGES"), out["errors"])
        self.assertEqual(self.store().rules["voyager.travel-credit"]["summary"], "Second change.")


class TestRejection(Base):
    """Invalid, duplicate, stale or unsupported edits: the whole import is refused and nothing changes."""

    def test_one_bad_row_blocks_the_good_rows_in_the_same_import(self):
        add(self.root, "sources", **source("ev-voyager-2027", VOYAGER))
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="A perfectly valid change.", evidence="ev-syn-voyager-guide;ev-voyager-2027")
        edit(self.root, "card_benefits", "voyager.phone-protection", valid_to="next summer", evidence="ev-syn-voyager-guide;ev-voyager-2027")
        out = self.rejected("REJECTED: card_benefits row voyager.phone-protection")
        self.assertTrue(any("YYYY-MM-DD" in e for e in out["errors"]), out["errors"])
        self.assertEqual(self.store().rules["voyager.travel-credit"]["summary"], "200 annual travel credit per cardmember year.")

    def test_failure_late_in_the_batch_undoes_the_earlier_changesets(self):
        add(self.root, "benefits", id="benefit.kestrel.bag-fee", name="Kestrel free checked bag")          # valid, staged first
        add(self.root, "card_benefits", id="ghost.bag-fee", card="card.does-not-exist", benefit="benefit.kestrel.bag-fee",
            applicability="confirmed", summary="Refers to a card that is not on file.", evidence="ev-syn-kestrel-guide")
        self.rejected("UNKNOWN_REFERENCE")
        self.assertNotIn("benefit.kestrel.bag-fee", self.store().entities)

    def test_duplicates(self):
        rows = read(self.root, "card_benefits")
        write(self.root, "card_benefits", rows + [dict(rows[0])])
        self.rejected("DUPLICATE_ROW")
        tables.export(self.root)
        add(self.root, "card_benefits", id="voyager.travel-credit-again", card=VOYAGER, benefit="benefit.voyager.travel-credit",
            applicability="confirmed", summary="Same relationship under another id.", evidence="ev-syn-voyager-guide")
        self.rejected("DUPLICATE_RELATIONSHIP")
        tables.export(self.root)
        add(self.root, "benefits", id=VOYAGER, name="Benefit reusing a card's id")
        self.rejected("ID_EXISTS")

    def test_unsupported_edits(self):
        cases = [
            (lambda: write(self.root, "card_benefits", read(self.root, "card_benefits")[1:]), "ROW_DELETED"),
            (lambda: edit(self.root, "card_benefits", "voyager.travel-credit", EQ_state="retired"), "READ_ONLY_COLUMN"),
            (lambda: edit(self.root, "tier_baselines", "baseline.orbit-summit.rental-cover", EQ_last_verified="2099-01-01"), "READ_ONLY_COLUMN"),
            (lambda: edit(self.root, "card_benefits", "voyager.travel-credit", card=KESTREL), "LOGIC_CHANGE"),
            (lambda: edit(self.root, "card_benefits", "voyager.travel-credit", evidence=""), "EVIDENCE_REMOVED"),
            (lambda: edit(self.root, "sources", "ev-syn-voyager-guide", summary="Rewritten after the fact."), "EVIDENCE_IMMUTABLE"),
            (lambda: add(self.root, "sources", **source("ev-orphan", VOYAGER)), "UNUSED_SOURCE"),
            (lambda: edit(self.root, "card_benefits", "voyager.travel-credit", evidence="ev-syn-voyager-guide;ev-nowhere", summary="x"), "UNKNOWN_SOURCE"),
            (lambda: edit(self.root, "card_benefits", "voyager.travel-credit", ended_on="2026-12-31"), "BAD_VALUE"),
            (lambda: edit(self.root, "card_benefits", "voyager.travel-credit", _action="delete"), "BAD_VALUE"),
            (lambda: edit(self.root, "parties", "tier.orbit-summit", kind="organization"), "KIND_CHANGE"),
            (lambda: edit(self.root, "cards", KESTREL, sources=""), "EVIDENCE_REMOVED"),
            (lambda: edit(self.root, "cards", KESTREL, issuer="tier.orbit-summit"), "BAD_ROLE"),
            (lambda: edit(self.root, "cards", KESTREL, annual_fee_usd="ninety-five"), "BAD_VALUE"),
            (lambda: add(self.root, "card_benefits", id="k.maybe", card=KESTREL, benefit="benefit.orbit-summit.rental-cover",
                         applicability="probably", summary="Guess.", evidence="ev-syn-kestrel-guide"), "BAD_VALUE"),
            (lambda: add(self.root, "card_benefits", id="k.nosrc", card=KESTREL, benefit="benefit.orbit-summit.rental-cover",
                         applicability="confirmed", summary="No source given."), "MISSING_VALUE"),
            (lambda: add(self.root, "card_benefits", id="k.early", card=KESTREL, benefit="benefit.orbit-summit.rental-cover",
                         applicability="confirmed", summary="Tries to set its own review date.", evidence="ev-syn-kestrel-guide",
                         review_by="2030-01-01"), "BAD_VALUE"),
            (lambda: add(self.root, "tier_baselines", id="baseline.wrong", tier=VOYAGER, benefit="benefit.orbit-summit.rental-cover",
                         summary="A card is not a tier.", evidence="ev-syn-orbit-summit-benefits"), "BAD_BASELINE_SHAPE"),
            (self._edit_view, "READ_ONLY_VIEW"),
            (self._break_header, "BAD_HEADER"),
        ]
        for do, code in cases:
            do()
            self.rejected(code)
            tables.export(self.root)   # the maintainer starts over from a fresh export

    def _edit_view(self):
        path = os.path.join(self.root, "tables", "view_applicability.csv")
        spit(path, slurp(path).replace("UNPROVEN", "CONFIRMED"))

    def _break_header(self):
        path = os.path.join(self.root, "tables", "cards.csv")
        spit(path, slurp(path).replace("id,name,", "id,name,cardholder,", 1))

    def test_stale_tables_are_refused_not_merged(self):
        edit(self.root, "card_benefits", "voyager.travel-credit", summary="Edit made on an old export.")
        out = changes.apply(self.root, {"id": "cs-other", "op": "add_entity", "author": "someone else", "date": D, "reason": "r",
                                        "data": {"entity": {"id": "benefit.added-meanwhile", "kind": "benefit", "name": "Added meanwhile"}}})
        self.assertTrue(out["ok"])
        st = tables.status(self.root)
        self.assertEqual((st["stale"], st["edited"]), (["benefits.csv"], ["card_benefits.csv"]))
        self.rejected("TABLES_STALE")

    def test_export_is_never_silently_stale(self):
        cs = {"id": "cs-cli-1", "op": "add_entity", "author": "m", "date": D, "reason": "r",
              "data": {"entity": {"id": "benefit.via-cli", "kind": "benefit", "name": "Added through the command line"}}}
        path = os.path.join(self.tmp, "cs.json")
        spit(path, json.dumps(cs))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["--root", self.root, "apply", path]), 0)
        self.assertIn("tables/ refreshed", buf.getvalue())                       # clean tables follow the store automatically
        self.assertIn("benefit.via-cli", [r["id"] for r in read(self.root, "benefits")])
        # with unimported edits present, the files are left alone and the staleness is reported loudly
        edit(self.root, "benefits", "benefit.via-cli", name="Half-finished edit")
        spit(path, json.dumps(dict(cs, id="cs-cli-2", data={"entity": {"id": "benefit.second", "kind": "benefit", "name": "Second"}})))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["--root", self.root, "apply", path])
            main(["--root", self.root, "lint"])
            code = main(["--root", self.root, "tables", "status"])
        self.assertIn("left untouched", buf.getvalue())
        self.assertIn("TABLES_STALE", buf.getvalue())
        self.assertIn("TABLES_EDITED", buf.getvalue())
        self.assertEqual(code, 1)
        self.assertIn("Half-finished edit", slurp(os.path.join(self.root, "tables", "benefits.csv")))

    def test_import_without_an_export_is_refused(self):
        os.remove(os.path.join(self.root, "tables", tables.MANIFEST))
        self.rejected("NO_EXPORT")

    def test_batch_apply_is_all_or_nothing(self):
        good = {"id": "cs-b1", "op": "add_entity", "author": "m", "date": D, "reason": "r",
                "data": {"entity": {"id": "benefit.batch-one", "kind": "benefit", "name": "One"}}}
        bad = {"id": "cs-b2", "op": "flag_rule", "author": "m", "date": D, "reason": "r", "target": "no-such-rule",
               "data": {"open_questions": ["q"]}}
        before = self.store().digest()
        out = changes.apply_many(self.root, [good, bad])
        self.assertFalse(out["ok"])
        self.assertEqual((out["failed_index"], out["failed_id"]), (1, "cs-b2"))
        self.assertEqual(self.store().digest(), before)
        self.assertFalse(os.path.exists(os.path.join(self.root, "data/audit/changesets/cs-b1.json")))
        last = read_audit(self.root)[-1]
        self.assertEqual((last["changeset"], last["result"], last["batch_size"]), ("cs-b2", "rejected", 2))


class TestLiveProject(unittest.TestCase):
    def test_committed_tables_match_the_live_store(self):
        st = tables.status(ROOT)
        self.assertTrue(st["exists"], "run: python3 -m prices tables export")
        self.assertEqual((st["stale"], st["edited"]), ([], []), "tables/ is out of step with data/: run `python3 -m prices tables export`")

    def test_live_store_has_no_synthetic_cards(self):
        s = Store.load(ROOT)
        self.assertFalse([e["id"] for e in s.entities.values() if "synthetic" in e["name"].lower()])
        self.assertFalse([p for p in s.files if p.startswith("data/") and "syn-" in p])

    def test_program_depends_on_the_standard_library_only(self):
        import ast
        names = getattr(sys, "stdlib_module_names", None)
        if names is None:
            self.skipTest("needs Python 3.10+ to list standard-library modules")
        for fn in sorted(os.listdir(os.path.join(ROOT, "prices"))):
            if not fn.endswith(".py"):
                continue
            tree = ast.parse(slurp(os.path.join(ROOT, "prices", fn)))
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                       [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
                for m in mods:
                    self.assertIn(m.split(".")[0], names, "%s imports %s, which is not in the standard library" % (fn, m))


if __name__ == "__main__":
    unittest.main()
