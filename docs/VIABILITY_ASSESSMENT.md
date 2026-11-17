# PRICES foundation viability assessment

Commission: "FABLE COMMISSION — PRICES Foundation Viability Test" (Bradley, 2026-11-16). Executed 2026-11-16 by Claude Fable 5.2 on branch `exp/foundation-viability`, created from `dev/eng-02b-bilt-election-correction` at `d36ebbc`. Reproduce with `python3 experiments/viability/run.py` (46 checks, about 20 seconds). Generated evidence: `experiments/viability/results/`.

> **Update 2026-11-17 (foundation safety correction, branch `dev/foundation-safety-correction`).** This assessment is kept as written. Three things in it are superseded: the `unchecked` list (section 4, D-53) is replaced by a reviewer's class for every restriction and open question, with a missing class blocking; check 3.4, which expected United Silver 2027 to be established on PQP alone, was a false positive and now asserts UNRESOLVED; and gaps G1, G4 and G18 are corrected. The experiment now has 52 checks. See `docs/CONDITION_REVIEW.md` and `experiments/safety/results/BEFORE_AFTER.md`.

## 1. Verdict

**Viable with specific architectural corrections.**

The central question was: after building the first set of capabilities, can we add substantially more programmes primarily through sourced data entry and review?

- **For cards, card benefits, transfers and per-dollar earning: yes.** 28 real records from three programmes the engine had never held went in with no change to the code. 26 were accepted exactly as first written. The engine then answered questions about them correctly, including calculations.
- **For the programmes' own mechanics: not yet.** How an airline or hotel status is earned and how long it lasts, recurring grants, a member's choice of award, caps and minimums: these could be written down, and some could be forced into a workable shape, but only 5 of the 28 records had every answer-changing term captured. Capturing the rest needs engine work for 20 of 28, and all of that work is reusable across programmes.
- **Two defects had to be corrected for any expansion to be safe**, and both are small: text restrictions were being presented as if the engine had checked them, and changed terms could not be recorded without rewriting or erasing answers about the past. Both are corrected on this branch and tested.

Nothing in the core needed rebuilding. The eligibility engine, the dated validity of rules, the evidence policy, the candidate quarantine and the audit trail all held on real content.

## 2. The actual baseline (before this experiment)

| | Observed |
|---|---|
| Verified rules in force | 10, all from the original build: Marriott top tier to JAL and Aeroplan status, the Hyatt and Aeroplan challenge, three transfers, award capabilities |
| Candidates awaiting review | 113, none promoted: Chase Sapphire Reserve 54, Bilt Palladium 52, network baselines 5, loyalty 2. 44 carry open questions |
| Real personal records | Eric: two confirmed statuses. No card, election, credit or threshold record for any real person |
| Code | 5,273 lines in `prices/`: engine 408, pipeline 700, lint 672, tables 587, elections 503, credits 462, earned 451 |
| Tests | 358 passing. **54 load the real store**; they check that it lints, the ten seed rules, the quarantine and the Bilt election gates |

What the passing suite did **not** show: no test had ever asked what a real cardholder would be told about a real card. Recurring credits and spending thresholds were proven on invented cards only. Transfers displayed a ratio but nothing calculated with it. Earning rates existed only as sentences.

Known before this work: one verified transfer rule rests on two secondary sources with the note that no official page was read; the Bilt Cash wallet is unsupported; card years are counted from the opening date for every issuer.

## 3. The real-data sample and its provenance

| Batch | Content | Source | Records |
|---|---|---|---|
| 1 | Airline and hotel loyalty links; Chase Sapphire Reserve benefits, earning, credits, $75,000 thresholds, 14 transfers, lounge and status enrolments | The ten verified rules; Michaela's packet of 2026-11-14 as converted by Argon (`data/candidates`) | 10 + 58 promoted in the copy |
| 2 | Capital One Venture X; ten Capital One transfer partners; World of Hyatt tiers and a milestone reward; United Premier qualification | Nine pages read by engineering on 2026-11-16, eight official (`batch2.json`, `sources`) | 28 |
| Maintenance | United's 2027 qualification terms | Two independent secondary sources (`maintenance.json`) | 4 |

Batch 1 added no source term: its earning rates, credit terms and unchecked conditions are transcribed from the candidates' own text. Batch 2 was read through a tool that returns extracts, and nothing in it has been reviewed by Argon. It is a test sample. Where a page was silent the field is absent: the Venture X credit's renewal date, how long a Hyatt or United status lasts, Capital One's transfer increment.

**Recorded, evaluated, calculated.** After the first capabilities, across the two batches:

| Kind of answer | Meaning | Examples that worked |
|---|---|---|
| Recorded | Sourced text, shown as text | Insurance terms, lounge rules, United's partner earning formula |
| Evaluated | The engine decided whether it applies to a person on a date | Marriott Titanium to oneworld Ruby (action needed); United Silver from three recorded figures; a 2026-only credit absent in 2027 |
| Calculated | Arithmetic on a published number | $400 of dining = 1,200 points; 30,000 Capital One miles = 22,500 JAL miles; a credit period from the account's opening date |
| Declined | The engine said why it would not answer | Chase to Hyatt (no ratio published); "travel" on a card with three travel rates; a credit whose four-year period has no stated start |

Fourteen questions with the engine's full output are in `results/ANSWERS.md`.

## 4. The restriction finding

The commission asked whether text-only restrictions could be mistaken for machine-enforced eligibility. **They were.**

- The 73 real non-transfer candidates carry 124 restriction strings. Engineering read each one (`restriction_classes.json`): 68 are usage terms, 24 are conditions on who has the benefit that the rule does not check, 12 are conditions that are checked, 11 are time windows, 9 are research notes.
- 20 of the 73 candidates state an unchecked condition, and 19 of those derive an entitlement.
- Promoted as they stand, they told an invented cardholder whose account opened in 2024 that nine such benefits were "DERIVED ENTITLEMENTS - established". One was the welcome offer for new applicants.

The correction is a field, `unchecked`, for conditions on who has a benefit. A rule that lists any never establishes its output: the answer is UNRESOLVED and the text is the stated reason. Usage terms stay in `restrictions` and are printed with the answer as text that was not evaluated. The guard also reaches credits and calculations. It is safe rather than clever: such a benefit stays unresolved until the condition is modelled as something a person can attest.

This needs a content pass by Argon over those 20 candidates before any of them is promoted.

## 5. Expansion economics (batch 2, code frozen at `6efaed6`)

| Measure | Result |
|---|---|
| Records needing a change to `prices/` | 0 of 28 |
| Accepted exactly as first written | 26 of 28 (93%) |
| Reshaped after a refusal | 2 of 28 (7%) |
| Pipeline operations refused | 3 of 82; each with a message that named the problem |
| Answers its main question correctly today | 23 of 28: 10 calculated, 13 evaluated |
| Recorded as text only | 5 of 28 (18%) |
| Fitted only by a workaround in how the record is shaped | 9 of 28 (32%) |
| Every answer-changing term captured | 5 of 28 (18%) |
| To capture the rest: schema change only | 3 of 28 (11%) |
| To capture the rest: schema and engine code | 20 of 28 (71%) |
| Reusable gaps / programme-specific gaps behind those | 23 / 0 |
| Values written per record: sheet / full changeset | 11.2 / 25.1 |
| Pipeline operations per record | 2.9 |

Reading these honestly:

- **The 93% is entry, not completeness.** The engine accepts a wide range of facts through data alone, and refuses malformed ones. That part scales.
- **The 18% is the cost of the missing mechanisms.** Nine of the 23 incomplete records are transfers whose minimum is text (small). Seven are Hyatt and United status rules: qualification is decided, but the engine does not know the status lasts into the following year. On 2027-02-01 it no longer shows a Silver status earned in 2026.
- **The workaround matters.** Status thresholds were entered as conditions on figures named by year (`united.2026.pqp`). It works and it is fully machine-checked, but it means new rules and new figure names every year, written by hand.
- **Human minutes were not measured.** An AI wrote the sheet. The counts above are what a person would have to write and how many decisions a reviewer would have to make.

History agrees. Two of the mechanism modules built before this test each serve the records of one card so far: elections (503 lines, two commissions) for five Bilt Palladium records, and earned benefits (451 lines) for Sapphire Reserve's five $75,000 unlocks. Both are general in design, but batch 2 could use neither: Hyatt's tiers were refused by the earned-benefit shape because they are not earned on a card. Bilt Cash is still unsupported.

## 6. Maintenance

| Test | Result |
|---|---|
| A real change arrives: United's 2027 terms, while the 2026 terms are in force | **Refused at the freeze** (`DUPLICATE_RELATIONSHIP`). After the correction: accepted next to the 2026 rules |
| History kept | The 2026 answer is unchanged, through the 2026 rule |
| New terms apply from their date | 5,400 PQP on 2027-07-01 is not Silver; 6,100 is, through the 2027 rule |
| Revising a term in place (a test edit) | **Rewrites the past**: the answer for 2026-11-16 changed from 1,200 to 800. The audit trail holds the old record and the revision was undone exactly |
| The same change as a successor rule | 1,200 until 2027-03-31, 800 from 2027-04-01; each answer names its own rule |
| A source is called into question | What rested only on it dropped to UNRESOLVED and its conversion stopped; both returned when the doubt was withdrawn |
| ... where a second sourced route exists | The answer stayed established and moved to the other route by itself |

So dependents follow correctly, and nothing is lost from the audit trail. But until this branch, the store could hold only one version of a relationship, so any change of terms either rewrote answers about earlier dates or, with `retire_rule`, removed the rule from every date. The correction: the same relationship with non-overlapping dates is a successor. Two hazards remain and are in the register: `revise_rule` still edits terms in place, and `retire_rule` still erases.

## 7. Defect and gap register

Full text in `experiments/viability/gaps.json`. "Needs": content = a pass over records; schema = fields only; schema+code = engine logic; tooling = commands around the engine.

| Id | Gap or defect | Needs | Scope | Status |
|---|---|---|---|---|
| G1 | Text restrictions presented as established eligibility | content | reusable | Guard built here; 20 candidates need the pass |
| G4 | Changed terms rewrote or erased the past | schema+code | reusable | Successor rules built here; in-place revision and retirement still open |
| G3 | Programme status: several measures, a period, a validity term | schema+code | reusable | Open. The largest gap for airline and hotel programmes |
| G2 | Account facts conditions depend on: primary or authorized user, new applicant, bonus history | schema | reusable | Open; such benefits stay unresolved |
| G6 | Recurring grants: anniversary points, free-night awards | schema+code | reusable | Open |
| G7 | Transfer minimum, increment, timing, bonus tiers are text | schema+code | reusable | Open; small |
| G10 | Earning rates with a cap or minimum purchase | schema+code | reusable | Open |
| G8 | A member's choice among awards | schema+code | reusable | Open |
| G9 | Earning formulas; grants of qualifying points | schema+code | reusable | Open |
| G11 | Redemption values, so nothing compares currencies | schema+code | reusable | Open |
| G5 | A credit whose period the source does not state cannot be recorded as a credit | schema | reusable | Open; small |
| G17 | A card cannot name its sources until a rule has brought them in | schema | reusable | Open; small |
| G18 | `retire_rule` removes a rule from every date | schema+code | reusable | Open |
| G15 | Card-year definitions differ by issuer | schema+code | reusable | Open (ENG-02B) |
| G14 | One fact entered twice in two shapes can disagree | content | reusable | Open; seen on Sapphire Reserve IHG Platinum |
| G12 | Tables author 7 record types; the rest need hand-written changesets | tooling | reusable | Open |
| G13 | One changeset per record, sources repeated in full, one promotion each | tooling | reusable | Sheet reader exists only in the experiment |
| G16 | Bilt Cash wallet and linked election | schema+code | programme-specific | Elections built; wallet not |

## 8. Scalability assessment

**What scales by data entry today** (on this branch): card benefit lists with their terms; who is eligible through chains of cards, statuses and enrolments; transfers, with amounts where the source publishes a ratio; per-dollar earning by category; recurring credits with a stated cycle; card spending thresholds; network baselines and exclusions; dated offers. A new card of an ordinary kind needs sourced entry and review, not engineering.

**What does not scale yet**: the inside of a loyalty programme. Every airline and hotel programme has tier qualification, and the engine has no proper place for it. Adding ten programmes now would mean ten sets of year-named workaround rules and no answer to "do I still have this status".

**What would have gone wrong without this test**: promotion of the Chase and Bilt candidates as they stand would have shown cardholders benefits they do not have, and the first change of terms would have corrupted past answers. Neither was visible from the passing suite.

**Review is the real bottleneck, not entry.** 113 candidates wait on one decision each. 44 are blocked by open questions, most of them transfer ratios the issuers do not publish. The pipeline is right to block them; the process needs a way to decide many records at once and to settle a ratio from the logged-in portal with the owner's attestation.

**Risk that remains**: `unchecked` depends on the person entering content putting each who-condition in the right field. Nothing can check that automatically. It needs to be a required reviewer decision per restriction.

## 9. Recommended next milestone: foundation corrections before more content

In order. The first three are small and make expansion safe; the fourth is the one that opens loyalty programmes.

1. **Adopt the restriction guard** (`unchecked`) into the main line. Add it to the card-benefits table. Require a recorded reviewer decision on every restriction: usage term or condition. Argon's pass over the 20 candidates comes before any promotion.
2. **Adopt successor rules.** Then make `revise_rule` refuse a change of terms unless it is marked as the correction of an entry error, and make a retired rule keep answering for dates before it ended.
3. **Supported intake.** A command that reads a sheet (sources once, one row per fact), enters it in a copy, reports refusals, and lets a reviewer decide records in one sitting. Tables for transfers, enrolments, thresholds and earning rates.
4. **Programme status qualification** (G3): thresholds on several measures with any-of and all-of, a qualification period, and a validity term, anchored to programme membership rather than a card. Test it on Hyatt, United and Marriott before building.
5. **Account facts** (G2): role on the account, how it was opened, bonus history. This turns most unresolved gates into attested answers.
6. **Limits on numbers**: earning caps and minimums (G10), transfer minimums (G7), credits with no stated period (G5), recurring grants (G6).

Defer: redemption values and award pricing, the Bilt Cash wallet, shopping portals whose rates change daily. Do not spend the next milestone on Bilt.

One practice to keep: **enter a real sample before building a mechanism.** Both defects, and the gap in status qualification, appeared as soon as real content was evaluated, and had survived every invented test.

## 10. Limits of this experiment

- Batch 2 is 28 records from three programmes, read from extracts by engineering. It is not reviewed content and must not be promoted from here.
- The freeze is real for the code, but engineering had read the Capital One pages before writing the calculations. Hyatt and United were not designed for.
- The restriction classification is one reader's judgement.
- "Verified" in the copy means promoted for the test, not checked by a person.
- No human effort was timed.
- The three mutation checks from earlier commissions were run once, in the clean checkout; no new mutation check was written for the code added here.

## 11. Deliverables

| Required | Where |
|---|---|
| Reproducible code and tests | `experiments/viability/run.py`; `tests/test_r_viability_capabilities.py` (23), `tests/test_s_viability_experiment.py` (1); 382 tests pass |
| Real-data sample and provenance | `batch1.json`, `batch2.json`, `maintenance.json`; section 3 |
| Factual queries and calculations | `results/ANSWERS.md`; commands `earnings` and `convert` |
| Intake and maintenance measurements | `results/RESULTS.md`, `results/measurements.json`; sections 5 and 6 |
| Defect and gap register | `gaps.json`; section 7 |
| Scalability assessment | Sections 1 and 8 |
| Next milestone | Section 9 |
| A process another operator can follow | `experiments/viability/README.md` |
