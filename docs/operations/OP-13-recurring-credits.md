# OP-13  Record or correct the terms of a recurring card credit, and what a cardholder's account shows

**ops:** `tables import` (credits.csv) or `set_credit_terms`; for a person: `record_entitlement` / `record_usage` / `correct_entry` / `revise_entitlement`, and `opened_on` via `set_holding`

**Use when:** a card benefit is a credit that comes back on a schedule (every year, half year, quarter, month, card anniversary, or every few years) and you need to write down its published terms, correct them, or record what one cardholder's own account shows for one period.

**The one idea to hold on to.** Three different things. Never fill in one from another.

| What | Where it lives | Who can say so |
|---|---|---|
| The **published terms**: how much, how often, caps, conditions | the `credit` block of the card-benefit rule; edited in `tables/credits.csv` | a cited source |
| Whether the benefit **applies to a person** | worked out by the program from their card, the rule, and any election (OP-12) | nobody types this |
| What **one person's account shows** for one period: allowance, each use | an entitlement record for that rule, account and period | the owner |

A card publishing 500 a year says nothing about what anyone has left. With no personal record the report says **NOT RECORDED**. It never says "500 remaining".

## 1. Inputs and context
- The source page for the terms, and exactly what it states. Anything it does not state is left **empty**.
- The rule id of the card benefit (`tables/card_benefits.csv`, column `id`).
- See what is recorded: `python3 -m prices credits` (published terms) and `python3 -m prices credits --profile <p>` (one person).
- For a person: their holding id of the card, the period, and what the owner says the account shows.

## 2. Permitted actions

**Published terms** (in `tables/credits.csv`: export, edit, import in one sitting; OP-10 explains the protocol)

| Column | Write | Leave empty when |
|---|---|---|
| `id` | the card_benefits row id | never |
| `amount`, `unit` | the allowance for **one period** (150 for a "300 a year in two halves" credit), and its currency | never: no amount, no row |
| `cycle` | `calendar_year`, `calendar_half` (Jan-Jun, Jul-Dec), `calendar_quarter`, `calendar_month`, `anniversary_year` (from the account's opening date), `multi_year` | never |
| `years`, `anchor` | only for `multi_year`: how many years; counted from `account_opening` or `last_use` | `anchor`: the source does not say what the years are counted from |
| `max_per_transaction` | the most one transaction or booking can earn; `none` if the source says there is no such limit | the source does not mention one |
| `min_stay_nights`, `min_transaction` | the minimum the source requires | the source does not mention one |
| `rollover` | `none` (unused amount is lost) or `allowed` | the source does not say |
| `rollover_max` | with `allowed`: the most that carries over; `none` if stated as unlimited | the source does not say |
| `note` | anything else a reader must know, in words | nothing to add |
| `_evidence` | for a rule already in force: the id of the source for this change (a `sources.csv` row) | the row is a candidate |
| `_action` | `remove` to take the structured terms off a rule (change nothing else) | otherwise |

- **Empty means "the source does not say".** Never write 0, never write `none`, never write a likely value to fill a cell.
- The start and end of the offer itself are `valid_from` / `valid_to` on the card_benefits row, not here.
- A brand-new credit: add the `card_benefits` row and the `credits` row in the same import. It enters as a candidate.
- A candidate's terms may be corrected in `credits.csv` in place. Its `card_benefits` row stays read-only until reviewed.
- The same change as a changeset: `set_credit_terms` (section 4). The block you give replaces the old one completely.
- A change of terms **from a date** (the bank raises the amount next year) is not a correction: retire the row with `ended_on` and add a new row with `valid_from` (OP-10).

**One person's account**
- The opening date of the account, for anniversary credits: `set_holding` with `opened_on` (OP-12, section 4). Ask the owner. Never use the date the card was first recorded here.
- A period on the account: `record_entitlement` with `cycle` = the period (`2027`, `2027-H1`, `2027-Q3`, `2027-07`; for an anniversary or multi-year period, the year it starts in), `effective_from` / `expires_on` and `allowance` **as the account shows them**.
- Each use: `record_usage` on that record. Remaining is computed; never type it.
- A wrong entry: `correct_entry` (the old one is kept). Wrong dates or allowance: `revise_entitlement`. (OP-11 has all four.)
- A credit counted "every N years from the last use": record the use as a period record whose `effective_from` is the date of use.

**Not permitted:** recording a balance, a use or an opening date the owner did not give; recording anything personal for a credit that is still a candidate; editing files by hand; promoting candidates (a reviewer does that).

## 3. Source and evidence requirements
The card's own terms or benefit guide. For a rule in force, every change of terms names its source in `_evidence` (or `evidence` in the changeset), even when the same page was simply read again. Personal records rest on the owner's statement in the attestation.

## 4. Output: the changeset
Table route: `python3 -m prices tables import --author "<you>" --date YYYY-MM-DD` writes the changesets for you.

By hand:
```json
{"id": "cs-YYYYMMDD-NNN-set-credit-terms", "op": "set_credit_terms", "author": "...", "date": "YYYY-MM-DD",
 "reason": "Per-booking maximum was transcribed as 250; the terms say 200.",
 "target": "<rule id>",
 "data": {"credit": {"amount": 500, "unit": "USD", "cycle": "calendar_year", "max_per_transaction": 200, "min_stay_nights": 2, "rollover": "none"}},
 "evidence": [{"id": "ev-...", "url": "...", "title": "...", "publisher": "...", "source_type": "official", "retrieved_on": "YYYY-MM-DD",
               "applies_to": ["<card id>"], "summary": "What the page says about this credit."}]}
```
Remove the terms: `"data": {"remove": true}`. For a candidate, `evidence` is optional.

A period on a person's account:
```json
{"id": "cs-YYYYMMDD-NNN-record-entitlement", "op": "record_entitlement", "author": "...", "date": "YYYY-MM-DD", "reason": "...",
 "profile": "<profile>",
 "data": {"entitlement": {"id": "e-dining-2027-h2", "rule": "<rule id>", "account": "<holding id of the card>", "cycle": "2027-H2",
                          "state": "confirmed", "effective_from": "2027-07-01", "expires_on": "2027-12-31",
                          "allowance": {"amount": 150, "unit": "USD"}, "basis": "Credit tracker on the account page"}},
 "attestation": {"by": "<owner exactly as in profile.json>", "on": "YYYY-MM-DD", "statement": "What the owner said or showed."}}
```
A use: `record_usage` with `"target": "<entitlement id>"` and `"data": {"usage": {"id": "u-...", "amount": 40, "used_on": "YYYY-MM-DD", "state": "confirmed", "basis": "..."}}`, same attestation.

## 5. Validation (done by the program)
- Terms: amount above zero; a known `cycle`; `years` and `anchor` only with `multi_year`; limits above zero or `none`; `rollover_max` only with `rollover: allowed`; only on a card-benefit rule.
- A rule in force changes only with evidence that meets the evidence policy. A candidate stays a candidate, with the same id.
- Personal: only the owner confirms; the account must be that person's own holding of that card; the period label must fit the cycle and the dates must overlap it; one record per rule, account and period; use inside the record's dates, not above the allowance, and **no single use above the published per-transaction maximum**.
- A rejected change changes nothing and prints `REJECTED` with a code.

## 6. Failure and escalation
| Message | Meaning | Do this |
|---|---|---|
| `EVIDENCE_REQUIRED` | A rule in force, and no source named | Add the source row and its id in `_evidence` |
| `BAD_VALUE`, `MISSING_VALUE`, `SCHEMA`, `BAD_CREDIT_SHAPE` | A cell is not what the column accepts | Re-read section 2. Do not pick the nearest allowed value: if the credit does not fit, stop and escalate |
| `UNKNOWN_RULE` (tables) | No card_benefits row has that id | Add that row first, or fix the id |
| `NO_CHANGE` | These are already the terms | Nothing to do |
| `UNKNOWN_RULE` (personal) | The rule has no credit terms, or is still a candidate | Stop. Nothing personal is recorded against a proposal |
| `BAD_PERIOD`, `BAD_DATES` | The period label does not fit the cycle, or the dates are another period's | Re-read the owner's statement |
| `USE_EXCEEDS_TRANSACTION_CAP` | One use is above the published maximum per transaction | Record each transaction separately. If the account really shows it, escalate |
| `USAGE_EXCEEDS_ALLOWANCE` | Use would exceed the period's allowance | Check amounts; correct the allowance first if the account shows a different one |
| `UNKNOWN_REFERENCE` on removing terms | A person's record depends on these terms | Escalate; do not remove |

In the report: `CREDIT_PERIOD_UNRESOLVED` means a date is missing (the opening date, or the last use): ask the owner; do not guess. `ALLOWANCE_DIFFERS_FROM_RULE`, `PERIOD_DIFFERS_FROM_RULE` and `USE_OVER_TRANSACTION_CAP` mean the account and the published terms disagree: tell the coordinator; one of them may need correcting.

Escalate, changing nothing, when the credit does not fit the columns (see "What is not supported" in `docs/RECURRING_CREDITS.md`): leave it as prose in `summary` and `restrictions`.

## 7. How completion is independently established
- `IMPORTED` or `APPLIED`; `python3 -m prices lint` shows 0 errors; `python3 -m prices tables status` shows `no` twice.
- `python3 -m prices credits` shows the terms you entered, and prints **not stated by the source** for every cell you left empty.
- `python3 -m prices credits --profile <p> --as-of <date>` shows the period for that date; a day after the period's end it shows the next period with PERSONAL **NOT RECORDED**.
- `python3 -m prices audit --last 5` lists the change; the record as it was is in `data/audit/previous/`.
- A worked example with every command and its output: `python3 scripts/demo_credits.py`.
