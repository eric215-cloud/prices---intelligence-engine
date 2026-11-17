# Established or unresolved: reviewed conditions and protected history

Added by the foundation safety correction (2026-11-17). Code: `prices/conditions.py`, `prices/engine.py` (`standing`, step 1 of `evaluate`), `prices/changes.py` (`promote_candidate`, `classify_conditions`, `revise_rule`, `retire_rule`, `set_credit_terms`). Procedure for a reviewer: `docs/operations/OP-14-condition-review.md`.

## 1. The defect

A rule holds two kinds of text that the engine does not evaluate: `restrictions` (what the source states) and `open_questions` (what nobody has established). Until this correction the engine established the rule's output whenever its `when` condition held, whatever that text said. On real content this produced answers that were wrong:

- A Chase Sapphire Reserve welcome offer restricted to new applicants was reported as established for an account opened in 2024.
- United Premier Silver for 2027 was reported as established on 6,100 PQP while the same record said the sources did not settle whether a minimum of United-operated flights still applies.
- In the project's own verified rules, a JAL award pathway was reported as established although the rule says the JAL account must be 60 days old, which nothing records.

The viability experiment introduced a list field, `unchecked`, for the first case. It did nothing for open questions, and it only worked when someone remembered to move a text into it: forgetting was read as approval.

## 2. The mechanism

**Every restriction and every open question on a rule gets a class, recorded by a named reviewer. While a text has no class, or has a class that blocks, nothing is established through that rule.**

| Text | Class | Meaning | Effect |
|---|---|---|---|
| restriction | `enforced` | A condition on who has the output that the rule itself checks. `enforced_by` says where: `when:<entity or metric id>`, `dates`, `earn`, or `election` | none: the check is already made |
| restriction | `unchecked` | A condition on who has the output that is known and that nothing checks | **blocks** |
| restriction | `usage` | How the output is used: limits, booking channel, claim rules, notes. It does not decide who has it | none |
| open question | `affects_eligibility` | The answer could change who has the output | **blocks** |
| open question | `informational` | The answer would not change who has the output (a price, a ratio, how long it lasts) | none |
| either | *(no class recorded)* | Nobody has classified this text, or the rule was edited after it was reviewed | **blocks** |

"Blocks" means: the engine uses the rule only as a possibility. The output is reported **UNRESOLVED**, never ESTABLISHED and never CONDITIONAL, and each blocking text is given as the reason. What depends on that output is unresolved too. A clear "no" stays a "no": if the rule's `when` is not met, the answer is NOT_AVAILABLE as before. Another rule for the same output that is not blocked, or the owner's own confirmed record of holding it, still establishes it.

The record is on the rule:

```json
"condition_review": {"by": "<a promotion reviewer>", "on": "2026-11-17", "changeset": "<the changeset that recorded it>",
  "items": [{"text": "New applicants only", "class": "unchecked"},
            {"text": "Register by December 31, 2026", "class": "enforced", "enforced_by": "dates"},
            {"text": "How long the status lasts was not read", "class": "informational", "note": "optional reason"}]}
```

### What makes it safe by construction

1. **Silence blocks.** A text without a class blocks. A rule with restrictions and no `condition_review` at all establishes nothing.
2. **Only a reviewer can classify.** The record is written by `promote_candidate` (which now refuses a candidate that has any such text unless `data.conditions` classifies every one) and by `classify_conditions`. Both need an attestation by someone in `vocab.promotion_reviewers`. `revise_rule` cannot touch it, a candidate cannot carry one, and lint reports a record by anyone else as an error.
3. **`enforced` must point at a real check.** The pipeline and lint refuse `enforced` unless `enforced_by` names something the rule has: a positive leaf of its `when`, its validity dates, its `earn` block, or a cardholder election that governs it.
4. **Exact text.** Classes are matched to the exact text. Adding a restriction or a question leaves the new text unclassified. Removing or rewording a classified text sets the whole record aside, because the record then describes a rule that no longer exists. In both cases the rule establishes nothing until a reviewer classifies it as it now stands.
5. **It is one function.** `conditions.blockers(rule)` is the only place that decides. The engine, the calculations (`earnings`, `convert`), earned benefits, recurring credits and the card table all go through it, so the answer is the same in every report.

### Where it applies

| Content | What a blocking text does |
|---|---|
| Card benefits (`grants`) | benefit UNRESOLVED; the `cards` table adds "not established for a holder" |
| Status by match, link or threshold (`grants`, `acquire`) | status UNRESOLVED |
| Transfers | destination currency UNRESOLVED; `convert` answers NOT_CALCULATED with the text |
| Activation or enrolment requirements | UNRESOLVED unless the rule's `when` has the action and the class is `enforced` by it |
| Spending thresholds (`earns`) | threshold reached becomes UNRESOLVED instead of "earned, not yet confirmed"; below the threshold is unchanged |
| Earning rates and credits | `earnings` answers NOT_CALCULATED; a credit's period is computed but whether it applies is UNRESOLVED |

Not gated: `baseline` and `excludes` rules. They never establish an entitlement (a network baseline is "not established" by design; an exclusion only removes).

## 3. Protected history

Published terms change, and a record of what was true must survive the change.

- **Dated versions.** The same relationship may be recorded more than once if the validity dates do not overlap (viability experiment, D-55). To change terms: end the old rule on its last day and add the new terms from the next day.
- **An ordinary revision cannot change a past answer.** `revise_rule` and `set_credit_terms` refuse (`HISTORY_REWRITE`) to replace or remove a recorded term (`summary`, `restrictions`, `earning`, credit terms) or to move a date that has already passed. They still allow: ending a rule on a day that has not come, moving that day while it has not come, recording a term where none was recorded, and changing review dates, notes and open questions.
- **A correction must be declared.** If the entry was wrong from the start, the same change is accepted with `"correction": "<what was wrong>"` in the changeset's `data` (in the tables: `correct` in `_action`). The declaration is kept in the audit trail with the record as it was, and it can be reverted.
- **Retirement keeps history.** `retire_rule` takes `ended_on`. The rule stops answering after that day and keeps answering for the days before it, with the standing it had (a rule that was unverified is not trusted in retrospect). No second rule may be recorded for days it still answers for.
- **Withdrawing a rule from every date** (it was never true) is `retire_rule` with `"void": true` and a declared `correction`. The record is kept.
- **The audit trail is unchanged in kind:** every attempt is logged, applied or rejected; every applied change keeps the record as it was (`data/audit/previous/`); `revert_changeset` restores it exactly.

## 4. What this does not do

- **It does not judge the class.** A reviewer who records "new applicants only" as a usage term gets an established welcome offer. The record says who classed it and when, and `explain` prints every text with its class, so the choice can be seen and challenged. It cannot be made correct by code.
- **It does not resolve anything.** A blocked benefit stays unresolved until the condition is modelled as something the rule checks (a holding, an action, a figure) or a reviewer decides it is a usage term. Account facts such as account age, primary or authorised cardholder, country of an account, or "new applicant" are not recorded anywhere yet.
- **The reviewer list is the project's own.** `vocab.promotion_reviewers` names who may classify. A store with no such list accepts any attested name, as promotion always has.
- **A hand-edited record** is caught by lint (wrong reviewer, a check that is not there, stale text), not by the engine.
- **The verified rules that predate this correction are not classified.** See section 5.

## 5. The nine verified rules in the project

They carry 27 restrictions and open questions and no review, so they establish nothing at present. Engineering has not classified them: that is a content decision. A proposal with a reason for each text is in `experiments/safety/live_rules_proposal.json`; `python3 experiments/safety/proposal.py --list` prints it, and OP-14 says how a reviewer applies or changes it. `experiments/safety/results/BEFORE_AFTER.md` shows the answers before, now, and with the proposal applied in a copy.

## 6. How to check it

```
python3 -m unittest discover -s tests -p "test_t_safety.py"      # adversarial tests, invented data
python3 experiments/viability/run.py                             # real content in a throwaway copy: 52 checks
python3 experiments/safety/before_after.py                       # the earlier commit and this one, side by side (needs git)
python3 scripts/mutation_check_safety.py                         # 25 safeguards removed one at a time; the tests must notice each
python3 -m prices explain --profile <p> <entity>                 # every text on the deciding rule, with its class
python3 -m prices lint                                           # CONDITIONS_NOT_CLASSIFIED lists rules waiting for a reviewer
```
