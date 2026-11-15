# Data schema

The machine-readable schema is `prices/schema.json`; `python3 -m prices lint` enforces it and the cross-record rules below. This page is the human summary.

Ids are lowercase letters, digits, `.`, `_`, `-`. A record's `id` equals its file name without `.json`. Dates are `YYYY-MM-DD`.

## Entity — `data/kb/entities/<id>.json`

| Field | Required | Notes |
|---|---|---|
| `id`, `name` | yes | Convention: `program.thing`, e.g. `marriott.titanium` |
| `kind` | yes | `program`, `card`, `currency`, `status`, `benefit`, `action`, `capability`, `organization`, `network_tier`, `election` |
| `program` | no | Id of the parent program entity |
| `tags` | no | Must exist in `vocab.json` `tags`. Used by goal queries |
| `how` | no | For `action`: what the person must do |
| `economics` | no | For `capability`: free-text notes (`points_price`, `cash`, `time`, `risk`); optional numeric `points` + `currency` |
| `card` | no | For `card` only: who plays each role. Keys `cobrand_partner`, `program_manager`, `issuer`, `capital_provider`, `network` (organization ids) and `network_tier` (a `network_tier` id); optional `annual_fee_usd`. Missing key = not recorded; `null` = recorded as none. **Descriptive only: the engine derives nothing from it** |
| `network` | no | For `network_tier` only: the organization that runs the network |
| `sources` | no | Evidence ids for the entity's primary documents. Added to, never removed from |
| `election` | `election` only, mandatory | One option of a cardholder election group: `group`, `card`, `governs` (rule or candidate-rule ids that apply only under this option), optional `opened_before`, `default_before_anniversary`, `starts_at_anniversary`, `elect_before_anniversary` (each a date D: "the first card anniversary on or after D"), `source_note`. Revising it needs a reviewer. See `docs/ELECTIONS.md` |

`election` = one option the cardholder chooses between; a person holds it to record their election (OP-12). `action` = something the person can do (enroll, link, register, complete nights). `capability` = something useful the person can do with what they have (e.g. book a given award). `organization` and `network_tier` cannot be held by a person and cannot appear in a deriving rule.

## Rule — `data/kb/rules/<id>.json`

| Field | Required | Notes |
|---|---|---|
| `id`, `summary` | yes | |
| `kind` | yes | Deriving: `grants`, `acquire`, `transfer` (see Architecture). Non-deriving: `baseline` (exactly tier → benefit), `excludes` (exactly card → benefit). See `docs/RELATIONAL_TABLES.md` |
| `superseded_by` | `excludes` only, optional | The benefit the card has instead |
| `credit` | `grants` card-benefit rules only, optional | Structured terms of a recurring credit. See "Credit block" below and `docs/RECURRING_CREDITS.md`. Changed only by `set_credit_terms` or `tables/credits.csv` |
| `earn` | `earns` only, mandatory | See "Earn block" below. An `earns` rule is public knowledge only: `when` must be exactly `{"holds": <card>}`, `output` a benefit or status, and the engine never derives from it directly (`docs/EARNED_ENTITLEMENTS.md`) |
| `output` | yes | Entity id produced |
| `when` | yes | Condition (below) |
| `retention` | `acquire` only, mandatory | `{mode: fixed_term | while_qualified | unknown, retain_when?, note?}` |
| `transfer` | `transfer` only, mandatory | `{from, ratio?, note?}` |
| `valid_from`, `valid_to` | no | When the rule is in effect |
| `restrictions`, `open_questions` | no | Lists of sentences |
| `value_note` | no | Plain-language worth and caveats |
| `evidence` | yes | List of evidence ids (may be empty only if unverified) |
| `verification` | yes | `{status: verified | unverified | retired, last_verified, review_by}` |

### Credit block (rules of kind `grants` that say a card carries a benefit)

A key that is absent means **the source does not say**. It is never read as zero, unlimited or unrestricted.

| Field | Required | Notes |
|---|---|---|
| `amount`, `unit` | yes | Allowance for **one period** (a number above zero) and its currency |
| `cycle` | yes | `calendar_year`, `calendar_half`, `calendar_quarter`, `calendar_month`, `anniversary_year`, `multi_year` |
| `years` | `multi_year` only | Whole number, 2 or more |
| `anchor` | `multi_year` only, optional | `account_opening` or `last_use`. Absent: the period is unresolved |
| `max_per_transaction` | no | A number above zero, or `none` (the source says there is no limit) |
| `min_stay_nights`, `min_transaction` | no | Minimum stay (whole nights) or transaction amount |
| `rollover` | no | `none` (unused amount is lost) or `allowed` |
| `rollover_max` | only with `rollover: allowed` | A number, or `none` (stated as unlimited) |
| `note` | no | Free text |

The offer's effective and expiration dates are the rule's `valid_from` / `valid_to`.

### Earn block (rules of kind `earns`)

| Field | Required | Notes |
|---|---|---|
| `measure` | yes | Name of what is counted, e.g. `voyager.qualifying-spend`. Progress is recorded against this name |
| `period` | yes | `calendar_year` (the only value supported) |
| `threshold` | yes | Number greater than zero. `unit` optional (display only) |
| `activation` | yes | `automatic` or `required`. `activation_action` (an `action` entity) only with `required` |
| `term` | yes | How long the benefit lasts, as the source states it: `{ends: fixed, year_offset, month, day}` or `{ends: fixed, year_offset, month, month_end: true}` or `{ends: not_stated, note?}`. `year_offset` counts from the qualifying year |
| `allowance` | no | `{amount, unit}` for a consumable credit |

The rule's own `valid_from` / `valid_to` say which qualifying periods the offer covers. They never end a benefit someone already has.

## Condition

Exactly one of:

```json
{"holds": "entity.id"}
{"metric": "metric.id", "gte": 20}
{"all": [ ...conditions ]}
{"any": [ ...conditions ]}
{"not": {"holds": "entity.id"}}
```

## Evidence — `data/kb/evidence/<id>.json`

`id`, `url`, `title`, `publisher`, `source_type` (`official`, `reputable_secondary`, `community`, `owner_document`, `synthetic`), `retrieved_on`, `summary` (own words), optional `notes`, optional `applies_to` (entity ids the document is specifically about, e.g. the card whose guide it is). Evidence is never edited after creation.

## Holding — `profiles/<p>/holdings/<id>.json`

| Field | Required | Notes |
|---|---|---|
| `id`, `entity` | yes | |
| `state` | yes | `confirmed` (needs `confirmed_on`, `confirmed_by` = owner), `unconfirmed`, `ended`, `withdrawn` (entered by mistake: kept, never in effect; `withdrawn_on` set by `end_holding` with `withdrawn: true`) |
| `valid_from`, `valid_to` | no | `valid_to` is the expiry. Give it for every status |
| `opened_on` | no | Cards only: the account opening date. Card anniversaries (election terms) are computed from it, never from `valid_from` |
| `acquired_via`, `acquired_on` | no | Rule id through which it was obtained; activates retention checks |
| `quantity` | no | Balance, for currencies |

## Metric — `profiles/<p>/metrics/<id>.json`

`id`, `value`, `as_of`, `state` (`confirmed` / `unconfirmed`). A tracked number such as nights or spend. A metric whose `as_of` is after the query date is treated as not recorded on that date (D-28). For progress toward an earned benefit use a qualification, not a metric.

## Qualification — `profiles/<p>/qualifications/<id>.json`

One person's progress on one of their own accounts, for one measure, in one qualifying year. Written only by `record_progress` and `correct_entry`.

| Field | Required | Notes |
|---|---|---|
| `id` | yes | `q-<account>-<measure>-<cycle>` (generated) |
| `account` | yes | Id of a holding of the card in the same profile |
| `measure`, `cycle` | yes | The rule's measure; the four-digit qualifying year |
| `readings` | yes | Append-only list. Each: `id`, `value`, `observed_on` (date the figure refers to, or `unknown`), `value_kind` (`exact` default, `at_least`; undated readings must be `at_least`), `final` (year-end total, dated the last day of the year), `state` (`confirmed` / `unconfirmed` / `superseded`), `confirmed_by`, `confirmed_on`, `basis`, `superseded_by`, `changeset` |

## Entitlement — `profiles/<p>/entitlements/<id>.json`

One earned benefit as it actually sits on one account, **or one allowance period of a recurring credit** as the account shows it. Written only by `record_entitlement`, `revise_entitlement`, `record_usage` and `correct_entry`. For a recurring credit: `rule` is a rule in force with a `credit` block, `cycle` is the period label (`2027`, `2027-H1`, `2027-Q3`, `2027-07`; for an anniversary or multi-year period, the year it starts in), `allowance` is required, and the record feeds the credits report only (it never makes the benefit held).

| Field | Required | Notes |
|---|---|---|
| `id` | yes | |
| `rule`, `entity` | yes | The `earns` rule and its output. Cannot be revised |
| `account`, `cycle` | yes | The person's own card holding; the qualifying year it was earned in. Cannot be revised |
| `state` | yes | `confirmed` (owner attestation; sets `confirmed_by`, `confirmed_on`), `unconfirmed`, `superseded` (withdrawn, kept) |
| `effective_from`, `expires_on` | yes | A date or the word `unknown`. What the account shows, never copied from the rule |
| `ended_on`, `end_reason` | no | Ended early |
| `allowance` | credits only | `{amount, unit}`. Never reduced; remaining is computed |
| `usage` | no | Append-only list. Each: `id`, `amount`, `used_on` (date or `unknown`), `state`, `confirmed_by`, `confirmed_on`, `basis`, `superseded_by`, `changeset` |
| `basis`, `notes` | no | |

## Profile — `profiles/<p>/profile.json`

`id`, `label`, `synthetic` (true/false), `owner` (the only name whose attestation confirms holdings), optional `valuations` (`{currency id: cents per point}`, the owner's own assumptions), `notes`.

## Candidate — `data/candidates/<id>.json`

`id`, `status` (`proposed`, `promoted`, `rejected`), `created_on`, `proposed_rule` (a rule without evidence ids or verification), `proposed_entities`, `evidence` (full evidence objects), `search_path`, `open_questions`, optional `mentions`, `run`, `review`.

## Observation — `data/observations/<id>.json`

`id`, `type` (`promotion`, `availability`), `summary`, `tags`, `checked_on`, `valid_to` (mandatory), `url`, `publisher`, optional `valid_from`, `confirmed_by`.

## Discovery run — `data/discovery_runs/<id>.json`

`id`, `date`, `mode`, `profile`, `executor`, `tasks`, `steps` (`query`, `finding`, optional `sources_seen`), `cells` (`cell`, `outcome`, `candidates`, `note`), optional `extraction`, `verification`, `mentions`.

## Coverage ledger — `data/coverage/ledger.json`

`{"cells": {"<entity>|<question>": {last_run, run, outcome, candidates, note}}}`. Written only by `record_discovery_run`.

## Vocabulary — `data/kb/vocab.json`

| Key | Purpose |
|---|---|
| `tags` | Allowed tags, each with `keywords` used to match goal text |
| `questions` | Discovery question templates |
| `goal_research` | External research tasks appended to goal reports |
| `evidence_policy` | What can verify a rule |
| `promotion_reviewers` | Who may promote candidates |
| `seeded_signatures` | Relationships supplied in the commissioning brief (not counted as discoveries) |
| `watchlist` | Program names to investigate |

Vocab is edited by reviewers, not through changesets. Run the tests after any edit.

## Changeset

Fields: `id`, `op`, `author`, `date`, `reason`; then per operation `target`, `profile`, `data`, `evidence`, `attestation`. Templates are on the cards in `docs/operations/`.

## Audit — `data/audit/`

`log.jsonl`: one line per attempted changeset (`applied` or `rejected`, with errors, changed paths, before/after digests). `changesets/<id>.json`: a copy of every applied changeset. `previous/<id>.json`: every record that changeset replaced, as it was before (kept for changesets applied from 2026-11-14 on). Replaying those copies in log order over the starting data reproduces the current data exactly; `successor_test/harness.py` uses this to detect hand edits.

## Tables — `tables/*.csv`

Generated view of the store and authoring input. Columns, ownership and rules: `docs/RELATIONAL_TABLES.md`. Not a record type: nothing is read from them except through `python3 -m prices tables import`.

## Engine flags

| Code | Meaning | Usual response |
|---|---|---|
| `STALE_RULE` | Verified rule past `review_by` | OP-01 |
| `EXPIRED_HOLDING` | Holding past `valid_to` | OP-07 with the owner |
| `UNCONFIRMED_HOLDING` | Recorded, not confirmed | OP-07 with the owner |
| `CONFLICTING_HOLDINGS` | Two records disagree | Escalate |
| `RETENTION_CONDITION_FAILED` | Acquired status; rule says it needs a qualification that is gone | Owner confirms account state |
| `RETENTION_TERMS_UNKNOWN` | Acquired status; source lapsed; terms unknown | Research terms; owner confirms |
| `SOURCE_LAPSED_FIXED_TERM` | Status safe until expiry but cannot be renewed the same way | Plan renewal |
| `ACQUISITION_RULE_MISSING` | `acquired_via` points nowhere | Escalate |
| `NEGATIVE_CYCLE` | Rule excluded for circular exclusion | Escalate |
| `CREDIT_PERIOD_UNRESOLVED`, `ALLOWANCE_DIFFERS_FROM_RULE`, `PERIOD_DIFFERS_FROM_RULE`, `USE_OVER_TRANSACTION_CAP` (and `CREDIT_USE_UNCONFIRMED`, `UNCONFIRMED_ENTITLEMENT`, `CONFLICTING_ENTITLEMENTS` for a credit period) | Recurring credits; shown by `python3 -m prices credits --profile <p>`, not by `status`. Meanings: OP-13 section 6 | OP-13 with the owner |
| `ELECTION_NOT_RECORDED`, `CONFLICTING_ELECTIONS`, `UNCONFIRMED_ELECTION`, `ELECTION_START_NOT_RECORDED`, `ANNIVERSARY_NOT_RECORDED`, `ELECTION_NOT_PERMITTED`, `ELECTION_TERMS_UNVERIFIED`, `MULTIPLE_CARD_ACCOUNTS`, `ELECTION_WITHOUT_CARD` | Cardholder elections; none of the group's options is applied (except `ELECTION_TERMS_UNVERIFIED`, info). Meanings: OP-12 section 5 | OP-12 with the owner |
| `QUALIFICATION_NOT_RECORDED`, `CONFLICTING_QUALIFICATION`, `CONFLICTING_PROGRESS`, `CONFLICTING_ENTITLEMENTS`, `QUALIFICATION_OUTCOME_NOT_RECORDED`, `UNCONFIRMED_ENTITLEMENT`, `ENTITLEMENT_UNRESOLVED`, `CREDIT_USE_UNCONFIRMED`, `EXPIRED_ENTITLEMENT`, `CREDIT_LAPSED_UNUSED`, `ACCOUNT_NOT_HELD`, `TERM_DIFFERS_FROM_RULE`, `ALLOWANCE_DIFFERS_FROM_RULE` | Earned benefits. Meanings: `docs/EARNED_ENTITLEMENTS.md` section 5 | OP-11 with the owner; escalate conflicts |
