# OP-06  Retire an ended benefit

**op:** `retire_rule`

**Use when:** a source shows the benefit or offer has ended for good. Retiring keeps the record as history; nothing is deleted.

## 1. Inputs and context
- The rule id; the source stating the end; the end date.

## 2. Permitted actions
- Set the rule to `retired` with `valid_to` = the last day it applied.
- Holdings that people acquired through it are **not** touched: they stand or fall on their own dates and retention terms.

## 3. Source and evidence requirements
At least one evidence record (any type) or an attestation. Prefer the official notice.

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-retire-rule",
  "op": "retire_rule",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Program announced the end of the offer.",
  "target": "<rule id>",
  "data": {"ended_on": "YYYY-MM-DD"},
  "evidence": [
    {
      "id": "ev-<publisher>-<topic>-<yyyymmdd>",
      "url": "https://...",
      "title": "Page title",
      "publisher": "Who published it",
      "source_type": "official",
      "retrieved_on": "YYYY-MM-DD",
      "summary": "In your own words, only what the page says about this rule."
    }
  ]
}
```

## 5. Validation (done by the program)
- Rule exists and is not already retired; evidence or attestation present.

## 6. Failure and escalation
- If it is only an expected end date on a still-running offer, use OP-02 (`valid_to`) instead.
- If you are not sure it ended, use OP-05.

## 7. How completion is independently established
`APPLIED`; rule file still exists with `"status": "retired"`; lint clean; review note written if requested by the output.
