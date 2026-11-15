# Fable Commission — Earned benefits, achievement cycles and personal validity
Date: 2026-11-14
Sponsor: Eric
Coordinator: Bradley, Chief PRICES Specialist
Target: dev/fable-integration only; do not modify main
Status: Commission prepared for Eric to authorize execution. No real-card data is authorized by this brief.

## Why this is next
The relational foundation (head f1ff740 when reviewed) correctly separates product facts, tier baselines and card-level applicability. Eric identified a missing personal dimension: some benefits are *earned* through a requirement (for example, a card's annual spend threshold), may require subsequent activation, last for benefit-specific periods, and may be partly or wholly consumed. A product's advertised benefit is not evidence of a person's achievement.

Bradley's code inspection also found that prices/engine.py currently reads metric.value and metric.state when evaluating a threshold but does not check the metric's as_of date against the query date. Therefore, a later observation could affect a past-dated query. Existing metric records are one current value per ID, not an explicit annual achievement history. These are real hazards for milestone-based benefits, not evidence that the relational foundation failed its own commission.

## Goal
Deliver the smallest safe, portable, end-to-end mechanism to distinguish:
1. A sourced product/program benefit and its qualifying rule.
2. An individual person's account-scoped, period-scoped progress or qualifying achievement, with provenance and known/unknown dates.
3. Eligibility for a benefit versus its *actual* activation/acquisition.
4. An individual's benefit-specific effective date, expiration, and where relevant consumed/remaining amount.
5. Independent qualifying cycles (for example 2026 and 2027), without accidentally overwriting, retroactively granting, or double-counting rights.

Do not assume that a card holder has earned a milestone or that a benefit has been activated merely because it is offered or a spending threshold has been met.

## Starting context and constraints
Read CONTINUATION.md, STATUS.md, docs/RELATIONAL_TABLES.md, docs/SCHEMA.md, docs/DECISIONS.md, the existing engine, profile/metric/holding schemas, and changeset/audit pipeline first. Verify baseline on the current branch (144 tests reported at f1ff740; 0 lint errors, 1 prior Aeroplan warning). Preserve the established JSON store as authority, immutable public evidence, owner attestation boundaries, candidate quarantine, reversibility and offline Python-standard-library operation. Preserve the card/network non-inheritance guarantee.

Choose a compact representation based on what the current engine already supports. An entitlement instance/achievement record or another tested design is acceptable; do not graft a new authoritative spreadsheet database onto PRICES. Personal records stay person/account-scoped and separate from card product authoring tables. Do not conflate holder, authorized user, guest or companion; sharing is not part of this commission.

## Synthetic acceptance scenario
Use entirely invented cards, programs, benefits, people, terms and spend observations. Illustrate:
- One invented card with a qualifying calendar-year spending threshold of 75,000 currency units, checked against a scoped qualifying-account metric, not lifetime spend.
- A holder below the threshold; a holder achieving the threshold; and a second holder who did not qualify.
- One earned status benefit valid into a later February, another ending the preceding December; both from the same qualifying event.
- One award requiring a distinct enrollment/linking/activation step. Crossing the threshold must not be represented as having completed this step.
- One consumable credit where the original allowance, consumed amount and remaining amount are not conflated.
- A second qualifying year with independent progress, achievement and resulting benefit instances, including overlapping valid periods where applicable.
- A rule's public marketing/offer validity is different from the earned instance's personal expiration. When the original qualifying period ends, an acquired fixed-term entitlement must not silently disappear, and when that personal expiration arrives, it must not silently persist.
- A query made *before* an observation's as_of/achievement date must never use that later fact to establish historical eligibility. Unknown achievement dates must remain unknown; never infer precise start dates from a year-only attestation.
- Unrecorded, unconfirmed or conflicting progress/activation/expiry cannot be silently promoted to ESTABLISHED or AVAILABLE.

## Required deliverable
- A durable schema and/or minimal engine extension, through the ordinary changeset pipeline, with explicit permission/attestation requirements for personal facts.
- A CLI report usable by a maintainer: per person, account/card, qualification year, progress/achieved state, activation state, usable benefit, relevant date(s), and credit remaining when meaningful. The report must distinguish public rule, personal achievement and current entitlement.
- An inspectable chain from official/synthetic source rule through owner's qualification evidence/attestation to each displayed result.
- Preservation and audit history for updates and corrections; no direct file edits or automatic import of personal holdings from product tables.
- Synthetic fixtures, maintenance procedure, before/after demonstrations, and automated tests for all cases above, including time travel, overlapping cycles, stale observations, invalid input, idempotency and regression.
- All prior tests unchanged and passing, lint clean except documented baseline warning, fresh clean-clone/offline and export pass, byte-identical previous outputs where no new personal facts exist.
- A concise RESULTS document with exact commands, observed output, commit hashes, known limits, and what weaker models have/have not demonstrated.

## Scope limits and escalation
No real Eric/Todd spend figures, new real holdings, live card research, bank connections, account access, credential handling, UI, scheduled monitoring, broad household benefit sharing or portal earn-stack math. Do not invent an account statement or a source qualification date. If a clean implementation requires a semantic change to existing rules that breaks backward compatibility, stop and document the issue instead of approximating eligibility.

Checkpoint-commit recoverable increments to dev/fable-integration. A passing synthetic proof is required; architecture diagrams or prose alone are not completion.
