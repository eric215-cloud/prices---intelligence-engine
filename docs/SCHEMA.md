# Data schema

The machine-readable schema is `prices/schema.json`; `python3 -m prices lint` enforces it and the cross-record rules below. This page is the human summary.

Ids are lowercase letters, digits, `.`, `_`, `-`. A record's `id` equals its file name without `.json`. Dates are `YYYY-MM-DD`.

## Entity — `data/kb/entities/<id>.json`

| Field | Required | Notes |
|---|---|---|
| `id`, `name` | yes | Convention: `program.thing`, e.g. `marriott.titanium` |
| `kind` | yes | `program`, `card`, `currency`, `status`, `benefit`, `action`, `capability`, `organization`, `network_tier` |
| `program` | no | Id of the parent program entity |
| `tags` | no | Must exist in `vocab.json` `tags`. Used by goal queries |
| `how` | no | For `action`: what the person must do |
| `economics` | no | For `capability`: free-text notes (`points_price`, `cash`, `time`, `risk`); optional numeric `points` + `currency` |
| `card` | no | For `card` only: who plays each role. Keys `cobrand_partner`, `program_manager`, `issuer`, `capital_provider`, `network` (organization ids) and `network_tier` (a `network_tier` id); optional `annual_fee_usd`. Missing key = not recorded; `null` = recorded as none. **Descriptive only: the engine derives nothing from it** |
| `network` | no | For `network_tier` only: the organization that runs the network |
| `sources` | no | Evidence ids for the entity's primary documents. Added to, never removed from |

`action` = something the person can do (enroll, link, register, complete nights). `capability` = something useful the person can do with what they have (e.g. book a given award). `organization` and `network_tier` cannot be held by a person and cannot appear in a deriving rule.

## Rule — `data/kb/rules/<id>.json`

| Field | Required | Notes |
|---|---|---|
| `id`, `summary` | yes | |
| `kind` | yes | Deriving: `grants`, `acquire`, `transfer` (see Architecture). Non-deriving: `baseline` (exactly tier → benefit), `excludes` (exactly card → benefit). See `docs/RELATIONAL_TABLES.md` |
| `superseded_by` | `excludes` only, optional | The benefit the card has instead |
| `output` | yes | Entity id produced |
| `when` | yes | Condition (below) |
| `retention` | `acquire` only, mandatory | `{mode: fixed_term | while_qualified | unknown, retain_when?, note?}` |
| `transfer` | `transfer` only, mandatory | `{from, ratio?, note?}` |
| `valid_from`, `valid_to` | no | When the rule is in effect |
| `restrictions`, `open_questions` | no | Lists of sentences |
| `value_note` | no | Plain-language worth and caveats |
| `evidence` | yes | List of evidence ids (may be empty only if unverified) |
| `verification` | yes | `{status: verified | unverified | retired, last_verified, review_by}` |

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
| `state` | yes | `confirmed` (needs `confirmed_on`, `confirmed_by` = owner), `unconfirmed`, `ended` |
| `valid_from`, `valid_to` | no | `valid_to` is the expiry. Give it for every status |
| `acquired_via`, `acquired_on` | no | Rule id through which it was obtained; activates retention checks |
| `quantity` | no | Balance, for currencies |

## Metric — `profiles/<p>/metrics/<id>.json`

`id`, `value`, `as_of`, `state` (`confirmed` / `unconfirmed`). A tracked number such as nights or spend.

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
