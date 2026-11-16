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

## D-17  The JSON store stays the system of record; tables are a view and a validated input (2026-11-14)
**Decision.** CSV files in `tables/` are generated from the store and may be edited; edits are compiled into ordinary changesets. No table is authoritative for anything.
**Why.** Argon's proposal left open which layer is authoritative. Two authoritative copies need a merge policy, and merges are where provenance is lost. A view plus a compiler needs none: there is one truth and one write path, the one already tested. Nothing observed while building this argued for moving authority out of the store.
**Revisit if** table editing becomes the main way of working and the one-sitting limit (D-18) is a real burden.

## D-18  Export, edit, import in one sitting; a stale table is refused, never merged
**Decision.** Import compares the tables with a fresh export of the current store. If the store moved since the export, the import stops.
**Why.** The alternative is a three-way merge per row. It is more code, harder to explain to a weaker maintainer, and its failure mode is a silent stale overwrite, which is the specific risk the commission names. Refusing costs the maintainer a re-export.
**Alternative rejected.** Per-row revision stamps. They allow partial merges but cannot tell a person's edit of a read-only cell from staleness.

## D-19  Seven card layers are one entity and six references; the engine ignores them
**Decision.** A card entity carries a `card` block naming its co-brand partner, program manager, issuer, capital provider, network and network tier. Organizations and tiers are entities of new kinds `organization` and `network_tier`. Nothing is derived from the block.
**Why.** The layers describe who stands behind a product. Treating them as descriptive makes the central safety property structural: the engine cannot infer a benefit from a role because it never reads one. Missing key means not recorded; `null` means recorded as none.

## D-20  Network baselines and exclusions are rule kinds that never derive
**Decision.** `baseline` (tier → benefit) and `excludes` (card → benefit, optionally `superseded_by`) are stored as rules, skipped by the engine, and read only by the applicability report. Lint forbids holding a tier, and forbids any deriving rule from mentioning a tier or organization.
**Why.** They are sourced statements and need everything rules already have: evidence, verification dates, review, retirement with history, candidate quarantine. A separate record type would have duplicated that machinery. Making them non-deriving kinds, and blocking the two ways a tier could be wired back in, keeps "a tier confers nothing" true by construction and not by convention.
**Trade-off.** `data/kb/rules/` now holds statements that can never fire. The kind names and `docs/RELATIONAL_TABLES.md` say so.

## D-21  Card-specific evidence is a label on the source, checked by lint
**Decision.** Evidence may carry `applies_to` (entity ids it is specifically about). A verified rule that grants a tier-advertised benefit, and every verified exclusion, must have policy-satisfying evidence whose `applies_to` names the card.
**Why.** "Positive card-specific applicability" has to be checkable by a program. This is the smallest check that makes a network's general page insufficient, and that makes "has the card and has not opted out" fail.
**Known weakness.** Like `source_type`, the label is written by a person or model. Named-reviewer promotion is the control (D-10).
**Scope.** Not required for a card's own benefits that no tier advertises; the ordinary evidence policy applies there. Requiring it everywhere would have invalidated an original acceptance test.

## D-22  New rows from tables are candidates; holdings never come from tables
**Decision.** A new `tier_baselines` or `card_benefits` row becomes a candidate and waits for a reviewer. Tables have no holder column, and the importer emits no holding operation.
**Why.** Bradley's guardrails: bulk-imported rules stay quarantined; roster examples must not become personal holdings. Who holds a card is a fact about a person and keeps its own path (OP-07, owner attestation).

## D-23  Every applied changeset keeps the previous version of what it replaced
**Decision.** `data/audit/previous/<id>.json` stores each replaced record. `revert_changeset` (reviewers only) restores them and is refused if the records changed again. `apply_many` applies a list all-or-nothing.
**Why.** The audit log held new values only, so "before" depended on git. Tables make multi-record edits routine; they need to be atomic and undoable inside the system.

## D-24  Earned benefits get their own personal record types (2026-11-14)
**Decision.** Two new record types under each profile: `qualifications/` (dated readings of progress, per account, measure and year) and `entitlements/` (the benefit as it sits on the account, with its own dates, allowance and uses). `holdings` and `metrics` are not extended.
**Why.** A holding has one validity range and no cycle, account, allowance or use; a metric is one number with one date. Stretching either would have changed what existing records mean. Separate types keep every existing code path and output untouched for anyone without such records (verified byte for byte, `scripts/compare_with_baseline.py`).

## D-25  `earns` is a rule kind the general engine never derives from
**Decision.** A rule of kind `earns` (card, measure, period, threshold, term, activation, optional allowance) is public knowledge only. The rule loop skips it. Its consequences enter the engine as base facts computed in `prices/earned.py` from a person's own records, and only when that person has such records.
**Why.** The existing rule kinds answer "does the condition hold now". An earned benefit depends on a figure scoped to one account and one year, read on a date, and then on a separate account fact. Evaluating it as an ordinary rule would make every cardholder "eligible" or would need lifetime metrics, which is the conflation the commission forbids.

## D-26  Reaching the threshold is eligibility; only an account record is possession
**Decision.** Achieved progress gives `can_get` (and `have` only as CONDITIONAL, needing an acquire step and, where the rule says so, the activation action). `have` is ESTABLISHED only from a confirmed entitlement record inside its own dates. Eligibility stays a separate fact after the record exists; it ends with the entitlement.
**Why.** Benefits post late, need activation, or never post. The owner's account is the only authority on what is there. Keeping eligibility after the record is added also stops the pipeline from reporting a false "something got weaker" when a benefit is recorded.

## D-27  Valid time; a later reading never reaches back; unknown stays unknown
**Decision.** Queries answer "what was true on that date, as far as the records now show". A reading counts from the date it refers to. For an earlier date: if a later reading is still below the threshold, the earlier date is known below (cumulative progress does not decrease); if the only at/above reading is later, the earlier date is UNRESOLVED. The crossing day is never computed.
**Alternative considered.** Ignore later readings entirely for earlier dates (answer NOT_AVAILABLE). Rejected: the records then say "not eligible" on a date when the honest answer is "not known", and a maintainer looking back would be told something false. UNRESOLVED never satisfies anything, so nothing is promoted.
**Not done.** Record-time ("what did the system believe on that date") queries. The audit trail holds that history; queries do not replay it.

## D-28  A metric observed after the query date is unknown, not satisfied
**Decision.** In a `metric` condition, an observation whose `as_of` is after the query date is treated as not recorded (UNRESOLVED).
**Why.** Bradley's hazard note: the engine compared `metric.value` with the threshold and ignored `as_of`, so a November figure satisfied a June query. This is a tightening of existing behaviour. No live rule or profile uses metrics and no existing test or output changed; a profile that did rely on a future-dated metric would now see UNRESOLVED on earlier dates, which is the correct answer.

## D-29  Dates may be the word `unknown`; they are never inferred
**Decision.** `observed_on`, `used_on`, `effective_from` and `expires_on` accept a date or `unknown`. `effective_from` and `expires_on` must always be written, so leaving a date out is a refused input, not a silent default. An undated reading must be `at_least` and is relied on from its confirmation date or the end of the year, whichever is earlier. An unknown start is unresolved before the confirmation date; an unknown expiry is unresolved after it.
**Why.** "Never infer a precise start from a year-only attestation." Making `unknown` a value the maintainer has to type turns guessing into a visible act and lets the program compute the consequences.

## D-30  The owner's confirmation stands; contradictions are shown, not overridden
**Decision.** A confirmed entitlement with no established achievement on file is ESTABLISHED and flagged `QUALIFICATION_NOT_RECORDED`. One contradicted by a final below-threshold figure, by conflicting readings, or by a second live record is UNRESOLVED and flagged. An active entitlement on an account no longer held is flagged `ACCOUNT_NOT_HELD` and left as recorded.
**Why.** The account is the authority on what is on it (banks grant exceptions; statements lag). The program's job is to keep the chain inspectable and say where a link is missing, not to overrule the owner or to hide the gap. Same principle as D-07: the engine never ends something on its own.

## D-31  Readings and uses are append-only; the identity of a record never changes
**Decision.** A correction marks the old reading or use `superseded` and adds a new entry (`correct_entry`). The rule, account and cycle of an entitlement cannot be revised; a wrong record is withdrawn (`state: superseded`) and a new one entered. The same figure for the same date, the same use, and a second record for the same benefit, account and year are refused.
**Why.** Idempotency and no double counting: typing a fact twice must not count it twice, and the history of what was believed must survive a correction without depending on git.

## D-32  The personal expiry governs; the rule's term only informs
**Decision.** The rule's `term` yields an expected end date that is displayed and used for one thing: when unclaimed eligibility lapses. An entitlement record's own `expires_on` decides when the benefit ends, whatever the rule says and whether or not the rule is still on offer, retired or flagged. Differences are flagged as information. Expiry with no later record, and a credit lapsing with something left, raise review flags.
**Why.** "The rule's public offer validity is not the instance's personal expiration." An acquired fixed-term benefit must neither vanish when the qualifying period or the offer ends nor persist past its own date.

## D-33  Earned benefits are not in the CSV tables
**Decision.** No table has a column for progress, achievement, entitlement or use, and the importer emits none of the personal operations. Earn rules are authored as candidates and promoted by a reviewer.
**Why.** D-22 (holdings never come from tables) applies with more force here: these are per-person, per-account, per-year facts needing owner attestation. A row-per-benefit table also cannot carry the `earn` block without inventing columns Argon's content architecture has not asked for.

## Departures from the brief, stated plainly

- The brief lists "matching" and "spending requirements" as things to represent. Spending and night thresholds are supported two ways: as `metric >=` conditions (tracked numbers) or as actions (things to do). There is no dedicated "spend" construct.
- "Actually available booking options" can only ever come from a person's live check. The system has no access to award search and should not pretend to.

## Departures from Argon's proposal (2026-11-14), stated plainly

- No workbook and no Google Sheets. Plain CSV files, because they diff in git, need no account, and open in any spreadsheet program. A workbook can be generated from them later if wanted.
- Six authoring tables and two generated views, not seven tabs plus a change log. The change log is the existing audit trail plus before-snapshots.
- The proposal's `not holds optout.X` inheritance pattern is rejected outright (D-20, D-21), as the proposal's own caveats and Bradley's guardrails asked.
- Tabs for underwriting rules, loyalty programs, portals and cross-program bridges were not built. Programs and bridges already work in the engine through changesets; their conditions (`all`, `any`, `not`, retention terms) do not flatten into one row without losing meaning.
- A round-trip importer/exporter exists, but only in the safe form: the export is always regenerated from the store, and an import is refused when stale.

## D-34  Argon's content is integrated by replay, and the audit history is only ever added to (2026-11-15)
**Decision.** The intake applied Argon's 246 packaged changesets through the ordinary pipeline on the engineering base instead of copying the package's files. Every changeset re-applied with identical results and store digests, and the result equals the package byte for byte, except that the package omitted two base audit records (`cs-20261112-101-set-holding`, `cs-20261112-102-set-holding`, Eric's holdings, by Bradley). Those are kept.
**Why.** Replay proves the content passes the current validator and pipeline, not just that files were copied; and an integration must never delete audit history. `scripts/verify_argon_intake.py` repeats the whole check from the committed archive.

## D-35  Elections are named outside the rules, by option entities that govern rules
**Decision.** An option is an entity of kind `election` (`group`, `card`, `governs`, optional terms). The engine adds "and the person elected this option" to each governed rule or candidate at evaluation time. The rules are not edited.
**Alternatives considered.** (a) Write `{"all": [holds card, holds option]}` into each rule: the Bilt rules are `card_benefits` rows whose condition the tables own (`{"holds": card}`, read back on export), and the content is Argon's. (b) `{"not": {"holds": other}}`: infers an election from silence. (c) Group metadata on rules: same table problem as (a).
**Why.** Works unchanged for table rows, hand-written rules and candidates, before and after promotion. A store with no election entities is unaffected (49 commands byte-identical against the intake commit).

## D-36  A person's election is a holding of the option; nothing is inferred from silence
**Decision.** The election is a holding (existing `set_holding` / `end_holding`, owner attestation, dates, audit). With no election recorded, every option that could apply is UNRESOLVED, never established, unless an option's published terms make it the default on that date. Conflicts, unconfirmed or undated records, records the terms forbid, an unknown anniversary and two card accounts all leave the group UNRESOLVED with a named flag.
**Alternative considered.** CONDITIONAL ("needs election"), as ENG-02's acceptance criterion words it. Rejected for the unrecorded case: CONDITIONAL in this engine means "a step the person could take", but an election has usually already been made on the account; what is missing is the fact. UNRESOLVED with "CONFIRM: election … not recorded" says that. Neither is ever established, which is what the criterion protects.

## D-37  The 2027 transition is computed from the account's own opening date
**Decision.** Option terms name a date D meaning "the first card anniversary on or after D", computed from an optional `opened_on` on the card holding. Before 2027 the anniversary is certainly later, so `opened_on` is only needed from 2027-01-01. It is never inferred from `valid_from`; holding the card before D does prove it was opened before D. A February 29 opening gives a February 28 - March 1 window that is treated as unknown.
**Why.** The commission: "respects the cardholder's actual anniversary". Calendar-date switching would be wrong for every cardholder whose anniversary is not January 1.

## D-38  A holding entered by mistake can be withdrawn
**Decision.** `end_holding` with `"data": {"withdrawn": true}` sets state `withdrawn`: kept on file, never in effect on any date. Owner attestation if the record was confirmed; a maintainer may withdraw an unconfirmed one.
**Why.** Resolving a contradictory election needs it: ending a mistaken record from a date leaves it in effect before that date. The same rule as `correct_entry` for earned-benefit entries (D-31). No existing holding is affected.

## D-39  Election definitions are content; revising one needs a reviewer
**Decision.** Adding an option entity needs no reviewer: gating can only narrow what a rule grants. Revising an `election` block (which rules it governs, its dates) needs a promotion reviewer, because removing a rule from `governs` would un-gate it. The four Bilt definitions are an engineering transcription of Argon's own restrictions text and ENG-02, for Argon to confirm.

## Limits of the earned-benefit work (2026-11-14), stated plainly

- Calendar-year periods only. Other cycle types are refused, not approximated.
- Refunds and clawbacks are not modelled; progress is assumed not to decrease within a year.
- Sharing (authorized users, guests, companions, household pooling) is not modelled at all. Every record belongs to one person and one of that person's own accounts.
- Not bitemporal (D-27).
- No lower-capability model has run the new procedure (OP-11). The procedure has been exercised only by its author and by automated tests.
- Full list: `docs/EARNED_ENTITLEMENTS.md` section 8.

## D-40  Credit terms live on the card-benefit rule, once (2026-11-15)
**Decision.** A recurring credit's terms are an optional `credit` block on the `grants` rule "card C carries benefit B". Nothing is added to the benefit entity. The offer's effective and expiration dates remain the rule's `valid_from` / `valid_to`; the block has no dates. A `credit` block is refused on any other kind of rule; an earned credit keeps its allowance in `earn.allowance`.
**Why.** The rule is the record that is sourced, reviewed, dated, retired and audited, and it is specific to a card (the same benefit could be carried by two cards on different terms). Putting terms on the entity as well, or dates in the block as well, would create a second place to disagree with.

## D-41  Absent means "the source does not say"
**Decision.** Every optional term is either stated (a number, or the word `none` where the source says there is none) or absent. Absent is reported as "not stated by the source" and is never read as zero, unlimited or unrestricted. Terms are replaced as a whole block, so a key left out of a correction goes back to "not stated".
**Why.** The commission: unknown must stay unknown. Three states per field (value, stated none, not stated) is the smallest representation that keeps them apart; a default would silently pick one.

## D-42  The credit block describes; the engine decides who it applies to
**Decision.** Adding, changing or removing a `credit` block changes no engine answer. Whether a credit applies to a person is the ordinary status of `have:<benefit>`, so holdings, verification, offer dates and cardholder elections (D-35) all count without any credit-specific logic. The credits report reads that status; it cannot grant.
**Why.** One eligibility mechanism. It is also what keeps ENG-02 intact: a credit on one side of an election is governed like any other rule.

## D-43  Periods that depend on an unrecorded date are unresolved
**Decision.** Calendar periods are computed from the date alone. An anniversary year needs `opened_on` on the person's card holding (never `valid_from`); a multi-year period needs its anchor: `opened_on`, or an owner-confirmed, dated record of the last use; with no stated anchor it is unresolved. A February 29 opening is unresolved on February 28 of other years. A period cut by the offer's `valid_to` keeps the published amount (not pro-rated).
**Why.** "Missing account-opening dates producing an unresolved anniversary rather than an invented date." Pro-rating would be inventing a number the source did not give.

## D-44  Personal balances reuse the earned-benefit record; one record per rule, account and period
**Decision.** What a cardholder's account shows for one period is an entitlement record whose `rule` is a credit rule in force, `cycle` the period label, with `allowance` and append-only `usage`. Same operations, attestation and correction rules as earned benefits (D-31). No record means NOT RECORDED. The record never grants the benefit, cannot be made against a candidate, and a single use above the published per-transaction maximum is refused.
**Alternatives considered.** Usage events attached to the rule with remaining = published amount minus recorded use: rejected, because it turns the published allowance into a personal balance by default. A separate balance-observation record type: a second accounting system with no demonstrated need.
**Cost.** One record per period is by hand; for a monthly credit that is twelve a year if someone wants a balance each month. Nothing is created automatically, because the program would have to assume the allowance.

## D-45  Terms are set by one operation that keeps the rule's identity; candidates are amended in place
**Decision.** `set_credit_terms` targets a rule id. For a rule in force it needs evidence meeting the evidence policy (as `revise_rule` does) and leaves `last_verified` alone: recording the credit's terms is not a re-verification of the rule. For a candidate awaiting review it needs neither reviewer nor new evidence, and the candidate keeps its id and its `proposed` status.
**Why in place.** The existing way to change a candidate is withdraw and re-add under a new id. For Argon's candidates that would change rule ids that election options already govern, and would reduce the count of proposed candidates. Terms are a structured transcription of what the candidate's prose already says; the reviewer sees them at promotion; every change is in the audit log with a before-snapshot.

## D-46  A separate table, credits.csv, keyed by the card_benefits row id
**Decision.** Terms are authored in `tables/credits.csv`, one row per card_benefits row that has terms, instead of eleven more columns on `card_benefits.csv`. An empty credits table leaves older import ids unchanged.
**Departure from Argon's wording.** ENG-01's acceptance says "round-trips credit columns in `card_benefits.csv` (or `benefits.csv`)". The round trip is delivered; the columns are in their own file. Reasons: most card benefits are not credits; the existing header, fixtures and input files stay valid; and a candidate's terms can be editable while its card_benefits row stays read-only. If Argon prefers columns on `card_benefits.csv`, the change is confined to `prices/tables.py`.

## D-47  Period ends are surfaced in review and timeline, on the period's last day
**Decision.** `review` and `timeline` list each allowance period ending in the window for credits that apply (or may apply) to the person, with the published amount and what happens to an unused amount. The key is present only when there is something to list, so reports for people without credit terms are byte-identical to before.

## D-48  The Bilt Legacy Election is one linked arrangement (ENG-02B)
**Decision.** A third group, `bilt-palladium.arrangement`, holds the one real choice (`legacy-election` or `refreshed-arrangement`). The four ENG-02 options keep their ids and governed rules and `follow` it. Before the transition anniversary the housing options are the cardholder's own choice and the legacy annual benefits apply automatically; afterwards only the arrangement decides.
**Alternatives considered.** (a) One group of two options governing all five rules: cannot express "Housing-only before the anniversary with the legacy benefits". (b) Retire the four options and add new ones: changes ids that tests, documents and the credits report refer to, for no gain. (c) Conditions written into the rules: the tables own those rules (D-35).
**Why.** It is what the published terms say (docs/ELECTIONS.md section 8), and it is the smallest change: a store without `follows` behaves exactly as before.

## D-49  The refreshed arrangement is recorded, not inferred, for accounts opened before 2027
**Decision.** Accounts opened on or after 2027-01-01 get the refreshed arrangement from opening with no record. For older accounts past their anniversary, the owner records it; with nothing recorded both arrangements are UNRESOLVED.
**Why.** The terms make it mandatory absent a Legacy Election, but PRICES cannot see that absence. A cardholder who made a Legacy Election and has not recorded it would otherwise be shown the $600 and lose Flexible Bilt Cash on paper. Silence is not evidence (D-36).

## D-50  Card anniversary as a window; `anniversary_on` on the card holding
**Decision.** Where an option says `anniversary_cycle_days`, the anniversary is counted from the first billing cycle after opening. It is exact only when the holding records `anniversary_on`; otherwise it is a window and dates inside it are unknown. Bilt's value is 62.
**Alternatives considered.** Keep the opening-date anniversary (wrong by up to a year for accounts opened late in a year); treat every date after `opened_on` + 1 year as unknown unless `anniversary_on` is recorded (honest but unusable).
**Why.** 62 days is not a published figure; it is two billing cycles, chosen so the window cannot be too narrow. It is stored on the definitions, where Argon can change it, not in code. One ENG-02 assertion that placed an anniversary on the opening date's own day was moved accordingly (results file).

## D-51  The four revised definitions are attested by "Commissioning build"
**Decision.** Revising an `election` block needs a promotion reviewer (D-39). The four revisions carry the attestation of "Commissioning build", stating that commission ENG-02B orders the correction and that no named reviewer has checked the definitions line by line.
**Why.** Fable is not Eric or Bradley and must not sign as them. The alternative, leaving the live definitions wrong until someone else applies the changesets, would not meet the commission. Eric or Bradley can countersign or revert (`revert_changeset`).

## D-52  Bilt Cash is not given a `credit` block
**Decision.** No ENG-01 credit terms were added to the Bilt Cash candidates. Election eligibility is decided; grant dates, per-grant expiry and the wallet are not computed (docs/ELECTIONS.md section 8.6).
**Why.** ENG-01 periods have one balance per period and an anniversary counted from `opened_on`. Describing Bilt Cash that way would look supported and be wrong.

## D-53  Text conditions on who has a benefit never establish it (`unchecked`) — experimental branch
**Decision.** A rule may list `unchecked`: conditions stated by the source on WHO has the output that `when` does not check. While any is listed, nothing is established through the rule; the answer is UNRESOLVED with the texts as the reason. `restrictions` keeps usage terms, which are shown as text and never block.
**Alternatives considered.** Cap every rule that has any restriction (makes nearly everything unresolved: 68 of 124 real restrictions are usage terms); a prefix convention inside `restrictions` (survives the tables but is easy to get wrong); leave it to review (the defect is that review did not catch it: 20 of 73 real candidates).
**Why.** Promoted as written, real candidates reported a new-applicant welcome offer as established for a 2024 account. The guard is deliberately blunt: to resolve such a benefit, model the condition as something a person can attest and put it in `when`.

## D-54  Calculations are a separate kind of answer (`prices/calc.py`) — experimental branch
**Decision.** `earnings` and `convert` return CALCULATED with rule, verification, evidence, arithmetic, assumptions and unevaluated terms, or NOT_CALCULATED with the reason. They use only verified rules in effect whose benefit the engine established for that person. Rates are published totals and are never added. Spend categories form a tree in the vocabulary; a question broader than the published rates is declined, not answered with the catch-all.
**Why.** A number looks more certain than a sentence. Every stop (no ratio, no rate, unverified, unconfirmed, unchecked condition) is a place where an estimate would otherwise appear.

## D-55  The same relationship with later dates is a successor, not a duplicate — experimental branch
**Decision.** Two rules with the same signature are duplicates only if their validity windows overlap. To change published terms: end the old rule (`revise_rule`, `valid_to`) and add the new one with a later `valid_from`.
**Alternatives considered.** Version terms inside one rule (a larger change to every reader of rules); keep refusing (then every change of terms rewrites or erases the past).
**Why.** United's real 2027 terms could not be entered beside the 2026 terms. Not yet done: `revise_rule` still changes terms in place, and a retired rule is still absent from every date.

## D-56  Real content is tested in a throwaway copy, with the code frozen between batches — experimental branch
**Decision.** `experiments/viability/run.py` promotes real candidates only in a copy, and its end-to-end test proves the project's data is untouched. The second batch was entered at a recorded commit with `prices/` unchanged.
**Why.** Both defects found here had survived 358 tests on invented data.

## Limits of the Argon intake and election work (2026-11-15), stated plainly

- The 113 Argon candidates are integrated exactly as packaged and none is promoted. Engineering did not review their content.
- Elections are recorded per person; two accounts of one card are reported, not resolved.
- The Bilt option definitions were first modelled as two independent elections. ENG-02B corrected that from the published terms: one linked arrangement (D-48 to D-52).
- No lower-capability model has run OP-12.
- Full list: `docs/ELECTIONS.md` section 7 and the commission results file.

## Limits of the recurring-credit work (2026-11-15), stated plainly

- No real credit has structured terms: Argon's candidates were not edited. Which of them fit the block is Argon's call.
- Statement-cycle card years, per-grant expiry (Bilt Cash), activation requirements, shared credits and non-calendar sub-periods are not modelled. Full table: `docs/RECURRING_CREDITS.md` section 6.
- The carried-over amount under a rollover rule is not computed.
- No lower-capability model has run OP-13.
