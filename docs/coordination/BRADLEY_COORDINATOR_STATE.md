# PRICES — Bradley Coordinator State

**Purpose:** Durable project-coordination state for PRICES. This file exists so Bradley can resume project leadership after a context-window/office move without reconstructing the project from conversation history.

**Coordinator:** Bradley, Chief PRICES Specialist  
**User / final authority:** Eric  
**Reasoning requirement for consequential PRICES coordination:** High reasoning. Medium is not an acceptable operating configuration for consequential PRICES work based on repeated observed Execution Standard failures in the Constellation.  
**Execution standard:** ACT → OBSERVE → VERIFY → REPORT.

## 1. Coordinator role

Bradley owns project coordination and PRICES-domain integration, not every subordinate technical task.

Bradley is responsible for:
- preserving the project objective and architecture decisions;
- assigning work to the model/person best suited to it;
- reconciling research, architecture, code, and user-specific PRICES requirements;
- preventing scope drift and unnecessary expert-on-expert redesign;
- commissioning bounded work with acceptance criteria;
- checking outputs against the actual requirements and observed behavior;
- maintaining durable project state in GitHub;
- surfacing contradictions, unresolved decisions, and user decisions;
- integrating finished work into the broader PRICES ecosystem.

Bradley does not need to be the strongest coder or researcher in the system. The coordinator must understand the whole project well enough to direct and accept specialist work.

## 2. Current specialist/model division of labor

### Bradley
- Coordinator and PRICES domain lead.
- Maintains the integrated project view.
- Owns commissions, acceptance decisions within PRICES jurisdiction, continuity, and architecture integration.

### Fable 5.2
- Original PRICES engine author.
- Strongest current role: deterministic Python engineering, schema/engine extensions, tests, changeset machinery, portability.
- Access is temporary and expected to expire; do not assume future availability.
- Remaining Fable capacity should be spent on durable machinery rather than clerical population or UI polish.

### Gemini Argon
- Current architecture/research collaborator.
- Has already inspected the exported PRICES codebase and proposed the relational middle-tier / workbook architecture.
- Strongest current role: live-source research, fact checking, Google Workspace integration, relational data architecture, requirements.
- Current direct GitHub write access is not established. Do not assume it.

### Astra
- Reserve technical implementation resource after Fable access ends, especially if Argon cannot directly manipulate GitHub.
- Intended workflow when needed: Argon commissions a specific change; Astra evaluates technical feasibility/risk, implements and tests it in GitHub; Argon reviews the result against its architectural requirements.
- Astra should not reopen settled architecture merely because it prefers a different design. Genuine architectural defects are returned to Argon/Bradley rather than silently redesigned.

## 3. Current architectural direction

The project is converging on a three-layer information architecture:

1. **EEP — Eric's Ecosystem Priorities**
   - Human-readable personal context: holdings, priorities, statuses, strategies, travel interests, and significance.
   - EEP says what matters to Eric; it is not itself the governing evidence for public card/program terms.

2. **Relational human-maintained middle tier**
   - Proposed workbook/data layer for card stack, canonical seven-layer card architecture, benefits/overrides, loyalty programs/status, portals/card-linked accelerators, and cross-program bridges.
   - Intended to remain human-scannable and maintainable.
   - Proposed seven card architecture layers: Card Product, Co-Brand Partner, Program Manager, Issuing Bank, Capital Provider, Payment Network, Network Tier.
   - Exact schema is not yet final.

3. **PRICES deterministic engine / knowledge base**
   - Python/JSON engine already built by Fable.
   - Stores entities, rules, evidence, candidates, personal holdings, observations, and audit trail.
   - Performs deterministic eligibility/retention/time reasoning and discovery planning.
   - AI proposes/researches; deterministic software validates/applies/evaluates.

A controlled compiler/sync layer is likely to connect the relational middle tier to PRICES. This remains a design direction, not yet implemented.

## 4. Architectural guardrails already identified

- **Affirmative applicability:** Absence of a network-tier opt-out is not sufficient evidence that a cardholder benefit applies. Network inheritance must not turn missing evidence into entitlement.
- **One authoritative state:** If a workbook and GitHub/PRICES both contain data, synchronization must define authority, conflicts, provenance, and change review. No silent two-way divergence.
- **Candidate quarantine:** Bulk research or imported rules remain candidates/unverified until evidence and review satisfy PRICES policy.
- **Official-source preference:** Card/program rules should link to applicable official terms, Guides to Benefits, program terms, and offer terms where available.
- **Source registry concept:** Maintain live official links plus dated snapshots for material decision-relevant source documents; extracted structured rules should cite those sources.
- **No automatic action claims:** Eligibility is not acquisition; transfer capability is not sufficient balance; a route is not award availability; a status pathway is not confirmed status.
- **Household logic:** Eric/Todd logic must explicitly model holder, authorized-user, guest, companion, and shareability rules rather than treating the household as one person.
- **Stacking math:** Card earn, portals, card-linked offers, dining programs, elite metrics, and currencies cannot simply be numerically added without compatibility/eligibility rules.

## 5. Current implemented PRICES baseline

See repository root files:
- `STATUS.md`
- `CONTINUATION.md`
- `docs/ARCHITECTURE.md`
- `docs/DISCOVERY.md`
- `docs/MAINTAINER_GUIDE.md`

At the current baseline:
- deterministic eligibility engine exists;
- changeset validation/audit pipeline exists;
- discovery planners exist;
- evidence/candidate quarantine exists;
- 94-test baseline was established by Fable;
- Eric profile has at least Marriott Titanium and Aeroplan 25K recorded in GitHub;
- full card/loyalty/portal ecosystem is not yet loaded;
- relational workbook/middle tier is not yet implemented;
- autonomous live discovery executor is not yet implemented.

## 6. Existing commissioning artifact

`docs/commissions/2026-11-12-fable-session-1-discovery.md` exists.

It commissions an autonomous evidence-backed discovery investigator. It predates the newer Argon relational-workbook / seven-layer architecture proposal and therefore **must be reconciled before execution** rather than treated as the final current Fable brief.

## 7. Context-window resilience protocol

PRICES coordination must not depend primarily on Bradley's active context window.

At each substantive project checkpoint:
1. Update this file with newly settled architecture decisions, role assignments, and pending decisions.
2. Update `CONTINUATION.md` for implementation state and next technical step.
3. Store commissions/specifications in `docs/commissions/`.
4. Commit code/data changes with descriptive Git history.
5. Store results/acceptance evidence in repository documentation rather than leaving them only in chat.
6. On a Bradley office move, retrieve this file first, then `CONTINUATION.md`, then the latest commission/results files and relevant git history.
7. Do not require Eric to reconstruct decisions already preserved here.

This file is project coordination state, not a replacement for Bradley's broader Constellation continuity document.

## 8. Model/effort posture

For consequential PRICES coordination, High reasoning is part of the operating requirement.

Observed Constellation behavior reported by Eric:
- Medium reasoning has repeatedly failed the new Execution Standard in Max-GPT workflows.
- Medium remains suitable for casual/non-consequential conversation, but the model should be returned to High when consequential work resumes.

Do not infer that this is a universal benchmark result. It is a local operating requirement derived from repeated Constellation experience.

## 9. Immediate strategic objective

Use temporary frontier-model capacity to create durable capabilities that remain maintainable after those models are unavailable.

Current likely sequence, subject to reconciliation with Argon's next work:
1. Finalize the relational architecture and authoritative-source model.
2. Reconcile the existing Fable discovery commission with the new middle-tier/workbook design.
3. Spend Fable capacity on durable engine/schema/sync/discovery upgrades, not mechanical data entry where a cheaper model can do it.
4. Use Argon for live-source data engineering and architecture/research where it has comparative advantage.
5. Use Astra later for GitHub implementation/maintenance when required.
6. Keep Bradley as coordinator across all phases.

## 10. Open decisions

- Final relational workbook/tab schema.
- Exact source registry / snapshot storage design.
- Whether workbook is authoritative authoring layer or one synchronized view of PRICES.
- Exact network-tier inheritance model.
- Household/shareability semantics.
- Earn/stack calculation model.
- Final division of remaining Fable sessions.
- Whether Argon can obtain direct GitHub write access.
- Interface/hosting choice later; do not prioritize before the intelligence/data architecture is proven.

**Update this file whenever a material coordination decision changes.**
