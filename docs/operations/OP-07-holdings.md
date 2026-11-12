# OP-07  Record, update or end a personal qualification

**op:** `set_holding` / `end_holding`

**Use when:** a person's holding (status, card, currency balance, completed action) must be added, updated or ended.

## 1. Inputs and context
- The profile name; the entity id; dates; **who said so**.

## 2. Permitted actions
- `set_holding` with `state: unconfirmed` — allowed to any maintainer. Counts as UNRESOLVED.
- `set_holding` with `state: confirmed` — only with an `attestation` whose `by` is exactly the profile's `owner` (see `profiles/<name>/profile.json`) and whose `statement` quotes or closely reports what the owner said. Never write an attestation on someone's behalf.
- `end_holding` — also needs the owner's attestation. The record is kept with `state: ended`.
- If the holding was obtained through a rule, set `acquired_via` to that rule id and `acquired_on`. Always give `valid_to` for statuses when known.

## 3. Source and evidence requirements
The owner's own statement, screenshot or account page. Never store passwords, card numbers, account numbers or login tokens. A membership tier and its expiry date are enough.

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-set-holding",
  "op": "set_holding",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Owner confirmed status and expiry.",
  "profile": "<profile>",
  "data": {"holding": {
    "id": "h-<entity-with-dashes>",
    "entity": "<entity id>",
    "state": "confirmed",
    "valid_from": "YYYY-MM-DD",
    "valid_to": "YYYY-MM-DD",
    "acquired_via": "<rule id, only if obtained through a rule>"
  }},
  "attestation": {"by": "<owner exactly as in profile.json>", "on": "YYYY-MM-DD", "statement": "What the owner said or showed."}
}

For end_holding:  "op": "end_holding", "target": "<holding id>", "data": {"ended_on": "YYYY-MM-DD"}, plus profile and attestation.
```

## 5. Validation (done by the program)
- Profile and entity exist; owner attestation for confirmed/ended; dates sane; synthetic confirmations are refused in real profiles.

## 6. Failure and escalation
- `ATTESTATION_REQUIRED` / `OWNER_ATTESTATION_REQUIRED`: you do not have the owner's confirmation. Record as `unconfirmed` instead and escalate to the owner.
- Two records disagree about the same entity: escalate; do not pick one.

## 7. How completion is independently established
`APPLIED`; `python3 -m prices status --profile <p>` shows the holding with the right state; review note written if requested.
