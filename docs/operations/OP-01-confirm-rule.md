# OP-01  Confirm a rule is unchanged

**op:** `confirm_rule`

**Use when:** you have checked a current source and it still says what the rule says. Typical trigger: a `STALE_RULE` flag or a rule nearing `review_by`.

## 1. Inputs and context
- The rule id. Read `data/kb/rules/<id>.json`: `summary`, `when`, `restrictions`, `valid_to`.
- A source retrieved now (official page, or two reputable secondary publishers).

## 2. Permitted actions
- Add new evidence records.
- Set `last_verified` (taken from the changeset date) and a new `review_by`.
- Nothing else. This op cannot change what the rule says.

## 3. Source and evidence requirements
- The new evidence must be enough by itself: one `official` source, or two `reputable_secondary` sources from different publishers.
- `retrieved_on` must be on or after the rule's previous `last_verified` and not after the changeset date.
- Compare the source with **every** part of the rule: who qualifies, what they get, restrictions, end date. If any part differs, this is not OP-01: use OP-02 (dates, restrictions, wording) or OP-03 + OP-05 (logic).

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-confirm-rule",
  "op": "confirm_rule",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Re-checked against <source>; unchanged.",
  "target": "<rule id>",
  "data": {"review_by": "YYYY-MM-DD"},
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
- Rule exists and is `verified`.
- Evidence policy, evidence dates.
- `review_by` is after the changeset date and at most 400 days later. Pick about 6 months; pick 1 month for offers with an end date.

## 6. Failure and escalation
- `NOT_VERIFIED`: the rule is unverified or retired; escalate, do not confirm.
- `INSUFFICIENT_EVIDENCE` / `STALE_EVIDENCE`: find a better or newer source; if none exists, use OP-05.
- Source differs from rule: stop, switch card as described above.

## 7. How completion is independently established
`python3 -m prices apply` prints `APPLIED`; `python3 -m prices lint` prints 0 errors; the rule file shows the new `last_verified` and `review_by`; `python3 -m prices audit` lists the changeset as applied; `DOWNSTREAM REVIEW NEEDED` is `no`.
