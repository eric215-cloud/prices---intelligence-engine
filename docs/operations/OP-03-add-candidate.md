# OP-03  Add a newly found candidate relationship

**op:** `add_candidate`

**Use when:** research found a relationship that is not a rule yet, or suggests an existing rule's logic changed. Candidates are a waiting room: they never affect established results.

## 1. Inputs and context
- What you found, the queries you used, the sources.
- Existing entity ids: `ls data/kb/entities/`. Reuse them. Only add an entity when none exists.

## 2. Permitted actions
- Create one candidate with one proposed rule.
- Propose new entities inside `proposed_entities` (they are created only at promotion).
- You may not promote. Promotion is a reviewer's decision.

## 3. Source and evidence requirements
- Include every source, whatever its type; weak evidence is allowed here.
- List what is unknown in `open_questions`. A candidate from a single or weak source **must** have at least one open question.
- For `acquire` rules, `retention` is mandatory: use `{"mode": "unknown"}` unless the source states the terms. `fixed_term` = lasts for a stated period regardless; `while_qualified` = withdrawn if the qualifying status is lost.
- Rule kinds: `acquire` = a status the person must apply or register for and then holds in its own right; `grants` = a benefit that exists only while the condition holds; `transfer` = one currency converts into another (add a `transfer` block).

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-add-candidate",
  "op": "add_candidate",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Found while researching <cell or task>.",
  "data": {"candidate": {
    "id": "c-<output>-via-<source>",
    "status": "proposed",
    "created_on": "YYYY-MM-DD",
    "proposed_entities": [
      {"id": "program.tier", "kind": "status", "name": "Full Name", "program": "program"}
    ],
    "proposed_rule": {
      "id": "<output>-via-<source>",
      "kind": "acquire",
      "output": "program.tier",
      "when": {"holds": "other.status"},
      "summary": "One sentence stating the relationship.",
      "retention": {"mode": "unknown", "note": "Terms not stated in the sources read."},
      "restrictions": ["..."]
    },
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
    ],
    "search_path": ["exact query 1", "fetched URL 2"],
    "open_questions": ["What is still unknown"],
    "mentions": ["Names of programs seen in the sources that are not entities yet"]
  }}
}
```

## 5. Validation (done by the program)
- Candidate shape; all referenced entities exist or are proposed; no duplicate of an existing rule or open candidate (`DUPLICATE_RELATIONSHIP`).
- Optional pre-check: `python3 -m prices novelty work/<file>.json`.

## 6. Failure and escalation
- `DUPLICATE_RELATIONSHIP`: it is already known. If your source adds something, use OP-04 on the existing rule.
- `UNKNOWN_REFERENCE`: an entity id is wrong or missing from `proposed_entities`.
- You cannot express the relationship with `holds` / `all` / `any` / `not` / `metric`: escalate with a plain-language description.

## 7. How completion is independently established
`APPLIED`; a file exists at `data/candidates/<id>.json` with `status: proposed`; no file under `data/kb/rules/` changed; lint clean.
