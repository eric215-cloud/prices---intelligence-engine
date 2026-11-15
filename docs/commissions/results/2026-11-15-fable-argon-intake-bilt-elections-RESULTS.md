# Results — Argon content intake and Bilt election safety (ENG-02)

**Commission:** "PRICES COMMISSION — ARGON CONTENT INTAKE & BILT ELECTION SAFETY", issued in chat 2026-11-15 (not committed as a file). Input: `docs/inputs/Argon_PRICES_Content_Integration_OUTPUT.zip`, committed by Bradley in `52d026f` (direct child of the required base `ed92749`).
**Executed:** 2026-11-15 by Claude Opus 5.5 on branch **`dev/argon-content-intake`**, created from `52d026f`. `main`, `dev/fable-integration` and both research branches were not modified.
**Status:** all three phases complete and verified. Nothing required is unfinished. Two findings about the input and the judgment calls are in sections 3 and 6.

## 1. Baseline

| | Observed |
|---|---|
| Required base | `ed92749447413c5d327877618754a5642e3e7f02`; the input commit `52d026f` adds only the zip |
| Tests at base | `Ran 218 tests` … `OK` |
| Lint at base | `lint: 0 error(s), 1 warning(s)` (Eric's Aeroplan 25K holding has no expiry) |
| Archive | sha256 `bb736f4b31f808e790a6f606cf3dcd06d12f6372b0ea829920da530b4efc0d1e`, 988 members, all CRCs good, no unsafe paths |

## 2. Commits (branch `dev/argon-content-intake`)

| Commit | Content |
|---|---|
| `cdce9e1` | Phase 1: Argon content integrated by replay; `scripts/verify_argon_intake.py` |
| `d57a22f` | Phase 2: election entities, engine gate, `prices/elections.py`, lint, four Bilt definitions, `tests/test_n_elections.py`, mutation check |
| `87347fd` | Phase 2/3: withdrawable holdings, `scripts/demo_elections.py`, OP-12, `docs/ELECTIONS.md`, decisions D-34..D-39, docs, verifier updates. Export and clean-checkout verification run on this commit |
| next commit | This file only |

## 3. Phase 1 — content intake

**Method.** Instead of copying the package's files over the store, every one of Argon's 246 changesets was re-applied, in audit-log order, through the ordinary pipeline (`prices.changes.apply`) on the base, followed by `tables export`.

| Check | Observed |
|---|---|
| Manifest | 987 files listed = 987 packaged (plus the manifest itself); every sha256 and size matches |
| Replay | 246 of 246 changesets applied with the same result, changed files, `digest_before` and `digest_after` as Argon's log |
| Result vs package | `data/`, `profiles/`, `tables/` byte-identical to the package, **except** the two audit records below |
| Added | 135 entities, 8 evidence records, 111 candidates (all `proposed`), 246 audit records with before-snapshots, updated tables |
| Candidates | 113 proposed in total (111 new + 2 existing), none promoted; Argon's changesets contain no promotion |
| Active rules | the same 10 files as the base |
| `profiles/` | byte-identical to the base (no holding, progress, entitlement or election added) |
| Lint / tables | `0 error(s), 1 warning(s)` (unchanged); tables in sync |

**Finding 1: the package drops two existing audit records.** Its `data/audit/log.jsonl` and `data/audit/changesets/` lack `cs-20261112-101-set-holding` and `cs-20261112-102-set-holding`: the changesets by which Bradley recorded Eric's two holdings on 2026-11-12. Eric's holding files themselves are identical; only their provenance was missing. The intake keeps both records (audit history is only ever added to, D-34). This was caught only because the integration was done by replay.

**Finding 2: the report's counts differ from the package.** The report states 144 entities, 21 evidence records and 123 table + 123 other changesets. The package and the manifest contain 158 entities, 24 evidence records, and 117 table + 129 other changesets (246 total). The manifest's own counts are correct. No engineering effect; noted for Argon.

No content was re-researched, edited or reinterpreted. `scripts/verify_argon_intake.py` repeats every check above from the committed archive and lists anything added since (now: the four election definitions and their audit records).

## 4. Phase 2 — Bilt election safety (ENG-02)

**The hazard, demonstrated.** The five rules concerned are card-benefit candidates whose condition is only `{"holds": "card.bilt-palladium"}`; the exclusivity existed only as prose. With no election mechanism, promoting them makes every cardholder hold both housing options at once, and both the legacy credits and the $600 from 2027 (`tests/test_n_elections.py::TestStructure::test_no_election_entities_no_change`).

**Existing condition system, evaluated first.**
- `{"all": [{"holds": card}, {"holds": option}]}` can express "only with this election". But these rules are `card_benefits` table rows: the tables write their condition as `{"holds": card}` and read the card back from that shape (`prices/tables.py` lines 67 and 381). Editing them breaks the table round trip and changes Argon's content.
- `{"not": {"holds": other}}` grants an option whenever the other is merely unrecorded, which is the inference the commission forbids.
- Neither gives "unknown" for an unrecorded election, detects two recorded options, or knows an anniversary.

**Smallest correct extension (D-35 to D-39).**

| Piece | Change |
|---|---|
| Entity kind `election` | One option of a group on a card, with `governs` (rule or candidate ids) and optional terms: `opened_before`, `default_before_anniversary`, `starts_at_anniversary`, `elect_before_anniversary`. Dates mean "the first card anniversary on or after D" |
| Engine | Adds "and the person elected this option" to each governed rule or candidate (`gate`, 3 lines at rule loading); skips election holdings in the generic holding step; calls `elections.inject` |
| Personal facts | Election = an owner-confirmed holding of the option (existing `set_holding` / `end_holding`). New optional `opened_on` on card holdings. New holding state `withdrawn` (via `end_holding`, `withdrawn: true`) for a record entered by mistake |
| `prices/elections.py` (300 lines) | Decides per person, group and date which option is in effect (rules in `docs/ELECTIONS.md` section 4) |
| Lint | Definition checks (card, governs, overlap, defaults, nothing derives an election), holding checks, `CONFLICTING_ELECTIONS` warning |
| Pipeline | Revising an `election` block needs a promotion reviewer |
| Reports | `status` section "Card elections" and JSON key `elections` (only for people holding such a card); `explain` shows the election link; `timeline` includes election dates and each account's transition anniversary |

**The four Bilt definitions** (added by `add_entity` changesets `cs-20261115-eng02-01..04`; values transcribed from the candidates' own `restrictions` and Argon's ENG-02 text):

| Group | Option | Governs | Terms |
|---|---|---|---|
| `bilt-palladium.housing-rewards` | `…housing-tiered-points` | `cb.bilt-palladium.housing-tiered-points` | none |
| | `…housing-flex-bilt-cash` | `cb.bilt-palladium.housing-flex-bilt-cash-legacy` | opened before 2027; elected before the first 2027+ anniversary |
| `bilt-palladium.annual-credits` | `…annual-credits-legacy` | `cb.bilt-palladium.annual-bilt-cash-200-legacy`, `cb.bilt-palladium.hotel-credit-400-semiannual-legacy` | opened before 2027; default before the first 2027+ anniversary; retained only by an election made before it |
| | `…annual-credits-600` | `cb.bilt-palladium.annual-bilt-cash-600-post2027` | starts at the first 2027+ anniversary |

The audit log also keeps a first attempt of each of these four changesets, rejected because lint then treated a one-option group as an error; that rule was relaxed to a warning, since the two options of a group necessarily arrive in separate changesets.

**Requirement → evidence** (`tests/test_n_elections.py`, 36 tests; the last class runs the real definitions on a scratch copy with the five candidates promoted there only):

| Requirement | Demonstrated by | Observed |
|---|---|---|
| Unknown election never establishes either side | `TestUnknownElection`; `TestLiveBiltDefinitions` | Card held, nothing recorded: tiered and Flex both UNRESOLVED; `needs: CONFIRM: election bilt-palladium.housing-rewards: no election recorded` |
| A recorded election activates only its pathway, subject to other conditions | `TestConfirmedElection` (6) | Tiered recorded → tiered ESTABLISHED, Flex NOT_AVAILABLE; no card / unconfirmed card / unverified rule → not established |
| Contradictions detected and reported | `TestConflicts` (5); pipeline test | Two options overlapping → lint `CONFLICTING_ELECTIONS`, flag `CONFLICTING_ELECTIONS`, both UNRESOLVED; also two card accounts, and records the terms forbid (`ELECTION_NOT_PERMITTED`) |
| Changing elections | `TestChangingElections` (3); `test_withdrawing_a_mistaken_election` | Switch on 2026-09-01: tiered through Aug 31, Flex from Sep 1, earlier dates unchanged; gaps UNRESOLVED; withdrawn record never in effect |
| 2027 transition at the actual anniversary | `TestTransition2027` (8) | Opened 2025-06-01: legacy ESTABLISHED through 2027-05-31, $600 NOT_AVAILABLE; from 2027-06-01 with nothing recorded all UNRESOLVED; Jan 20 vs Oct 5 cardholders switch on their own days; unknown `opened_on` → UNRESOLVED from 2027 (`ANNIVERSARY_NOT_RECORDED`); Feb 29 account: Feb 28 unknown, not decided by convention |
| Legacy-election terms | `test_recorded_choice_at_the_transition`, `test_choices_that_do_not_respect_the_anniversary` | Legacy retained by a 2026-12-01 election → legacy continues past the anniversary; "retained" only after the anniversary, or $600 before it → `ELECTION_NOT_PERMITTED`, neither applied |
| No inference from absence | `test_nothing_is_inferred_from_the_absence_of_an_election` | Account opened 2027 (Flex impossible): tiered still UNRESOLVED; after 2027 anniversary with nothing recorded, $600 UNRESOLVED |
| Published eligibility separate from possession, activation, usage | engine design; `TestLiveBiltDefinitions::test_committed_store_keeps_the_candidates_proposed_and_gated` | Rules untouched; the election is personal; earned-benefit machinery unchanged (its 74 tests pass) |
| Only the owner confirms; definitions need a reviewer | `TestPipeline` (4) | Maintainer attestation → `OWNER_ATTESTATION_REQUIRED`; revising `governs` → `REVIEWER_NOT_AUTHORIZED` |

**Demonstration** (`python3 scripts/demo_elections.py`, abridged; scratch copy, invented cardholder opened 2025-06-01):

```
=== 2. Record the card, with the opening date the anniversary comes from
    [review] ELECTION_NOT_RECORDED bilt-palladium.housing-rewards
  2026-11-15   housing-tiered-points UNRESOLVED   housing-flex UNRESOLVED   200-legacy ESTABLISHED   400-legacy ESTABLISHED   600 NOT_AVAILABLE
  2027-06-01   all five UNRESOLVED   (this account's first 2027 anniversary; no choice recorded)
=== 3. Mistakes
REJECTED  OWNER_ATTESTATION_REQUIRED: attestation must be by the profile owner 'Bilt Holder (synthetic)', not 'junior maintainer'
REJECTED  REVIEWER_NOT_AUTHORIZED: only Eric, Bradley, Commissioning build may do this; escalate to one of them
=== 4. Record the owner's housing election          tiered ESTABLISHED, flex NOT_AVAILABLE
=== 5. A contradictory record                        [review] CONFLICTING_ELECTIONS ... both UNRESOLVED
    withdrawn by the owner                           tiered ESTABLISHED again
=== 6. Legacy retained (2026-12-10); housing switched to Flex from 2027-03-01
  2027-02-28   tiered ESTABLISHED  flex NOT_AVAILABLE  legacy credits ESTABLISHED  600 NOT_AVAILABLE
  2027-03-01   tiered NOT_AVAILABLE  flex ESTABLISHED  legacy credits ESTABLISHED  600 NOT_AVAILABLE
  2027-06-01   unchanged: Flex and legacy were both elected before the anniversary, as their terms require
```

## 5. Phase 3 — verification (observed)

| Command | Observed |
|---|---|
| `python3 -W error -m unittest discover -s tests` | `Ran 254 tests` … `OK` (218 existing, unmodified, + 36) |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` — same single warning as the base |
| `python3 -m prices tables status` | `out of date with the store: no` / `unimported edits: no` |
| `python3 scripts/verify_argon_intake.py` | every check `ok`; `ARGON INTAKE: PASS` |
| `python3 scripts/compare_with_baseline.py` (vs `cdce9e1`) | 49 commands byte-identical (all profiles' status, timeline, review, goal, discovery, cards; both card-fixture profiles), 21 file sets unchanged (rules, evidence, candidates, profiles, tables, fixtures, earlier tests), audit log append-only (273 → 281); `PASS` |
| `python3 scripts/mutation_check_elections.py` | `13 of 13 mutations caught` |
| `python3 scripts/mutation_check_earned.py` | `17 of 17 mutations caught` |
| `python3 scripts/verify_export.py` | 1,370 files exported; 18 steps `ok`; `TEST F: PASS` |
| `python3 scripts/verify_clean_checkout.py` (on `87347fd`, offline) | 17 steps `ok`, checkout unmodified; `CLEAN CHECKOUT: PASS` |
| Successor harness, untouched copy | `10 of 21 checks passed` (as before) |
| `git diff ed92749 HEAD -- profiles data/kb/rules` | empty: Eric's profile and all 10 active rules unchanged |
| `git diff cdce9e1 HEAD -- data/candidates tables` | empty: engineering changed no candidate and no table |

## 6. Judgment calls to review

1. **Integration by replay rather than copy (D-34).** Same content, verified harder, and it kept the two audit records the package dropped.
2. **Unrecorded election = UNRESOLVED, not CONDITIONAL (D-36).** Argon's ENG-02 acceptance says "Conditional - needs election". In this engine CONDITIONAL means "a step you could take"; an election has usually already been made on the account, so what is missing is the fact. Output: `needs: CONFIRM: election … not recorded`. Neither is ever established. A small change if Bradley prefers CONDITIONAL.
3. **The legacy credits apply without an election before the cardholder's first 2027+ anniversary** (for accounts opened before 2027). That is a published default stated in Argon's own text, not an inference; the only default in the four definitions.
4. **A record the published terms forbid is held UNRESOLVED, not refused or granted.** The owner's account may show an exception; it is flagged for a person.
5. **One record that cannot be checked stands** (`ELECTION_TERMS_UNVERIFIED`, e.g. no `opened_on`), consistent with D-30 for earned benefits.
6. **Two groups, not one.** ENG-02 and the commission list (A) and (B) separately. The candidates' wording ("legacy Flex/credit election") may mean a single legacy election. Argon to decide; one group or a link is a definitions change, not engineering.

## 7. Changed-file inventory (vs `52d026f`)

| Area | Files |
|---|---|
| Engine code | `prices/elections.py` (new, 300), `prices/engine.py` (+25), `prices/lint.py` (+107), `prices/changes.py` (+15), `prices/schema.json` (+25), `prices/cli.py` (+6), `prices/review.py` (+3) |
| Tests | `tests/test_n_elections.py` (new, 36 tests). No existing test or `tests/util.py` changed |
| Scripts | new: `verify_argon_intake.py`, `demo_elections.py`, `mutation_check_elections.py`; changed: `compare_with_baseline.py` (default baseline `cdce9e1`, audit log as append-only), `verify_clean_checkout.py`, `verify_export.py` |
| Content (Argon, by replay) | 135 entities, 8 evidence, 111 candidates, 246 audit changesets + 246 before-snapshots, audit log, 8 table files |
| Content (ENG-02) | 4 election entities `data/kb/entities/election.bilt-palladium.*`, 4 audit changesets + snapshots |
| Docs | new: `docs/ELECTIONS.md`, `docs/operations/OP-12-card-elections.md`, this file; changed: `DECISIONS.md` (D-34..D-39), `SCHEMA.md`, `ARCHITECTURE.md`, `MAINTAINER_GUIDE.md`, `README.md`, `STATUS.md`, `CONTINUATION.md` |
| Not changed | `profiles/`, `data/kb/rules/`, every candidate after intake, `fixtures/`, `successor_test/`, `main`, `dev/fable-integration`, research branches |

## 8. Remaining limitations

- **Elections are per person.** Two accounts of one card are reported (`MULTIPLE_CARD_ACCOUNTS`), not resolved.
- **The Bilt definitions are an engineering transcription** awaiting Argon's confirmation (section 6, item 6).
- **Accounts opened in 2027 or later:** Argon's text does not say what applies before their first anniversary; nothing is applied then, and $600 is UNRESOLVED afterwards until recorded.
- **No billing-cycle granularity** for housing switches; recorded by date.
- **Elections gate benefits; amounts, tiers and rates remain prose** (ENG-01, ENG-04 not started, as instructed). ENG-03 not started.
- **Nothing is live.** The five governed rules are proposed candidates; no profile holds a Bilt card or an election. No election, opening date or holding was recorded for Eric or Todd.
- **Engineering did not review the 113 candidates' content.** Transfer ratios are absent by Argon's design (`Q-BILT-004`, `Q-CSR-001`).
- **No lower-capability model has run OP-12** (or OP-10, OP-11).

## 9. Is the integrated candidate package ready for the next engineering commission?

**Yes, as a base for the next engineering commission.** The content is integrated through the pipeline, verified against Argon's manifest and audit log, lint-clean, in sync with the tables, and quarantined: 113 proposed candidates, none able to establish anything, Eric's profile and the 10 active rules untouched. The one structural hazard Argon identified for Bilt (ENG-02) is closed: if the five governed candidates are promoted, no cardholder can be granted both sides of either election.

**Not yet ready for promotion.** That is a content and review decision rather than an engineering one, and it should wait on:
1. Argon confirming the four Bilt election definitions (section 6, item 6) and the two report discrepancies (section 3);
2. Argon's own open questions, notably the transfer ratios (`Q-BILT-004`, `Q-CSR-001`) and the Hyatt 1:1 vs 4:3 question;
3. for the recurring-credit candidates (CSR $300 / $500 / $300, Bilt hotel credit), ENG-01 if their amounts and cadences are to be computed rather than described.
