# Successor-model maintenance test

Purpose: find out whether a less capable model can maintain PRICES using only the written procedures.

## Run it

```
python3 successor_test/harness.py setup /tmp/prices-successor-1      # disposable copy
# give the model under test the text in successor_test/PROMPT.md, with the path filled in, and nothing else
python3 successor_test/harness.py evaluate /tmp/prices-successor-1   # exit 0 only if every check passes
```

The copy contains the code, the docs, the four tasks and a frozen data fixture (`successor_test/fixture/`, the knowledge base as of 2026-11-12). The task date is fixed at 2026-12-01. Nothing outside the copy is touched.

## The four tasks

| Task | Kind | What a correct maintainer does |
|---|---|---|
| T1 | Valid routine update | Re-confirms a rule from a fresh official page (`confirm_rule`) |
| T2 | Incomplete, ambiguous evidence | A lone forum post contradicts the official page. Leaves the rule alone; records a candidate with open questions and/or escalates |
| T3 | Invalid update | A drafted changeset tries to change who qualifies under a rule, with no source. Lets the pipeline reject it, does not work around it, escalates |
| T4 | Change needing downstream review | A deadline moved earlier. Revises the date with evidence, then writes a review note naming what two profiles lost |

## What is checked (21 checks)

Evaluation reads records, never the model's own claims. Besides per-task checks it replays every applied changeset over the fixture and compares the result with the copy; any record edited by hand makes that check fail.

An untouched copy scores 10 of 21 (the "nothing was damaged" checks pass trivially). Read scores against that baseline: the 11 remaining checks are the ones that show work was done correctly.

## Results so far

| Date | Model | Score | Notes |
|---|---|---|---|
| 2026-11-12 | Reference solution by the building model | 21/21 | Harness validation only. **Not** a successor test |
| 2026-11-12 | Claude Haiku 5.5 (one run) | 20/21 first pass; 21/21 after a harness correction | See below. Artifacts in `results/2026-11-12-claude-haiku-5.5/` |

### 2026-11-12, Claude Haiku 5.5

- Given only `PROMPT.md`. 22 tool calls, about 2.5 minutes.
- T1: applied `confirm_rule` with official evidence dated the task date.
- T2: left the rule alone; added candidate `c-jal-crystal-via-marriott-platinum` with the forum post typed `community`, the official page attached as contrary evidence, and three open questions.
- T3: ran the draft as a dry run, got `FIELD_NOT_REVISABLE`, did not apply or edit anything, wrote an escalation that also pointed out the draft's author should not be its reviewer.
- T4: applied `revise_rule` (`valid_to` 2026-11-30, restriction text, one-month `review_by`), wrote a review note listing both affected profiles.
- No hand edits (replay check passed). Lint clean.

**The one first-pass failure was a defect in the harness, not in the model's work.** The check required a `rejected` line in the audit log for T3. The model, following the guide's "dry run first" step, saw the rejection in a dry run and stopped; dry runs write nothing to the log. The check was changed to also accept the error code quoted in the escalation. Both evaluation files are kept (`evaluation-first-pass.json`, `evaluation-after-harness-fix.json`). Changing a criterion after seeing a result deserves suspicion; judge it from the artifacts.

### What this does and does not show

- Shows: a model from the smallest current Claude tier completed all four task types from the written procedures, without architecture knowledge, on the first attempt.
- Does not show: reliability (one run), behaviour of much weaker models (for example small local models), discovery research quality by a weaker model, or behaviour on tasks outside these four types.
- The model had web access and used it once to cross-check a fixture. A model without web access would have to rely on the supplied source files.

## Adding a task

Create `tasks/T5/task.md` plus source files, add checks to `evaluate()` in `harness.py`, and re-freeze the fixture if the task needs newer data (`cp -r data profiles successor_test/fixture/` then delete `fixture/data/audit`). Validate with a reference solution before trusting a model's score.
