# Relational tables: card architecture and per-card benefits

Built for commission `docs/commissions/2026-11-14-fable-relational-foundation.md`, in response to `docs/inputs/ARGON_RELATIONAL_ARCHITECTURE_PROPOSAL.md`. First increment. Everything demonstrated here uses invented cards.

## 1. What was decided

1. **The JSON store stays the only system of record.** Nothing in the tested behaviour gave a reason to move authority. A second authoritative copy would need merge rules; a view plus a validated input does not.
2. **Tables are CSV files in `tables/`.** They are a generated view of the store and an authoring input. Edits are compiled into ordinary changesets and pass through the existing pipeline. There is no other path from a table into the store.
3. **Flow is one-way per sitting: export → edit → import.** Import refuses if the store changed after the export. There is no two-way merge, so there is nothing to diverge silently.
4. **Network tiers confer nothing.** A tier's advertised benefits are recorded, but a benefit applies to a card only through a verified card-level rule with evidence about that card.
5. **Holdings are not in the tables.** Who holds what stays under OP-07 with the owner's attestation. Tables describe products, not people.

Decision entries D-17 to D-23 in `docs/DECISIONS.md` give the reasoning.

## 2. Architecture fit: what the engine already had, and what was missing

| Argon's requirement | Before this increment | Gap | Added |
|---|---|---|---|
| Card Product | Entity of kind `card` | None | — |
| Co-Brand Partner, Program Manager, Issuing Bank, Capital Provider, Payment Network | Not representable | No organizations, no role assignments | Entity kind `organization`; a `card` block on the card entity with one key per role |
| Network Tier | Not representable | Same | Entity kind `network_tier` (with its `network`); `card.network_tier` |
| One organization in several roles | — | — | The same id in several role keys |
| "Not recorded" versus "none" | — | — | Missing key versus `null`; blank cell versus `none` |
| Card-level benefit: atomic, dated, retractable, evidenced | Already expressible: a `grants` rule card → benefit with dates, evidence, `retire_rule` | None | Shown as rows in `card_benefits.csv` |
| Network-tier baseline | Only as a `grants` rule from something holdable, which would create the inheritance to be avoided | No way to record a sourced statement that derives nothing | Rule kind `baseline` (never evaluated) |
| Card-specific exclusion; upgraded term | Free-text `restrictions` only | No sourced "this card does not get B" | Rule kind `excludes`, optional `superseded_by` |
| Positive, card-specific proof | Evidence policy per rule, but evidence could not say what it is about | A network page could "verify" a card benefit | `applies_to` on evidence; lint `CARD_SPECIFIC_EVIDENCE_REQUIRED` |
| Source identity | Evidence records: stable ids, never edited | Could not be cited by an entity; no table view | `sources` on entities; `sources.csv` |
| Change log with before and after | Audit log and a copy of each changeset (new values only) | Old values not kept | `data/audit/previous/<changeset>.json`; `revert_changeset` |
| Edit an existing entity | `add_entity` only | No update operation | `revise_entity` (id and kind are permanent) |
| Several rows applied together or not at all | One changeset at a time | — | `changes.apply_many` |
| Two people kept apart | Separate profiles; one evaluation per person | None for independence | Tested explicitly |
| Authorized-user, guest, companion sharing | Not modelled | Open | **Not built** (section 8) |
| Underwriting and servicing rules (tab 2) | Not modelled | Open | **Not built** |
| Loyalty programs and status tiers (tab 5) | Fully modelled in the engine | No table view | **Not built**; changesets remain the path |
| Cross-program bridges (tab 7) | Fully modelled (acquire / grants / transfer, retention) | A flat row cannot hold `all` / `any` / `not` conditions safely | **Not built**; changesets remain the path |
| Portals, card-linked offers, earn stacking (tab 6) | Not modelled | Excluded by the commission | **Not built** |
| Dated snapshots of source documents | Not modelled | Open | **Not built** |

The seven layers are therefore one entity (the card) plus six role references, not seven entity kinds. This matches the proposal's own note that the layers describe a business architecture.

## 3. How applicability is decided

```
tier_baselines.csv     "tier T advertises benefit B"          rule kind baseline   -> derives nothing, ever
card_benefits.csv      "card C has benefit B"   (confirmed)   rule kind grants     -> holder of C has B, once verified
                       "card C does not have B" (excluded)    rule kind excludes   -> derives nothing; explains why not
```

For each card and each benefit its tier advertises, `python3 -m prices cards` reports one standing:

| Standing | Meaning | Holder gets it? |
|---|---|---|
| `CONFIRMED` | Verified card-level rule with evidence about this card | Yes |
| `EXCLUDED` | Verified card-level exclusion | No |
| `SUPERSEDED` | Excluded because the card has its own, different benefit instead | No (they get the replacement, listed separately) |
| `PENDING_REVIEW` | A claim exists but is a candidate or unverified | No |
| `UNPROVEN` | The tier advertises it; nothing on record about this card | No |

Safeguards, each enforced by lint and covered by a test:

- A person cannot hold a tier or an organization (`NOT_HOLDABLE`).
- No deriving rule may mention a tier or organization in its condition or output (`TIER_INHERITANCE`). This blocks "card grants tier" and "holds card and holds tier".
- A verified rule granting a tier-advertised benefit, and every verified exclusion, needs policy-satisfying evidence whose `applies_to` names the card (`CARD_SPECIFIC_EVIDENCE_REQUIRED`). The network's own page does not count. A rule of the form "has the card and has not opted out" fails this check.
- A card cannot both grant and exclude the same benefit over overlapping dates (`CONFLICTING_APPLICABILITY`).
- When a confirmed benefit expires or is retired, the standing returns to `UNPROVEN`. It never falls back to the tier.

`UNPROVEN` pairs for cards a person holds are listed as research tasks by `python3 -m prices discover applicability --profile <p>`.

## 4. The tables

| File | Rows are | Stored as |
|---|---|---|
| `parties.csv` | Organizations and network tiers | Entities |
| `cards.csv` | Card products with their six role assignments, fee and primary sources | Entities with a `card` block |
| `benefits.csv` | Benefit names | Entities |
| `sources.csv` | Source registry | Evidence records |
| `tier_baselines.csv` | What a tier advertises | `baseline` rules |
| `card_benefits.csv` | What a card has (`confirmed`) or does not have (`excluded`) | `grants` / `excludes` rules |
| `credits.csv` | Structured terms of recurring credits: one row per `card_benefits` row that has them (same `id`). An empty cell means the source does not say; `none` means the source says there is none. A rule in force changes only with a source id in `_evidence`; `_action = remove` takes the terms off (OP-13, `docs/RECURRING_CREDITS.md`) | `credit` block on the `grants` rule or on the candidate's proposed rule |
| `view_applicability.csv` | One line per card × benefit with its standing | Generated; read-only |
| `view_holdings.csv` | Who holds what | Generated; read-only |
| `MANIFEST.json` | Fingerprints of the exported files | Generated; do not edit |

Lists of ids in one cell are separated by `;`. Restrictions are separated by ` | `. Dates are `YYYY-MM-DD`.

## 5. Who owns which field

| Field | Authority | In a table you may |
|---|---|---|
| Any `id`; an entity's `kind` | Permanent once created | Never change it |
| Entity `name`, `notes`; card roles, `annual_fee_usd`; a tier's `network` | Store | Edit the cell → `revise_entity` |
| Card `sources`; rule `evidence` | Store | Add ids; never remove |
| A source row | Immutable once recorded | Add new rows only |
| Rule `summary`, `restrictions`, `valid_from`, `valid_to`, `review_by` | Store | Edit the cell and cite a **new** source → `revise_rule` |
| Rule `tier`, `card`, `benefit`, `applicability`, `superseded_by` | Fixed for the life of the row | Not change. Retire the row and add a new one |
| `=state`, `=last_verified`, `=benefit_name` | Derived from the store | Not edit |
| A new `tier_baselines` or `card_benefits` row | Enters as a **candidate** | Add it; a reviewer promotes it |
| A candidate row | Awaiting review | Only `_action = withdraw` |
| A retired row | History | Nothing |
| Holdings | Owner attestation (OP-07) | Nothing; view only |
| `view_*.csv`, `MANIFEST.json` | Generated | Nothing |

`_action` values: `retire` (with `ended_on` and a new source), `confirm` (with a new `review_by` and a fresh source), `withdraw` (candidates only).

## 6. Conflict and failure behaviour

| Situation | Result |
|---|---|
| Store changed after the export | `TABLES_STALE`. Nothing imported. Re-export, redo the edits |
| Any row invalid | Whole import refused. No record changes. The edited files are left as they are |
| A later changeset in the batch fails | Earlier ones in the same import are not applied |
| Row missing | `ROW_DELETED` |
| Same id twice in a file | `DUPLICATE_ROW` |
| New row repeats an existing relationship | `DUPLICATE_RELATIONSHIP` |
| New row reuses an id | `DUPLICATE_ID` / `ID_EXISTS` |
| Read-only column or view edited | `READ_ONLY_COLUMN` / `READ_ONLY_VIEW` |
| Existing source edited; evidence removed | `EVIDENCE_IMMUTABLE` / `EVIDENCE_REMOVED` |
| New source that no row cites | `UNUSED_SOURCE` |
| Change with no new source | `EVIDENCE_REQUIRED` |
| Nothing changed | `NOTHING TO DO`. Importing twice is harmless |
| A changeset is applied from the command line while tables are untouched | Tables are re-exported automatically |
| ... while tables hold unimported edits | Tables are left alone; `lint` and `tables status` warn `TABLES_STALE` and `TABLES_EDITED` |
| Data committed without re-exporting | Test `test_committed_tables_match_the_live_store` fails |

Undoing: every applied changeset leaves a before-snapshot. A reviewer can apply `revert_changeset`; it is refused if the records changed again afterwards.

## 7. Commands

```
python3 -m prices tables export                      # write tables/ from the store
python3 -m prices tables status                      # stale? unimported edits?
python3 -m prices tables plan   --author NAME --date YYYY-MM-DD    # show what an import would do; writes nothing
python3 -m prices tables import --author NAME --date YYYY-MM-DD    # all or nothing
python3 -m prices cards [--profile P] [--as-of DATE] # roles, and the standing of every benefit per card
python3 -m prices discover applicability --profile P # research tasks for UNPROVEN pairs
```

The maintainer procedure is `docs/operations/OP-10-tables.md`.

Try it on invented data: `python3 -m prices --root fixtures/synthetic-cards cards --profile synthetic-alex`, or run `python3 scripts/demo_card_maintenance.py`.

## 8. Not built, and known limits

- **Household sharing.** Two people are independent profiles and are never merged. Authorized-user, guest and companion rules are not modelled. An authorized-user card can be recorded today only as its own card entity with its own evidenced benefits.
- **Tabs 2, 5, 6 and 7 of the proposal**, earn rates and stacking arithmetic, bulk research of real cards.
- **Source snapshots.** A source is a URL, a date and a summary in the maintainer's words. The page itself is not archived.
- **`applies_to` and `source_type` are labels** written by whoever records the source. A careless label defeats the card-specific check. Promotion by a named reviewer is the control.
- **Benefit terms are text** (`summary`, `restrictions`). Caps and limits are not structured numbers and cannot be compared by the program.
- **Spreadsheet programs may reformat cells**, most often dates. Import rejects a reformatted date rather than guessing. Set columns to plain text, or use a text editor. Google Sheets was not tested.
- **One sitting.** If the store changes between export and import, the edits must be redone. A three-way merge was judged not worth its risk at this size.
- **Promotion is not available from the tables.** A reviewer applies a `promote_candidate` changeset (template in `docs/DISCOVERY.md`).
- **Lower-capability model run of OP-10: not performed.** The procedure was executed by the building model and by automated tests only.
