# Results — Fable commission: PRICES relational foundation

**Commission:** `docs/commissions/2026-11-14-fable-relational-foundation.md`
**Executed:** 2026-11-14 by Claude Fable 5.2 on branch `dev/fable-integration`. `main` was not touched.
**Status:** every item in the commission's acceptance list has a passing automated test or an observed command result below. Items not built are listed in section 6.

Everything demonstrated uses invented cards, banks, a network, people and sources (`fixtures/`). No real card, benefit or holding was added to the live knowledge base.

## 1. Baseline before any change

| | Observed |
|---|---|
| Commit | `f9c35e1c681798e3c7b6c2416ad9e891cf039f6c` (`dev/fable-integration`); `main` at `f8e1ca1` |
| `python3 -m unittest discover -s tests` | `Ran 94 tests` … `OK` |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` (the warning: Eric's Aeroplan 25K holding has no expiry date) |
| `python3 scripts/verify_export.py` | `TEST F: PASS` |
| Python | 3.13.18, standard library only |

## 2. Commits

| Commit | Content |
|---|---|
| `d03f6f2` | Checkpoint 1: schema, engine, lint and pipeline extensions; tables code. Original 94 tests passing |
| `2427070` | Checkpoint 2: synthetic fixture built through the pipeline; new tests; live `tables/` export |
| `b196a99` | Checkpoint 3: documentation, OP-10 card, maintenance demo, clean-checkout script |
| next commit | Checkpoint 4: this file, `STATUS.md`, `CONTINUATION.md`, one gating refinement with its test |

## 3. What was built

| Piece | Where |
|---|---|
| Architecture-fit analysis and decisions | `docs/RELATIONAL_TABLES.md` sections 1–2; `docs/DECISIONS.md` D-17 to D-23 |
| Seven card layers: card entity + six role references; kinds `organization`, `network_tier` | `prices/schema.json`, `prices/lint.py` |
| Network-tier baselines and card exclusions as non-deriving rule kinds `baseline`, `excludes` (+ `superseded_by`) | `prices/engine.py` (skipped), `prices/lint.py` (shape and inheritance blocks) |
| Card-specific evidence: `applies_to` on evidence, lint `CARD_SPECIFIC_EVIDENCE_REQUIRED` | `prices/lint.py` |
| Applicability report: `CONFIRMED / EXCLUDED / SUPERSEDED / PENDING_REVIEW / UNPROVEN` | `prices/cards.py`; `python3 -m prices cards` |
| CSV tables: deterministic export, staleness detection, validated all-or-nothing import | `prices/tables.py`; `python3 -m prices tables …`; `tables/` |
| New operations `revise_entity`, `revert_changeset`; `apply_many`; before-snapshots in `data/audit/previous/` | `prices/changes.py` |
| Research tasks for unproven card/benefit pairs | `prices/discovery.py`; `python3 -m prices discover applicability` |
| Synthetic fixture: 2 cards, 6 organizations, 1 tier, 5 benefits, 3 baselines, 5 card rows, 2 people | `fixtures/synthetic-cards-input/` (authored rows), `fixtures/synthetic_cards.py` (builder), `fixtures/synthetic-cards/` (result) |
| Junior-maintainer procedure | `docs/operations/OP-10-tables.md` |
| Repeatable maintenance run; clean-checkout check | `scripts/demo_card_maintenance.py`; `scripts/verify_clean_checkout.py` |

Authority: the JSON store remains the system of record. Field ownership and conflict behaviour: `docs/RELATIONAL_TABLES.md` sections 5 and 6.

## 4. Verification after the change

| Command | Observed |
|---|---|
| `python3 -W error -m unittest discover -s tests` | `Ran 144 tests` … `OK` (94 original, unmodified; 18 in `test_j_relational.py`; 32 in `test_k_tables.py`) |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` (same warning as baseline) |
| `python3 -m prices tables status` | `out of date with the store: no` / `unimported edits: no` |
| `python3 scripts/verify_clean_checkout.py` (at `b196a99`) | `CLEAN CHECKOUT: PASS` — `git clone` to an empty directory, minimal environment with proxies pointed at a dead port, tests, lint, tables status, Eric status, fixture rebuild, maintenance demo, checkout left unmodified |
| `python3 scripts/verify_export.py` | `TEST F: PASS` (374 files; now also rebuilds the fixture and runs the demo in the unpacked copy) |
| `python3 scripts/demo_card_maintenance.py` | `DEMO COMPLETE`; transcript in section 5 |
| `successor_test/harness.py setup` + `evaluate` on an untouched copy | 10 of 21, the documented baseline; harness still works with the changed pipeline |

**Backward compatibility, measured.** With the old code (`f9c35e1`) and the new code run on the same data, the full JSON output of `status` was byte-identical for `eric`, `synthetic-demo` and `synthetic-acquired` at 2026-11-14, 2027-03-15 and 2028-01-05 (9 comparisons). So were the Japan goal report and the `synthetic-acquired` timeline. `git diff f9c35e1 -- data profiles` and the six original test files plus `tests/util.py`: no differences.

## 5. Acceptance list

| Commission item | Result | Evidence |
|---|---|---|
| Baseline rules unchanged; backward compatibility | **Pass** | 94 original tests unmodified and passing; byte-identical engine output (above) |
| Synthetic card-level applicability | **Pass** | `test_positive_card_evidence_confirms`; `test_fixture_is_valid_and_shows_the_four_required_cases` |
| Network perk explicitly not inherited | **Pass** | `test_tier_baseline_gives_the_cardholder_nothing`; `test_a_tier_cannot_be_held_or_routed_through`; `test_absent_opt_out_is_not_proof`; `test_network_page_alone_cannot_confirm_a_card_benefit`; `test_pipeline_refuses_to_promote_without_card_evidence`; `test_network_page_cannot_get_a_tier_benefit_confirmed_for_a_card` |
| Exclusion and upgrade | **Pass** | `test_exclusion`; `test_upgrade_replaces_baseline_without_merging`; `test_grant_and_exclusion_cannot_both_stand` |
| Different holders, independent | **Pass** | `test_two_people_are_never_conflated`; fixture test (Alex 3 benefits, Blake none); `test_tables_carry_no_holder_column_and_import_never_touches_profiles` |
| Invalid and duplicate rows rejected, nothing partially applied | **Pass** | `TestRejection` (9 tests, 20 unsupported-edit cases in one of them): each asserts store digest, audit length and the maintainer's files are unchanged |
| Import idempotency | **Pass** | `test_export_is_deterministic_and_import_of_untouched_tables_does_nothing`; second import in maintenance test and demo prints `NOTHING TO DO` |
| Historical record preservation | **Pass** | `test_retire_a_benefit_and_keep_its_history`; `test_role_change_keeps_the_previous_value`; before-snapshot assertions; `test_revert_restores_the_previous_record_exactly` |
| Exported data not silently stale | **Pass** | `test_stale_tables_are_refused_not_merged`; `test_export_is_never_silently_stale`; `test_committed_tables_match_the_live_store` |
| Evidence-linked per-benefit updates and retires survive validation and lint | **Pass** | `TestMaintenance` (9 tests) |
| Offline, clean checkout, no model dependency | **Pass** | `verify_clean_checkout.py`; `test_program_depends_on_the_standard_library_only` |
| Maintenance procedure provided and run | **Pass, by the building model only** | `docs/operations/OP-10-tables.md`; transcript below. **Not run by a lower-capability model** |

Defects found by the new tests and fixed during the work: a linter crash on a malformed exclusion rule; a changeset-id collision when identical table edits were re-imported after an intervening change.

### Maintenance run (abridged transcript, `scripts/demo_card_maintenance.py`)

```
=== 1. Change one benefit and its evidence; give another an end date; record a newly evidenced benefit
$ python3 -m prices --root <copy> tables plan --author junior maintainer --date 2026-12-01
PLAN (nothing written)  3 changeset(s)
  add_candidate      card_benefits row kestrel.lounge-day-pass    cs-20261201-tbl-5c58dfd9-01-add-candidate
  revise_rule        card_benefits row voyager.phone-protection   cs-20261201-tbl-5c58dfd9-02-revise-rule
  revise_rule        card_benefits row voyager.travel-credit      cs-20261201-tbl-5c58dfd9-03-revise-rule
$ python3 -m prices --root <copy> tables import --author junior maintainer --date 2026-12-01
IMPORTED  3 changeset(s)
  DOWNSTREAM REVIEW NEEDED: no
  tables/ refreshed
  New benefit rows are CANDIDATES. They establish nothing until a reviewer promotes them.
$ python3 -m prices --root <copy> lint
lint: 0 error(s), 0 warning(s)
$ python3 -m prices --root <copy> tables import --author junior maintainer --date 2026-12-01
NOTHING TO DO  (tables match the store)

=== 2. A mistake: trying to flip applicability in place is refused, and nothing changes
REJECTED  (no record was changed)
  LOGIC_CHANGE: card_benefits row voyager.phone-protection: applicability cannot be changed on an existing row. Retire this row (_action = retire) and add a new row with a new id.

=== 3. Retire a benefit, keeping its history
IMPORTED  1 changeset(s)
  retire_rule        card_benefits row voyager.travel-credit      cs-20261215-tbl-6b9df976-01-retire-rule
  DOWNSTREAM REVIEW NEEDED: yes

BENEFIT APPLICABILITY held by synthetic-alex, as of 2026-12-15
      UNPROVEN       network_baseline Orbit Summit lounge day pass   -> for synthetic-alex: NOT_AVAILABLE
      CONFIRMED      network_baseline Orbit Summit phone protection   -> for synthetic-alex: ESTABLISHED
      SUPERSEDED     network_baseline Orbit Summit rental car cover (secondary)   -> for synthetic-alex: NOT_AVAILABLE
      CONFIRMED      card_specific    Northwind Voyager primary rental car cover   -> for synthetic-alex: ESTABLISHED
BENEFIT APPLICABILITY held by synthetic-blake, as of 2026-12-15
      PENDING_REVIEW network_baseline Orbit Summit lounge day pass   -> for synthetic-blake: NOT_AVAILABLE
      EXCLUDED       network_baseline Orbit Summit phone protection   -> for synthetic-blake: NOT_AVAILABLE
      UNPROVEN       network_baseline Orbit Summit rental car cover (secondary)   -> for synthetic-blake: NOT_AVAILABLE

card_benefits.csv after the task (id, applicability, state, valid_to):
  kestrel.lounge-day-pass            confirmed  candidate
  kestrel.phone-protection-excluded  excluded   verified
  voyager.phone-protection           confirmed  verified   2027-06-30
  voyager.primary-rental-cover       confirmed  verified
  voyager.rental-cover-superseded    excluded   verified
  voyager.travel-credit              confirmed  retired    2026-12-14
```

## 6. Not built

| Item | Why |
|---|---|
| Authorized-user, guest and companion sharing | Out of this increment by the commission. Two people are independent; nothing is shared. The gap is real and needs a design decision first |
| Proposal tabs 2 (underwriting/servicing), 5 (programs/status), 6 (portals), 7 (bridges) as tables | 5 and 7 already work through changesets and do not flatten safely into a row; 2 and 6 were out of scope |
| Earn rates and stacking arithmetic; UI; web discovery; real-card research; live offers; monitoring | Excluded by the commission |
| Dated snapshots of source documents | Not attempted. Sources remain URL + date + summary |
| Structured benefit terms (caps as numbers) | Terms are text; the program cannot compare them |
| Promotion from the tables | Deliberate: promotion is a reviewer's changeset |
| Three-way merge of stale tables | Deliberate: refused instead (D-18) |
| Google Sheets round trip | Not tested. Only CSV files were exercised, including a BOM + CRLF file |
| OP-10 executed by a lower-capability model | Not performed. Maintainability of this increment by weaker models is **unverified** |
| Real card roster | None loaded. The eleven names in Argon's proposal were not ingested |

## 7. Limits worth knowing before relying on this

- `applies_to` and `source_type` are labels typed by whoever records a source. Mislabel a network page as being about a card and the card-specific check passes. Reviewer promotion is the control, and it is procedural.
- Card benefits appear in `cards` and in the tables. They do not yet appear in `goal` reports, because benefits carry no goal tags through the tables.
- A baseline or exclusion past its `review_by` raises `STALE_RULE` in every profile's status, including people who do not hold the card.
- Spreadsheet programs may reformat dates; import rejects them and the maintainer must retype.

## 8. Suggested next commissions, in order

1. **Lower-model test of OP-10.** Add four card tasks to `successor_test/` on the synthetic fixture (change a benefit, add an exclusion, retire, and one that must be refused), run with the weakest model that will really maintain the tables. Cheapest way to learn whether the procedure holds before real data depends on it.
2. **Real roster, products only.** Eric confirms the card list; Argon researches roles and primary documents; rows enter through the tables as candidates; a reviewer promotes. Holdings stay separate (OP-07).
3. **Household sharing decision.** Decide how authorized-user and guest benefits are represented, then build and test it. Do this before loading benefits whose value depends on sharing.
4. **Read-only views for programs and bridges** (`view_programs.csv`, `view_bridges.csv`). Generated views are safe; authoring them in tables is not.
5. **Source snapshots**, if Bradley and Eric decide dated copies are worth storing.
6. **Reconcile the Session 1 discovery commission** with this design; `discover applicability` is the hook.

Not recommended yet: earn-stack arithmetic. It needs earn rates, portals and exclusions modelled first, and it is the place where a plausible wrong number does the most harm.
