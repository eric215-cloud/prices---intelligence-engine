# Chase Sapphire Reserve (Personal) — PRICES Research Package

Prepared by Michaela, Travel Research Intern, for Bradley and Fable. Snapshot **2026-11-14**, U.S. **personal** Chase Sapphire Reserve only. This is a source-linked research artifact, not an account audit or authorization to transfer points.

## Files and ingestion

All text is UTF-8. Each `*.jsonl` file contains one complete independent JSON object per line; `source_index.csv` is a redundant flat source index. IDs are stable inside this snapshot. The files are intentionally **not** the canonical PRICES database schema; Fable should map independently into its controlled data model.

- `manifest.json`: snapshot metadata and record counts.
- `sources.jsonl`: Chase-published primary sources and pinpoints.
- `card_architecture.jsonl`: seven distinct required issuer/network/business roles.
- `benefits.jsonl`: twelve selected benefit families, including the $75k spending gateway.
- `program_bridges.jsonl`: individually maintainable transfer, lounge, elite and credit relationships; all five $75k unlocked effects are separate edges.
- `unresolved_questions.jsonl`: explicitly open questions, including personally qualified or activated benefits.
- `source_index.csv`: flat official-source index.
- `review_summary.md`: priorities, omitted lower-priority offers and important distinctions.

## Evidence and personal-state rules

- `VERIFIED` indicates a fact is directly supported, not that Eric has used it.
- `CONDITIONAL` indicates published facts depend on eligibility, action, card/account state or time.
- `UNRESOLVED` and `null` encode missing data, **not** a negative finding.
- The `personal_state` fields of benefits/bridges remain `null` because Eric's actual Chase account tracker, partner activations, credit usage and exact dates were not inspected.
- The presence of sequential relationships does not validate a multistep chain. Exclusions, enrollment and account state control.
- For point-transfer edges, `ratio=null` and `ratio_status=UNRESOLVED` mean no card-specific partner conversion rate is asserted. **Do not assign the newly reduced Preferred/Ink Hyatt 4:3 rate to Sapphire Reserve.**
- Current benefits may change without warning. For a live redemption, hotel charge, airport lounge or status use, re-verify operational terms and available account balances.

## Validated snapshot scope

The public $75,000 annual-purchases rule (calendar year) is separate from **actual spending achievement**. Primary status benefits unlocked by that threshold have different registration/wait and expiration rules. Additional $250 Shops and $500 Southwest credits have different usage conditions. The package captures each independently.

The published current annual fee is $795, with $195 per authorized user; Eric's actual assessed fees and existing-account offer are not presumed. Public new-cardholder acquisition bonus is not included among the twelve strategic benefit slots; it is not a promise to an existing holder.
