# Results — PRICES foundation viability test

**Commission:** "FABLE COMMISSION — PRICES Foundation Viability Test" (Bradley, Chief PRICES Specialist), issued in chat 2026-11-16; not committed as a file. It supersedes further Bilt-specific expansion.
**Executed:** 2026-11-16 by Claude Fable 5.2 on the experimental branch **`exp/foundation-viability`**, created from `dev/eng-02b-bilt-election-correction` at `d36ebbca1f9ceb4a24c740e7ed90e5c3761b9945`. `main`, every `dev/` branch and both research branches were not modified.
**Result:** **viable with specific architectural corrections.** The assessment, with every number, is `docs/VIABILITY_ASSESSMENT.md`. This file records what was run and observed.

## 1. Starting state (observed at `d36ebbc`)

| | Observed |
|---|---|
| Remote heads | main `f8e1ca1`, dev/fable-integration `52d026f`, dev/argon-content-intake `8039477`, dev/eng-01-recurring-credits `bb95d8b`, dev/eng-02b-bilt-election-correction `d36ebbc`, research branches `2fff6c6` and `f34a494` |
| Tests / lint / tables | 358 pass; 0 errors, 1 warning; tables in sync |
| Content | 10 verified rules; 113 proposed candidates; 24 evidence records |

## 2. Commits

| Commit | Content |
|---|---|
| `6efaed6` | **Freeze.** First capabilities (`unchecked`, `prices/calc.py`, `earnings`, `convert`, terms shown in `explain`) and batch 1. 378 tests |
| `21d4a4c` | Batch 2 entered. `prices/` and `tests/` identical to the freeze (`git diff 6efaed6 21d4a4c -- prices tests` is empty) |
| `c08acc7` | Maintenance phase; successor rules (the one change to `prices/` after the freeze); gap register; generated results; 382 tests. Clean-checkout and export verification run on this commit |
| next commit | Assessment, experiment README, decisions D-53 to D-56, status documents, this file. No code |

## 3. What was run and observed

| Check | Result |
|---|---|
| `python3 experiments/viability/run.py` | 46 checks, 0 failed, about 20 seconds |
| Full suite | `Ran 382 tests` … `OK`. The 358 earlier tests are unchanged and pass |
| `python3 -m prices lint` | 0 errors, 1 warning (the same as before) |
| `python3 -m prices tables status` | in sync, no unimported edits |
| `git diff d36ebbc -- data profiles tables` | empty: no project content, candidate, personal record or table changed |
| `scripts/compare_with_baseline.py` | PASS: 49 commands byte-identical, including every real profile |
| `scripts/verify_clean_checkout.py` on `c08acc7` | `CLEAN CHECKOUT: PASS`: every step ok in an offline clone, including 382 tests, the baseline comparison, the Argon intake replay and the earlier mutation checks (17 of 17, 23 of 23, 24 of 24) |
| `scripts/verify_export.py --skip-mutation-checks` | `TEST F: PASS (mutation checks skipped)` |

The export verification skipped its three mutation checks because the clean checkout runs them on the same code. No new mutation check was written for the code added on this branch; that is a stated limit, not an oversight to be assumed covered.

## 4. Constraints

| Constraint | How it was kept |
|---|---|
| Do not modify Eric's or Todd's personal records | `profiles/` is byte-identical to the base. Every person in the experiment is invented and exists only in the temporary copy |
| Do not promote unreviewed candidates | All 113 remain proposed. Promotion happens only inside the temporary copy; an end-to-end test proves `data/`, `profiles/` and `tables/` are untouched by a run |
| Do not weaken tests | No existing test was changed |
| Do not rebuild working components | 344 lines added and 10 changed in `prices/`; nothing replaced |
| Do not spend the assignment on Bilt | No Bilt work. Bilt appears only as history in the assessment |
| Separate branch | `exp/foundation-viability`. Nothing here is merged or proposed for merge without a coordinator decision |
| Keep verified, calculated and unresolved apart | Each answer is labelled; calculations carry their rule, verification and assumptions or decline with a reason |

## 5. What was not done

- Batch 2 was not reviewed by Argon and was read through a tool that returns extracts. It is a test sample.
- The restriction classification (124 strings) is engineering's reading, for measurement.
- Human entry and review time was not measured.
- The corrections are on an experimental branch. Adopting them, and the content pass on the 20 candidates with unchecked conditions, are decisions for the coordinator and the content owner.
