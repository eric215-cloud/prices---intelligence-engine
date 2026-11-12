# OP-05  Flag a broken or uncertain rule

**op:** `flag_rule`

**Use when:** a rule may be wrong and you cannot settle it: the source page is gone, sources conflict, a report contradicts it, or its logic seems to have changed.

## 1. Inputs and context
- The rule id and what made you doubt it.

## 2. Permitted actions
- Mark the rule `unverified` and add open questions. Everything depending on it becomes UNRESOLVED instead of ESTABLISHED. This is always safe and reversible by a reviewer.
- You may attach evidence of the doubt.

## 3. Source and evidence requirements
No evidence is required to flag. If you have the conflicting source, attach it with its true type.

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-flag-rule",
  "op": "flag_rule",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Official page no longer mentions this benefit.",
  "target": "<rule id>",
  "data": {"open_questions": ["Precise question that would settle it"]}
}
```

## 5. Validation (done by the program)
- Rule exists and is not retired; at least one non-empty question.

## 6. Failure and escalation
- Flagging will usually print `DOWNSTREAM REVIEW NEEDED: yes`: write the review note.
- Also write an escalation so a reviewer resolves the question.

## 7. How completion is independently established
`APPLIED`; rule shows `"status": "unverified"` and the question; `python3 -m prices status` no longer lists its output as established via this rule; review note and escalation exist.
