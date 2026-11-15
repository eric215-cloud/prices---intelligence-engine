# Results — ENG-01: structured recurring credits

**Commission:** "PRICES COMMISSION — ENG-01: STRUCTURED RECURRING CREDITS" (sponsor Eric, coordinator Bradley), issued in chat 2026-11-15; not committed as a file.
**Executed:** 2026-11-15 by Claude Fable 5.2 on branch **`dev/eng-01-recurring-credits`**, created from `dev/argon-content-intake` at `80394770e04d672cab735f11e24bffb5cf939b79`. `main`, `dev/fable-integration`, `dev/argon-content-intake` and both research branches were not modified.
**Status:** working, verified code. Every item under "Required engineering" and "Verification" has a passing test or an observed command result below. What does not fit the model is listed in section 7; decisions for Bradley are in section 8.

Everything demonstrated uses an invented card, invented credits, invented people and invented figures (`fixtures/synthetic-credits/`). No real credit has structured terms: Argon's 113 candidates were neither edited nor promoted. Nothing was recorded for Eric or Todd.

## 1. Starting state (observed at `8039477`)

| | Observed |
|---|---|
| Branch / commit | `dev/argon-content-intake` at `8039477`; remote heads for `main`, `dev/fable-integration` and both research branches as before |
| `python3 -W error -m unittest discover -s tests` | `Ran 254 tests` … `OK` |
| `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)` (Eric's Aeroplan 25K holding has no expiry) |
| `python3 -m prices tables status` | `out of date with the store: no` / `unimported edits: no` |

## 2. Commits (branch `dev/eng-01-recurring-credits`)

| Commit | Content |
|---|---|
| `8f38f34` | Checkpoint 1: schema, `prices/credits.py`, lint, `set_credit_terms`, `credits.csv`, `credits` command, fixture builder. 254 existing tests passing |
| `cc447bc` | Checkpoint 2: committed fixture, 73 new tests, mutation check |
| `a23f3de` | Checkpoint 3: demo, OP-13, `docs/RECURRING_CREDITS.md`, decisions D-40..D-47, docs, verifier updates. Export and clean-checkout verification run on this commit |
| next commit | This file only |

## 3. What now works

| Capability | How |
|---|---|
| **Structured terms** for a recurring credit | Optional `credit` block on the card-benefit rule: `amount`, `unit`, `cycle` (`calendar_year`, `calendar_half`, `calendar_quarter`, `calendar_month`, `anniversary_year`, `multi_year` with `years` and `anchor`), `max_per_transaction`, `min_stay_nights`, `min_transaction`, `rollover`, `rollover_max`, `note` |
| **One representation** | Terms only on the rule. Effective and expiration dates stay the rule's `valid_from` / `valid_to`. Refused on any rule that is not a card benefit |
| **Unknown stays unknown** | An absent key is printed as "not stated by the source". `none` (the source says there is none) is a different value. Nothing defaults to zero, unlimited or unrestricted |
| **Authoring** | `tables/credits.csv` (one row per card_benefits row with terms; deterministic round trip) or the `set_credit_terms` changeset. A rule in force needs evidence; history is kept; `revert_changeset` restores. A candidate is amended in place and stays a candidate with the same id. Promotion carries the terms |
| **Calculation for a date** | The allowance period (label, first and last day), the published allowance for it, the per-transaction maximum and minimums, the next reset date, what happens to an unused amount, and whether the offer has started or ended |
| **Per person** | Whether the credit applies is the engine's ordinary answer, so holdings, verification and elections count. Anniversary periods come from the account's own `opened_on`; without it the period is UNRESOLVED |
| **Personal balance** | Only from an owner-confirmed record for that rule, account and period, using the existing earned-benefit record and operations. No record: `NOT RECORDED` |
| **Report** | `python3 -m prices credits [--profile P] [--as-of D] [--card C] [--until D] [--candidates]`, text and `--json` |
| **Calendar ahead** | `review` and `timeline` list each allowance period ending in the window, on its last day (Argon's acceptance item) |

Argon's three acceptance criteria: the schema validates the `credit` block (yes); `prices.tables` round-trips the credit columns (yes, in their own table `credits.csv`: see section 8, decision 1); `prices.review` surfaces expiring credits in the window (yes).

## 4. Synthetic acceptance scenarios

Invented card "Northwind Voyager". Authored through the tables, promoted by the invented reviewer. Tests: `tests/test_o_credits.py` (O, in-memory, 42) and `tests/test_p_credits_pipeline.py` (P, on the fixture, 31).

| Scenario | Fixture | Observed (`credits --profile …`) |
|---|---|---|
| **A** 300 each card anniversary | travel credit, `anniversary_year` | Alex (opened 2025-03-15): 2027-03-14 → period 2026-03-15 to 2027-03-14; 2027-03-15 → 2027-03-15 to 2028-03-14 |
| **B** 500 a calendar year, 250 per booking, 2-night minimum | curated hotel credit | 2027-01-01 to 2027-12-31; "per transaction: maximum 250 USD; minimum stay 2 night(s)"; resets 2028-01-01 |
| **C** two separate 150 halves, no rollover | dining credit, `calendar_half` | 2027-06-30 → 2027-H1; 2027-07-01 → 2027-H2; "at most 300 USD in a calendar year"; Alex's H1 record EXHAUSTED, H2 `NOT RECORDED` |
| **D** 10 a month, expires at month end | ride credit, `calendar_month`, offer ends 2027-09-30 | 2027-03-31 → 2027-03; 2027-04-01 → 2027-04; September is the last period ("offer ends"); 2027-10-01 → no period, benefit NOT_AVAILABLE |
| **E** two cardholders, two anniversaries | Alex 2025-03-15, Erin 2024-11-02 | Same date 2027-03-10: Alex 2026-03-15 to 2027-03-14; Erin 2026-11-02 to 2027-11-01 |
| **F** opening date missing | Finn (no `opened_on`) | `PERIOD UNRESOLVED - the opening date of account … is not recorded`; flag `CREDIT_PERIOD_UNRESOLVED`; no allowance line; calendar credits unaffected. After the owner gives the date, the period resolves |
| **G** credit subject to an election | lifestyle (200 a year) or wellness (25 a month), ENG-02 options | Alex elected lifestyle: lifestyle ESTABLISHED, wellness NOT_AVAILABLE with no allowance. Erin, no election: both UNRESOLVED. Contradictory records: neither. Never both ESTABLISHED on any tested date |
| Every four years | traveler fee credit, `multi_year`, 4, `last_use` | Alex's recorded use 2025-09-10 → period to 2029-09-09; from 2029-09-10 available again. Erin and Finn, no use recorded: UNRESOLVED |
| Quarter, rollover stated | streaming credit | 2027-Q1; "unused allowance rolls over, up to 20 USD" |

| Required demonstration | Where |
|---|---|
| Boundary dates, reset transitions | O `TestCalendarPeriods`, `TestAccountPeriods`, `test_resets_at_each_boundary`; P `test_alex_boundaries_resets_and_expiration` (12 boundary pairs) |
| Expiration | O `test_expiration_of_the_offer` (incl. a yearly credit withdrawn mid-year: period cut, amount not pro-rated), `TestOfferDates`; P retired rule |
| Caps | O `test_use_above_the_per_transaction_cap_is_flagged`; P `test_use_caps_and_limits` (300 and 250.01 refused, 250 accepted) |
| Invalid inputs | O `TestStructure` (18 bad blocks); P `test_invalid_terms_are_refused` (15), `test_invalid_table_edits_change_nothing` (17), period-record errors (13), usage errors (8). Every rejection leaves the store digest unchanged |
| Corrections | P `test_correcting_terms_…_keeps_history` (before-snapshot, revert, idempotency), `test_corrections_keep_the_old_entry` (use and allowance), table correction with and without a source |
| Published is not personal | O `TestPublishedIsNotPersonal` (10), `TestPersonalRecords` (10); P live-data test |
| February 29, unknown anchor, two accounts | O `test_february_29_account`, `test_multi_year_with_no_stated_starting_point`, `test_two_accounts_of_one_person_…` |

Report excerpt (`python3 -m prices --root fixtures/synthetic-credits credits --profile synthetic-alex --as-of 2027-07-01`):

```
  Northwind Voyager curated hotel credit (synthetic)  [benefit.voyager.curated-hotel-credit]
     PUBLISHED   voyager.curated-hotel-credit (verified): 500 USD each calendar year (January 1 to December 31)
                 per transaction: maximum 250 USD; minimum stay 2 night(s); minimum transaction not stated by the source
                 rollover: none; unused allowance expires with the period
                 offer: in effect; evidence: ev-syn-voyager-credit-terms
     APPLIES     ESTABLISHED for this person on this date
     PERIOD      2027  2027-01-01 to 2027-12-31
                 2028-01-01: new period, allowance resets; unused allowance does not roll over
     ALLOWANCE   500 USD - published allowance for this period; not a personal balance
     PERSONAL    record e-hotel-2027: ACTIVE  2027-01-01 to 2027-12-31  (confirmed by Alex (synthetic) on 2027-02-11)
                 allowance 500 USD; used 250 (confirmed); remaining 250 (at least 70; 180 more may have been used, unconfirmed)

  Northwind Voyager dining credit (synthetic)  [benefit.voyager.dining-credit]
     ...
     PERIOD      2027-H2  2027-07-01 to 2027-12-31
     ALLOWANCE   150 USD - published allowance for this period; not a personal balance
     PERSONAL    NOT RECORDED - nothing is recorded for this account and period; the personal balance is not known
```

### Maintenance demonstration (abridged, `python3 scripts/demo_credits.py`)

```
=== 1. Correct a published term. The source, read again, says 200 per booking, not 250
$ tables import ...
REJECTED  EVIDENCE_REQUIRED: credits row voyager.curated-hotel-credit: this rule is in force. Put the id of the source for these terms in _evidence ...
(source row added, named in _evidence)
IMPORTED  1 changeset(s)   set_credit_terms   credits row voyager.curated-hotel-credit
before: {"amount": 500, "cycle": "calendar_year", "max_per_transaction": 250, "min_stay_nights": 2, "rollover": "none", "unit": "USD"}
after:  {"amount": 500, "cycle": "calendar_year", "max_per_transaction": 200, "min_stay_nights": 2, "rollover": "none", "unit": "USD"}

=== 2. Add a new credit in the tables
IMPORTED  2 changeset(s)   add_entity, add_candidate      New benefit rows are CANDIDATES.
     APPLIES     UNRESOLVED for this person on this date - CONFIRM: candidate c-voyager.spa-credit is not promoted
(after the reviewer promotes it)      APPLIES     ESTABLISHED      rollover: not stated by the source

=== 3. Mistakes
REJECTED  BAD_VALUE: credits row voyager.dining-credit: amount must be a number (got 'lots')
REJECTED  ... SCHEMA: ... $.credit.cycle: 'fortnightly' is not one of ['calendar_year', 'calendar_half', ...]
REJECTED  EVIDENCE_REQUIRED: changing the published terms of a rule in force needs evidence ...
REJECTED  BAD_CREDIT_SHAPE: ... max_per_transaction must be a number greater than zero, or the word none

=== 4. Opening date not on file
     PERIOD      UNRESOLVED - the opening date of account h-card-northwind-voyager is not recorded (opened_on), so its anniversary is not known
(owner: "opened on May 1, 2026")      PERIOD      2027  2027-05-01 to 2028-04-30

=== 5. What a cardholder's own account shows
     PERSONAL    NOT RECORDED - nothing is recorded for this account and period; the personal balance is not known
(period recorded, one use)      allowance 150 USD; used 40 (confirmed); remaining 110
REJECTED  USE_EXCEEDS_TRANSACTION_CAP: one use of 230 is more than the published maximum of 200 per transaction. ...
(2028-01-01)  PERIOD 2028-H1 ...  ALLOWANCE 150 USD ...  PERSONAL NOT RECORDED

=== 6. Election
     APPLIES     UNRESOLVED ... election voyager.annual-perk: no election recorded          (both credits)
(owner elects wellness)   lifestyle: NOT_AVAILABLE, "ALLOWANCE none for this person"; wellness: ESTABLISHED, ALLOWANCE 25 USD

=== 7. review 2027-09-15 -> 2027-11-05
      2027-09-30  benefit.voyager.ride-credit  period 2027-09 ends (10 USD published ...); unused allowance does not roll over; the offer ends
      2027-11-01  benefit.voyager.travel-credit  period 2026 ends (300 USD published ...); the source does not say whether unused allowance rolls over; a new period starts on 2027-11-02
lint: 0 error(s), 1 warning(s)   USE_OVER_TRANSACTION_CAP ... usage u-2027-02-10 (250) exceeds the rule's per-transaction maximum of 200
```

The last line is the system working as intended: after step 1 lowered the published maximum, another cardholder's earlier recorded use of 250 no longer fits and is surfaced for a person to look at. The owner's record is not altered.

## 5. Verification (observed)

| Requirement | Command | Observed |
|---|---|---|
| All 254 existing tests preserved and passing | `python3 -W error -m unittest discover -s tests` | `Ran 327 tests` … `OK`. No existing test file and not `tests/util.py` was changed (`git diff 8039477 -- tests` lists only the two new files) |
| Additional targeted tests | same | 73 new: 42 + 31 |
| Zero new lint errors | `python3 -m prices lint` | `lint: 0 error(s), 1 warning(s)`: the same single warning |
| Tables synchronized | `python3 -m prices tables status` | `out of date with the store: no` / `unimported edits: no` |
| Existing profile outputs preserved | `python3 scripts/compare_with_baseline.py` (vs `8039477`) | 49 commands byte-identical (status, timeline, review, goal, discovery, cards for `eric` and both synthetic profiles; both card-fixture people); `BASELINE COMPARISON: PASS` |
| Candidate quarantine intact | test `test_the_live_data_has_no_credit_terms_…`; `scripts/verify_argon_intake.py` | 113 proposed, 7 promoted earlier, 10 active rules; no rule or candidate carries a `credit` block; `ARGON INTAKE: PASS` |
| Eric's and Todd's records unchanged | `git diff 8039477 HEAD -- data profiles` | empty. (There is no Todd profile; none was created) |
| Earned-entitlement and election safeguards preserved | their tests and mutation checks | 74 earned + 36 election tests pass; `17 of 17` and `13 of 13` mutations caught |
| Mutation checks for credit safeguards | `python3 scripts/mutation_check_credits.py` | `23 of 23 mutations caught` (list below) |
| Export verification | `python3 scripts/verify_export.py` | 1,611 files exported and unpacked into a clean directory; 22 steps `ok`; `TEST F: PASS` |
| Clean offline checkout | `python3 scripts/verify_clean_checkout.py` (on `a23f3de`) | 22 steps `ok` (clone, tests, lint, tables, the fixtures rebuilt and the earned and credit ones compared with the committed copies, four demos, three mutation checks, baseline comparison, Argon intake check), checkout unmodified; `CLEAN CHECKOUT: PASS` |
| Successor harness, untouched copy | `successor_test/harness.py setup` + `evaluate` | `10 of 21 checks passed`, as before |

The 23 safeguards broken one at a time, each noticed by the tests: published allowance reported as a personal balance; missing opening date replaced by a guess; anniversary credit reset on January 1; February 29 decided by convention; the two half-years merged; a monthly credit not ending with the month; an unstated per-transaction cap reported as none; unstated rollover reported as no rollover; offer expiration ignored; a period not cut at the end of the offer; an unconfirmed last use fixing the period; no recorded use treated as available; a credit shown as applying regardless of the engine (elections bypassed); candidate terms treated as in force; records of other periods counted in this one; unconfirmed use reported as an established balance; period ends listed for credits that do not apply; the per-transaction maximum not enforced; terms of a rule in force changeable without evidence; a balance recordable against a candidate; credit period records treated as earned benefits; credit terms allowed on a rule that is not a card benefit; zero or negative amounts accepted.

**What changed for existing fixtures, stated exactly.** Adding a table means every tables directory gains an empty `credits.csv` (header line only) and its `MANIFEST.json` lists it. That applies to live `tables/`, `fixtures/synthetic-cards/tables/`, `fixtures/synthetic-earned/tables/`, and the input set `fixtures/synthetic-cards-input/`. Nothing else in those places changed, older import ids are unchanged, and the comparison script checks each of those `credits.csv` files is the header only.

## 6. Changed-file inventory (vs `8039477`)

| Area | Files |
|---|---|
| Engine code | `prices/credits.py` (new, 462), `prices/tables.py` (+104), `prices/cli.py` (+121), `prices/changes.py` (+64), `prices/lint.py` (+38), `prices/schema.json` (+28), `prices/review.py` (+23), `prices/earned.py` (+14), `prices/engine.py` (1 line) |
| Tests | new `tests/test_o_credits.py` (42), `tests/test_p_credits_pipeline.py` (31). No existing test changed |
| Fixtures | new `fixtures/synthetic_credits.py` and `fixtures/synthetic-credits/` (227 files); the empty `credits.csv` + manifest noted above |
| Scripts | new `demo_credits.py`, `mutation_check_credits.py`; updated `compare_with_baseline.py`, `verify_argon_intake.py`, `verify_export.py`, `verify_clean_checkout.py` |
| Docs | new `docs/RECURRING_CREDITS.md`, `docs/operations/OP-13-recurring-credits.md`, this file; updated `DECISIONS.md` (D-40..D-47), `SCHEMA.md`, `RELATIONAL_TABLES.md`, `ARCHITECTURE.md`, `MAINTAINER_GUIDE.md`, `README.md`, `STATUS.md`, `CONTINUATION.md` |
| Live content | `tables/credits.csv` (header only), `tables/MANIFEST.json`. `data/` and `profiles/`: no change |

## 7. Remaining limitations

**Unsupported credit structures** (full table with what each would need: `docs/RECURRING_CREDITS.md` section 6). Each stays as prose; none is approximated.

- A card year defined by statement closing dates rather than the opening date.
- The amount actually carried over under a rollover rule (the rule is stated; the personal carried amount is not computed).
- A credit that expires a set time after it was granted, such as Bilt Cash.
- Activation, enrollment or linking required before a credit works: not in the block, and card-benefit rules cannot carry a condition.
- A change of terms on a date inside one rule (works today as retire-and-add with `valid_from`).
- Per-day, per-merchant, per-category limits; eligible-merchant lists.
- A credit shared between the primary cardholder and authorized users.
- Sub-periods not aligned to the calendar; weekly cycles; multi-year periods counted in calendar years; pro-rated first or last periods.
- Multipliers, percentage earnings and portal stacking (ENG-04) and other earned-benefit periods (ENG-03): not started, as instructed.

**Other limits**

- **No real credit is structured.** The mechanism is proven on invented data only.
- **A personal balance needs one hand-made record per period.** Nothing is created automatically, because that would mean assuming an allowance. For a monthly credit this is laborious if someone wants every month tracked.
- **Dates and figures on personal records are the owner's report**; the program checks they are possible and flags disagreement with the published terms.
- **Credit flags appear in the `credits` report, `review` and `timeline`, not in `status`.**
- **A retired rule is treated as ended on every date**, earlier ones included (existing engine behaviour, unchanged).
- **Elections are per person**, as in ENG-02; the Bilt election questions were not resolved or assumed.
- **No lower-capability model has run OP-13** (nor OP-10, OP-11, OP-12).

**How Argon's credit candidates line up** (an engineering reading of the candidates' prose; nothing was entered, and Argon decides):

| Candidate | Fits the block as written? |
|---|---|
| CSR travel credit 300 | Yes: `anniversary_year`. Caveat: if Chase counts the year by statement cycle, the boundary may differ by days |
| CSR The Edit 500, 250 per booking, 2 nights | Yes: `calendar_year`, `max_per_transaction`, `min_stay_nights` |
| CSR Exclusive Tables 150 + 150 | Yes: `calendar_half`, `rollover: none` |
| CSR Lyft 10 a month to 2027-09-30 | Yes: `calendar_month`, `rollover: none`, the row's `valid_to` |
| CSR StubHub 150 + 150 to 2027-12-31 | Terms yes; the "requires activation" condition stays prose |
| CSR Select Hotel 250, 2026 only | Yes: `calendar_year` with the row's `valid_from` / `valid_to` |
| CSR Peloton 10 a month + 10X | The credit yes; the 10X half is ENG-04, so the candidate would need splitting |
| CSR trusted-traveler 120 every 4 years | `multi_year`, 4; the candidate does not say what the four years run from, so the period would be unresolved until Argon states it; "across primary and authorized users" stays prose |
| Bilt hotel credit 200 + 200, 2 nights (legacy election) | Yes: `calendar_half`, `min_stay_nights`, `rollover: none`; already governed by the ENG-02 election |
| Bilt 600 Bilt Cash at the anniversary (post-2027) | Amount and `anniversary_year` yes; Bilt Cash's own expiry does not fit |
| Bilt 200 annual Bilt Cash (legacy) | Not as written: whether "annual" is calendar or anniversary is not stated, and it expires 12 months after earning |
| Bilt Flex 4% Bilt Cash | Not a credit: ENG-04 |

## 8. Decisions for Bradley before the next commission

1. **`credits.csv` as its own table (D-46).** Argon's ENG-01 text expected credit columns on `card_benefits.csv` (or `benefits.csv`). I put them in a separate table keyed by the same row id, because most card benefits are not credits, existing headers and fixtures stay valid, and a candidate's terms can be edited while its card_benefits row stays read-only. If you or Argon prefer columns on `card_benefits.csv`, it is a contained change in `prices/tables.py`.
2. **Candidates are amended in place for credit terms (D-45).** This is an exception to "withdraw and re-add under a new id". Without it, structuring Argon's candidates would change rule ids that the Bilt election options already govern and would alter the count of proposed candidates. Every such edit is logged with a before-snapshot and the reviewer sees the terms at promotion. Confirm this is acceptable.
3. **Who enters the terms for Argon's candidates, and when.** Engineering did not, by instruction. The route is `tables/credits.csv` (OP-13). The table at the end of section 7 is a starting point only.
4. **Which unsupported structure to build first,** if any. From Argon's content the ones that bite are: activation-required credits (StubHub), per-grant expiry (Bilt Cash), and statement-cycle card years (if Chase's travel credit works that way). The first could be folded into ENG-03's work on activation windows.
5. **Still open from ENG-02:** whether Bilt's legacy credits and Flex housing option are one election or two, and what applies to accounts opened in 2027 before their first anniversary. ENG-01 assumed nothing about either.
6. **A lower-model test** of OP-10 to OP-13 on the synthetic fixtures remains the cheapest way to find out whether weaker maintainers keep "published" and "personal" apart.
