# OP-10  Maintain cards and card benefits through the tables

**Commands:** `python3 -m prices tables export | status | plan | import`

**Use when:** a card's benefit changed, gained an end date, was removed, or you have the card's own document showing that a benefit applies or does not apply. Also for card roles (issuer, network and so on) and fees.

Do **not** use for: who holds a card (OP-07), status matches and transfers between programs (OP-03), promotions with an end date (OP-09).

## 1. Inputs and context
- The task, and the source document for the change. For a card benefit this must be the **card's own** guide or terms. A network's general page shows only what the network advertises.
- Current state: `python3 -m prices cards` and the files in `tables/`.
- Background: `docs/RELATIONAL_TABLES.md` sections 3 to 6.

## 2. Permitted actions

Work in one sitting: **export, edit, plan, import.**

```
python3 -m prices tables export
   ... edit the CSV files ...
python3 -m prices tables plan   --author "your name" --date YYYY-MM-DD
python3 -m prices tables import --author "your name" --date YYYY-MM-DD
python3 -m prices lint
```

| You want to | Do this in the tables |
|---|---|
| **Change a benefit's wording, limits or dates** | 1. Add a row to `sources.csv` for the new document. 2. In `card_benefits.csv` edit `summary`, `restrictions`, `valid_from` or `valid_to`. 3. Add the new source id to that row's `evidence` cell (keep the old ids; separate with `;`). |
| **Give a benefit an end date** | Same as above, editing only `valid_to`. |
| **Record that a tier benefit applies to a card** | Add a `sources.csv` row for the card's own document, with the card id in `applies_to`. Add a `card_benefits.csv` row: new `id`, `card`, `benefit`, `applicability` = `confirmed`, `summary`, `evidence`. Leave `=` columns, `_action`, `ended_on` and `review_by` empty. |
| **Record that a tier benefit does not apply** | Same, with `applicability` = `excluded`. If the card has its own stronger version, put that benefit's id in `superseded_by` and add a second `confirmed` row for it. |
| **Change `confirmed` to `excluded` or the reverse** | Not in place. Retire the old row (next line), then add a new row with a new id. |
| **Remove a benefit that has ended** | Add a `sources.csv` row for the notice. In the benefit's row put `retire` in `_action`, the last valid day in `ended_on`, and add the source id to `evidence`. Change nothing else in that row. |
| **Re-confirm a row after re-reading its source** | Add a fresh `sources.csv` row. Put `confirm` in `_action`, a new date in `review_by`, and add the source id to `evidence`. |
| **Withdraw a row that is still a candidate** | Put `withdraw` in `_action`. Change nothing else. |
| **Change a card's issuer, manager, network, tier or fee** | Edit the cell in `cards.csv`. Add a source row and add its id to the card's `sources`. Use `none` for "confirmed none"; leave blank for "not recorded". |
| **Add a card, bank, network or tier** | New row in `cards.csv` or `parties.csv` with a new id. |

You may **never**: delete a row; change an `id`; edit a column whose name starts with `=`; edit a `view_` file or `MANIFEST.json`; edit an existing `sources.csv` row; remove an id from `evidence` or `sources`; edit a retired row; add anything about who holds a card.

A tier benefit with no card-specific document stays out of `card_benefits.csv`. Leaving it out is correct: it shows as `UNPROVEN`. Do not add a `confirmed` row because "cards of this tier normally have it".

## 3. Source and evidence requirements
- Every change to an existing row needs a **new** source row, cited in that row.
- A `confirmed` or `excluded` row for a benefit that the tier advertises needs a source whose `applies_to` contains the card id. That source must satisfy the evidence policy by itself: one `official` document, or two `reputable_secondary` ones from different publishers. Set `applies_to` only if the document really is about that card.
- Write `summary` in your own words. Say only what the document says.
- `source_type` values are defined in `docs/MAINTAINER_GUIDE.md`.

## 4. Output
The edited CSV files, then the output of `tables import`. No changeset file is written by hand; the import writes them (ids start `cs-<date>-tbl-`). A new source row looks like:

```
id,url,title,publisher,source_type,retrieved_on,applies_to,summary,notes
ev-<card>-guide-<yyyymm>,https://...,Title of the document,Publisher,official,YYYY-MM-DD,<card id>,What it says about this benefit.,
```

## 5. Validation (done by the program)
`plan` and `import` check the same things; `plan` writes nothing. Checked: the tables are not out of date; headers; duplicate ids; deleted rows; read-only cells; which columns may change; that sources exist and are cited; then every resulting changeset against the full pipeline (schema, lint, evidence policy, card-specific evidence). **If anything fails, nothing is imported.**

## 6. Failure and escalation

| Message | What to do |
|---|---|
| `TABLES_STALE` | Someone changed the store after your export. Copy your edits aside, run `tables export`, redo them. |
| `EVIDENCE_REQUIRED` | Add a new source row and cite it. If you have no document, stop and escalate. |
| `LOGIC_CHANGE` | Retire the row and add a new one. |
| `CARD_SPECIFIC_EVIDENCE_REQUIRED` (at promotion) | The source is not about this card. Find the card's own document, or leave the benefit unproven. |
| `ROW_DELETED`, `READ_ONLY_COLUMN`, `READ_ONLY_VIEW`, `EVIDENCE_IMMUTABLE`, `EVIDENCE_REMOVED`, `ROW_READ_ONLY`, `CANDIDATE_READ_ONLY` | You changed something that may not be changed. Run `tables export` to get clean files and redo only the permitted edits. |
| `REJECTED: <row>: ...` | The row reached the pipeline and failed there. Read the message; fix the cell it names. |
| A date turned into `11/30/2026` | Your spreadsheet program reformatted it. Type it again as `2026-11-30` in a plain-text cell. |
| Sources disagree, or you are unsure whether a document is about this card | Change nothing. Escalate (see the maintainer guide). |

After a rejected import your edited files are still as you left them. Fix them, or run `tables export` to discard the edits.

New `tier_baselines` and `card_benefits` rows become **candidates**. They change nothing for anyone until a reviewer promotes them. Tell the reviewer; do not try to promote.

If the import prints `DOWNSTREAM REVIEW NEEDED: yes`, write the review note described in the maintainer guide.

## 7. How completion is independently established
- `tables import` printed `IMPORTED` and listed the expected operations.
- `python3 -m prices lint` prints 0 errors and no `TABLES_` warning.
- Running `tables import` again prints `NOTHING TO DO`.
- `python3 -m prices cards` shows the expected standing; the row in `card_benefits.csv` shows the expected `=state`.
- `python3 -m prices audit` lists the changesets under your name.
- For a retirement: the row is still in the table with `=state` = `retired`.
