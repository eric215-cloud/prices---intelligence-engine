# OP-02  Revise a rule's dates, restrictions or wording

**op:** `revise_rule`

**Use when:** a source shows that an end date, start date, restriction, note or wording changed, while **who qualifies and what they get stayed the same**.

## 1. Inputs and context
- The rule id and its current JSON.
- The source showing the new value.

## 2. Permitted actions
Change only these fields, inside `data.set`:

| Field | Meaning |
|---|---|
| `valid_from`, `valid_to` | When the rule is in effect (`valid_to` may be `null`) |
| `restrictions` | Full replacement list of restriction sentences |
| `open_questions` | Full replacement list |
| `summary`, `value_note`, `retention_note` | Wording |
| `review_by` | Next check date |

You may **not** change `kind`, `output`, `when`, `retention.mode`, `evidence` or `verification.status`. A change to who qualifies or what is granted is a different relationship. If a source shows such a change, record the new relationship with OP-03 and flag the old rule with OP-05. If there is no source (someone merely asks for it), change nothing and escalate.

## 3. Source and evidence requirements
Evidence is required and must satisfy the policy (one `official`, or two `reputable_secondary` from different publishers).

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-revise-rule",
  "op": "revise_rule",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Official page now gives a different registration deadline.",
  "target": "<rule id>",
  "data": {"set": {"valid_to": "YYYY-MM-DD", "restrictions": ["...", "..."]}},
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
- Field whitelist, evidence policy, date sanity (`valid_to` not before `valid_from`).
- The program then compares every profile before and after and prints the impact.

## 6. Failure and escalation
- `FIELD_NOT_REVISABLE`: the changeset tries to change the rule's logic. Do not retry it in another form and do not edit the file. With a source in hand: OP-03 for the new relationship, OP-05 for the old rule, then escalate. Without a source: escalate only; the existing rule stays as it is.
- Sources disagree about the new value: use OP-05 instead and list both values as open questions.

## 7. How completion is independently established
`APPLIED`; lint clean; rule file shows the new value. If `DOWNSTREAM REVIEW NEEDED: yes`, a review note exists at `reviews/<changeset-id>.md` (see the maintainer guide).
