# OP-14  Classify a rule's restrictions and open questions (reviewers only)

**ops:** `promote_candidate` (with `data.conditions`), `classify_conditions`

**Use when:** you are a promotion reviewer (`data/kb/vocab.json`, `promotion_reviewers`) and (a) you are promoting a candidate that has any restriction or open question, or (b) `python3 -m prices lint` reports `CONDITIONS_NOT_CLASSIFIED` or `STALE_CLASSIFICATION` for a rule, or (c) you now think an earlier class was wrong.

**The one idea to hold on to.** The engine does not read the text. Your class tells it whether the text matters for **who has the benefit**. A text you do not classify counts against the rule: nothing is established through it. When unsure, choose the class that blocks.

## 1. Inputs and context
- The rule or candidate (`data/kb/rules/<id>.json`, `data/candidates/<id>.json`) and its sources. Read the source, not only the summary.
- `python3 -m prices explain --profile <p> <entity>` prints each text with its present class.

## 2. The classes

Ask of each **restriction**: *could a person who meets the rule's `when` still not have this, because of what this sentence says?*

| Answer | Class | Also give |
|---|---|---|
| No. It says how the benefit is used: a limit, where to book, how to claim, a caveat | `usage` | |
| Yes, and the rule checks it **on every route to the benefit** | `enforced` | `enforced_by`: a list of claims, each the exact machine condition: `{"holds": id}`, `{"not": {"holds": id}}`, `{"metric": id, "gte": N}` (N = the number the text states), `{"valid_to": date}`, `{"valid_from": date}`, `{"earn_threshold": N}`, `{"earn_activation": true}`, `{"earn_term": true}`, `{"acquire": true}`, `{"election": true}`. The program refuses a claim that is not true on every route (`any` alternatives included) |
| Yes, and nothing checks it | `unchecked` | |

Ask of each **open question**: *could the answer change who has this?*

| Answer | Class |
|---|---|
| Yes, or you cannot tell | `affects_eligibility` |
| No: it is about a price, a ratio, how long it lasts, what it leads to | `informational` |

Examples from real content:

| Text | Class | Why |
|---|---|---|
| "New applicants only" | `unchecked` | Nothing records whether the holder was a new applicant |
| "Register by December 31, 2026", on a rule whose `when` requires the registration action and which ends 2026-12-31 | `enforced` by `[{"holds": "<the action>"}, {"valid_to": "2026-12-31"}]` | The date shows only that registering was possible; the action must be recorded too. Dates alone are refused |
| "Register by December 31, 2026", on a rule whose `when` is the status alone | `unchecked` | Nothing records the registration |
| "Requires enrolment", on a rule whose `when` includes the enrolment action | `enforced` by `[{"holds": "<the action>"}]` | |
| "Requires enrolment", on a rule whose `when` is the card alone | `unchecked` | You cannot mark it enforced: the program refuses |
| "At least 1,000 qualifying nights", on a rule checking nights ≥ 1 | `unchecked` | The rule checks less than the text says; `{"metric": ..., "gte": 1000}` is refused |
| "Card A holders only", on a rule that accepts card A OR card B | `unchecked` | Not every route requires card A |
| "Two-night minimum stay" | `usage` | A term of using the credit |
| "Whether a minimum number of flights still applies was not established" | `affects_eligibility` | If it does, the points alone do not qualify |
| "How long the status lasts was not read" | `informational` | |

## 3. Permitted actions
- Give **every** restriction and open question exactly one class. The text must be copied exactly.
- Change your mind later with a new `classify_conditions` changeset (the earlier classes stay in the audit trail).

**Not permitted:** classifying as anyone but yourself; marking a text `enforced` when the rule does not check it; leaving a text out; editing `condition_review` in a file by hand; classifying a text as `usage` or `informational` to make a result appear. If the condition matters and is not checked, the honest result is UNRESOLVED.

## 4. Output: the changeset
At promotion (the other fields are as in `docs/DISCOVERY.md`):
```json
{"id": "cs-YYYYMMDD-NNN-promote-candidate", "op": "promote_candidate", "author": "...", "date": "YYYY-MM-DD", "reason": "...",
 "target": "<candidate id>",
 "data": {"review_by": "YYYY-MM-DD", "accept_open_questions": true,
          "conditions": [{"text": "New applicants only", "class": "unchecked"},
                         {"text": "Book through the portal", "class": "usage"},
                         {"text": "Is it renewed each year?", "class": "informational"}]},
 "attestation": {"by": "<your name as in promotion_reviewers>", "on": "YYYY-MM-DD", "statement": "What you read and checked."}}
```
For a rule already in the store:
```json
{"id": "cs-YYYYMMDD-NNN-classify-conditions", "op": "classify_conditions", "author": "...", "date": "YYYY-MM-DD",
 "reason": "Reviewed the restrictions and open questions against the source.", "target": "<rule id>",
 "data": {"items": [{"text": "Register by December 31, 2026", "class": "enforced", "enforced_by": [{"holds": "hyatt.link_aeroplan"}, {"valid_to": "2026-12-31"}]},
                    {"text": "One challenge per calendar year", "class": "unchecked", "note": "optional: why"}]},
 "attestation": {"by": "<your name>", "on": "YYYY-MM-DD", "statement": "What you read and checked."}}
```
Apply with `python3 -m prices apply <file>`.

**The nine rules verified before this procedure existed** have a ready proposal. Read it (`python3 experiments/safety/proposal.py --list`, reasons in `experiments/safety/live_rules_proposal.json`), edit the JSON where you disagree, then:
```
python3 experiments/safety/proposal.py --write-changesets <dir> --reviewer "<your name>" --on YYYY-MM-DD --statement "<what you checked>"
python3 -m prices apply <dir>/<each file>
```

## 5. Validation (done by the program)
- `CONDITIONS_NOT_CLASSIFIED`: the candidate has such texts and `data.conditions` is missing.
- `BAD_CLASSIFICATION`: a text is missing, classified twice, not on the rule, given a class of the wrong family, or marked `enforced` without something that enforces it. The message names the text.
- `REVIEWER_NOT_AUTHORIZED`, `ATTESTATION_REQUIRED`: as for promotion.
- A refused changeset changes nothing.

## 6. Failure and escalation
- You cannot tell whether a restriction decides who has the benefit: class it `unchecked` and say so in `note`.
- The condition should be checked by the rule (for example an enrolment the owner can confirm): that is a new relationship. Record it with OP-03 and retire or end the old rule; do not mark the text `enforced`.
- The text itself is wrong: fix the text first (OP-02), then classify. Any change to a rule's restrictions or open questions after review needs a new classification.

## 7. How completion is independently established
`APPLIED`; `python3 -m prices lint` no longer lists the rule under `CONDITIONS_NOT_CLASSIFIED`; `python3 -m prices explain` shows each text with the class you gave and your name; results that depend on an `unchecked` or `affects_eligibility` text are UNRESOLVED.
