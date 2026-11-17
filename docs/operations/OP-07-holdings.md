# OP-07  Record, update or end a personal qualification

**op:** `set_holding` / `end_holding` / `set_absence`

**Use when:** a person's holding (status, card, currency balance, completed action) must be added, updated or ended.

## 1. Inputs and context
- The profile name; the entity id; dates; **who said so**.

## 2. Permitted actions
- `set_holding` with `state: unconfirmed` — allowed to any maintainer. Counts as UNRESOLVED.
- `set_holding` with `state: confirmed` — only with an `attestation` whose `by` is exactly the profile's `owner` (see `profiles/<name>/profile.json`) and whose `statement` quotes or closely reports what the owner said. Never write an attestation on someone's behalf.
- `end_holding` — also needs the owner's attestation. `ended_on` is the **last day** the person held it. The record is kept with `state: ended` and `ended_from` (the state it had), and it keeps answering for the days it was held (CHANGED 2026-11-17: before, ending a holding erased it from every date). If the holding was recorded in error and was never true, it is withdrawn, not ended.
- `set_absence` — the owner's statement that they do **not** hold something, with dates. Needs the owner's attestation. It is the only thing that makes a rule condition "not held" true: without it, "not held" is unknown. Record it only when the owner says so.
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
For set_absence:  "op": "set_absence", "data": {"absence": {"id": "a-<entity-with-dashes>", "entity": "<entity id>", "valid_from": "YYYY-MM-DD"}},
                  plus profile and an attestation by the owner.
```

## 5. Validation (done by the program)
- Profile and entity exist; owner attestation for confirmed/ended/absences; dates sane (`ended_on` not before the holding began and not after its own end); synthetic confirmations are refused in real profiles.

## 6. Failure and escalation
- `ATTESTATION_REQUIRED` / `OWNER_ATTESTATION_REQUIRED`: you do not have the owner's confirmation. Record as `unconfirmed` instead and escalate to the owner.
- Two records disagree about the same entity: escalate; do not pick one.

## 7. How completion is independently established
`APPLIED`; `python3 -m prices status --profile <p>` shows the holding with the right state; review note written if requested.
