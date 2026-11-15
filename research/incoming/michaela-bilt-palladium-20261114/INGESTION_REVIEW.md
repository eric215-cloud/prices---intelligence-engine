# Michaela Bilt Palladium research — ingestion staging and Bradley review

**Status: STAGED RESEARCH, NOT AUTHORITATIVE PRICES KNOWLEDGE.**
Source: user-provided ZIP `michaela_prices_bilt_palladium_20261114.zip`, SHA-256 `76c3561e75f564e33e331324f227bea022849b90657d1c23ee37274281cfc1b5`.
Research snapshot: 2026-11-14. Saved by Bradley from Michaela's original files, unchanged. No real user holding, credit, membership, activation or rule has been added to PRICES.

## Observed package checks
- ZIP CRC checks: pass (9 files).
- JSON/JSONL parsing: pass.
- Counts: 6 official-source entries, 7 card architecture records, 12 selected benefit records, 26 program bridges, 5 questions; 6-source CSV index.
- Distinct record IDs: pass; source references all resolve; no unreferenced source.
- Independent primary-source spot checks: official Bilt Card Offer Terms (last updated 2026-10-27), Bilt Cash Terms (same date), named transfer-partner directory, and Palladium Guide to Benefits opened. The core 2027 legacy-election / $200+$400 vs $600 structure, Bilt Cash 12-month expiry, and Point Accelerator limitations are supported by the cited official sources. This is **not** a complete line-by-line factual verification of every finding.

## Mandatory gates before PRICES import
1. **Candidate quarantine.** This package is research input. Do not silently promote its records or treat `status=VERIFIED` as a PRICES reviewer decision.
2. **Product vs person.** No assumption that Eric has the published welcome bonus, selected/retained a legacy election, activated Priority Pass, obtained specific Bilt Cash credits, or transferred points. The authoritative user's account remains separate.
3. **2027 temporal conditions.** Account-open date, first 2027-or-later anniversary, rewards election and relevant billing-cycle transitions determine which terms apply; don't import a single evergreen credit rule.
4. **Program-wide transfers.** The 26 named links are Bilt Rewards program relationships, not 26 card-exclusive grants. Transfer ratios and posting times are deliberately `null`/unresolved. Do not infer availability or balances.
5. **Benefit granularity.** `BEN-BILT-012` bundles multiple distinct insurance/coverage types into a single selected strategic finding. Split into atomic coverage rules with their own triggers/caps before using it for comparisons or claims. `BEN-BILT-002`, `BEN-BILT-003`, and `BEN-BILT-004` likewise require structured conditional/time-specific subrules rather than copying a descriptive sentence as an unconditional benefit.
6. **Role mappings.** `co_brand_partner` and `issuing_bank` differ from current PRICES field names `cobrand_partner` and `issuer`; translate explicitly. Formal program-manager status is not established simply because Cardless is the servicer; economic capital provider remains unknown.
7. **Source identity and support.** Map source IDs to immutable PRICES evidence with appropriate card/product applicability and actual source scope. Evidence assertions are reviewable labels, not independent authentication.
8. **Maintenance.** Keep the nine supplied research files byte-for-byte intact; construct conversion changesets separately, run lint/tests, report unresolved records, and do not edit profiles/eric or profiles/todd.

Review owner: Bradley. This staging commit records receipt and structural checks only; no schema compatibility or end-to-end ingestion pass is claimed.
