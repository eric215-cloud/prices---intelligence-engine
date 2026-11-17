# Results: FABLE — PRICES Foundation Safety Correction

Commissioned by Bradley, 2026-11-17. Executed 2026-11-17 by Claude Fable 5.2 (engineering).
Branch `dev/foundation-safety-correction`, created from `exp/foundation-viability` at `c3b96a9`. Not merged anywhere. The commit is given in the report that accompanies this file and by `git log -1`.

## Result

The engine now tells established eligibility from unresolved eligibility the same way in every kind of content. The false positive named in the commission is corrected and reproduced side by side with the earlier commit. The price, stated first: **the project's own nine verified rules have no reviewer's classification yet, so until a reviewer acts, everything derived from them reads UNRESOLVED.** That is the fail-safe working as specified, not a regression, but it is the first thing a user will notice.

## 1. Code and tests

| | |
|---|---|
| Tests | 412, all passing (`python3 -m unittest discover -s tests`). 382 before; 24 new in `tests/test_t_safety.py`, 6 new in `tests/test_live_data.py` |
| Real-content regression | `python3 experiments/viability/run.py`: 52 checks, 0 failed (46 before) |
| Before and after | `python3 experiments/safety/before_after.py`: every line as expected |
| Guards on the safeguards | `python3 scripts/mutation_check_safety.py`: 25 of 25 caught. Three were missed on the first run; the tests were tightened until each was caught |
| Lint | 0 errors, 10 warnings (9 are the rules waiting for classification) |
| Project records | `data/`, `profiles/`, `tables/` byte-identical to `c3b96a9`; 113 candidates still `proposed`; no personal record touched |

New: `prices/conditions.py`, op `classify_conditions`, `tests/test_t_safety.py`, `scripts/mutation_check_safety.py`, `experiments/safety/` (`before_after.py`, `scenario.py`, `proposal.py`, `live_rules_proposal.json`, `results/BEFORE_AFTER.md`), `fixtures/condition_classes.py`, `docs/CONDITION_REVIEW.md`, `docs/operations/OP-14-condition-review.md`.
Changed: `prices/engine.py`, `changes.py`, `lint.py`, `calc.py`, `earned.py`, `credits.py`, `cards.py`, `elections.py`, `tables.py`, `cli.py`, `schema.json`; the three fixture builders and their regenerated fixtures; the experiment sheets and runner; two demos; two verification scripts; OP-02, OP-06, OP-10, OP-13; decisions D-57 to D-61.
Removed: the experimental `unchecked` list field (D-53), replaced by the recorded class.

## 2. Before and after, on real sourced content

Full table, generated: `experiments/safety/results/BEFORE_AFTER.md`. BEFORE is commit `c3b96a9` run with its own code.

| Case | Before | After |
|---|---|---|
| United Premier Silver 2027 on 6,100 PQP, flight minimum not settled by the sources (experiment check 3.4) | ESTABLISHED | UNRESOLVED; the reason printed is the open question |
| United Premier Silver 2026 (the rule checks the four-flight minimum) | ESTABLISHED | ESTABLISHED |
| 2027, 5,400 PQP | NOT_AVAILABLE | NOT_AVAILABLE (a "no" is not turned into "unresolved") |
| Sapphire Reserve welcome offer, "new applicants only", account opened 2024, candidate promoted as written | ESTABLISHED | promotion refused; once classed, UNRESOLVED |
| All benefits established on unchecked conditions for that account | 9 | 0 (58 real candidates refused until classed) |
| Project store: JAL business award via JAL miles (rule says the account must be 60 days old) | ESTABLISHED | UNRESOLVED, also after the proposed review |
| Project store: Marriott Titanium to JAL Crystal to oneworld Ruby (rule says Crystal depends on FLY ON Points, not the link alone) | CONDITIONAL | UNRESOLVED, also after the proposed review |
| Project store: Amex points to Aeroplan to ANA business award | ESTABLISHED | UNRESOLVED now; ESTABLISHED once a reviewer applies the proposed classes |
| Nine Capital One transfers with a published ratio | calculated | calculated (the tenth, "U.S.-based accounts only", is declined in both) |
| A recorded rate revised in place: answer for an earlier date | 1,200 became 800 | refused; with a declared correction it is accepted, logged and reversible |
| A rule retired as ended: answer for a day it was in force | lost (300 became 60) | kept (300) |

Eric's own profile (records untouched): four derived answers moved from CONDITIONAL to UNRESOLVED (`hyatt.aeroplan_challenge`, `hyatt.globalist`, `jal.crystal`, `oneworld.ruby`). Under the proposed classes they stay UNRESOLVED, for stated reasons: whether an Aeroplan status obtained through the Marriott match is accepted for the Hyatt challenge is an open eligibility question on the rule, and Crystal depends on points the rule does not check.

## 3. The reusable mechanism

`docs/CONDITION_REVIEW.md`. In brief: every restriction and open question on a rule carries a class recorded by a named promotion reviewer. Restrictions: `enforced` (must name what on the rule enforces it), `unchecked`, `usage`. Open questions: `affects_eligibility`, `informational`. `unchecked`, `affects_eligibility` and **no class** block: nothing is established through the rule and each blocking text is given as the reason. One function decides (`conditions.blockers`), used by the engine, the calculations, earned benefits, credits and the card table. Promotion refuses a candidate whose texts are not all classified. Editing a rule's texts after review sets the review aside. History: dated successors; in-place rewrites of recorded terms refused unless declared a correction; retirement keeps earlier answers; the audit trail is unchanged in kind.

## 4. Remaining limitations

1. **The class is a judgement.** A reviewer who classes a real eligibility condition as a usage term gets a false positive. The experiment keeps this visible (check 0.5). The record names the reviewer; `explain` prints every text with its class.
2. **Nothing new is resolved.** Blocked benefits stay unresolved until the condition is modelled. Account age, primary or authorised cardholder, country of a loyalty account, new applicant, and how a status was obtained are not recorded anywhere. Each is a design decision, not made here.
3. **The nine verified rules await review** (27 texts). Engineering's proposal is offered with reasons and applied only in copies. Three of its calls deserve a second look and are listed at the top of the file.
4. **Engineering's classes for the experiment's content are not a content review** (`restriction_classes.json`, the `condition_classes` maps in the sheets). One is a judgement worth naming: the Capital One card requirement is classed as enforced by holding Capital One miles, on the reading that such miles exist only on a miles card; Capital One's card pages name Venture X, Venture and VentureOne as the cards that can transfer.
5. `baseline` and `excludes` rules are not gated: they establish nothing.
6. A store whose vocabulary names no reviewers accepts any attested name, as promotion always has. A hand-edited review is caught by lint, not by the engine.
7. A successor entered through the tables takes two imports.
8. `scripts/compare_with_baseline.py` is not expected to pass any more (answers changed on purpose); `before_after.py` replaces it.
9. The three synthetic fixtures were regenerated by their builders, so their audit files have new ids. The project's audit trail is untouched.
10. No lower-capability model has run OP-14.

## 5. Existing test expectations that changed

Each is marked `CHANGED 2026-11-17 (safety correction)` in the file. Eight of the 358 earlier tests:

| Test | Was | Now | Why |
|---|---|---|---|
| `test_e_maintenance` retire | earlier date NOT_AVAILABLE after retirement | earlier date keeps ESTABLISHED; later date NOT_AVAILABLE | retirement erased history |
| `test_e_maintenance` revise dates and restrictions | ESTABLISHED at once | UNRESOLVED until a reviewer classes the new restriction, then ESTABLISHED | a new text is not approved by default |
| `test_k_tables` change one benefit | in-place edit accepted | refused; accepted with `correct`; unresolved until classed | history protection and classification |
| `test_p_credits_pipeline` retired rule | earlier-date picture empty | earlier-date picture as before retirement | as above |
| `test_p_credits_pipeline` table edits (2 tests) | changeset data without a declaration | data carries the declared correction | corrections are declared |
| `test_live_data` second hop | `oneworld.ruby` CONDITIONAL | UNRESOLVED | rests on unclassified, unchecked text |
| `test_live_data` practical query | 2 established, 1 conditional | 0 and 0; a new test shows 1 established with the proposal in a copy | as above |

Inputs adapted without a change of expectation: `_action = correct` or `correction` where a test edits terms in force; `conditions` on scratch promotions of real Bilt candidates; fixture rules in `tests/util.py` stand for reviewed rules (all usage) unless a test says otherwise. In the viability tests written last commission: the `unchecked` list became a class (same expectations), and the experiment's checks 0.2 to 0.5, 1.1, 3.4, 3.6 and 3.7 assert the corrected behaviour.

## 6. Independent review

```
git fetch origin dev/foundation-safety-correction && git checkout dev/foundation-safety-correction
python3 -m unittest discover -s tests                    # Ran 412 tests ... OK
python3 experiments/safety/before_after.py               # runs c3b96a9 beside this commit; "every line is as expected"
python3 experiments/viability/run.py                     # 52 checks, 0 failed
python3 scripts/mutation_check_safety.py                 # 25 mutations, 0 not caught
python3 -m prices lint                                   # 0 errors; 9 rules listed as CONDITIONS_NOT_CLASSIFIED
python3 -m prices explain --profile eric jal.crystal     # the reason, and each text with its class
git diff c3b96a9 --stat -- data profiles tables          # empty
python3 experiments/safety/proposal.py --list            # the classes proposed for the nine rules
```

Questions a reviewer should press on: (a) are any of the proposed classes in `live_rules_proposal.json` wrong; (b) is "no class blocks" acceptable for the nine existing rules until they are reviewed, given what it does to current answers; (c) `tests/test_t_safety.py`: is there a way to get ESTABLISHED through a rule with an unsettled condition that it does not try; (d) the eight changed expectations above.
