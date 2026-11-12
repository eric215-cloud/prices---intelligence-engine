# Decision record

Each entry: the decision, why, and what would make it worth revisiting. Add new entries at the bottom; do not rewrite old ones.

## D-01  Python standard library only
**Decision.** No third-party packages. JSON files, `unittest`, a small in-house schema validator.
**Why.** The build environment had no package installs available, and the future maintainer may have even less. Zero dependencies means setup is "have Python". It also removes a class of breakage weaker maintainers cannot diagnose.
**Revisit if** the validator needs features beyond its subset; then vendor one file rather than add an install step.

## D-02  One JSON file per record, in git
**Decision.** No database. Records are small files under `data/` and `profiles/`.
**Why.** Anyone can open, diff and review a record. A weaker model reads one bounded file rather than querying a schema. Git gives history and undo for free. Expected scale (hundreds of rules, one person) does not need a database.
**Revisit if** the store passes a few thousand records or needs concurrent writers.

## D-03  AI proposes, software disposes
**Decision.** No AI call anywhere in the program. Research output enters only as changesets. Evaluation is deterministic.
**Why.** Routine operation costs nothing and gives the same answer twice. The model doing research can be swapped without touching the code. The only interface to an AI is "here is a task list (JSON); return changesets (JSON)".
**Revisit if** never; this is the core of the design.

## D-04  Four assumption levels instead of true/false
**Decision.** Statuses `ESTABLISHED / CONDITIONAL / UNRESOLVED / NOT_AVAILABLE`, computed by running the same chaining with different permitted assumptions.
**Why.** The brief's central requirement is that uncertain never silently becomes satisfied. Separate runs make that structural: an unconfirmed fact is simply not present in the strict run. It is also easy to explain to a maintainer.
**Alternatives rejected.** Probabilities (false precision, no way to source them); a single three-valued pass (cannot tell "do this" from "confirm this").

## D-05  Least fixed point from base facts
**Decision.** Derivations only grow upward from holdings. Negation is stratified; negation on a cycle is a lint error.
**Why.** This is what makes circular rule sets harmless without a chain-length cap, and guarantees every established result has a finite derivation ending in confirmed facts.

## D-06  `acquire` and `grants` are different rule kinds; holdings carry `acquired_via`
**Decision.** Eligibility to obtain a status is not the status. An obtained status is a personal holding with its own dates, linked to the rule it came through. Retention terms live on the rule.
**Why.** This is the acquisition/retention distinction in the brief. It lets the engine answer "Titanium expired; what about the Aeroplan status?" from recorded terms rather than from graph shape.

## D-07  The engine never ends a holding
**Decision.** When retention fails or is unknown the holding becomes `UNRESOLVED` and is flagged. Only the owner's attestation changes a holding.
**Why.** Programs often do not withdraw matched status immediately, and terms are frequently silent. The real account state is a fact about the world that only the owner can confirm.

## D-08  Stale verified rules still apply, loudly
**Decision.** A verified rule past `review_by` keeps working and raises `STALE_RULE` wherever used.
**Why.** Automatically downgrading every overdue rule would turn a missed maintenance pass into a wall of UNRESOLVED and hide the real signal. The flag appears in status, goal and timeline output so it is never silent.
**Revisit if** maintenance proves irregular; then downgrade after a grace period.

## D-09  Evidence policy
**Decision.** A verified rule needs one `official` source or two `reputable_secondary` sources from different publishers. `community` never verifies. The policy is data (`vocab.json`), enforced by lint.
**Why.** Simple enough to apply mechanically; strict enough to keep forum rumours out.
**Known weakness.** `source_type` is assigned by whoever writes the evidence. A careless maintainer can mislabel. Mitigation: promotion is limited to named reviewers.

## D-10  Candidates are quarantined; promotion needs a named reviewer
**Decision.** Discoveries go to `data/candidates/`. Only people listed in `vocab.json` `promotion_reviewers` may promote.
**Why.** "Unverified research should not automatically modify authoritative records."
**Honest note.** The commissioning build is on the reviewer list and promoted the first ten rules itself. This is a procedural control, not a cryptographic one: nothing stops a maintainer typing a reviewer's name. Remove "Commissioning build" from the list once a person has spot-checked the rules.

## D-11  Changesets are the only write path, with a narrow whitelist per operation
**Decision.** Fifteen operations, each touching named fields only. Rule logic (`kind`, `output`, `when`, `retention.mode`) cannot be edited in place.
**Why.** Bounded operations are what a weaker model can do reliably. Changing a rule's logic is a new claim and should go back through candidate and review.

## D-12  Coverage ledger as the discovery mechanism
**Decision.** Discovery is defined as filling cells of (entity × question). Planners list empty and stale cells.
**Why.** It turns "think of connections nobody thought of" into a countable, repeatable job. The frontier extends itself: a promoted rule makes new entities reachable, which creates new cells. Negative results are recorded so effort is not repeated, and expire so the question is asked again.
**Limit.** It finds what the question list can express. New kinds of relationship need a new question in `vocab.json` (a reviewer task).

## D-13  Temporary things are observations with a mandatory end date
**Decision.** Promotions and availability are `data/observations/` records, never rules; `prune_observations` deletes expired ones.
**Why.** Keeps the rule base from filling with dead deals.

## D-14  No prices unless sourced
**Decision.** Capability records carry free-text economics notes. Numeric point prices are recorded only with a source; otherwise the note says "not recorded".
**Why.** During commissioning, sources disagreed on Aeroplan pricing because of 2025 and 2026 chart changes. A wrong number is worse than none.

## D-15  Synthetic and real data never mix
**Decision.** Profiles declare `synthetic`. Lint rejects synthetic confirmations in real profiles and synthetic evidence can never verify a live rule. Test fixtures live only in `tests/`.

## D-16  Actions as entities
**Decision.** An enrollment, registration or required stay is an entity of kind `action`. Not done: the engine may assume it and reports `CONDITIONAL` with the action as a step. Done: a holding of the action (with an expiry if the activation expires).
**Why.** One mechanism covers enrollment, linking, registration, spend and stay requirements, and activation state.
**Convention.** For `acquire` rules the act of applying is the acquisition step itself; do not add a separate action.

## Departures from the brief, stated plainly

- The brief lists "matching" and "spending requirements" as things to represent. Spending and night thresholds are supported two ways: as `metric >=` conditions (tracked numbers) or as actions (things to do). There is no dedicated "spend" construct.
- "Actually available booking options" can only ever come from a person's live check. The system has no access to award search and should not pretend to.
