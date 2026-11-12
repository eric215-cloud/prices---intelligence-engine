# PRICES status report — 2026-11-12

Built in one session by Claude Fable 5.2 (commissioning build). This report separates what was observed from what is claimed.

## Acceptance demonstrations

| Test | Result | Evidence observed |
|---|---|---|
| A Conditional eligibility | **Pass** | `tests/test_a_conditional.py`, 14 tests: direct, conjunctive, alternative, nested, 60-step chain, actions, acquire vs have, thresholds, exclusions |
| B Temporal integrity | **Pass** | `tests/test_b_temporal.py`, 14 tests. The Titanium → Aeroplan → Hyatt case under all three retention modes, with renamed entities to show nothing is hardcoded. Also runs on the real rules (`test_illustrative_case_on_real_rules`) |
| C Evidence integrity | **Pass** | `tests/test_c_i_evidence_cycles.py`, 9 tests: unverified rules, unconfirmed holdings, candidates and weak evidence cannot establish anything |
| D Genuine discovery | **Pass, limited scope** | One relationship not in the brief, found by the planner's own question, verified against the official page, preserved in `data/discovery_runs/`. Plus one further hop found by frontier expansion. Two cells investigated out of 13 then open. This is a demonstration, not coverage |
| E Maintenance | **Pass** | `tests/test_e_maintenance.py`, 22 tests. Also happened for real: the pipeline rejected one of the build's own changesets (audit log, `cs-20261112-017`) |
| F Portability | **Pass** | `scripts/verify_export.py`: export, unpack to an empty directory with a clean environment, run all tests, lint, status, goal and harness setup there |
| G Lower-model operation | **Pass on one run of one model; otherwise unverified** | Claude Haiku 5.5, 4 tasks, 21/21 objective checks after one harness correction (20/21 before). Details and caveats in `successor_test/README.md`. Models weaker than this tier: **untested** |
| H Practical query | **Pass on synthetic data** | Japan business-class report: 2 established capabilities, 1 conditional pathway, 1 unresolved lead, 3 external research tasks, 0 promotions, 0 availability. No prices or availability invented |
| I Circular dependency integrity | **Pass** | `tests/test_c_i_evidence_cycles.py`, 11 tests: cycles, self-loops, acquire loops, mutual retention, contradictory conditions, conflicting records, exclusion cycles |

94 automated tests pass. Run: `python3 -m unittest discover -s tests`.

## Capability status

### Complete
- Portable project: Python standard library only, JSON files, git history, zip export.
- Eligibility engine with four statuses, inspectable derivations, acquisition/retention semantics, time, flags.
- Whole-store validation and the changeset pipeline with 15 bounded operations, impact reports and audit log.
- Discovery planners (forward, backward, bridge, exploratory), coverage ledger, candidate quarantine, novelty check.
- Goal reports in five separated sections.
- Maintainer guide, nine operation cards, schema, decision record, successor-test harness.

### Partial
- **Knowledge base: 10 rules, 23 entities, 16 evidence records.** Enough to exercise the software. It does not describe the loyalty landscape.
- **Evidence quality varies.** 4 rules rest on an official source; 6 rest on two independent secondary sources. Two official pages (Hyatt offer, JAL Crystal) were read only through search-engine excerpts because the sites refuse automated fetching; this is noted on those evidence records.
- **Every rule was promoted by the build itself**, which is on the reviewer list. No person has checked them.
- **Economics.** Goal reports carry sourced notes on cost, time and risk. Numeric point prices are absent because sources conflicted. Value-per-point arithmetic exists and is tested but has no live data to run on.
- **Goal matching is keyword-to-tag.** Goals outside the small tag vocabulary return "no tag matched" until a reviewer adds tags.
- **Bridge and exploratory discovery** are implemented and unit-tested but were not exercised with real research.
- **Reviewer and owner controls are procedural.** The program checks the name on an attestation; it cannot check who typed it.

### Blocked
- **Remaining Eric holdings.** Two owner-confirmed real statuses (Marriott Titanium, Aeroplan 25K) were imported November 12. The rest of Eric's ecosystem remains to be reconciled and loaded; a two-record profile is not complete.
- **Persistence between sessions.** The complete project and subsequent audited changes are preserved in Eric's private GitHub repository; the original exported ZIP remains a separate baseline.
- **Live award availability and targeted offers.** Not obtainable without logged-in sessions, which the system must not hold.

### Untested
- Maintenance by models weaker than Claude Haiku 5.5, and repeated runs for reliability.
- Discovery research performed by a weaker model.
- Behaviour at scale (hundreds of rules). Evaluation is simple iteration; expected fine, not measured.
- Windows. Paths use forward slashes internally and `os.path` for files; not run there.

## Known limitations
- Rule logic is limited to `holds`, `metric >=`, `all`, `any`, `not holds`. No arithmetic, no counting ("any 2 of 3"), no per-person household logic.
- One currency balance is not checked against a price: "established capability" means the route exists, not that the balance suffices.
- Evidence is a summary plus URL. Pages are not archived, so a changed page cannot be compared with what was read.
- `vocab.json` is edited directly by reviewers, outside the changeset pipeline.
- A stale verified rule keeps applying (flagged). See decision D-08.
- The successor harness was corrected once after seeing a result. Both evaluations are kept.

## Recurring costs
None are built in. No subscription, hosting or API is required to run, test, query or validate. The only ongoing cost is research: re-verifying rules before `review_by` and running discovery passes, which need a model with web search or a person's time. With 10 rules that is minutes per quarter. It grows in proportion to the number of rules kept, which is a reason to keep only rules connected to real holdings.

## Open items a person should decide
1. Spot-check the 10 rules, then remove "Commissioning build" from `promotion_reviewers` in `data/kb/vocab.json`.
2. Reconcile and record the remaining holdings in `profiles/eric/` through owner attestations (OP-07).
3. Choose where the repository lives.
4. Decide on candidate `c-united-silver-via-marriott-top-tier` (secondary sources only) and `c-ana-business-award-via-ana-miles` (one source).
