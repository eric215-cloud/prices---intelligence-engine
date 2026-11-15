# Results — Fable commission: earned benefits, achievement cycles and personal validity

**Commission:** `docs/commissions/2026-11-14-fable-earned-entitlements.md`
**Executed:** 2026-11-14 by Claude Fable 5.2 on branch `dev/fable-integration`, starting from `6eb9ec9580ebede55add6c9ff10474c911fa2616`. `main` and the two research branches were not touched.
**Status:** every case in the commission's acceptance scenario has a passing automated test and an observed command result below. Nothing on the required list is unfinished. What was deliberately not built is in section 7; the judgment calls a coordinator should look at are in section 6.

Everything demonstrated uses an invented card, invented benefits, invented people and invented figures (`fixtures/synthetic-earned/`). No real earn rule, spending figure, achievement, activation date, balance or expiry was recorded for anyone. Michaela's research was not read into the knowledge base. A test (`test_no_earned_facts_or_earn_rules_exist_in_the_live_data`) fails if the live data ever gains an `earns` rule or a personal earned record without that test being changed deliberately.

## 1. Baseline before any change

| | Observed at `6eb9ec9` |
|---|---|
| `python3 -m unittest discover -s tests` | `Ran 144 tests` … `OK` |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` (Eric's Aeroplan 25K holding has no expiry date) |
| Reference outputs | 16 command outputs saved before the first edit; later widened to the 50 commands in `scripts/compare_with_baseline.py`, which re-creates the baseline from git on every run |
| Python | 3.13, standard library only |

## 2. Commits

| Commit | Content |
|---|---|
| `93ece37` | Checkpoint 1: schema, storage, `prices/earned.py`, engine / lint / changeset extensions. 144 existing tests passing |
| `2fccd03` | Checkpoint 2: `earned` report command, fixture builder, `tests/test_l_earned.py`. (Its message says 56 tests; the correct count is 44) |
| `fc0b4d5` | Checkpoint 3: committed fixture, `tests/test_m_earned_pipeline.py`, mutation check |
| `29fd419` | Checkpoint 4: eligibility kept separate from account records (see 6.3); demo; baseline comparison |
| `ab4f4e0` | Checkpoint 5: OP-11 card, design document, decisions D-24 to D-33, schema, status. Clean-checkout verification run on this commit |
| next commit | This file and a cosmetic change to `scripts/verify_export.py` |

25 files changed outside the fixture, about 3,100 lines added, 31 changed. No file under `data/`, `profiles/` or `tables/` changed. No existing test file changed.

## 3. What was built

| Piece | Where |
|---|---|
| Public rule kind `earns` with an `earn` block (measure, calendar-year period, threshold, term, activation, optional allowance) | `prices/schema.json`, `prices/lint.py` |
| Personal progress: dated, append-only readings per person, account, measure and year | `profiles/<p>/qualifications/` via `record_progress`, `correct_entry` |
| Personal entitlement: the benefit as it sits on the account, own start and expiry, allowance, uses | `profiles/<p>/entitlements/` via `record_entitlement`, `revise_entitlement`, `record_usage`, `correct_entry` |
| Evaluation: achievement from readings on a date; state of each record; credit arithmetic; base facts for the engine | `prices/earned.py` (447 lines), `prices/engine.py` (+25) |
| Report per person, account, qualifying year, benefit: PUBLIC RULE / ACHIEVEMENT / ENTITLEMENT / WHOLE PERSON, with `--detail` and `--json` | `python3 -m prices earned` |
| Existing commands made aware: `status` section, `explain` chain, `timeline` boundaries, pipeline impact report | `prices/cli.py`, `prices/review.py` |
| Fix: a `metric` observed after the query date is no longer used for that date | `prices/engine.py` (D-28) |
| Synthetic scenario built only through changesets | `fixtures/synthetic_earned.py` → `fixtures/synthetic-earned/` |
| Maintenance procedure | `docs/operations/OP-11-earned-benefits.md` |
| Design, decisions, schema | `docs/EARNED_ENTITLEMENTS.md`, `docs/DECISIONS.md` D-24..D-33, `docs/SCHEMA.md` |
| Before/after demonstration | `scripts/demo_earned.py` |
| Proof the guarantees are guarded | `scripts/mutation_check_earned.py` |
| Proof nothing else moved | `scripts/compare_with_baseline.py` |

The three layers and what follows from each:

```
public rule on offer                           -> nothing personal
readings at or above the threshold             -> ELIGIBLE  (can_get ESTABLISHED; have CONDITIONAL)
confirmed entitlement record, inside its dates -> HELD      (have ESTABLISHED)
nothing recorded                               -> nothing derived
```

## 4. Verification after the change

| Command | Observed |
|---|---|
| `python3 -W error -m unittest discover -s tests` | `Ran 218 tests` … `OK` (144 unchanged + 44 + 30) |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` (same warning as the baseline) |
| `python3 -m prices --root fixtures/synthetic-earned lint` | `lint: 0 error(s), 0 warning(s)` |
| `python3 -m prices tables status` | `out of date with the store: no` / `unimported edits: no` |
| `python3 scripts/compare_with_baseline.py` | `50 commands compared, 16 file sets compared, 0 difference(s)` / `BASELINE COMPARISON: PASS` |
| `python3 scripts/mutation_check_earned.py` | `17 of 17 mutations caught` |
| `python3 scripts/demo_earned.py` | exit 0, `DEMO COMPLETE`; both "identical before and after: yes" lines |
| `python3 scripts/verify_export.py` | 15 steps `ok` (export, unpack, tests, lint, reports, both fixtures rebuilt and compared, both demos, mutation check), `TEST F: PASS` |
| `python3 scripts/verify_clean_checkout.py` (on `ab4f4e0`) | 14 steps `ok`, checkout unmodified, `CLEAN CHECKOUT: PASS` |
| `python3 successor_test/harness.py setup` + `evaluate` on an untouched copy | `10 of 21 checks passed`, as before (harness unchanged) |

**Byte-identical where no new personal facts exist.** `compare_with_baseline.py` unpacks commit `6eb9ec9` with `git archive`, runs the old program on the old files and this program on these files, and compares raw output: `lint`, `cards`, `tables status`, `audit`, and for each of `eric`, `synthetic-acquired`, `synthetic-demo`: `status` (JSON and text) at three dates, `timeline`, `review`, `cards`, `goal`, two `discover` modes; plus `status`, `cards`, `timeline` for both people in `fixtures/synthetic-cards`. All 50 identical. It also hashes `data/`, `profiles/`, `tables/`, the card fixture, `tests/util.py`, the nine earlier test files and `successor_test/`: all the same files.

**Mutation check.** Each of 17 guarantees is broken, one at a time, in a scratch copy, and the two new test files are run against it. All 17 are noticed: legacy metric ignoring its date; threshold giving possession; a later reading reaching back; an undated reading counted from January 1; personal expiry ignored; entitlement active before its start; unknown expiry persisting; unknown start assumed; later use counted earlier; unconfirmed use counted as used; unconfirmed entitlement established; unconfirmed reading counted; offer end revoking an existing entitlement; a maintainer confirming; a duplicate reading accepted; an `earns` rule evaluated as an ordinary rule; cycles merged.

## 5. Acceptance scenario

The invented rule: 75,000 units on the Northwind Voyager card in one calendar year. Four things on offer: a status (to the end of February two years later), a companion fare (to December 31 of the following year; offer ends with qualifying year 2026), a suite award (same term; needs activation), a 300 credit (same term; consumable). Tests are in `tests/test_l_earned.py` (L, in-memory) and `tests/test_m_earned_pipeline.py` (M, on the fixture).

| Commission case | Demonstrated by | Observed |
|---|---|---|
| Threshold checked against a scoped account metric, not lifetime | L `test_progress_is_scoped_to_the_account_not_the_person`, `..._to_the_cycle`; M `test_progress` | 40,000 + 40,000 on two accounts is not eligible; 2026's 91,250 leaves 2027 `BELOW`; a reading on another person's account is `UNKNOWN_ACCOUNT` |
| A holder below | L `test_holder_below_...`; M `test_holder_who_did_not_qualify_casey` | Casey 2026-09-15: `BELOW` / `NOT_EARNED` / `NOT_AVAILABLE`, no flags |
| A holder achieving | M `test_holder_who_achieves_it_alex_2026` | Alex: below (June 15) → unknown (July 15) → eligible (Oct 31) → held (Nov 8) |
| A second holder who did not qualify | M `test_holder_who_did_not_qualify_casey` | Casey final 61,300: `NOT_QUALIFIED`; same card and year as Alex, nothing rubs off |
| One event, status into a later February, another benefit ending the preceding December | L `test_one_qualifying_event_two_benefits_two_expiries`; M Alex table | 2027-12-31 both held; 2028-01-01 fare `NOT_AVAILABLE`, status `ESTABLISHED`; 2028-03-01 status ends (without a 2027 record) |
| Activation is a distinct step | L `test_activation_is_a_separate_personal_fact`; M Alex table | Award `ACTIVATION_REQUIRED`, `have` CONDITIONAL needing `ACQUIRE` + `DO Activate…` from Oct 31 until the recorded activation on 2027-01-15 |
| Credit: allowance, consumed, remaining not conflated | L `TestCredit` (5 tests); M `test_credit_allowance_used_and_remaining` | 300 / 0 / 300 → 300 / 120 / 180 → 300 / 200 / 100; with 60 unconfirmed: "remaining 100 (at least 40)"; allowance on file still 300 |
| Second qualifying year, independent, overlapping | L `TestCycles` (3 tests); M `test_second_year_is_independent_and_overlaps_alex_2027` | 2027-12-01: status records for 2026 and 2027 both `ACTIVE`, listed apart; credits 100 and 300, never 400; 2027 award needs its own activation; status continues to 2029-02-28 on the 2027 record alone |
| Offer validity is not personal expiration | L `test_offer_validity_is_not_personal_expiry`, `test_the_end_of_the_qualifying_year_does_not_end_the_benefit`, `test_personal_expiry_ends_it_and_says_so` | Fare offer ends 2026-12-31; Alex's 2026 fare still held 2027-09-01 and ends on its own date; retiring or un-verifying the rule does not revoke it; 2027 spend earns no fare (`NOT_OFFERED`) |
| Query before an observation never uses the later fact | L `TestTime` (11 tests); mutation "later reading reaches back" | Reading dated Oct 31 queried Mar 1: `UNCERTAIN`, `can_get` UNRESOLVED, never ESTABLISHED. Legacy metric dated June 30 queried June 29: UNRESOLVED (was ESTABLISHED before this work) |
| Unknown achievement dates stay unknown | L `test_year_only_attestation_keeps_its_date_unknown`; M `test_year_only_attestation_and_unknown_start_date_devon` | Devon: `observed_on` and `effective_from` are the word `unknown` on file; unresolved during 2026; achieved once 2026 is over with "date unknown"; status UNRESOLVED until the day Devon confirmed seeing it |
| Unrecorded, unconfirmed or conflicting facts never promoted | L `TestUnrecordedUnconfirmedConflicting` (9 tests); M `TestAttestation` (3 tests) | Each yields UNRESOLVED with a named flag; a maintainer's or another person's attestation is refused; a typed-in `confirmed_by` is discarded |
| Invalid input | M `TestInvalidInput` (6 tests) | 60+ malformed changesets, each rejected with a specific code; store digest, file list unchanged; attempt logged |
| Idempotency | M `TestIdempotency` (3 tests) | Same changeset twice: `DUPLICATE_CHANGESET`. Same fact under a new id: `DUPLICATE_READING` / `DUPLICATE_USAGE` / `DUPLICATE_INSTANCE`. A failing batch writes nothing |
| Corrections and history | M `TestCorrectionsAndHistory` (4 tests) | Old reading kept as `superseded` with `superseded_by`; before-snapshot holds the prior record; `revert_changeset` restores it byte for byte; withdraw and re-enter works |
| No import of personal holdings from product tables | M `test_tables_carry_no_personal_earned_facts_and_import_creates_none`, `test_personal_ops_are_the_only_way_in` | No table column or cell carries a personal earned fact; a table import leaves earn rules and personal records untouched; `set_holding` of the card creates no progress and no entitlement |
| Regression | 144 earlier tests; L `TestNoPersonalFactsNoChange`; M `test_people_without_earned_records_are_unaffected`; `compare_with_baseline.py` | Section 4 |

### Report (abridged, `python3 -m prices --root fixtures/synthetic-earned earned --profile synthetic-alex --as-of 2026-12-20 --cycle 2026`)

```
EARNED BENEFITS  profile=synthetic-alex  owner=Alex (synthetic)  as-of=2026-12-20  [SYNTHETIC DATA]
ACCOUNT h-card-northwind-voyager  Northwind Voyager (synthetic)  [confirmed, held on this date]
  QUALIFYING YEAR 2026  (2026-01-01 to 2026-12-31)   measure voyager.qualifying-spend
    progress on file  76,900 units as of 2026-10-31  (reading r-2026-10, 50 days before this date)

    Orbit Concierge status (synthetic)  [status.orbit-concierge]
      PUBLIC RULE   voyager.earn-concierge-status (verified): 75,000 units on voyager.qualifying-spend in one calendar year; lasts through the last day of February 2 years after the qualifying year (for this cycle: 2028-02-29); activation automatic
                    evidence: ev-syn-voyager-milestones
      ACHIEVEMENT   ACHIEVED - at or above the threshold on 2026-10-31 (reading r-2026-10). The day the threshold was crossed is not recorded
      ENTITLEMENT   ACTIVE
                    record e-2026-concierge-status: ACTIVE  2026-11-08 to 2028-02-29  (confirmed by Alex (synthetic) on 2026-11-14)
      WHOLE PERSON  ESTABLISHED on this date across all of this person's accounts and qualifying years (from entitlement e-2026-concierge-status)

    Northwind Voyager milestone travel credit (synthetic)  [benefit.voyager.milestone-credit]
      ...
                    record e-2026-milestone-credit: ACTIVE  2026-11-08 to 2027-12-31  (confirmed by Alex (synthetic) on 2026-11-14)
                      credit: allowance 300 units; used 120 (confirmed); remaining 180

    Northwind Voyager suite night award (synthetic)  [benefit.voyager.suite-award]
      ...
      ACHIEVEMENT   ACHIEVED - at or above the threshold on 2026-10-31 (reading r-2026-10). ...
      ENTITLEMENT   ACTIVATION_REQUIRED - eligible; the separate activation step had not been done on this date (a record shows it taking effect 2027-01-15)
      WHOLE PERSON  CONDITIONAL on this date across all of this person's accounts and qualifying years (from rule voyager.earn-suite-award)

Only ENTITLEMENT = ACTIVE means the benefit can be used on this date. ACHIEVED means eligible, not held.
```

The year-end figure (91,250, dated December 31) does not appear in this December 20 report.

### Maintenance run (abridged, `python3 scripts/demo_earned.py`)

Casey, who missed the threshold in 2026, has her 2027 recorded one changeset file at a time with `python3 -m prices apply`.

```
=== 0. BEFORE
      ACHIEVEMENT   NOT_RECORDED - no progress recorded for this cycle
      ENTITLEMENT   NOT_EARNED - no progress recorded for this cycle

=== 1. Record progress that is still below the threshold
APPLIED  cs-20270905-demo-01-record-progress
      ACHIEVEMENT   BELOW - below the threshold as of the latest reading (2027-08-31, 5 days before this query date); later progress is not recorded

=== 2. Four mistakes. Each is refused and no record changes
REJECTED  OWNER_ATTESTATION_REQUIRED: attestation must be by the profile owner 'Casey (synthetic)', not 'junior maintainer'
REJECTED  FUTURE_DATE: reading.observed_on (2027-12-15) is after the changeset date 2027-11-03
REJECTED  DUPLICATE_READING: reading r-2027-08 already records 52000 on 2027-08-31
REJECTED  MISSING_DATA: entitlement.effective_from is required. If it is not known, write the word unknown; do not leave it out and do not copy the rule's general term

=== 3. Record the figure that reaches the threshold: Casey becomes ELIGIBLE. Nothing is held yet
APPLIED  cs-20271103-demo-06-record-progress
    can_get:status.orbit-concierge: NOT_AVAILABLE -> ESTABLISHED
    have:status.orbit-concierge: NOT_AVAILABLE -> CONDITIONAL
      ENTITLEMENT   EARNED_NOT_CONFIRMED - eligible; not yet confirmed as present on the account
$ explain --as-of 2027-11-03 status.orbit-concierge   ->  CONDITIONAL   needs: ACQUIRE Orbit Concierge status (synthetic)
$ explain --as-of 2027-10-15 status.orbit-concierge   ->  UNRESOLVED    needs: ... CONFIRM: qualification ... is not established: UNCERTAIN
$ explain --as-of 2027-08-15 status.orbit-concierge   ->  NOT_AVAILABLE

=== 4. Record what is actually on the account
APPLIED  cs-20271112-demo-07-record-entitlement
    have:status.orbit-concierge: CONDITIONAL -> ESTABLISHED
      ENTITLEMENT   ACTIVATION_REQUIRED - eligible; the separate activation step is not recorded as done      (the suite award)

=== 5. Record a use of the credit
                      credit: allowance 300 units; used 140 (confirmed); remaining 160

=== 6. A correction: the October figure was misread
APPLIED  cs-20271210-demo-10-correct-entry
    [review] QUALIFICATION_NOT_RECORDED e-2027-concierge-status
  DOWNSTREAM REVIEW NEEDED: yes
      reading r-2027-10          79,400 exact    observed 2027-10-31 superseded    -> r-2027-10b  [October statement]
      reading r-2027-10b         74,400 exact    observed 2027-10-31 confirmed   by Casey (synthetic) on 2027-12-10  [October statement, re-read]

=== 7. The year-end figure settles it
    progress on file  88,000 units as of 2027-12-31, final
      ACHIEVEMENT   ACHIEVED - at or above the threshold on 2027-12-31 (reading r-2027-final). ...

=== 8. AFTER: what the calendar does next, with no further input
2029-01-01
   have:benefit.voyager.milestone-credit: ESTABLISHED -> NOT_AVAILABLE
   [review] CREDIT_LAPSED_UNUSED e-2027-milestone-credit: ... lapsed with 160 units unused
2029-03-01
   have:status.orbit-concierge: ESTABLISHED -> NOT_AVAILABLE
   [review] EXPIRED_ENTITLEMENT e-2027-concierge-status: ... expired on 2029-02-28 and no later cycle's instance is on record

=== 10. People with no new personal facts: unchanged, byte for byte
synthetic-blake status report identical before and after: yes
synthetic-alex  status report identical before and after: yes
```

## 6. Judgment calls to review

These are ordinary implementation choices under the commission's authorization, but each changes what a report says, so each is written down (also in `docs/DECISIONS.md`).

1. **A date before a later at/above reading reads UNRESOLVED, not NOT_AVAILABLE (D-27).** The commission says a query before an observation "must never use the later fact". The later reading is never used to *satisfy* anything on an earlier date. It is used to say "not known" instead of "no", because the threshold was crossed at some unrecorded time before it. Where a later reading is still *below* the threshold, earlier dates are reported as below, since yearly progress does not decrease. If a stricter reading is wanted (treat later readings as absent), it is a small change in one function and three test tables; say so.
2. **The legacy `metric` fix is a behaviour change (D-28).** A metric dated after the query date used to satisfy a threshold; it now reads as unknown. Nothing live uses metrics, no existing test or output changed, and this is the hazard Bradley's note named. It is a tightening, not a compatibility break of the kind the commission said to stop for.
3. **Eligibility stays after the account record is added.** First implementation dropped `can_get` once an entitlement record existed, which made the pipeline print "DOWNSTREAM REVIEW NEEDED: yes" for a correct step. Changed in checkpoint 4: eligibility is judged from progress alone; possession comes from the record.
4. **The owner's confirmation stands when progress on file does not support it (D-30).** Confirmed status with no achieved reading: ESTABLISHED, flagged `QUALIFICATION_NOT_RECORDED`. Confirmed status against a final below-threshold figure: UNRESOLVED, flagged `CONFLICTING_QUALIFICATION`. The program never overrules the account and never hides the gap.
5. **`effective_from` and `expires_on` must be typed, as a date or the word `unknown` (D-29).** Leaving one out is refused. This is stricter than holdings, on purpose.
6. **Earn rules are not in the CSV tables (D-33).** Content architecture is Argon's; no column was invented for this. Earn rules are authored as candidates and promoted by a reviewer.

No semantic change to existing rule kinds was needed, so the commission's stop condition did not arise.

## 7. Not built, and limits worth knowing before relying on this

- **Calendar-year periods only.** Cardmember-year, rolling-12-month and program-year windows are refused, not approximated. This is the first thing real content will run into. Do not load a real rule with a different window as if it were a calendar year.
- **No refunds or clawbacks.** Progress in a year is assumed never to decrease.
- **Valid time, not record time.** Queries answer "what was true on that date, as now known". They do not replay what the system believed on that date. The audit trail holds that history.
- **One threshold, one measure, one card account per rule.** No tiered thresholds in one rule, no spend combined across cards or people.
- **No sharing of any kind.** Holder, authorized user, guest and companion are not conflated because none of them is represented; every record belongs to one person and one of that person's own accounts. A companion fare here is simply a benefit its earner holds.
- **Dates and balances are the owner's report.** The program checks that they are possible and flags disagreement with the rule's term. It cannot verify them against any account, and `confirmed_by` is a name checked against the profile, not an authentication.
- **A card account ended with `end_holding` reads as not held on every date**, including earlier ones (existing engine behaviour for ended holdings). An entitlement on it stays as recorded and is flagged `ACCOUNT_NOT_HELD`.
- **Activation is recorded by the entitlement record**, not by separately holding the activation `action` entity.
- **Creating a new profile is still a file creation by a reviewer** (unchanged; the fixture builder does it for its two extra invented people). Every personal fact inside a profile goes through the pipeline.
- **Earned benefits are not in goal reports, the applicability matrix or the tables.**
- No portal earn-stack math, bank connection, account access, UI or scheduled monitoring, as the commission excluded.

## 8. What weaker models have and have not demonstrated

- **Have not:** no model other than the builder has run OP-11, read `docs/EARNED_ENTITLEMENTS.md`, or used the `earned` report. The commission did not ask for a lower-model run and none was made. Whether a weaker model keeps "eligible" and "held" apart, or resists filling in a date, is **unverified**.
- **Have (unchanged, from the first build):** one run of Claude Haiku 5.5 on four older maintenance tasks, 21/21 checks after one harness correction. That run did not touch earned benefits or tables. OP-10 also remains untested by any other model.
- **What exists to make that test cheap:** the procedure card in the house format, messages that say what to do instead ("write the word unknown"), a rejecting pipeline, the worked demo, and a fixture with known answers at known dates.

## 9. Suggested next steps, in order

1. A lower-model test of OP-11 on a copy of `fixtures/synthetic-earned/` (three or four tasks: record a below reading; record a year-only statement; record a credit and a use; correct a misread figure), scored by the fixture's known answers. Combine with the outstanding OP-10 test.
2. Argon decides which real earned-benefit rules matter first. For each, the qualification window. Any that are not calendar-year need their own small, tested engineering step before loading.
3. The household-sharing decision. Earned companion and guest benefits are where it will first matter.
4. Only then: real earn rules as candidates with card-specific evidence, and real personal facts only as the owner supplies each figure and date.
