# Recurring card credits (ENG-01)

Many card benefits are credits that come back on a schedule: 300 a year from the account anniversary, 500 a calendar year with a cap per booking, 150 in each half of the year, 10 a month. Until now PRICES held their mechanics only as prose. This document says how they are now structured, computed and reported. How to do the work: [operations/OP-13-recurring-credits.md](operations/OP-13-recurring-credits.md). Why: [DECISIONS.md](DECISIONS.md) D-40 to D-47. Fields: [SCHEMA.md](SCHEMA.md).

## 1. Three layers

| Layer | Record | Says |
|---|---|---|
| **Published terms** | `credit` block on the `grants` rule "card C carries benefit B" (a `card_benefits` row) | Allowance per period, the cycle, per-transaction maximum, minimums, rollover. Sourced and reviewed with the rule |
| **Applies to a person** | nothing stored: the engine's ordinary answer for `have:<benefit>` | Card held and confirmed, rule verified and in effect, election satisfied (ENG-02) |
| **Personal balance** | an entitlement record for (rule, account, period) with `allowance` and `usage` | What the owner's account shows for that one period |

One representation each. The offer's effective and expiration dates are the rule's existing `valid_from` / `valid_to`; the `credit` block has no dates of its own. A benefit earned by reaching a threshold keeps its allowance in `earn.allowance` (earned benefits); a `credit` block is refused on anything but a `grants` card-benefit rule.

**A published allowance is never a personal balance.** With no personal record the report says `NOT RECORDED`. Adding or changing a `credit` block changes no engine answer for anyone: it describes the credit; it grants and withholds nothing.

## 2. The credit block

| Field | Meaning | Absent means |
|---|---|---|
| `amount`, `unit` | Allowance for one period, and its currency | (required) |
| `cycle` | `calendar_year`, `calendar_half`, `calendar_quarter`, `calendar_month`, `anniversary_year`, `multi_year` | (required) |
| `years` | `multi_year` only: length of the period, 2 or more | (required for `multi_year`) |
| `anchor` | `multi_year` only: `account_opening` or `last_use` | the source does not say what the years are counted from: the period is unresolved |
| `max_per_transaction` | Number, or `none` (the source says there is no limit) | the source does not say |
| `min_stay_nights`, `min_transaction` | Minimum stay or transaction amount | the source states no minimum |
| `rollover` | `none` or `allowed` | the source does not say |
| `rollover_max` | With `allowed`: number, or `none` (stated as unlimited) | the source does not say |
| `note` | Free text | |

**Absent always means "the source does not say"** and is printed as "not stated by the source". It is never read as zero, unlimited or unrestricted. `none` is a statement by the source and is kept apart from absent.

A credit described as "300 a year in two halves" is `amount: 150`, `cycle: calendar_half`: the halves are separate periods. The report derives "at most 300 in a calendar year" for display.

## 3. Periods

| Cycle | Period containing a date | Needs |
|---|---|---|
| `calendar_year` | January 1 to December 31 | nothing |
| `calendar_half` | January 1 to June 30; July 1 to December 31 | nothing |
| `calendar_quarter` | the calendar quarter | nothing |
| `calendar_month` | the calendar month (leap years included) | nothing |
| `anniversary_year` | from the anniversary of the account's opening date to the day before the next | `opened_on` on the person's card holding |
| `multi_year`, `account_opening` | N-year blocks counted from the opening date | `opened_on` |
| `multi_year`, `last_use` | from the last recorded use for N years; after that, open until the next use | an owner-confirmed, dated record of the last use |

Rules that do not bend:

- **A period that depends on a date nobody recorded is UNRESOLVED.** No `opened_on`: the anniversary period is unresolved (flag `CREDIT_PERIOD_UNRESOLVED`). `opened_on` is never inferred from `valid_from`. No recorded last use: unresolved, not "available".
- **An account opened on February 29** has no anniversary day in other years. On February 28 of such a year the period is unresolved; from March 1 it is known, with a note that it may begin or end a day differently.
- **The offer's dates cut the period.** A period that runs past `valid_to` ends on `valid_to` and is the last one; the published amount is shown as is and is **not pro-rated**. After `valid_to` there is no period and no allowance, and the benefit itself is NOT_AVAILABLE.
- **Reset** is the first day of the next period. What happens to an unused amount is printed from `rollover`: lost, carried over (up to the stated maximum), or "the source does not say".
- Labels: `2027`, `2027-H1`, `2027-Q3`, `2027-07`. For anniversary and multi-year periods the label is the year in which the period starts.

## 4. One person

`python3 -m prices credits --profile <p> [--as-of D] [--card C] [--until D] [--candidates]` prints, for each card account and each structured credit:

- `PUBLISHED` - the terms, the offer's dates, the evidence.
- `APPLIES` - the engine's status for this person on this date, with what is missing if it is not ESTABLISHED, and the election it depends on.
- `PERIOD` - the period for this date and its account, the next reset, and what happens to an unused amount; or UNRESOLVED with the reason.
- `ALLOWANCE` - the published amount for the period, labelled "not a personal balance". Not printed when the benefit does not apply to the person.
- `PERSONAL` - the owner's record for this period, if there is one: allowance, confirmed use, remaining (a range when some use is unconfirmed). Otherwise `NOT RECORDED`.

Without `--profile` the command prints published terms only. `--until` lists periods ending up to a date. `--candidates` also shows terms on candidates awaiting review, marked UNRESOLVED; nothing personal can be recorded against them.

`review` and `timeline` list each allowance period that ends in the window, on its last day, for credits that apply to the person (key `credit_periods`, present only when there is something to list).

### Elections (ENG-02)

A credit that is one side of a cardholder election is an ordinary credit rule governed by an election option. `APPLIES` comes from the engine, so: no election recorded, neither credit is established; one recorded, only that one; contradictory records, neither. If a credit applies today but will not on the last day of the current period (for example the Bilt 2027 transition at the account's anniversary), the report says the period may be cut short.

### Personal records

The personal layer reuses the earned-benefit record and operations (`record_entitlement`, `record_usage`, `correct_entry`, `revise_entitlement`, owner attestation, append-only use). One record is one period on one account. Differences from an earned benefit:

- `rule` names a rule **in force** with a `credit` block (never a candidate); `cycle` is the period label; `allowance` is required.
- The record feeds the report only. It never makes the benefit held: the rule and the election decide that.
- A single use above the published `max_per_transaction` is refused.
- Each period stands alone. A record for January-June says nothing about July-December; a used-up period does not make the benefit unavailable.

Flags in the credits report: `CREDIT_PERIOD_UNRESOLVED`, `CREDIT_USE_UNCONFIRMED`, `UNCONFIRMED_ENTITLEMENT`, `CONFLICTING_ENTITLEMENTS`, `ALLOWANCE_DIFFERS_FROM_RULE` (info), `PERIOD_DIFFERS_FROM_RULE` (info), `USE_OVER_TRANSACTION_CAP`.

## 5. Authoring

- **Tables.** `tables/credits.csv` has one row per card_benefits row that has terms (same `id`). It is exported from the store and compiled into changesets on import, like every table. A new card benefit and its credits row in one import become one candidate. A changed row becomes one `set_credit_terms`. `_action = remove` takes the terms off. A rule in force needs a source id in `_evidence`.
- **Changeset.** `set_credit_terms`, target = the rule id. For a rule in force: evidence meeting the evidence policy is required, the before-snapshot keeps the old terms, `revert_changeset` restores them. For a candidate: no reviewer and no new evidence needed; its id and status do not change, so nothing that refers to it (an election's `governs`) breaks. Promotion carries the terms into the rule.
- Terms are replaced as a whole block. A key that is left out goes back to "not stated".

## 6. What is not supported

Each of these stays as prose in `summary` / `restrictions` (and `note`) until built. None is approximated.

| Structure | Why it does not fit | What would be needed |
|---|---|---|
| A card year defined by statement closing dates rather than the opening date | Only `opened_on` anniversaries are computed; the boundary can differ by days | A per-account cycle-date field |
| The amount actually carried over under `rollover: allowed` | Depends on the person's unused amount in the previous period | Chaining period records; today the owner's record states the allowance the account shows |
| A credit that expires N months after it was granted (for example Bilt Cash) | Expiry belongs to each grant, not to a calendar period | A per-grant term, as earned benefits have |
| Terms that change on a date within one rule | One block per rule | Retire and add a new rule with `valid_from` (works today, OP-10) |
| Activation, enrollment or linking required before the credit works | Card-benefit rules are `{holds: card}` only; there is no activation in the block | A condition on the rule, or an activation field as on `earns` rules |
| Per-day, per-merchant or per-category limits; lists of eligible merchants | One per-transaction maximum only | More fields; today: `restrictions` |
| A credit shared by the primary cardholder and authorized users | Every record belongs to one person and one account | The household-sharing decision (open since the first commission) |
| Half-years, quarters or months not aligned to the calendar; weekly cycles | Calendar periods only | New cycle values |
| A first year that is pro-rated; an amount reduced when a period is cut short | The published amount is shown as is | Source-specific rules |
| Multi-year periods counted in calendar years | Anchors are the opening date or the last use | A calendar anchor |
| Percentage earnings, multipliers, portal stacking | Not credits | ENG-04 (not started) |
| Credits earned by reaching a spending threshold in other period types | Earned benefits, calendar year only | ENG-03 (not started) |

Also unchanged: a retired rule is treated as ended on every date, earlier ones included; queries are valid-time, not record-time; the program cannot check an owner's figures against an account.
