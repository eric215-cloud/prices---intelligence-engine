# Established or unresolved: reviewed conditions and protected history

Added by the foundation safety correction (2026-11-17); sections 2, 3 and 4 revised by the consolidated safety repair the same day (`docs/commissions/results/2026-11-17-fable-foundation-safety-repair-RESULTS.md`). Code: `prices/conditions.py`, `prices/engine.py` (`standing`, step 1 of `evaluate`), `prices/changes.py` (`promote_candidate`, `classify_conditions`, `revise_rule`, `retire_rule`, `set_credit_terms`). Procedure for a reviewer: `docs/operations/OP-14-condition-review.md`.

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
| restriction | `enforced` | A condition on who has the output that the rule itself checks. `enforced_by` lists the exact machine conditions that check it (table below); each must hold on **every** path by which the rule establishes its output | none while every claim is demonstrated; **blocks** otherwise |
| restriction | `unchecked` | A condition on who has the output that is known and that nothing checks | **blocks** |
| restriction | `usage` | How the output is used: limits, booking channel, claim rules, notes. It does not decide who has it | none |
| open question | `affects_eligibility` | The answer could change who has the output | **blocks** |
| open question | `informational` | The answer would not change who has the output (a price, a ratio, how long it lasts) | none |
| either | *(no class recorded)* | Nobody has classified this text, or the rule was edited after it was reviewed | **blocks** |
| the rule | *(stale review)* | The review classifies a text no longer on the rule, even if no text is left | **blocks** |

### Enforcement claims

| Claim | Demonstrated when |
|---|---|
| `{"holds": "<entity>"}` | every way the rule's `when` can be met requires holding that entity |
| `{"not": {"holds": "<entity>"}}` | every way requires the owner's **recorded absence** of it (section 3) |
| `{"metric": "<id>", "gte": N}` | every way requires that figure at N or more; a path checking less fails |
| `{"valid_to": "YYYY-MM-DD"}` / `{"valid_from": ...}` | the rule ends on or before / starts on or after that date |
| `{"earn_threshold": N}` | an earns rule whose threshold is N or more |
| `{"earn_activation": true}` | an earns rule whose activation is `required` (reaching the threshold gives ACTIVATION_REQUIRED, never the benefit) |
| `{"earn_term": true}` | an earns rule whose `term` computes when the benefit ends |
| `{"acquire": true}` | an acquire rule: the output is reached only by the step itself and held only once the owner records it |
| `{"election": true}` | a cardholder election governs the rule |

"Every way" is decided on the structure of `when`: a leaf satisfies a claim only if it is that claim or stricter; `all` satisfies it if one part does; `any` only if **every** alternative does; `not` never satisfies a positive claim. Anything that cannot be shown this way fails. Two cross-checks on the text, because the machine cannot read it: a restriction that names an action (register, enrol, activate, link, opt in, sign up, nominate) must have a claim that records the action (`holds` on an entity of kind `action`, `acquire`, `election` or `earn_activation`), since a date window shows only that the action was possible; and a `metric` or `earn_threshold` claim must carry a number the text states, when the text states one. The old forms (`"when:<id>"`, `"dates"`, `"earn"`, `"election"`) named something present in the rule, not something enforced; they are refused and never count.

"Blocks" means: the engine uses the rule only as a possibility. The output is reported **UNRESOLVED**, never ESTABLISHED and never CONDITIONAL, and each blocking text is given as the reason. What depends on that output is unresolved too. A clear "no" stays a "no": if the rule's `when` is not met, the answer is NOT_AVAILABLE as before. Another rule for the same output that is not blocked, or the owner's own confirmed record of holding it, still establishes it.

The record is on the rule:

```json
"condition_review": {"by": "<a promotion reviewer>", "on": "2026-11-17", "changeset": "<the changeset that recorded it>",
  "items": [{"text": "New applicants only", "class": "unchecked"},
            {"text": "Register by December 31, 2026", "class": "enforced", "enforced_by": [{"holds": "hyatt.link_aeroplan"}, {"valid_to": "2026-12-31"}]},
            {"text": "How long the status lasts was not read", "class": "informational", "note": "optional reason"}]}
```

### What makes it safe by construction

1. **Silence blocks.** A text without a class blocks. A rule with restrictions and no `condition_review` at all establishes nothing.
2. **Only a reviewer can classify.** The record is written by `promote_candidate` (which now refuses a candidate that has any such text unless `data.conditions` classifies every one) and by `classify_conditions`. Both need an attestation by someone in `vocab.promotion_reviewers`. `revise_rule` cannot touch it, a candidate cannot carry one, and lint reports a record by anyone else as an error.
3. **`enforced` must be enforced.** The pipeline and lint refuse an `enforced` item whose claims are not demonstrated, and the engine checks them again every time it reads the rule: an item that stops being demonstrable (the rule's dates were changed, the record was edited by hand) blocks.
4. **Exact text.** Classes are matched to the exact text. Adding a restriction or a question leaves the new text unclassified. Removing or rewording a classified text makes the review stale, which blocks on its own, even when no text is left. The rule establishes nothing until a reviewer classifies it as it now stands (`classify_conditions`, with an empty list if no text remains).
5. **One question per rule.** `conditions.blockers(rule, ctx)` decides what blocks a rule; `Result.rule_applies(rule_id)` answers "does THIS rule apply to this person on this date?" with the same levels and tokens the solver uses for status (its whole `when`, its election gate, its verification, its blockers). The earnings and transfer calculators and recurring credits ask that question about the rule whose rate, ratio or allowance they use; another rule establishing the same output does not make it apply. Every calculation carries the answer as `eligibility`. A CALCULATED number is arithmetic on a published figure for a rule that applies; balances, minimums and posting are not checked and are listed as assumptions.

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

## 3. Unknown is not absent

A rule may require that something is NOT held: `{"not": {"holds": "club.member"}}`. A missing holding is not evidence of that: holdings record what the owner has told us, not everything they have. So a negative condition is:

- **false** when the entity is established as held;
- **true** only when the owner has recorded its absence (`profiles/<p>/absences/<id>.json`, op `set_absence`, owner attestation, with dates) and no record or rule says it may be held;
- **unknown** otherwise: the output is UNRESOLVED, with "no record says X is NOT held" as the reason. It is never ESTABLISHED and never NOT_AVAILABLE on missing information.

An absence and a holding of the same entity on the same dates contradict each other: lint warns, and the engine relies on neither (the holding counts as unconfirmed, the absence is ignored).

## 4. Protected history

Published terms change, and a record of what was true must survive the change.

- **Dated versions.** The same relationship may be recorded more than once if the validity dates do not overlap (viability experiment, D-55). To change terms: end the old rule on its last day and add the new terms from the next day.
- **A condition change on a rule that has already answered is never ordinary.** Adding, removing or rewording a restriction on a rule whose `valid_from` is before today (or absent) is refused (`HISTORY_REWRITE`), including the first restriction ever recorded on it. If the source added the term from a date, end the rule and add a successor; if it always applied, declare the correction. On a rule that has not started, the change is allowed. In every case the rule then needs a fresh review before it establishes anything.
- **An ordinary revision cannot change a past answer.** `revise_rule` and `set_credit_terms` refuse (`HISTORY_REWRITE`) to replace or remove a recorded term (`summary`, `restrictions`, `earning`, credit terms) or to move a date that has already passed. They still allow: ending a rule on a day that has not come, moving that day while it has not come, recording a term where none was recorded, and changing review dates, notes and open questions.
- **A correction must be declared.** If the entry was wrong from the start, the same change is accepted with `"correction": "<what was wrong>"` in the changeset's `data` (in the tables: `correct` in `_action`). The declaration is kept in the audit trail with the record as it was, and it can be reverted.
- **Retirement keeps history.** `retire_rule` takes `ended_on`. The rule stops answering after that day and keeps answering for the days before it, with the standing it had (a rule that was unverified is not trusted in retrospect). No second rule may be recorded for days it still answers for.
- **Withdrawing a rule from every date** (it was never true) is `retire_rule` with `"void": true` and a declared `correction`. The record is kept.
- **Ending a holding keeps its history.** `end_holding` records `ended_on` as the holding's last day and the state it had (`ended_from`). The holding keeps that state for its own days: a card held January to May and ended on May 31 still supports an answer for March, and nothing after May 31. An unconfirmed holding stays unconfirmed. A `withdrawn` holding (recorded in error) answers for no day. Elections and recurring credits read holdings the same way.
- **The audit trail is unchanged in kind:** every attempt is logged, applied or rejected; every applied change keeps the record as it was (`data/audit/previous/`); `revert_changeset` restores it exactly.

## 5. What this does not do

- **It does not judge the class or the claim's fit to the text.** The machine shows that the claimed condition is enforced on every path; it cannot read whether that condition is what the text means. A reviewer who claims `{"holds": "card.a"}` for "requires $4,000 of spend" passes the check (no number is claimed, so the number cross-check does not apply). The action and number cross-checks narrow this; they do not close it.
- **It does not judge the class.** A reviewer who records "new applicants only" as a usage term gets an established welcome offer. The record says who classed it and when, and `explain` prints every text with its class, so the choice can be seen and challenged. It cannot be made correct by code.
- **It does not resolve anything.** A blocked benefit stays unresolved until the condition is modelled as something the rule checks (a holding, an action, a figure, a recorded absence) or a reviewer decides it is a usage term. Account facts such as account age, primary or authorised cardholder, country of an account, or "new applicant" are not recorded anywhere yet.
- **NOT_AVAILABLE still means "nothing on file supports it".** For positive conditions a missing holding gives NOT_AVAILABLE, as before: the engine does not treat every unrecorded card as possibly held. Only negative conditions and missing figures are treated as unknown.
- **`usage` is not checked against action words.** "Points post about six weeks after linking" is a usage term and contains "linking"; the action cross-check applies to `enforced` items only. A reviewer who classes a real activation requirement as usage gets a false positive.
- **The reviewer list is the project's own.** `vocab.promotion_reviewers` names who may classify. A store with no such list accepts any attested name, as promotion always has.
- **A hand-edited record** is caught by lint (wrong reviewer, a check that is not there, stale text), not by the engine.
- **The verified rules that predate this correction are not classified.** See section 5.

## 6. The nine verified rules in the project

They carry 27 restrictions and open questions and no review, so they establish nothing at present. Engineering has not classified them: that is a content decision. A proposal with a reason for each text is in `experiments/safety/live_rules_proposal.json`; `python3 experiments/safety/proposal.py --list` prints it, and OP-14 says how a reviewer applies or changes it. `experiments/safety/results/BEFORE_AFTER.md` shows the answers before, now, and with the proposal applied in a copy.

## 7. How to check it

```
python3 -m unittest discover -s tests -p "test_t_safety.py"      # adversarial tests, invented data
python3 experiments/viability/run.py                             # real content in a throwaway copy: 52 checks
python3 experiments/safety/before_after.py                       # the earlier commit and this one, side by side (needs git)
python3 -m unittest discover -s tests -p "test_u_repair.py"     # adversarial tests of the repair, one class per defect
python3 experiments/safety/repair_before_after.py                # each repaired defect on commit 22bca1a and now (needs git)
python3 scripts/mutation_check_safety.py                         # 51 safeguards removed one at a time; the tests must notice each
python3 -m prices explain --profile <p> <entity>                 # every text on the deciding rule, with its class
python3 -m prices lint                                           # CONDITIONS_NOT_CLASSIFIED lists rules waiting for a reviewer
```
