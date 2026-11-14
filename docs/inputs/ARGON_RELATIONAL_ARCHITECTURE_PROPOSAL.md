# Argon proposal — relational authoring layer for PRICES
**Status:** External architecture input supplied by Eric, NOT an approved schema or instruction to replace the existing engine.  
**Prepared by:** Bradley, November 14, 2026, from Argon's proposal and subsequent codebase analysis pasted into the Bradley conversation.  
**Audience:** Fable engineering commission; later Argon review.  
**Authority:** The existing PRICES code, validations, user-confirmed holdings, and project guardrails remain authoritative until a tested design decision is accepted.

## Why this input exists
Argon proposed a **human-readable relational editing layer** between Eric's EEP and Fable's deterministic PRICES Python/JSON knowledge base. The purpose is to make many cards, programs, statuses, issuer/network distinctions and separately maintainable benefits understandable and editable without manually navigating hundreds of atomic JSON files. Eric wants both straightforward situational answers and discovery of nonobvious, conditional, multihop paths; the information must remain accurate and inexpensive to maintain by lower-capability models.

This document summarizes the substantive content of Argon's supplied proposal. It is *not* a verbatim transcript, a finished schema, a mandate to use Google Sheets, or independent validation of card/product claims. Argon had inspected the original ZIP, not necessarily the later GitHub commits.

## The seven canonical credit-card layers proposed
For each card, distinguish:
1. **Card Product**
2. **Co-Brand Partner**
3. **Program Manager**
4. **Issuing Bank**
5. **Capital Provider**
6. **Payment Network**
7. **Network Tier**

A single organization may occupy more than one role. Roles are not interchangeable; do not infer a consumer benefit solely from a network-tier label, issuing-bank name, or co-brand. The layer labels describe a business architecture, not necessarily seven required PRICES entity kinds.

## Proposed human-editable relational workbook
Argon initially proposed four tabs for approximately 14 cards, then extended to seven ecosystem tabs, with an additional change log:

| Proposed tab | Purpose and indicative fields |
|---|---|
| 1. Portfolio Master Index | Card_ID; cardholder Eric/Todd; card product; seven-layer role assignments; annual fee; primary Guide to Benefits and pricing/terms links |
| 2. Underwriting & Servicing Rules | Issuing bank / program manager policy, application eligibility or velocity restrictions, servicing rules; source and review dates |
| 3. Network Tier Baselines | Documented baseline offerings for World Legend, World Elite, Visa Infinite/Signature etc., with applicability explicitly distinguished from marketing defaults |
| 4. Card-Level Benefits & Overrides Ledger | Distinct atomic perks, earn rates, credits, protection terms and conditions, source layer, card-specific applicability, issuer upgrades and express exclusions |
| 5. Loyalty Programs & Status Tiers | Programs/currencies/status levels; personal tier, qualifying metrics, expiry; downstream unlocks; acquisition pathway |
| 6. Portals & Card-Linked Accelerators | Portals, dining, linked-offer networks, currencies earned, eligible transaction categories, overlaps, status-qualifying metrics |
| 7. Cross-Program Bridges & Arbitrage Rules | Qualifying source state and conditions → resulting action/status/benefit; registration, provenance, windows, acquisition/retention, expiry |
| Change Log (originally also called Tab 5 in the earlier four-tab plan) | Before/after value, affected record/layer, date, source, reviewer, reason; preserve history |

This is a conceptual row/field vocabulary only. It is **not** approval to build an eight-tab sheet or to create a duplicate independent database. Normalize shared policies, but correctly model per-card applicability and exceptions.

## Argon's proposed PRICES integration
Argon described:
- **EEP:** user-facing description of Eric's existing ecosystem, priorities and holdings, *not* official evidence of public terms.
- **Relational middle tier:** human-scannable research/maintenance authoring surface; proposed Google Sheets/CSV/JSON or modular records.
- **PRICES:** existing deterministic entity/rule/evidence store, changeset validator, forward-chaining eligibility engine and discovery planners.

Argon envisioned an exporter/compiler translating relational rows into existing PRICES operations (e.g., add_entity, set_holding, candidate and vetted rule operations) and running apply/lint/tests. Existing engine files include `engine.py`, `changes.py`, `lint.py`, and discovery modules; exact current paths must be read from the repository. Argon proposed Python scripts such as `scripts/import_workbook.py` or `scripts/workbook_sync.py` as examples, **not binding file names or 50-/80-line implementation limits**.

A round-trip importer/exporter was proposed. The project must first decide which layer is authoritative and prevent silent two-way divergence, stale overwrites and provenance loss. A one-way authoring/compiler flow or generated read-only workbook may prove safer.

## Cases Argon wants represented
1. **Network applicability:** A card carrying a network tier does *not* thereby entitle its holder to every advertised tier perk. Argon floated inherited tier benefits guarded by `not holds optout.X`, but this is insufficient evidence. A tier benefit needs positive proof of applicability to the specific card/product/holder; absence of an opt-out is **not** proof.
2. **Issuer/product upgrade:** A card may provide stronger coverage than a generic network baseline. Record actual coverage, eligible transactions, caps and evidence; do not blindly merge conflicting baselines.
3. **Per-benefit atomicity:** The same card-program pair may involve transfers, status, credits and earning, each separate, dated and retractable.
4. **Household states:** Eric and Todd have distinct holdings and personal statuses. Authorized-user, companion and lounge-guest rules may permit limited sharing but must be evidenced.
5. **Earn stacks:** Card earn, shopping portals, card-linked offers and dining programs may interact, but currencies and elite-qualifying metrics differ. Do not add purported 4x+3x+5x unless the independent components actually stack for the same qualifying purchase; record exclusions and overlapping networks.
6. **Conditional chains:** Status pathways require correct source/status/acquisition method, action, registration, dates, retention, eligibility, evidence and downstream consequences; graph edges alone cannot prove an entitlement.
7. **Expiry and targeted offers:** Long-lived connections and annual milestones differ from temporary, targeted offers. Do not confuse potential eligibility with Eric's current activated status, or award routes with live availability.

Examples Argon used (NOT verified data for ingestion): Apple Card/World Elite opt-outs, Bilt Palladium/World Legend perks, Chase Sapphire Preferred insurance upgrades, AA eShopping/SimplyMiles/AA Dining stacks, Marriott Titanium → Aeroplan 25K → possible Hyatt challenge, and an illustrative AA tier threshold. These examples are test-case ideas; **do not promote them as sourced live terms or confirmed personal holdings.**

## Argon's phased population concept
1. Reconcile the complete Eric/Todd card roster (Argon had identified 11 names but asked Eric for three additional cards and holders); lock IDs, layers and primary sources.
2. Verify shared issuers/program managers/network baselines.
3. Audit card-specific benefits in manageable batches against current official guides and terms.
4. Add programs, portals, bridges and Eric/Todd confirmed status and expiry information.
5. Compile through validated PRICES changesets, test, and maintain an audit log.

Eleven *illustrative roster candidates* referenced by Argon, **not an owner-confirmed complete holdings profile:** Amex Platinum; Bilt Palladium; Chase Sapphire Reserve; Citi / AAdvantage Executive; United Quest; Marriott Bonvoy Bevy; Prime Visa; Apple Card; Citi Strata Premier; Chase Sapphire Preferred; Citi / AAdvantage Platinum Select. Do not assign owners, exact product tiers, benefits, or statuses without checking.

## Maintenance suggestions from Argon
- Update at the layer where the actual rule changed; propagate implications via dependencies.
- Favor official primary sources (Guides to Benefits, specific product disclosures, issuer and program terms); third-party research may suggest candidates, not certify eligibility.
- Preserve old and new records, evidence references, reviewer and last-verified date; never silently overwrite.
- Review by volatility/expiry (Argon proposed quarterly sweeps, 90-day expiry alerts and 180-day stale flags as examples, not proven optimal schedules).
- Maintain official live URLs; consider dated snapshots of consequential documents and explicit source/evidence IDs.
- Routine maintenance must be doable by a cheaper model using bounded procedures with automated checks.

## Explicit engineering freedoms and guardrails
Fable should inspect actual code before proposing or implementing changes. The seven layers and tab names specify **information the system must be able to represent and communicate**, not mandatory schema or platform. Keep PRICES deterministic eligibility, circular-path safeguards, record provenance, candidate quarantine, audit trail, synthetic-vs-personal separation, tests and portable operation.

Do not build all capabilities in one batch. Demonstrate the minimum verified, maintainable data interchange and at least one realistic difficult exception. Prefer a small tested addition and checkpoint/branch commit over a grand untested rewrite. Do not quietly change the authority of the original JSON store or require permanent Claude/Fable access.

## Decisions still for Bradley/Eric after engineering assessment
- Authoritative editing/storage layer and conflict policy.
- Exact mapping from seven card roles to existing PRICES schema.
- Source/evidence registry and whether/how dated snapshots are preserved.
- Scope of household/shareability and arithmetic semantics in first tested increment.
- Google Sheets vs files: presentation/editor choice follows safety and interoperability tests.
- Real 14-card roster and person-specific holdings; currently incomplete.
