# Results: PRICES — Consolidated Foundation Safety Repair

Commissioned 2026-11-17 (supersedes the two-defect correction assignment). Executed 2026-11-17 by Claude (engineering).
Branch `dev/foundation-safety-repair`, created from `dev/foundation-safety-correction` at `22bca1a4c832fb29de0db27435d397dade79c0f7`. Not merged anywhere. The commit is given in the accompanying report and by `git log -1`.

## Result

All six defects are corrected. Each one is reproduced on `22bca1a` and shown corrected on this commit by one script (`experiments/safety/repair_before_after.py`, 18 cases, all as expected). The earlier safety work is kept: all 412 earlier tests pass, the real-content experiment passes 52 of 52, and the comparison with `c3b96a9` still holds. The project's records and every real profile's answers are unchanged.

## 1. Existing tests retained

All 412 tests from `22bca1a` are retained and pass. Six have a changed expectation or input, each marked `CHANGED 2026-11-17 (repair)` in the file (listed in section 4). Seven classification records inside earlier tests changed only in form (`"when:x"` / `"dates"` / `"earn"` to the claim list) with the same expected results; `test_live_data` now passes the claim context.

## 2. New tests added

38, in `tests/test_u_repair.py`:

| Defect | Tests | What they assert |
|---|---|---|
| 1 Enforced means enforced | 7 | A-or-B refused and blocking; nested AND/OR; threshold claims must equal or be stricter than the rule and match the text; another leaf on the same figure is not the claimed predicate; 13 malformed or misplaced claims never count; re-checked on every read; `explain` shows why |
| 2 Unknown is not absent | 8 | Unknown membership is UNRESOLVED (neither ESTABLISHED nor NOT_AVAILABLE); a recorded absence establishes it; absences end; contradictions rely on neither; derived negatives; action plus absence is CONDITIONAL; unattested absences ignored; only the owner records one |
| 3 One question per rule | 7 | A-or-B transfer honoured; figure and "not" requirements not ignored; a blocked earning rate or credit is not unlocked by another rule; arithmetic is not a transaction; 150 random condition shapes where status, `rule_applies` and the transfer calculator agree |
| 4 Window is not action | 4 | Dates and cards cannot stand for activation, registration, enrolment, linking, opt-in, sign-up; an activated benefit is CONDITIONAL until the activation is recorded; earned activation |
| 5 Personal history | 6 | Card held January to May still answers for March, not June; unconfirmed stays unconfirmed; end dates checked; legacy and withdrawn records; credit periods of an ended card |
| 6 Restriction changes | 6 | First restriction on a past rule refused unless declared; allowed on a rule not yet started; successors keep history; removing the last reviewed restriction blocks until fresh review; removing or rewording a blocking one does not unblock; a resolved question needs review |

450 tests in all.

## 3. Mutations caught

`scripts/mutation_check_safety.py`: **51 of 51 caught** (it removes one safeguard at a time in a scratch copy and runs the safety tests). the 25 from the earlier commit (re-pointed where the code they guard changed) and 26 for the repair (claims on OR, thresholds, presence, re-checking, old forms, dates, numbers, elections; absence proof, conflicts, attestation; rule-specific earnings, transfers, credits and tokens; action words; holding history in the engine and credits; restriction changes and stale reviews). The first run of the expanded suite missed 5. Each was either a safeguard with no test, fixed by adding a test, or a mutation that a second safeguard also caught: those tests now check the first safeguard's own message, or the mutation was replaced with one that tests something.

## 4. Changed expected results

Tests from earlier commits:

| Test | Was | Now | Why |
|---|---|---|---|
| `test_a_conditional` exclusion, nothing recorded about the blocker | ESTABLISHED | UNRESOLVED; ESTABLISHED with a recorded absence | defect 2 |
| `test_j_relational` ending one person's card | ended on the date asked about, answer changed that day | ended the day before | `ended_on` is the last day held, and the day keeps its answer (defect 5) |
| `test_e_maintenance` revise dates and restrictions | accepted | refused; accepted as a declared correction | defect 6 |
| `test_r_viability_capabilities` adding a restriction | accepted with evidence | refused; accepted as a declared correction | defect 6 |
| `test_t_safety` what an ordinary revision may still do | first restriction on an existing rule accepted | refused | defect 6 |
| `test_t_safety` editing after review | blockers `[None]` | `["stale", None]` | the stale review now blocks by itself (defect 6) |

Real content in the experiment copies and the proposal (nothing here is applied to the project):

| Item | Was | Now |
|---|---|---|
| Hyatt 2026 tiers: "Bonus Points do not count toward tier status" | enforced by `when:hyatt.2026.base_points` | refused: base points are only one of three alternatives (nights, base points, meetings). Reclassified `usage` with a note: it defines the figure recorded and adds no condition on any route. **Engineering's judgement, for a reviewer to confirm** |
| Three Chase "link ... to activate" earned benefits (Hyatt Explorist, IHG Diamond, Southwest A-List) | enforced by `earn` (the spend threshold) | `{"earn_activation": true}`: the activation the rule actually requires |
| Five Chase "valid through December 31 ..." earned benefits | enforced by `earn` | `{"earn_term": true}` |
| Chase transfer card requirement; Capital One card requirement | `when:<id>` | `{"holds": <id>}`, demonstrated on every path |
| Proposal: "Register by December 31, 2026" (Hyatt challenge) | enforced by `dates` | `[{"holds": "hyatt.link_aeroplan"}, {"valid_to": "2026-12-31"}]` |

The experiment's checks and counts are unchanged: 52 checks; 30 enforced, 12 unchecked, 79 usage, 1 affects-eligibility, 16 informational at promotion.

## 5. Mechanism (concise)

1. **Enforcement claims.** `enforced_by` lists exact conditions (`holds`, `not`, `metric`+`gte`, `valid_to`, `valid_from`, `earn_threshold`, `earn_activation`, `earn_term`, `acquire`, `election`). A claim counts only if every way the rule's `when` can be met satisfies it: `any` needs every alternative, and a leaf must be the claim or stricter. If that cannot be shown, the item blocks. The check runs at review, in lint, and every time the engine reads the rule. Two text cross-checks: a restriction naming an action needs a claim that records the action, and a figure claim must carry a number the text states.
2. **Unknown is not absent.** `not` is true only from the owner's recorded absence (`profiles/<p>/absences/`, `set_absence`), false when the entity is established, and otherwise unknown.
3. **One question.** `Result.rule_applies(rule_id)` evaluates one rule's own condition, election gate, verification and blockers at the solver's levels. Earnings, transfers and credits use it, and every calculation carries it as `eligibility`.
4. **Actions.** Covered by 1: a date window never stands for an action.
5. **Holding history.** `engine.holding_state`: an ended holding keeps its state (`ended_from`) for its own days. The engine, elections and credits all use it.
6. **Condition changes.** Any restriction change on a rule that has already answered is a declared correction or a successor; on a rule not yet started it is allowed. A stale review blocks, even when no text is left.

## 6. Remaining known safety limitations

1. **The claim's fit to the text is judged by the reviewer.** The machine proves the claimed condition is enforced; it cannot read whether that is what the text means. For example, `{"holds": "card.a"}` claimed for "requires $4,000 of spend" passes (no number is claimed). The action and number cross-checks narrow this but do not close it.
2. **Classes are judgements.** A real condition classed `usage`, or an eligibility question classed `informational`, gives a false positive. The action-word check applies to `enforced` items only (usage texts legitimately mention linking).
3. **Positive facts keep the earlier convention.** A missing holding gives NOT_AVAILABLE ("nothing on file supports it"), not UNRESOLVED. Only negative conditions and missing figures are unknown. Changing that would turn every unrecorded card into "possibly held". It is a design choice to revisit if profiles are meant to be complete.
4. **Unrecorded facts.** Account age, primary or authorised cardholder, country of an account, new applicant, and how a status was obtained are not recorded, so conditions on them stay unchecked and their benefits UNRESOLVED.
5. **Absences are owner statements.** They are as good as the owner's knowledge, and a contradiction is detected only when both records exist.
6. **Open questions and the history guard.** Adding or removing an open question is not a history change (it records knowledge, not terms). It does force a fresh review.
7. **First records of `summary`, `earning` and credit terms** on an existing rule are still ordinary revisions. They add arithmetic detail, not eligibility conditions.
8. **Live rules.** The nine verified rules still have no classification, so nothing is established through them. The proposal's one enforced entry is corrected. The two Hyatt calls above (bonus points as usage; the challenge question classed `affects_eligibility`) are judgements to confirm.
9. `baseline` and `excludes` rules are not gated (they establish nothing). A store with no reviewer list accepts any attested reviewer.

## 7. Live-rule classifications invalidated

None is applied in the project store, so no live answer changes. In the proposal for a reviewer (`experiments/safety/live_rules_proposal.json`), **one entry was invalidated and corrected**: "Register by December 31, 2026" on `hyatt-challenge-via-aeroplan-elite` (was enforced by `dates`). Every entry in the corrected proposal is validated by `tests/test_live_data.py` with the full claim checks. The comparison with `c3b96a9` (`experiments/safety/results/BEFORE_AFTER.md`) still holds line for line.

## 8. Independent review

```
git fetch origin dev/foundation-safety-repair && git checkout dev/foundation-safety-repair
python3 -m unittest discover -s tests                    # Ran 450 tests ... OK
python3 -m unittest discover -s tests -p "test_u_repair.py"   # the 38 repair tests
python3 experiments/safety/repair_before_after.py        # each defect on 22bca1a and now: "every line is as expected"
python3 experiments/safety/before_after.py               # the earlier comparison with c3b96a9 still holds
python3 experiments/viability/run.py                     # 52 checks, 0 failed
python3 scripts/mutation_check_safety.py                 # 51 mutations, 0 not caught (several minutes)
python3 scripts/verify_clean_checkout.py                 # offline clean checkout: all of the above and more
python3 -m prices lint                                   # 0 errors, 10 warnings (9 rules await classification)
git diff 22bca1a --stat -- data profiles tables          # empty
```

Questions worth pressing: (a) `tests/test_u_repair.py` and `repair_scenarios.py`: is there a route to ESTABLISHED through an unenforced, negative or unrecorded condition they do not try? (b) Is "missing positive holding = NOT_AVAILABLE" acceptable (limitation 3)? (c) The Hyatt bonus-points reclassification. (d) Whether `summary` and `earning` first records should also be history changes (limitation 7).
