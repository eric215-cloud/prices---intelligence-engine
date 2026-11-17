# PRICES status report — 2026-11-14

Foundation built 2026-11-12 by Claude Fable 5.2 (commissioning build). Relational foundation and earned benefits added 2026-11-14 on branch `dev/fable-integration`; Argon's Bilt Palladium and Chase Sapphire Reserve content (candidate-only) and cardholder elections added 2026-11-15 on branch `dev/argon-content-intake`; structured recurring credits (ENG-01) added 2026-11-15 on branch `dev/eng-01-recurring-credits` (none merged to `main`). This report separates what was observed from what is claimed.

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
| H after the safety correction (2026-11-17) | **Unresolved until reviewed** | The same report now lists 0 established and 0 conditional pathways: none of the rules behind them has a reviewer's classification. With the proposed classes applied in a copy: 1 established (ANA via Aeroplan); the JAL pathway stays unresolved (60-day account condition) |
| I Circular dependency integrity | **Pass** | `tests/test_c_i_evidence_cycles.py`, 11 tests: cycles, self-loops, acquire loops, mutual retention, contradictory conditions, conflicting records, exclusion cycles |

### Relational foundation (2026-11-14) — all demonstrated on invented cards only

| Test | Result | Evidence observed |
|---|---|---|
| J Card applicability | **Pass** | `tests/test_j_relational.py`, 18 tests: a network tier gives its cardholder nothing; a tier cannot be held or routed through; an absent opt-out proves nothing; a network page cannot confirm a card benefit; exclusion; upgrade; two people kept apart |
| K Tables | **Pass** | `tests/test_k_tables.py`, 32 tests: deterministic export; all-or-nothing import; 20 kinds of unsupported edit refused with nothing changed; stale tables refused; new rows quarantined; change, expire, retire and revert a benefit with history kept |
| Backward compatibility | **Pass** | The 94 original tests are unmodified and pass. Engine output for all three earlier profiles at three dates is byte-identical before and after |
| Clean checkout, offline | **Pass** | `scripts/verify_clean_checkout.py` |
| Maintenance procedure OP-10 | **Run by the building model and by tests only** | `scripts/demo_card_maintenance.py`. Lower-model execution: **untested** |

Full record: `docs/commissions/results/2026-11-14-fable-relational-foundation-RESULTS.md`.

### Earned benefits (2026-11-14) — all demonstrated on invented cards, people and figures only

| Test | Result | Evidence observed |
|---|---|---|
| L Earned-benefit semantics | **Pass** | `tests/test_l_earned.py`, 44 tests: an offer gives nothing; reaching a threshold gives eligibility, never possession; activation is a separate fact; one event, two expiries; scoping by person, account and year; a later reading never reaches back; unknown dates stay unknown; offer end vs personal expiry; two overlapping years; credit allowance / used / remaining; unconfirmed and conflicting records never established |
| M Earned-benefit pipeline | **Pass** | `tests/test_m_earned_pipeline.py`, 30 tests on `fixtures/synthetic-earned/`: the commission's scenario read off at a series of dates; owner attestation; 60+ invalid inputs refused with nothing changed; idempotency; corrections with history and revert; tables carry no personal facts; the `earned` report |
| Guarantees actually guarded | **Pass** | `scripts/mutation_check_earned.py`: 17 guarantees broken one at a time in a scratch copy; the tests notice all 17 |
| Backward compatibility | **Pass** | The 144 earlier tests are unmodified and pass. `scripts/compare_with_baseline.py`: 50 commands byte-identical against the commit before this work; live records, tables, earlier tests and the card fixture are the same files |
| Clean checkout, offline; export | **Pass** | `scripts/verify_clean_checkout.py`, `scripts/verify_export.py` |
| Maintenance procedure OP-11 | **Run by the building model and by tests only** | `scripts/demo_earned.py`. Lower-model execution: **untested** |

Full record: `docs/commissions/results/2026-11-14-fable-earned-entitlements-RESULTS.md`.

### Argon content intake and cardholder elections (2026-11-15)

| Test | Result | Evidence observed |
|---|---|---|
| Intake integrity | **Pass** | `scripts/verify_argon_intake.py`: manifest hashes match; all 246 Argon changesets re-apply through the pipeline with identical digests; store equals the package except two base audit records the package omitted (kept) |
| Boundaries | **Pass** | 10 active rules and `profiles/` byte-identical to the base; 113 proposed candidates, none promoted |
| N Cardholder elections | **Pass** | `tests/test_n_elections.py`, 36 tests: unknown, confirmed, conflicting, changing and withdrawn elections; the 2027 transition at each cardholder's own anniversary, unknown and February 29 anniversaries; the real Bilt definitions on a scratch copy with the candidates promoted there |
| Guarantees actually guarded | **Pass** | `scripts/mutation_check_elections.py`: 13 of 13 caught |
| No change for anyone else | **Pass** | `scripts/compare_with_baseline.py` against the intake commit: 49 commands byte-identical, 21 file sets unchanged, audit log append-only |
| Maintenance procedure OP-12 | **Run by the building model and by tests only** | `scripts/demo_elections.py`. Lower-model execution: **untested** |

Full record: `docs/commissions/results/2026-11-15-fable-argon-intake-bilt-elections-RESULTS.md`.

### Structured recurring credits, ENG-01 (2026-11-15) — demonstrated on invented cards, people and figures only

| Test | Result | Evidence observed |
|---|---|---|
| O Credit periods and reporting | **Pass** | `tests/test_o_credits.py`, 42 tests: calendar year / half / quarter / month and anniversary boundaries, February 29, multi-year periods, offer start and end, unstated terms stay unstated, published allowance is never a personal balance, elections still decide, period ends in review and timeline |
| P Credit authoring and personal records | **Pass** | `tests/test_p_credits_pipeline.py`, 31 tests on `fixtures/synthetic-credits/`: scenarios A-G with boundary dates; `set_credit_terms` (evidence, history, revert, candidates in place); `credits.csv` round trip and 17 invalid edits; period records, per-transaction cap, corrections; the `credits` report |
| Safeguards actually guarded | **Pass** | `scripts/mutation_check_credits.py`: 23 of 23 caught |
| No change for anyone else | **Pass** | `scripts/compare_with_baseline.py` against the commit before ENG-01: 49 commands byte-identical; `data/`, `profiles/`, tables and older fixtures unchanged apart from the new, empty `credits.csv` and the manifest that lists it |
| Candidate quarantine | **Pass** | 113 proposed candidates, none promoted, none edited; no live rule or candidate has a `credit` block (a test enforces this) |
| Maintenance procedure OP-13 | **Run by the building model and by tests only** | `scripts/demo_credits.py`. Lower-model execution: **untested** |

Full record: `docs/commissions/results/2026-11-15-fable-eng-01-recurring-credits-RESULTS.md`.

### Bilt election correction, ENG-02B (2026-11-15) — demonstrated on invented cardholders only

| Test | Result | Evidence observed |
|---|---|---|
| Q Corrected Bilt election model | **Pass** | `tests/test_q_bilt_election_correction.py`, 31 tests: the committed definitions run on a scratch copy with the five candidates promoted there, 20 invented cardholders, acceptance cases 1 to 8 with boundary days; anniversary windows; linked options in general; definition checks |
| ENG-02 tests preserved | **Pass, one assertion moved** | `tests/test_n_elections.py`, 36 tests. One date changed from 2027-06-01 to 2027-08-02: the published Card Anniversary Date of that invented account is not 2027-06-01 |
| Safeguards actually guarded | **Pass** | `scripts/mutation_check_elections.py`: 24 of 24 caught (13 from ENG-02, 11 new) |
| No change for anyone else | **Pass** | `scripts/compare_with_baseline.py` against the commit before ENG-02B: 49 commands byte-identical; in `data/` only the six election definitions and their audit records differ; `profiles/` and tables identical |
| Candidate quarantine | **Pass** | 113 proposed candidates, none promoted, none edited |
| Published terms confirmed by the content owner | **Not yet** | Engineering read the terms on 2026-11-15; Argon has not confirmed the six definitions. No named reviewer has checked them line by line |

Full record: `docs/commissions/results/2026-11-15-fable-eng-02b-bilt-election-correction-RESULTS.md`.

### Foundation viability test (2026-11-16) — real content, in a throwaway copy only; branch `exp/foundation-viability`

**Verdict: viable with specific architectural corrections.** Full assessment: `docs/VIABILITY_ASSESSMENT.md`. Reproduce: `python3 experiments/viability/run.py`.

| Test | Result | Evidence observed |
|---|---|---|
| Baseline on real content | **Defect found** | Promoted as they stand, real candidates told an invented 2024 cardholder that nine benefits with unchecked conditions were established, including the new-applicant welcome offer. 20 of 73 non-transfer candidates state such a condition |
| First capabilities | **Pass** | `unchecked` conditions never establish; `earnings` and `convert` calculate from published rates and ratios or say why not. `tests/test_r_viability_capabilities.py`, 23 tests |
| Batch 1: existing research | **Pass** | 24 checks on the Sapphire Reserve packet and the ten verified rules |
| Batch 2: new programmes, code frozen | **Entry passes; completeness does not** | 28 real records (Venture X, Capital One transfers, Hyatt tiers, United Premier): 0 code changes, 26 accepted as first written, 23 answer their main question; only 5 have every answer-changing term captured |
| Maintenance | **Defect found and corrected** | Changed terms were refused as duplicates, so the past could only be rewritten or erased. Successor rules now keep both; in-place revision and retirement still do not |
| Reviewed content | **None** | Batch 2 was read by engineering from extracts. Nothing was promoted in the project |

358 automated tests from earlier commissions still pass unchanged; 382 in all. Run: `python3 -m unittest discover -s tests`.

### Foundation safety correction (2026-11-17) — branch `dev/foundation-safety-correction`, from `exp/foundation-viability` at `c3b96a9`

**Established and unresolved eligibility are now told apart by a reviewer's recorded class for every restriction and open question; a missing class blocks.** Description: `docs/CONDITION_REVIEW.md`. Before and after on real content: `experiments/safety/results/BEFORE_AFTER.md`.

| Test | Result | Evidence observed |
|---|---|---|
| The known false positives | **Corrected** | United Silver 2027 on 6,100 PQP: ESTABLISHED before, UNRESOLVED now (reason shown: the open flight minimum). Sapphire Reserve welcome offer for a 2024 account: promotion as written is refused; once classed it is UNRESOLVED. `python3 experiments/safety/before_after.py` runs commit `c3b96a9` and this checkout side by side |
| Correct eligibility remains | **Pass** | United Silver 2026 (flight minimum checked by the rule), Amex points to the ANA award via Aeroplan, nine Capital One transfers, usage-only card benefits: all still ESTABLISHED or CALCULATED. A clear "no" stays NOT_AVAILABLE |
| Across kinds of content | **Pass** | `tests/test_t_safety.py`, 24 tests on invented data: card benefits, status by threshold, transfers, activation, spending thresholds, account eligibility; seven ways a review can fall short; the pipeline; history |
| Real-content regression | **Pass** | `experiments/viability/run.py`: 52 checks (46 before; the checks that recorded defects now assert the corrected answers) |
| Historical terms | **Corrected** | In-place change of a recorded term is refused unless declared a correction; retirement keeps the answers for earlier dates; dated successors as before |
| Safeguards actually guarded | **Pass** | `scripts/mutation_check_safety.py`: 25 of 25 caught |
| The project's records | **Untouched** | `data/`, `profiles/`, `tables/` byte-identical to `c3b96a9`; 113 candidates still proposed |
| The project's answers | **Changed on purpose** | The nine verified rules have no classification yet, so 38 derived answers across the three profiles (three dates each) moved from ESTABLISHED or CONDITIONAL to UNRESOLVED. None moved up. A proposal for a reviewer is in `experiments/safety/live_rules_proposal.json` (OP-14) |
| Existing tests | **8 of the 358 earlier tests have a changed expectation, each marked in the file** | Listed in the results record. None was weakened: each change replaces an expectation that encoded a defect (retirement erasing history; a new restriction establishing at once; live answers resting on unclassified text) or follows the rule that a correction is declared |

412 tests. Full record: `docs/commissions/results/2026-11-17-fable-foundation-safety-correction-RESULTS.md`.

### Consolidated foundation safety repair (2026-11-17) — branch `dev/foundation-safety-repair`, from `dev/foundation-safety-correction` at `22bca1a`

**The six further defects reproduced by Bradley and Astra are corrected; each is shown on `22bca1a` and now by `python3 experiments/safety/repair_before_after.py` (18 cases, every one as expected).** Mechanism: `docs/CONDITION_REVIEW.md` (sections 2 to 4).

| Defect | Result | Evidence observed |
|---|---|---|
| 1 "Enforced" accepted on presence of a leaf | **Corrected** | Claims are exact structured conditions that must hold on every path (OR, nested, thresholds); re-checked on every read. A-or-B and 1,000-vs-1 cases: ESTABLISHED before, refused and UNRESOLVED now |
| 2 Missing fact read as a negative fact | **Corrected** | "Not a member" with no record: ESTABLISHED before, UNRESOLVED now; ESTABLISHED only from the owner's recorded absence (new record type) |
| 3 Calculators interpreting eligibility themselves | **Corrected** | One question, `Result.rule_applies`, for status, earnings, transfers and credits. A-or-B transfer now calculated; figure and "not" requirements no longer ignored; a blocked rate or credit no longer used because another rule gives the same benefit. 150 random condition shapes: status and calculators agree on every one |
| 4 Date window read as activation | **Corrected** | Date claims cannot enforce an action; proposal entry for "Register by December 31, 2026" corrected |
| 5 Ending a holding erased its past | **Corrected** | Card held January to May: March answer kept (was NOT_AVAILABLE) |
| 6 Condition changes on rules that already answered | **Corrected** | First restriction on a past rule: declared correction or successor; removing the last reviewed restriction leaves a stale review that blocks |
| Existing protections | **Kept** | All 412 earlier tests pass; 6 have a changed expectation or input, each marked; experiment 52 of 52; the comparison with `c3b96a9` still holds |
| Mutation suite | **51 of 51 caught** | `scripts/mutation_check_safety.py` (25 before, 26 added) |
| Real profiles | **Unchanged** | Every report for every profile on three dates is identical to `22bca1a`; `data/`, `profiles/`, `tables/` untouched |

450 tests. Full record: `docs/commissions/results/2026-11-17-fable-foundation-safety-repair-RESULTS.md`.

## Capability status

### Complete
- Portable project: Python standard library only, JSON files, git history, zip export.
- Eligibility engine with four statuses, inspectable derivations, acquisition/retention semantics, time, flags.
- Whole-store validation and the changeset pipeline with 23 bounded operations (`end_holding` can now also withdraw a mistaken holding), all-or-nothing batches, impact reports, audit log and before-snapshots of every replaced record.
- Discovery planners (forward, backward, bridge, exploratory), coverage ledger, candidate quarantine, novelty check.
- Goal reports in five separated sections.
- Maintainer guide, thirteen operation cards, schema, decision record, successor-test harness.
- Card architecture: a card's six parties (co-brand partner, program manager, issuer, capital provider, network, network tier) recorded as descriptive roles the engine never reads.
- Applicability: network-tier baselines and card exclusions recorded as sourced statements that derive nothing; a tier benefit applies to a card only on verified, card-specific evidence. Report: `python3 -m prices cards`.
- CSV tables (`tables/`): generated view plus validated, all-or-nothing authoring input. The JSON store remains the system of record.
- Earned benefits: a public `earns` rule, a person's dated progress per account and year, and the benefit as it actually sits on the account are three separate records. Reaching a threshold gives eligibility only; possession needs an owner-confirmed account record with its own dates. Credits keep allowance, used and remaining apart. Report: `python3 -m prices earned --profile <p>`. Design: `docs/EARNED_ENTITLEMENTS.md`.
- A `metric` observed after the query date is no longer used for that date (it reads as unknown).
- Cardholder elections: mutually exclusive card options are named by `election` entities that govern rules; a person's choice is an owner-confirmed holding of one option; nothing is applied without a recorded election except a published default; the Bilt 2027 transition follows each account's own anniversary. Design: `docs/ELECTIONS.md`.

### Partial
- **Knowledge base: 10 active rules, 162 entities, 24 evidence records, 113 proposed candidates.** The 2026-11-15 intake added Argon's Bilt Palladium and Chase Sapphire Reserve content (cards, programs, currencies, statuses, 26 Bilt and 14 Chase transfer candidates, 5 Chase `earns` candidates, card-benefit candidates) and four Bilt election definitions. All new rules are proposed candidates: none can establish anything until a reviewer promotes it.
- **Evidence quality varies.** 4 rules rest on an official source; 6 rest on two independent secondary sources. Two official pages (Hyatt offer, JAL Crystal) were read only through search-engine excerpts because the sites refuse automated fetching; this is noted on those evidence records.
- **Every rule was promoted by the build itself**, which is on the reviewer list. No person has checked them.
- **Economics.** Goal reports carry sourced notes on cost, time and risk. Numeric point prices are absent because sources conflicted. Value-per-point arithmetic exists and is tested but has no live data to run on.
- **Goal matching is keyword-to-tag.** Goals outside the small tag vocabulary return "no tag matched" until a reviewer adds tags.
- **Bridge and exploratory discovery** are implemented and unit-tested but were not exercised with real research.
- **Reviewer and owner controls are procedural.** The program checks the name on an attestation; it cannot check who typed it.
- **Recurring credits: the machinery is in place; no real credit has structured terms.** Argon's credit candidates still carry their mechanics as prose. Statement-cycle card years, per-grant expiry (Bilt Cash), activation requirements, shared credits and carried-over amounts are not modelled (`docs/RECURRING_CREDITS.md` section 6). A person's balance exists only where the owner recorded a period; nothing is created or assumed automatically.
- **Card data: candidate-only.** Bilt Palladium and Chase Sapphire Reserve, with their organizations and network tiers, are in the knowledge base and tables as entities and proposed candidates. Transfer ratios are deliberately absent (Argon `Q-BILT-004`, `Q-CSR-001`). Engineering did not review this content.
- **Card-specific evidence is a label** (`applies_to`) typed by whoever records the source. Reviewer promotion is the control.
- **Tables cover cards, parties, benefits, sources, tier baselines and card benefits.** Programs, status tiers, bridges, portals and underwriting rules have no table; they are maintained through changesets as before.
- **Card benefits are not in goal reports** (no goal tags reach them through the tables).
- **Earned benefits: none real.** No real earn rule, progress figure, achievement, activation, balance or expiry is recorded for anyone. The live knowledge base has no `earns` rule and no profile has a qualification or entitlement record (a test enforces this).
- **Earned benefits cover calendar-year thresholds on one card account.** Cardmember-year and rolling periods, refunds and clawbacks, tiered thresholds, spend combined across cards or people, and any form of sharing are not modelled. Queries are valid-time, not record-time. Full list: `docs/EARNED_ENTITLEMENTS.md` section 8.
- **Dates and balances on an earned benefit are what the owner reports.** The program checks they are possible and flags disagreement with the rule's stated term; it cannot check them against an account.

### Blocked
- **Remaining Eric holdings.** Two owner-confirmed real statuses (Marriott Titanium, Aeroplan 25K) were imported November 12. The rest of Eric's ecosystem remains to be reconciled and loaded; a two-record profile is not complete.
- **Persistence between sessions.** The complete project and subsequent audited changes are preserved in Eric's private GitHub repository; the original exported ZIP remains a separate baseline.
- **Live award availability and targeted offers.** Not obtainable without logged-in sessions, which the system must not hold.

### Untested
- Maintenance by models weaker than Claude Haiku 5.5, and repeated runs for reliability.
- **OP-10 (table maintenance) by any model other than the builder.**
- **OP-11 (earned benefits) by any model other than the builder.**
- **OP-12 (card elections) by any model other than the builder.**
- **OP-13 (recurring credits) by any model other than the builder.**
- Google Sheets as the editor for the CSV files. Only plain CSV, including a BOM + CRLF variant, was exercised.
- Discovery research performed by a weaker model.
- Behaviour at scale (hundreds of rules). Evaluation is simple iteration; expected fine, not measured.
- Windows. Paths use forward slashes internally and `os.path` for files; not run there.

## Known limitations
- Rule logic is limited to `holds`, `metric >=`, `all`, `any`, `not holds`. No arithmetic, no counting ("any 2 of 3"), no per-person household logic.
- Household sharing (authorized user, guest, companion) is not modelled. Two people are independent profiles and nothing is shared between them.
- Benefit terms are text. Caps and limits cannot be compared by the program. No earn rates, no stacking arithmetic.
- Table edits must be imported in the same sitting as the export; if the store changes in between, the import is refused and the edits must be redone.
- One currency balance is not checked against a price: "established capability" means the route exists, not that the balance suffices.
- Evidence is a summary plus URL. Pages are not archived, so a changed page cannot be compared with what was read.
- `vocab.json` is edited directly by reviewers, outside the changeset pipeline.
- A stale verified rule keeps applying (flagged). See decision D-08.
- The successor harness was corrected once after seeing a result. Both evaluations are kept.

- A reviewer's class for a restriction or open question is a judgement; the engine records it and cannot check it. Blocked benefits stay unresolved until the condition is modelled (account age, primary cardholder, new applicant and the like are not recorded anywhere).

## Recurring costs
None are built in. No subscription, hosting or API is required to run, test, query or validate. The only ongoing cost is research: re-verifying rules before `review_by` and running discovery passes, which need a model with web search or a person's time. With 10 rules that is minutes per quarter. It grows in proportion to the number of rules kept, which is a reason to keep only rules connected to real holdings.

## Open items a person should decide
0. **(Safety correction)** A promotion reviewer to classify the 27 restrictions and open questions on the nine verified rules (OP-14; proposal ready). Until then nothing is established through them.
1. Spot-check the 10 rules, then remove "Commissioning build" from `promotion_reviewers` in `data/kb/vocab.json`.
2. Reconcile and record the remaining holdings in `profiles/eric/` through owner attestations (OP-07).
3. Choose where the repository lives.
4. Decide on candidate `c-united-silver-via-marriott-top-tier` (secondary sources only) and `c-ana-business-award-via-ana-miles` (one source).
5. Review `dev/fable-integration` and decide whether to merge it to `main`.
6. Confirm the expiry date of Eric's Aeroplan 25K. Without it the holding cannot be tracked, and after Marriott Titanium's recorded expiry (2027-01-31) the engine will report it as unresolved.
7. Decide how household sharing should be represented before loading benefits whose value depends on it.
8. Argon to confirm the four Bilt election definitions, in particular whether the legacy credits and the Flex housing option are one election or two (modelled as two), and what applies to accounts opened in 2027 before their first anniversary.
9. Decide (Argon, content) which real earned-benefit rules to author first, and which period types they need. Anything other than a calendar year needs an engineering step before it can be loaded.
10. Argon to enter structured terms for the credit candidates that fit (`tables/credits.csv`; candidates are amended in place and stay candidates), and to say which do not fit.
11. Before any real earned benefit, election, credit balance or account opening date is recorded for Eric or Todd: the owner supplies each figure, date and balance. None has been entered or inferred.
