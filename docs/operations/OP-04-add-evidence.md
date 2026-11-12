# OP-04  Add or validate evidence for an existing rule

**op:** `add_evidence`

**Use when:** you have another source for a rule, or you were asked to check that a rule's evidence still supports it.

## 1. Inputs and context
- The rule id; its `evidence` list; each `data/kb/evidence/<id>.json`.

## 2. Permitted actions
- Add evidence records to the rule. Existing evidence is never edited or removed.
- To validate: open each evidence URL and compare with the rule. If all still support it, use OP-01. If one no longer does, use OP-05 and name the evidence id in the open question.

## 3. Source and evidence requirements
Any source type may be added; it is recorded with its true type. Adding evidence does not change the rule's verification status.

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-add-evidence",
  "op": "add_evidence",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Additional independent source.",
  "target": "<rule id>",
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
- Rule exists; evidence ids are new (or identical to an existing record); dates sane.

## 6. Failure and escalation
- `EVIDENCE_ID_EXISTS`: choose a new id; never reuse an id for different content.

## 7. How completion is independently established
`APPLIED`; the rule's `evidence` list contains the new id; lint clean.
