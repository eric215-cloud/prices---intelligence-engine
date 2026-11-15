# Results — ENG-02B: Bilt election correction

**Commission:** "PRICES ENGINEERING COMMISSION — ENG-02B: BILT ELECTION CORRECTION" (sponsor Eric, coordinator Bradley), issued in chat 2026-11-15; not committed as a file.
**Executed:** 2026-11-15 by Claude Fable 5.2 on branch **`dev/eng-02b-bilt-election-correction`**, created from `dev/eng-01-recurring-credits` at `bb95d8b87d9223938b2b5d23c64a70f31f381df6`. `main`, `dev/fable-integration`, `dev/argon-content-intake`, `dev/eng-01-recurring-credits` and both research branches were not modified.
**Status:** working, verified code. The corrected behaviour is in the engine and in the six committed election definitions, and each acceptance case has a passing test. Three things are not done and are not claimed: Argon has not confirmed the definitions; no named reviewer has checked them; Argon's 2026-11-15 election audit was not available (section 4).

Every cardholder, account date and election in the tests and the demonstration is invented. No personal record of Eric or Todd was read for, or changed by, this work. Eric's statement that he made the Legacy Election is noted in `CONTINUATION.md` as a profile task for the coordinator; it was not recorded.

## 1. Starting state (observed at `bb95d8b`)

| | Observed |
|---|---|
| Branch / commit | `dev/eng-01-recurring-credits` at `bb95d8b`; working tree clean |
| Remote heads | main `f8e1ca1`, dev/fable-integration `52d026f`, dev/argon-content-intake `8039477`, research/michaela-bilt-20261114 `2fff6c6`, research/michaela-card-packets-20261114 `f34a494` |
| `python3 -m unittest discover -s tests` | `Ran 327 tests` … `OK` |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` (Eric's Aeroplan 25K holding has no expiry) |
| `python3 -m prices tables status` | `out of date with the store: no` / `unimported edits: no` |

## 2. Commits

| Commit | Content |
|---|---|
| `95e999e` | Checkpoint 1: `prices/elections.py`, schema, lint, six definition changesets, 31 new tests. 358 tests passing |
| `cd3c1ad` | Checkpoint 2: mutation check, demonstration, OP-12, `docs/ELECTIONS.md` section 8, decisions D-48 to D-52, verifiers. Clean-checkout and export verification run on this commit |
| next commit | This file only |

## 3. Corrected behaviour

What ENG-02 got wrong: it treated housing rewards and annual credits as two independent elections. A person could be shown Flexible Bilt Cash with the $600, or Housing-only with the legacy credits after the transition, and an account opened in 2027 got nothing until its first anniversary.

What the engine does now (T = the account's first Card Anniversary Date on or after 2027-01-01):

| Account | Date | Housing | $200 Bilt Cash + $400 hotel credit | $600 Bilt Cash |
|---|---|---|---|---|
| Opened before 2027 | before T | The cardholder's recorded choice. Not recorded → both UNRESOLVED | Apply automatically, whatever the housing option. Not an election | No |
| Opened before 2027, Legacy Election recorded (must start before T) | from the election on, including after T | Flexible Bilt Cash, carried by the election itself. A Housing-only record on top is a flagged contradiction | Apply | Never |
| Opened before 2027, refreshed arrangement recorded | from T | Housing-only | No | Yes, from T |
| Opened before 2027, nothing recorded | from T | UNRESOLVED | UNRESOLVED | UNRESOLVED |
| Legacy Election left on day X (owner records it) | from X | Housing-only | Stop on X | From the first card anniversary on or after X |
| Legacy Election recorded again after leaving, or starting on or after T | | Not applied; `ELECTION_NOT_PERMITTED` | | |
| Opened on or after 2027-01-01 | from opening | Housing-only, nothing to record | No | Yes, from opening |
| A record of the legacy credits or the $600 as a choice of its own | | Not used; `ELECTION_NOT_SELECTABLE` | | |

How: a new group `bilt-palladium.arrangement` holds the one real choice (`legacy-election`, `refreshed-arrangement`). The four ENG-02 options keep their ids and the rules they govern, and now `follow` it. The mechanism is general (six new optional terms on an option; `docs/ELECTIONS.md` section 3) and a store that does not use them behaves exactly as before.

Two consequential choices, both recorded as decisions:

1. **The refreshed arrangement is recorded for older accounts, not inferred (D-49).** The terms make it mandatory when no Legacy Election was made, but PRICES cannot see that nothing was made. Inferring it would show the wrong benefits to a cardholder whose Legacy Election is simply not on file yet.
2. **The card anniversary is not the opening date (D-50).** The terms count it from the first billing cycle that begins after opening. ENG-02 used the opening date's own day. The engine now takes the anniversary from a new optional `anniversary_on` on the card holding; without it the anniversary is a window (opening + 1 to 62 days, each year) and dates inside it are unresolved. 62 is an engineering allowance, not a published number.

The six definition changes went through the pipeline (`cs-20261115-eng02b-01` to `-06`). Two are new entities. Four revise an `election` block, which needs a promotion reviewer: they are attested by "Commissioning build", with a statement that the commission orders the correction and that no named reviewer has checked them (D-51). Any of them can be undone with `revert_changeset`.

## 4. Sources

Read on 2026-11-15 through the web fetch tool, which returns extracts rather than the full page:

- Bilt Rewards Card Offer Terms, last updated 2026-10-27, bilt.com/terms/bilt-card-offer-terms. Read twice with separate question sets; the two readings agree.
- Bilt Cash Program Terms of Use, last updated 2026-10-27, bilt.com/terms/bilt-cash.
- Bilt help centre, "Bilt Card 2.0 Program Overview" (cross-check).
- Secondary coverage of the 2026-10-27 update (One Mile at a Time, View from the Wing, NerdWallet, AwardWallet and others), used only to check the reading. None contradicts it.

**Argon's 2026-11-15 election audit is not in the repository or any of its six branches and was not attached.** It was not used. If it differs from section 3, that needs reconciling before promotion.

Discrepancies and open points are listed in `docs/ELECTIONS.md` sections 8.4 and 8.5. In short:

| Point | State |
|---|---|
| Help-centre page still shows the January 1 Bilt Cash grant and year-end expiry | Stale page; the 2026-10-27 terms are followed |
| Bilt Cash terms say anniversary "in 2027"; Offer Terms say "on or after January 1, 2027" | Differ for accounts opened late December 2026. Not modelled (hotel redemption caps) |
| Can a Legacy Election be cancelled before T? When does it take effect? | Terms silent. A recorded election applies from its recorded start |
| Can an older account move to the refreshed arrangement before T? | Terms silent. Such a record is flagged, not applied |
| Product change (upgrade, downgrade) and the Legacy Election | Terms silent. Not modelled |
| Is the January 1, 2027 hotel credit issued to accounts that move later in 2027? | Bilt says yes publicly; terms silent. A credit-period question, not modelled |
| Length of the first billing cycle | Terms say "approximately 30 days". The 62-day allowance is ours |

## 5. Acceptance tests (`tests/test_q_bilt_election_correction.py`, 31 tests)

The committed definitions run on a scratch copy of the live store with Argon's five candidates promoted there only. Twenty invented cardholders. Standard invented account: opened 2026-03-10, anniversary shown as April 5, so T = 2027-04-05.

| # | Required | Tests | What is checked |
|---|---|---|---|
| 1 | Switching housing before T without losing the legacy credits | `test_1_*` (2) | Housing-only to 2026-08-04, Flexible from 2026-08-05; $200 and $400 ESTABLISHED throughout; no flag. From T the choice no longer decides |
| 2 | Retaining the linked legacy arrangement | `test_2_*` (2) | Flexible, $200, $400 ESTABLISHED before and after T; Housing-only and $600 NOT_AVAILABLE; the election alone carries Flexible |
| 3 | Transition to refreshed at T | `test_3_*` (2) | T − 1: legacy credits. T: Housing-only and $600. A refreshed record dated before T is flagged |
| 4 | Account opened in 2027 | `test_4_*` (2) | Housing-only and $600 from the opening day, before any anniversary, nothing recorded, no flag. A Legacy Election on it is refused |
| 5 | Mutual exclusion | `test_5_*` (2) | All 20 cardholders × 144 days: never both housing options; never the $600 with any legacy piece; the two legacy credits always move together |
| 6 | Permanent exit | `test_6_*` (2) | Legacy stops on the exit day; $600 only from the next anniversary; re-election (after T, and before T) is flagged and never applied |
| 7 | Missing dates, unverified elections | `test_7_*` (3) | No opening date; opening date without the issuer's anniversary (window); unconfirmed election; election with no start date |
| 8 | Boundaries | `test_8_*` (4) | Election deadline T − 1 vs T; billing-cycle switch day; Legacy Election locks housing; stale record reported; timeline dates |
| | General machinery | 9 | Anniversary windows; the same behaviour with invented options; definition and holding checks |
| | Scratch store sound; live store untouched | 3 | Scratch copy lints clean; candidates proposed; no election or `anniversary_on` in any real profile; the committed definitions are one linked arrangement |

**One existing assertion was changed** (`tests/test_n_elections.py`, `TestLiveBiltDefinitions`): "all five UNRESOLVED on 2027-06-01" became "on 2027-08-02". The invented account there was opened 2025-06-01; ENG-02 took 2027-06-01 as its anniversary, which the published definition rules out (it falls between 2027-06-02 and 2027-08-02). The assertion is as strict as before; only the date moved. `scripts/compare_with_baseline.py` checks that this is the only difference in that file. No other existing test was touched.

## 6. Verification (observed)

| Check | Result |
|---|---|
| Full suite, working tree at `cd3c1ad` | `Ran 358 tests` … `OK` (327 existing + 31 new) |
| `python3 -m prices lint` | `0 error(s), 1 warning(s)` (same warning as the baseline) |
| `python3 -m prices tables status` | in sync, no unimported edits |
| Candidate quarantine | 113 proposed, none promoted or edited; `git diff bb95d8b -- data/candidates data/kb/rules` empty |
| Personal records | `git diff bb95d8b -- profiles` empty |
| `scripts/mutation_check_elections.py` | 24 of 24 caught (13 ENG-02, 11 new). Run once in the working tree and once inside the clean checkout |
| `scripts/compare_with_baseline.py` (vs `bb95d8b`) | PASS: 49 commands byte-identical, including every real profile; `data/` differs only in the six definitions, their 12 audit records and the log (old log an unchanged prefix, 281 → 287) |
| `scripts/verify_argon_intake.py` | PASS |
| `scripts/demo_elections.py` | completes; it now stops if any day's result differs from the expected one |
| `scripts/verify_clean_checkout.py` on `cd3c1ad` | `CLEAN CHECKOUT: PASS`, every step ok: 358 tests, lint, tables, demos, baseline comparison, Argon intake, mutation checks 17 of 17 (earned), 23 of 23 (credits), 24 of 24 (elections); the clone is clean afterwards |
| `scripts/verify_export.py --skip-mutation-checks` on `cd3c1ad` | `TEST F: PASS (mutation checks skipped)`: 1,627 files exported, unpacked elsewhere, 358 tests and every demo pass there |

To limit repeated full-suite runs, the earned and credits mutation checks were run once (inside the clean checkout), and the export verification was run with its three mutation checks skipped, since the clean checkout had just run them on the same commit.

## 7. Changed files (vs `bb95d8b`)

| Area | Files |
|---|---|
| Engine | `prices/elections.py` (rewritten around the same decision), `prices/engine.py` (one line), `prices/lint.py`, `prices/schema.json` (six option terms; `anniversary_on` on holdings) |
| Live content | `data/kb/entities/election.bilt-palladium.*` (2 new, 4 revised), 12 audit records, audit log |
| Tests | `tests/test_q_bilt_election_correction.py` (new); `tests/test_n_elections.py` (one assertion) |
| Scripts | `mutation_check_elections.py`, `demo_elections.py`, `compare_with_baseline.py`, `verify_export.py` |
| Documents | `docs/ELECTIONS.md`, `docs/operations/OP-12-card-elections.md`, `docs/DECISIONS.md`, `STATUS.md`, `CONTINUATION.md`, `README.md`, this file |

## 8. Bilt Cash mechanics that are not supported

Election eligibility is decided. None of the following is computed, and no `credit` block was put on the Bilt Cash candidates (D-52):

- per-grant expiry (end of the month 12 months after earning; first to expire is spent first);
- grant dates on the Card Anniversary Date, and the grant at account opening (ENG-01's anniversary cycle counts from `opened_on`, which is not Bilt's anniversary);
- the Bilt Cash wallet: balances, redemptions, returned redemptions;
- conversion of unredeemed hotel credit to Bilt Cash when a Legacy Election holder leaves;
- unused hotel credit expiring at T;
- hotel redemption caps and Point Accelerator limits.

"$600 ESTABLISHED" therefore means "this account is under the $600 benefit on this date". It does not mean a balance exists.

## 9. Before Argon integrates the deferred Bilt candidates

1. **Argon confirms the six definitions** against the published terms, or corrects them, and reconciles them with the 2026-11-15 audit that engineering did not see.
2. **A named reviewer (Eric or Bradley) countersigns** the four revised definitions, or reverts them.
3. **The candidates' own text is partly out of date.** For example the $600 candidate says "effective at first card anniversary in 2027 or later"; for accounts opened in 2027 it is effective at opening. The $200 candidate should say it is credited on opening and on each Card Anniversary Date. The engine no longer depends on that wording, but a reviewer will read it at promotion. Candidates were not edited here.
4. **Decide the 62-day allowance** or replace it with a figure Argon can source.
5. **Decide the open points in section 4** that affect real accounts: early cancellation of a Legacy Election, and product changes.
6. **Per-grant Bilt Cash accounting** (section 8) is needed before any Bilt Cash amount is shown as a balance. It is not needed to promote the five governed candidates as eligibility rules.
7. **Personal records.** When the candidates are promoted, a Bilt Palladium holder with nothing recorded will show UNRESOLVED from T on. The coordinator should record `opened_on`, `anniversary_on` and the Legacy Election for anyone who has told us theirs (OP-12 section 0). Nothing was recorded here.
