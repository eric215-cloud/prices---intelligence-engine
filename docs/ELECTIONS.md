# Cardholder elections (ENG-02, corrected by ENG-02B)

Some cards make the holder choose between options that cannot both apply. If each option is an ordinary rule "holding the card grants X", every holder is granted every option at once. This document says how PRICES prevents that. How to do the work: [operations/OP-12-card-elections.md](operations/OP-12-card-elections.md). Why: [DECISIONS.md](DECISIONS.md) D-34 to D-39.

## 1. What the existing conditions could and could not do

| Need | Existing conditions | Verdict |
|---|---|---|
| "Only with this election" | `{"all": [{"holds": card}, {"holds": option}]}` | Expressible, **but** the Bilt rules are `card_benefits` table rows. The tables write them as `{"holds": card}` and read the card back from that shape (`prices/tables.py`); editing the condition breaks the table round trip, and the content is Argon's |
| "Not the other option" | `{"not": {"holds": other}}` | **Wrong**: grants an option whenever the other one is merely not recorded, which is inferring an election from silence |
| Unknown election = unknown | No election recorded = condition unmet = NOT_AVAILABLE | **Misleading**: the cardholder may well have the option; the honest answer is "not known" |
| Two options recorded at once | Both holdings established, both rules fire | **Unsafe** |
| Switch at the cardholder's own anniversary | No anniversary concept | **Missing** |

So the smallest correct extension keeps the rules untouched and adds three things: a way to name the options of a group, a per-person, per-date decision of which option is in effect, and an opening date to compute anniversaries from.

## 2. The pieces

| Piece | Where | Kind of fact |
|---|---|---|
| Option of a group | entity of kind `election`, with an `election` block: `group`, `card`, `governs` (rule or candidate-rule ids), optional terms | public content |
| The person's election | a holding of the option entity (`set_holding`, `end_holding`; owner attestation) | personal |
| Account opening date | optional `opened_on` on the person's card holding | personal |
| The decision | `prices/elections.py`, called by the engine for every evaluation when election entities exist | computed |

The engine adds "and the person has elected this option" to every governed rule, whether it is a verified rule or a candidate evaluated with `--candidates`. Rules that no option governs are untouched. A store with no election entities behaves exactly as before.

## 3. Option terms

Dates in the `*_anniversary` terms mean **the first card anniversary on or after that date**, computed from `opened_on`.

| Term | Meaning |
|---|---|
| `opened_before: D` | Only for accounts opened before D |
| `default_before_anniversary: D` | Applies **without any election** until the first anniversary on or after D, for accounts opened before D. At most one per group |
| `starts_at_anniversary: D` | Cannot be in effect before the first anniversary on or after D |
| `elect_before_anniversary: D` | An election of this option must start before the first anniversary on or after D |

Terms added by ENG-02B (section 8 says why):

| Term | Meaning |
|---|---|
| `follows: <option>` | This option is in effect when that option of **another group** is. Nobody records it separately once the choice period is over |
| `choose_before_anniversary: D` | The cardholder's own choice of this option counts only before the first anniversary on or after D (accounts opened before D). Needs `follows` |
| `default_opened_on_or_after: D` | Applies without any record, **from the day the account opens**, to accounts opened on or after D |
| `permanent_exit: true` | Once an election of this option has ended, it cannot be made again |
| `after_exit_from_anniversary: true` | Needs `follows`. If the followed option took effect after the person left another option of its group, this option starts at the first anniversary on or after that change |
| `anniversary_from: first_billing_cycle_after_opening` | The issuer counts the anniversary from the first day of the first billing cycle that begins after opening. See section 8.3. (Replaces `anniversary_cycle_days`, removed in Step 04B: lint warns `ANNIVERSARY_CYCLE_DAYS_REMOVED` and the engine ignores it) |
| `takes_effect: next_billing_cycle` | A switch to this option takes effect on the first day of the next billing cycle after the request. See section 8.7 |
| `exit_takes_effect: next_billing_cycle` | Leaving this option takes effect the same way |
| `requires_active: <option>` | This option can be elected only while that option (of another group on the same card) is the person's confirmed choice. See section 8.8 |
| `terms_by` / `approval` | Set by the pipeline only: who wrote the terms, and an independent reviewer's approval of exactly those terms (section 8.9) |

Bilt Palladium, as corrected by ENG-02B from the published Bilt Rewards Card Offer Terms (updated 2026-10-27; Argon to confirm):

| Group | Option | Governs | Terms |
|---|---|---|---|
| `bilt-palladium.arrangement` | `election.bilt-palladium.legacy-election` | nothing directly | opened before 2027-01-01; elected before the first 2027+ anniversary; permanent exit |
| | `election.bilt-palladium.refreshed-arrangement` | nothing directly | from opening for accounts opened on or after 2027-01-01; otherwise not before the first 2027+ anniversary |
| `bilt-palladium.housing-rewards` | `election.bilt-palladium.housing-tiered-points` | `cb.bilt-palladium.housing-tiered-points` | own choice before the first 2027+ anniversary; then follows the refreshed arrangement |
| | `election.bilt-palladium.housing-flex-bilt-cash` | `cb.bilt-palladium.housing-flex-bilt-cash-legacy` | opened before 2027-01-01; own choice before the first 2027+ anniversary; then follows the Legacy Election |
| `bilt-palladium.annual-credits` | `election.bilt-palladium.annual-credits-legacy` | `cb.bilt-palladium.annual-bilt-cash-200-legacy`, `cb.bilt-palladium.hotel-credit-400-semiannual-legacy` | automatic before the first 2027+ anniversary (accounts opened before 2027-01-01); then follows the Legacy Election. Never a choice of its own |
| | `election.bilt-palladium.annual-credits-600` | `cb.bilt-palladium.annual-bilt-cash-600-post2027` | follows the refreshed arrangement; after a Legacy Election is left, from the next anniversary. Never a choice of its own |

All six carry `anniversary_from: first_billing_cycle_after_opening` (Step 04B; the former `anniversary_cycle_days: 62` was an invented allowance and is removed). The Legacy Election also carries `requires_active: election.bilt-palladium.housing-flex-bilt-cash` and `exit_takes_effect: next_billing_cycle`; both housing options carry `takes_effect: next_billing_cycle`. None of the six is approved yet (section 8.9).

## 4. The decision, for one person, one group, one date

1. Card not held: nothing to decide (governed rules need the card anyway).
2. More than one holding of the card in effect → every possible option UNRESOLVED (`MULTIPLE_CARD_ACCOUNTS`).
3. Two different options recorded as in effect → every possible option UNRESOLVED (`CONFLICTING_ELECTIONS`).
4. One option recorded:
   - no start date and the owner had not yet confirmed it on that date → UNRESOLVED (`ELECTION_START_NOT_RECORDED`);
   - not confirmed by the owner → UNRESOLVED (`UNCONFIRMED_ELECTION`);
   - its terms forbid it on that date → UNRESOLVED, the recorded option included (`ELECTION_NOT_PERMITTED`);
   - its terms cannot be checked (usually no `opened_on`) → **in effect**, on the owner's word, flagged `ELECTION_TERMS_UNVERIFIED`;
   - otherwise → **in effect**, and no other option of the group applies.
5. Nothing recorded:
   - an option's default applies with certainty → **in effect** without an election;
   - whether a default applies depends on an anniversary nobody recorded → UNRESOLVED (`ANNIVERSARY_NOT_RECORDED`);
   - no option is allowed at all on that date → nothing applies, no flag;
   - otherwise → every option that could apply is UNRESOLVED (`ELECTION_NOT_RECORDED`, raised only once a governed rule is actually in force).

"Every option that could apply" leaves out options whose terms certainly forbid them on that date. UNRESOLVED never satisfies a condition, so nothing downstream is established either.

An account opened on February 29 has no anniversary day in other years. The window February 28 to March 1 is treated as unknown rather than decided by a convention.

## 5. Changing, correcting, withdrawing

An election is a holding with dates. A switch is `end_holding` on the old option (last day it applied) plus `set_holding` for the new option (from the next day); both stay on file, so earlier dates keep their answer. An ended election counts as confirmed up to its end date. A record entered by mistake is withdrawn (`end_holding` with `"withdrawn": true`): kept on file, never in effect on any date. Revising an option's definition (`revise_entity` on the `election` block) needs a reviewer, because it can change who is granted what.

## 6. Reading the output

- `python3 -m prices status --profile <p>`: section **Card elections**, one line per group: `IN EFFECT <option>` or `UNRESOLVED <options>` with the reason. JSON: key `elections`. Both appear only for people who hold a card with election groups.
- `python3 -m prices explain --profile <p> <benefit>`: the governed benefit's chain shows `have:<option> <- election:<holding>`, `election-default:<group>` or `election-unknown:<group>`, and `needs: CONFIRM: election <group>: <reason>`.
- `timeline` shows election start and end dates and each account's transition anniversary.

## 7. Limits

- **Elections are per person, not per account.** Two accounts of one card are reported, not resolved.
- **The definitions are engineering's reading of the published terms**, for Argon to confirm (section 8.5 lists what the terms leave open).
- **No billing-cycle arithmetic.** The terms make a housing change, and leaving the Legacy Election, effective on the first day of the next billing cycle. PRICES stores no statement dates: the owner records the day a change took effect, and the engine uses that day.
- **Elections gate benefits; they do not compute them.** Tier percentages, Bilt Cash amounts, grant dates and expiry stay prose (section 8.6).
- **Nothing is live yet.** The five governed Bilt rules are still proposed candidates; no profile records a Bilt election. The safeguard takes effect when they are promoted.

## 8. Linked options and the Bilt correction (ENG-02B)

### 8.1 What was wrong

ENG-02 modelled Bilt Palladium as two independent elections: housing rewards (Housing-only or Flexible Bilt Cash) and annual credits (legacy $200 + $400, or $600). The published terms say otherwise:

| Situation | Published terms | ENG-02 model |
|---|---|---|
| Account opened before 2027, before its first Card Anniversary Date on or after 2027-01-01 | Housing option is the cardholder's choice, changeable from the next billing cycle. $200 Bilt Cash and $400 hotel credit apply whatever it is | Right, but the legacy credits were also offered as an election |
| Legacy Election (made before that anniversary, with Flexible Bilt Cash active) | **One** choice: keeps Flexible Bilt Cash, the $200 and the $400. Housing-only is no longer selectable | Two separate choices; a person could hold Flexible Bilt Cash with the $600, or Housing-only with the legacy credits |
| No Legacy Election, from that anniversary | Housing-only and $600 Bilt Cash, mandatory | Presented as two elections |
| Account opened on or after 2027-01-01 | Refreshed from opening; $600 credited at opening | Nothing until the first anniversary |
| Leaving the Legacy Election later | Effective next billing cycle; permanent; $600 from the next anniversary | Not modelled |

### 8.2 How it is modelled

One group, `bilt-palladium.arrangement`, holds the real choice: `legacy-election` or `refreshed-arrangement`. The four older options keep their ids and the rules they govern, and now **follow** it:

- **Choice period** (account opened before 2027, date before its transition anniversary). Housing: the cardholder's recorded choice decides, as before. Annual benefits: the legacy pair applies automatically; it is not an election. If a Legacy Election is already recorded, Flexible Bilt Cash applies with it, and a Housing-only record on top of it is a contradiction (`CONFLICTING_ELECTIONS`).
- **Afterwards**, and for accounts opened in 2027 or later. Only the arrangement decides. Legacy Election in effect → Flexible Bilt Cash, $200, $400. Refreshed arrangement in effect → Housing-only, $600. Arrangement not recorded → all five UNRESOLVED (`ELECTION_NOT_RECORDED`). A housing choice recorded for the choice period no longer counts (`ELECTION_SUPERSEDED`, information only).
- **The refreshed arrangement is not an election.** Accounts opened in 2027 or later get it from opening with nothing recorded. For an older account the owner records it, to state that no Legacy Election was made (or that one was left). It is not inferred from a missing record: an owner who made a Legacy Election and has not recorded it yet would otherwise be shown the wrong benefits.
- **A record of `annual-credits-legacy` or `annual-credits-600` is never used** (`ELECTION_NOT_SELECTABLE`).
- **Leaving is permanent.** End the `legacy-election` holding on the last day it applied and record `refreshed-arrangement` from the next day. Legacy benefits stop that day; the $600 starts at the first card anniversary on or after it. A later `legacy-election` record is refused its effect (`ELECTION_NOT_PERMITTED`).

`ELECTION_NOT_RECORDED` for the arrangement group is raised only when a group with a rule in force is actually waiting on it, so nobody is nagged before their transition anniversary.

### 8.3 The card anniversary

The terms define the Card Anniversary Date as one year after the first day of the first billing cycle that begins **after** the account was opened, then the same day each year. It is not the opening date's anniversary, and it cannot be computed from `opened_on`.

- Record `anniversary_on` on the card holding: any card anniversary date as the Bilt app shows it. The engine then uses its month and day exactly.
- Or record `first_billing_cycle_on`: the first day of the first billing cycle after opening. The anniversary is that month and day, a year on.
- With only `opened_on`, the engine knows a **lower bound**: the anniversary falls after the opening date's anniversary. There is **no upper bound**: no published figure says how long after opening the first cycle begins. Before the lower bound: certainly before. From it on, indefinitely: unknown, flagged `ANNIVERSARY_NOT_RECORDED`. (Changed in Step 04B. Until then a 62-day "engineering allowance" closed the window and declared the anniversary "certainly past" afterwards; that number was not published, and could grant the $600 from a guessed date.)
- With neither date, results from 2027-01-01 on are unresolved.

Options without `anniversary_from` (every invented fixture, and any future card whose anniversary is the opening date) behave exactly as before.

### 8.7 Request date and effective date (Step 04B)

The terms say a Rewards Option switch takes effect on the first day of the next billing cycle. A request is not the switch.

- `valid_from` on an election holding is always the **issuer-effective** date. `requested_on` is the day the cardholder asked. For an exit, `exit_requested_on`, and `valid_to` is the last day before the exit took effect.
- With `billing_cycle_day` on the card holding, the engine checks the two: an effective date that is not after the request, or not the next cycle start, is `ELECTION_EFFECTIVE_DATE_INVALID`. Such a record makes every date near it unknowable, including the loss of what it carried. Without a request date, a `valid_from` that is not a cycle start (or the opening date) is also invalid.
- With a request date and no effective date, the engine computes it from `billing_cycle_day`; with neither, the change is UNRESOLVED from the day after the request (`ELECTION_EFFECTIVE_DATE_NOT_RECORDED`).
- **Limitation.** A record with only `valid_from` and no `billing_cycle_day` cannot be checked: a request date typed into `valid_from` is undetectable. OP-12 tells maintainers never to do that.

### 8.8 The Legacy Election's prerequisite (Step 04B)

The Legacy Election is open only to a cardholder whose active Rewards Option is Flexible Bilt Cash. The engine requires a confirmed (or ended) Flexible Bilt Cash record **in effect on the Legacy Election's start**:

- shown → the prerequisite holds;
- a Housing-only record in effect then → `ELECTION_NOT_PERMITTED`;
- nothing, an unconfirmed record, or one that starts later or ended earlier → `ELECTION_TERMS_UNVERIFIED`, UNRESOLVED.

Missing history never establishes Flexible Bilt Cash, the $200, the $400 or any other spendable value. More generally (Step 04B), any term that cannot be checked now leaves the option UNRESOLVED; before, it stood on the owner's word with an information flag.

### 8.9 Independent approval of the definitions (Step 04B, A8)

An option's terms are a factual claim about a published program. The pipeline records who wrote them (`terms_by`: author, attester, changeset). `approve_election` (OP-12 section 8) lets a promotion reviewer who is neither of those approve the terms' exact digest. Until every option of a group is approved, the whole group is UNRESOLVED (`ELECTION_DEFINITION_NOT_APPROVED`). A revision of the terms drops the approval; an approval cannot be written in with the terms.

The six Bilt definitions were revised in Step 04B by engineering, with "Commissioning build" as the builder's own attestation. That attestation is not independent. **All live Bilt election outcomes are UNRESOLVED until Eric or Bradley approves them.**

### 8.10 Product changes (A4: documented, not modelled)

Bilt's own Bilt Card 2.0 Program Overview, 10/27/26 section (DISC-03-04, first-party, verified 2026-11-19), says: "Changing your card moves you to the refreshed benefits, even if you opted out on your current card." It also says upgrades reset the Card Anniversary Date and downgrades do not.

So a product change ends a Legacy Election (the opt-out is lost), and after an upgrade the anniversary on file is wrong. PRICES does not model product changes: there is no op or holding fact for them, and nothing detects one. OP-12 sends any reported card change to escalation. Until an owner reports one, a recorded Legacy Election is taken as current; this is a known gap (A4, CONTAINED), not a supported behaviour.

### 8.4 Sources read (2026-11-15)

| Source | Used for |
|---|---|
| Bilt Rewards Card Offer Terms, updated 2026-10-27 (bilt.com/terms/bilt-card-offer-terms) | Everything in 8.1 to 8.3 |
| Bilt Cash Program Terms of Use, updated 2026-10-27 (bilt.com/terms/bilt-cash) | Expiry: end of the month 12 months after earning; hotel redemption limits; Point Accelerator |
| Bilt help centre, "Bilt Card 2.0 Program Overview" | Cross-check only |

Discrepancies between them:

1. The help-centre page still describes the $200 Bilt Cash as credited "around January 1" and Bilt Cash as expiring at year end with a $100 carry-over. The 2026-10-27 terms credit it on opening and on each Card Anniversary Date, with 12-month expiry. The terms are followed.
2. The Bilt Cash terms define "Eligible Palladium Cardholders" for older accounts by reaching the anniversary "in 2027". The Offer Terms use the first anniversary "on or after January 1, 2027", which for an account opened in late December 2026 can fall in January 2028. Not modelled (hotel redemption caps are not among the five rules).
3. The same definition excludes anyone who made a Legacy Election; it does not say what applies after such a cardholder leaves it.

Argon's 2026-11-15 election audit was named as a research input but is not in the repository or its branches, so it was not used.

### 8.5 What the published terms leave open (kept unresolved or flagged, never assumed)

- Whether a Legacy Election can be cancelled before the transition anniversary, and when it takes effect.
- Whether an older account can move to the refreshed arrangement before its transition anniversary. A `refreshed-arrangement` record dated earlier is flagged `ELECTION_NOT_PERMITTED`.
- What a product change does to the Rewards Option itself. (What it does to a Legacy Election and to the anniversary is now stated by Bilt's overview: section 8.10. Still not modelled.)
- Whether the first-half-2027 hotel credit is issued on 2027-01-01 to an account that will move at a later 2027 anniversary. Bilt has said so publicly; the terms do not.
- Whether the Legacy Election is per card account or per rewards account. PRICES records elections per person and reports two accounts of the card as unresolved.

### 8.6 Bilt Cash mechanics that are not supported

Eligibility ("is this person under the $600 benefit on this date") is decided here. The following are not computed anywhere, and no `credit` block has been put on the Bilt Cash candidates to pretend otherwise:

- per-grant expiry (each Bilt Cash award expires at the end of the month 12 months after it was earned; first to expire is spent first);
- grant dates on the Card Anniversary Date (ENG-01's `anniversary_year` cycle counts from `opened_on`);
- the Bilt Cash wallet: balances, redemptions, returned redemptions keeping their original expiry;
- conversion of unredeemed hotel credit into Bilt Cash when a Legacy Election holder leaves ($400 less what was redeemed since the last anniversary);
- unused hotel credit expiring at the transition anniversary;
- hotel redemption caps, Point Accelerator activations and their own limits.
