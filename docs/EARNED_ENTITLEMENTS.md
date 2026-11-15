# Earned benefits: public rule, personal achievement, current entitlement

Some benefits are not included with a card. They are earned by reaching a threshold in a period ("75,000 in purchases in a calendar year"), sometimes need a separate activation step, and then run on their own dates. This document says how PRICES represents that without ever assuming that a person has something merely because it is on offer or because a threshold was met.

How to do the work: [operations/OP-11-earned-benefits.md](operations/OP-11-earned-benefits.md). Why it was built this way: [DECISIONS.md](DECISIONS.md) D-24 to D-31. Field lists: [SCHEMA.md](SCHEMA.md).

## 1. Three layers, three kinds of record

| Layer | Record | Says | Says nothing about |
|---|---|---|---|
| **Public rule** | rule of kind `earns` in `data/kb/rules/` | On this card, reaching this threshold on this measure in one period earns this benefit; how long it lasts; whether activation is needed; any allowance. Sourced and reviewed like every rule | Any person |
| **Personal achievement** | `profiles/<p>/qualifications/<id>.json` | This person's dated readings of the measure, on one of their own accounts, in one qualifying year | Whether anything landed on the account |
| **Current entitlement** | `profiles/<p>/entitlements/<id>.json` | The benefit as it actually sits on that account: its own start, its own expiry, its allowance, each use | The public rule's general term |

What follows from what:

```
public rule on offer                         -> nothing personal
readings at or above the threshold           -> ELIGIBLE        (engine: can_get ESTABLISHED, have CONDITIONAL)
confirmed entitlement record, inside its dates -> HELD           (engine: have ESTABLISHED)
nothing recorded                             -> nothing derived (NOT_AVAILABLE)
```

Each layer is scoped. A reading belongs to one person, one account, one measure, one year. An entitlement belongs to one person, one account, one rule, one year. Two accounts are never added together, one person's records never affect another's, and one year's figure never counts toward the next.

## 2. Time

Every answer is for a date (`--as-of`). The model is **valid time**: "what was true on that date, as far as the records on file now show".

- **A reading counts from the date it refers to**, never earlier. Asked about a date before the reading, the program does not use it as a fact. If a later reading is *at or above* the threshold, the earlier date is **unknown** (UNRESOLVED), not achieved: the threshold was crossed at some unrecorded time. If a later reading is still *below* the threshold, earlier dates are known to be below, because cumulative progress in a year does not go down.
- **The crossing day is never invented.** "At or above on October 31" is all a statement shows. The report says so.
- **A date may be the word `unknown`.**
  - A reading with no date ("I reached it some time in 2026") must be `at_least`. It is relied on from the day its owner confirmed it, or from the last day of the year if that came first. Before then: unknown.
  - An entitlement with an unknown start is UNRESOLVED before the day its owner confirmed it active.
  - An entitlement with an unknown expiry is UNRESOLVED after that day. It is never quietly kept and never quietly dropped.
- **Three different end dates, never mixed.** The qualifying period ends (December 31). The public offer may end (`valid_to` on the rule). The personal entitlement expires (`expires_on` on the record). An entitlement that exists keeps running on its own dates after the qualifying year ends and after the offer is withdrawn, retired or flagged, and it stops on its own expiry even if the rule is still on offer.
- **Each year is independent.** 2026 and 2027 have separate readings, separate achievements and separate entitlement records. Records from two years may overlap in time; they are listed separately, a credit from one is never added to a credit from the other, and a status is simply held while at least one record is active.

## 3. States

Achievement, per account, measure and year:

| State | Meaning |
|---|---|
| `NOT_RECORDED` | No progress on file for this year |
| `NOT_STARTED` | The query date is before the year begins |
| `BELOW` | Known to be below on this date |
| `UNCERTAIN` | Not established on this date: the only at/above reading is later, undated, or unconfirmed |
| `ACHIEVED` | A confirmed reading at or above the threshold exists on or before this date. **Means eligible** |
| `NOT_QUALIFIED` | The year's final figure is below the threshold |
| `INCOMPLETE` | The year is over and no final figure is on file |
| `CONFLICT` | Readings contradict each other across the threshold. Reported, never resolved by picking one |

Entitlement, per benefit:

| State | Meaning | Engine `have` |
|---|---|---|
| `NOT_OFFERED` | The public offer does not cover this year | - |
| `NOT_EARNED` | Not achieved | NOT_AVAILABLE |
| `UNRESOLVED` | Achievement uncertain, or the record is unconfirmed, conflicting, or missing a date that matters on this date | UNRESOLVED |
| `EARNED_NOT_CONFIRMED` | Eligible; nothing recorded on the account | CONDITIONAL |
| `ACTIVATION_REQUIRED` | Eligible; the separate activation step is not recorded as done | CONDITIONAL (needs the action) |
| `NOT_YET_EFFECTIVE` | A record exists and starts later | as eligibility stands |
| `ACTIVE` | Confirmed record, inside its own dates, something left to use | **ESTABLISHED** |
| `EXHAUSTED` | Credit fully used | NOT_AVAILABLE |
| `EXPIRED` / `ENDED` | Past its own expiry / ended early on a recorded date | NOT_AVAILABLE |
| `LAPSED_UNCLAIMED` | Achieved, never recorded on the account, and the rule's term is over | NOT_AVAILABLE |

Only `ACTIVE` means usable.

## 4. Credits

A consumable benefit has three separate numbers: the **allowance** (on the record, never reduced), **used** (the sum of confirmed uses dated on or before the query date) and **remaining** (always computed, never stored). Unconfirmed or undated use is shown as *possibly used* and turns remaining into a range ("remaining 100, at least 40"). If unconfirmed use might have emptied the credit, it is UNRESOLVED, not available.

## 5. Flags raised for a person

| Code | Meaning |
|---|---|
| `QUALIFICATION_NOT_RECORDED` | An entitlement is confirmed, but reaching the threshold is not established on file. It stands on the owner's word; the gap is shown |
| `CONFLICTING_QUALIFICATION` | An entitlement is recorded, but the year's progress says not qualified. Held as UNRESOLVED |
| `CONFLICTING_PROGRESS` | Readings contradict each other |
| `CONFLICTING_ENTITLEMENTS` | Two live records for the same benefit, account and year |
| `QUALIFICATION_OUTCOME_NOT_RECORDED` | Year over, no final figure |
| `UNCONFIRMED_ENTITLEMENT`, `ENTITLEMENT_UNRESOLVED` | Recorded but not confirmed / a date that matters is unknown |
| `CREDIT_USE_UNCONFIRMED` | Some use is not confirmed; remaining is a range |
| `EXPIRED_ENTITLEMENT` | Expired or ended, and no later year's record replaces it |
| `CREDIT_LAPSED_UNUSED` | A credit expired with something left on it |
| `ACCOUNT_NOT_HELD` | An entitlement is active but the card account is no longer held. The program does not guess whether it survived |
| `TERM_DIFFERS_FROM_RULE`, `ALLOWANCE_DIFFERS_FROM_RULE` | (info) The account's date or allowance differs from the rule's general statement. The personal value is used |

## 6. Reading the report

```
python3 -m prices earned --profile <p> [--as-of YYYY-MM-DD] [--account <holding id>] [--cycle YYYY] [--detail] [--json]
```

For each account, each qualifying year and each benefit it prints four lines:

- `PUBLIC RULE` - the rule, its threshold, term, activation, allowance, evidence, and whether the offer covers this year.
- `ACHIEVEMENT` - the state and the reading it rests on.
- `ENTITLEMENT` - the state, then each account record with its dates, who confirmed it and when, and the credit numbers.
- `WHOLE PERSON` - the engine's answer for that benefit across all of the person's accounts and years on this date, and the record or rule it comes from.

`--detail` adds every reading (including superseded ones), the source documents, and every use. `--json` carries the same chain: rule, evidence, qualifying readings with their changeset ids, account records, result. `python3 -m prices explain --profile <p> <entity>` shows the same chain inside the engine (`entitlement:<id>` or `qualification:<id>`). `status` lists earned benefits on record in one short section; `timeline` shows each date on which something earned starts, ends or changes.

## 7. How facts get in, and how they are corrected

Only through changesets ([OP-11](operations/OP-11-earned-benefits.md)): `record_progress`, `record_entitlement`, `record_usage`, `correct_entry`, `revise_entitlement`. `confirmed` is set only from the profile owner's own attestation; anyone may record `unconfirmed`, which counts as UNRESOLVED. Readings and uses are append-only: a correction marks the old entry `superseded` and adds a new one. Every applied changeset leaves a log line, a copy of the changeset and a before-snapshot of each record it replaced; `revert_changeset` restores them. The CSV tables carry none of this and the table importer cannot create it. Holding a card creates no progress and no entitlement.

## 8. What is deliberately not here (known limits)

- **Calendar-year periods only.** Cardmember-year, rolling-12-month and program-year cycles are not modelled. The `period` field exists so they can be added; the engine refuses any other value today.
- **No refunds or clawbacks.** Progress in a year is assumed never to decrease. A lower later reading across the threshold is reported as a conflict for a person to resolve.
- **Valid time, not record time.** The system answers "what was true on that date, as now known", not "what did the system believe on that date". The audit trail holds the history, but queries do not replay it.
- **Activation is recorded by the entitlement record**, with the owner's attestation. Holding the activation `action` entity separately does not activate anything.
- **One threshold, one measure, one card per rule.** No tiered thresholds in one rule, no combined spend across cards or people, no pooled household qualification.
- **No sharing.** Holder, authorized user, guest and companion are not distinguished here because sharing was out of scope; every record belongs to exactly one person and one of that person's accounts.
- **Earned benefits are not in the CSV tables**, the card applicability matrix, or goal reports. Earn rules are authored as candidates (OP-03) and promoted by a reviewer.
- **Dates on an entitlement are whatever the owner reports.** The program checks that they are possible, flags when they differ from the rule's stated term, and does not verify them against any account.
- **Names are labels.** `confirmed_by` is checked against the profile's `owner` string; the system cannot authenticate who typed it. This is the same boundary as holdings (D-06).
- **The legacy `metric` condition** now refuses to use an observation dated after the query date (D-28). No live rule or profile used metrics, so no existing output changed.
