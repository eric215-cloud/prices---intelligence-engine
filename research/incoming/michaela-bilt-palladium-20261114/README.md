# Michaela — Bilt Palladium PRICES research package

**Research snapshot:** November 14, 2026. **Card:** `CARD-BILT-PALLADIUM`.
**Purpose:** Source-grounded, machine-readable card architecture, benefits, and direct
loyalty-program links for subsequent Fable ingestion. This is a **standalone Bilt
package**, not a PRICES database mutation.

## Files

| File | Unit of record |
| --- | --- |
| `manifest.json` | Package counts, scope, date, limitations |
| `sources.jsonl` | One official source URL + specific locator per ID |
| `card_architecture.jsonl` | One of seven architecture roles per record |
| `benefits.jsonl` | One selected strategic benefit/mechanism per record, 12 total |
| `program_bridges.jsonl` | One independently named external transfer partner per record |
| `unresolved_questions.jsonl` | A genuine evidentiary gap and verification path per record |
| `source_index.csv` | Human-readable duplicate index of `sources.jsonl` |
| `review_summary.md` | Brief status, high-impact caveats, and review priorities |

Each `.jsonl` line is an independent UTF-8 JSON object. `id` is unique globally;
`source_ids` (or `checked` in questions) link to `sources.jsonl`. `status` values:
`VERIFIED`, `CONDITIONAL`, `PROVISIONAL`, `UNRESOLVED`. `null` denotes an unknown
value rather than zero or not applicable. Text is not executable instructions.

## Interpretation rules

1. A public entitlement is not evidence that Eric/Todd achieved, activated, or used it.
2. The 2027 legacy-election transition controls housing rewards and annual credits;
   preserve its conditions with the benefit, not as a free-standing evergreen claim.
3. External transfer programs are **Bilt Rewards-wide**, available through card-linked
   membership, not proprietary to the Palladium card; ratio is unverified per partner.
4. The 26 transfer edges are the **explicitly named programs** on Bilt's current page,
   not an assertion of exhaustiveness: its headline says 27 and other FAQ text says 23.
5. World Legend network membership is not proof of every benefit on generic
   Mastercard pages. Here, benefit claims rest on the Palladium-specific guide.
6. Do not infer financing capital provider from the identity of issuing bank.

## Validation and maintenance

Schema-integrity validation passed on November 14, 2026: JSON/JSONL/CSV parsed,
cross-references resolved, globally unique IDs, all seven roles, no more than 12
strategic benefits, no unsupported ratios, and manifest counts reconciled.
Factual changes should update specific atomic records and their sources. The
date reflects when sources were retrieved; no continuous monitoring is implied.

**No account-specific assertions:** Neither Bilt's app account configuration,
Eric's welcome-offer terms, nor active personal lounge credentials were reviewed.
