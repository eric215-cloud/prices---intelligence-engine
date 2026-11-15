# Cardholder elections (ENG-02)

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

Bilt Palladium, as transcribed from Argon's candidates (Argon to confirm):

| Group | Option | Governs | Terms |
|---|---|---|---|
| `bilt-palladium.housing-rewards` | `election.bilt-palladium.housing-tiered-points` | `cb.bilt-palladium.housing-tiered-points` | none |
| | `election.bilt-palladium.housing-flex-bilt-cash` | `cb.bilt-palladium.housing-flex-bilt-cash-legacy` | opened before 2027-01-01; elected before the first 2027+ anniversary |
| `bilt-palladium.annual-credits` | `election.bilt-palladium.annual-credits-legacy` | `cb.bilt-palladium.annual-bilt-cash-200-legacy`, `cb.bilt-palladium.hotel-credit-400-semiannual-legacy` | opened before 2027-01-01; default before the first 2027+ anniversary; retained only by an election made before it |
| | `election.bilt-palladium.annual-credits-600` | `cb.bilt-palladium.annual-bilt-cash-600-post2027` | starts at the first 2027+ anniversary |

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
   - no option is allowed at all on that date → nothing applies, no flag (e.g. an account opened in 2027, before its first anniversary);
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
- **The option definitions are an engineering transcription** of Argon's candidate restrictions and ENG-02 text. Argon owns them and should confirm: in particular whether preserving the legacy credits and choosing the Flex housing option are **one** legacy election or two independent ones. They are modelled as two, as ENG-02 and the commission list them.
- **Accounts opened in 2027 or later:** Argon's text does not say what applies before their first anniversary; the definitions give nothing then, and $600 as UNRESOLVED until an election is recorded after it. Not inferred.
- **No "billing cycle" granularity.** Argon's housing restriction says the options are exclusive "in a given billing cycle". Elections are recorded by date; a switch mid-cycle is recorded on the day the owner gives.
- **Elections gate benefits; they do not compute them.** Tier percentages, Bilt Cash amounts and redemption rates stay prose (ENG-01, ENG-04 not started).
- **Nothing is live yet.** The five governed Bilt rules are still proposed candidates; no profile holds a Bilt card or an election. The safeguard takes effect when they are promoted.
