# OP-09  Record or prune temporary observations

**op:** `add_observation` / `prune_observations`

**Use when:** a goal investigation found a promotion with an end date, or the owner confirmed live availability. These are never rules.

## 1. Inputs and context
- The source URL, the end date, the goal tags it relates to (tags must exist in `data/kb/vocab.json`).

## 2. Permitted actions
- `add_observation` type `promotion`: needs URL and `valid_to` (the promotion's end date).
- `add_observation` type `availability`: needs an attestation from the person who saw it; set `valid_to` two days after the check.
- `prune_observations`: removes observations whose `valid_to` is before the changeset date. Run it at the start of any goal investigation.

## 3. Source and evidence requirements
Record only what was seen. Never estimate availability, fares or targeted offers.

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-add-observation",
  "op": "add_observation",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Current transfer bonus relevant to the Japan goal.",
  "data": {"observation": {
    "id": "promo-<program>-<yyyymm>",
    "type": "promotion",
    "summary": "What is offered, in one sentence.",
    "tags": ["region:japan"],
    "checked_on": "YYYY-MM-DD",
    "valid_to": "YYYY-MM-DD",
    "url": "https://...",
    "publisher": "..."
  }}
}

For pruning:  {"id": "...", "op": "prune_observations", "author": "...", "date": "YYYY-MM-DD", "reason": "Housekeeping"}
```

## 5. Validation (done by the program)
- Shape; tags known; not already expired; attestation for availability.

## 6. Failure and escalation
- `ALREADY_EXPIRED`: do not record it.
- If the 'promotion' has no end date and looks permanent, it is a relationship: use OP-03.

## 7. How completion is independently established
`APPLIED`; `python3 -m prices goal ...` lists it under promotions or available options until `valid_to`.
