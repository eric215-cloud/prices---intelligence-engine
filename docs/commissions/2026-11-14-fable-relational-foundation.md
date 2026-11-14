# Fable Commission — PRICES relational foundation (first engineering increment)
**Date:** 2026-11-14  
**Sponsor:** Eric  
**PRICES coordinator:** Bradley, Chief PRICES Specialist  
**Working branch:** `dev/fable-integration`; do not change `main`  
**Status:** Active commission once Eric instructs Fable to execute.  

## Goal
Make the existing portable, deterministic PRICES system capable of **safe, maintainable authoring/import of structured credit-card and related ecosystem relationships**, using Argon's proposed seven-layer distinctions as requirements to evaluate, not a mandated replacement architecture. The result must remain usable and maintainable when Fable is unavailable.

Read first:
- `CONTINUATION.md`, `STATUS.md`, `docs/coordination/BRADLEY_COORDINATOR_STATE.md`;
- `docs/inputs/ARGON_RELATIONAL_ARCHITECTURE_PROPOSAL.md` (substantive Argon integration proposal, not final schema);
- current schema, decision log, operations, data models, change validator, linter and tests.

## Execution sequence
1. **Verify baseline:** on current `dev/fable-integration`, record original commit SHA, test count, lint status, commands and behavior before changing code.
2. **Architecture fit:** Determine what Argon's seven roles, card-level benefit applicability, source identity and authoring ledger can already express in the current PRICES entities/rules/evidence and what exact gaps require an extension. Write a concise architectural decision *in the code repository*, grounded in existing code. Preserve existing JSON as system of record unless compelling tested evidence supports a change; the workbook may be a generated view or validated authoring input, not a second diverging truth.
3. **Build the smallest functional end-to-end increment:** provide a human-editable, tabular representation (CSV/TSV or another readily inspectable standard format) for a small representative credit-card set, plus a documented, deterministic, validated one-way import/compiler (and export when it can be safe and accurate). Convert edits through existing PRICES changesets, not hand edits to authoritative files. Protect stable IDs, evidence references, previous values, duplicate detection, reversibility and invalid/unsupported updates. Explicitly define field ownership/authority and conflict behavior.
4. **Demonstrate applicability:** represent (a) a card/product's confirmed benefit, (b) a network-tier advertised baseline that **does not** establish an entitlement without card-specific positive evidence, (c) a card-specific exclusion or upgraded term, and (d) two people whose holdings cannot be conflated. Use clearly labeled **synthetic fixtures**, not real benefit claims or assumed Eric/Todd holdings.
5. **Prove maintenance:** provide a bounded junior-maintainer procedure for changing one atomic benefit and its evidence, updating applicability or expiration, and removing/retiring a benefit while preserving history. Run a concrete maintenance task and check effects with tests.
6. **Save incrementally:** make recoverable branch commits after each tested working stage. Preserve original tests and run full suite, lint and clean-clone/export verification after changes. Update `STATUS.md` and `CONTINUATION.md` accurately with results and limitations.

## Safety and semantic requirements
- The current deterministic inference rules, temporal handling, acquisition-versus-holding distinctions, evidence provenance, circular-path safeguards, candidate quarantine, audited changesets and synthetic/personal separation remain intact.
- Missing evidence or an absent opt-out must **never** establish that a network benefit applies. Positive card-specific applicability is required.
- Do not create qualified personal holdings from roster examples, marketing network lists or demonstration data.
- Keep Eric's and Todd's holdings independent; do not implement broad shareability assumptions. If full household rules are outside this bounded increment, explicitly record the remaining gap.
- A transfer capability is not a sufficient balance, an opportunity is not acquisition, and a route is not live seat availability.
- Do not implement earned-point stack arithmetic, a full UI, autonomous web discovery, 14-card bulk research, live offers or scheduled monitoring in this commission.
- Avoid new hosted databases or proprietary services. Prefer Python standard library and easily exported, documented data formats.
- If a fundamental proposed feature cannot be safely implemented, deliver the tested subset and a precise evidence-based blocker; do not silently approximate complex eligibility.

## Acceptance tests and handoff
Report exact commands, observed outputs, test counts, commits and paths. Include tests for:
- Baseline rules unchanged; backward compatibility.
- Synthetic card-level applicability, network perk explicitly not inherited, exclusion and upgrade behavior.
- Different holders with independent qualifications.
- Invalid and duplicate import rows rejected without partially applying updates.
- Import idempotency and historical record preservation; exported data not silently stale.
- Evidence-linked per-benefit updates/retires surviving validation and lint.
- Offline operation from a clean checkout, with no model-specific dependency.

The accepted deliverable is **working code and small fixtures**, not just a schema document. Do not self-certify untested behavior or weaken tests to create a pass. Finish with a concise report stating exactly what is built, not built, and what we should commission next.
