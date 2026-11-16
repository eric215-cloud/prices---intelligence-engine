# Foundation viability experiment

Commissioned by Bradley on 2026-11-16. Question: after a first set of capabilities is built, can PRICES add many more programmes mainly by sourced data entry and review?

The assessment is in `docs/VIABILITY_ASSESSMENT.md`. This folder is the reproducible demonstration behind it.

## Run it

```
python3 experiments/viability/run.py            # about 20 seconds; exit 0 only if all 46 checks hold
python3 experiments/viability/run.py --write    # also regenerates results/
python3 -m unittest discover -s tests -p "test_s_*.py"    # the same run as a test; also proves data/, profiles/, tables/ are untouched
```

The run copies `data/`, `profiles/` and `tables/` to a temporary folder and works only there. Real candidates are promoted in the copy alone, by the first listed reviewer, with a statement that it is an experiment and not a content review. Nothing in the project is promoted, and no real person's record is read for a decision or changed.

## Files

| File | What it is |
|---|---|
| `run.py` | The four phases and their checks. Each expected value was worked out from the source terms, not copied from output |
| `lab.py` | The throwaway copy, the pipeline wrapper that logs every attempt, invented people, the command runner |
| `batch1.json` | Batch 1: which existing candidates are used, and the structured terms transcribed from their own text |
| `restriction_classes.json` | Engineering's reading of all 124 restriction strings on the 73 real non-transfer candidates |
| `batch2.json` | Batch 2: 9 source pages, 23 entities, 28 records from programmes the engine had never held, and a per-record assessment |
| `maintenance.json` | A real change of terms (United, 2027) used in the maintenance phase |
| `gaps.json` | The gap and defect register |
| `results/RESULTS.md` | Generated: checks, measurements, per-record table, refusals, gap register |
| `results/ANSWERS.md` | Generated: each question, the command, and what the engine printed |
| `results/measurements.json` | Generated: the same numbers for machines |

## Where the freeze is

| Commit | State |
|---|---|
| `6efaed6` | **Freeze.** First capabilities built, batch 1 passing. `prices/` and `tests/` as batch 2 must use them |
| `21d4a4c` | Batch 2 entered. `git diff 6efaed6 21d4a4c -- prices tests` is empty |
| `c08acc7` | Maintenance phase. One correction to `prices/` (successor rules), made after batch 2 was measured |

To see the defect the correction fixed, check out `21d4a4c` and enter `maintenance.json`: all four 2027 rules are refused with `DUPLICATE_RELATIONSHIP`.

One limit on the freeze: engineering had already read the Capital One pages when the calculation code was written. The Hyatt and United content was not designed for, and that is where the frozen engine fell short.

## The intake process another operator can follow

This is what was done for batch 2. Steps 3 to 6 are one command (`run.py`); steps 1, 2 and 7 are the work.

1. **Read the issuer's or programme's own pages.** One source record per page: URL, title, publisher, date read, and a summary in your own words of only what the page says. Write "not stated" for what it does not say. Two independent secondary sources are the minimum when no official page exists.
2. **Write one row per fact** in a sheet shaped like `batch2.json`:
   - new things (card, currency, status, benefit, action) under `entities`;
   - each relationship under `records`: its kind (`grants`, `acquire`, `transfer`), what it needs (`when`), what it gives (`output`), a one-sentence summary, and which sources support it;
   - **every condition on WHO gets it** that `when` does not check goes in `unchecked`, word for word. How the benefit is used goes in `restrictions`;
   - numbers go in a structure only where one exists and the source states them: `earning` rates, `credit` terms, a transfer `ratio`. If the source is silent, leave the field out and add an open question. Never fill a gap from memory;
   - new spend categories go in `spend_categories`, each under its broader category.
3. **Enter the sheet in a copy of the store.** Entities, then one candidate per record with its sources, then promotion in the copy.
4. **Read every refusal.** Each is a rule of the store, with a message. Fix the row, or reshape it, and note which.
5. **Run lint.** No errors.
6. **Ask the questions the content should answer** for an invented person, and check each answer against the source by hand: one that should be established, one that should be unresolved, one calculation, one that must be declined.
7. **Hand over for review**: the sheet, the refusals, the answers, and for each record whether everything that changes an answer was captured. Promotion in the real store is the content owner's and a named reviewer's decision, record by record.

What this process does not yet have: a supported command for step 3 (the sheet reader lives in `run.py`), and a table for transfers, thresholds, earning rates and unchecked conditions (they cannot be entered through `tables/`).
