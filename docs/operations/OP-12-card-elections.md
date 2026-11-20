# OP-12  Record a cardholder's election between mutually exclusive card options

**ops:** `set_holding` / `end_holding` (on an election option, and the anniversary and billing-cycle facts on the card holding); `approve_election` (a reviewer only, section 8)

**Use when:** a card makes its holder choose between options that cannot both apply, and you need to record which one this person has, change it, or fix a wrong record. Today: Bilt Palladium housing rewards (housing-only tiered points **or** Flexible Bilt Cash) the linked Legacy Election / refreshed arrangement, and the annual credits that follow it (legacy $200 Bilt Cash + $400 hotel credit **or** $600 Bilt Cash). For Bilt the anniversary is **not** the opening date (section 0).

**The one idea to hold on to.** If no election is recorded, **none** of the options is applied: each one that could apply shows as UNRESOLVED. Never record an option because another one is missing, because it is "the default", or because it seems likely. Record only what the owner says.

| What | Where it lives | Who can say so |
|---|---|---|
| The **options** and which rules each one governs | entities of kind `election` (`data/kb/entities/election.*`) | content (Argon); changing one needs a reviewer |
| The **account opening date** (a lower bound for a Bilt anniversary, never the anniversary itself) | `opened_on` on the person's card holding | the owner |
| The **card anniversary** as the issuer shows it, or the start of the first billing cycle | `anniversary_on` / `first_billing_cycle_on` on the card holding | the owner (from the issuer's app or statement) |
| The **billing-cycle start day** (1-31) | `billing_cycle_day` on the card holding | the owner (statement) |
| Whether the option definitions may be used at all | `election.approval`, set by `approve_election` | a reviewer who did not author or attest the terms (section 8) |
| The person's **election** of one option, from a date | a holding of that option entity | the owner (confirmed) or anyone (unconfirmed) |

## 0. Bilt Palladium: what to record (corrected by ENG-02B)

The Bilt choices are **linked**. Record only these, and only what the owner tells you:

| The owner says | Record | Notes |
|---|---|---|
| The card anniversary shown in the Bilt app | `anniversary_on` on the card holding (with `opened_on`) | Bilt counts the anniversary from the first billing cycle after opening. `opened_on` alone says only that the anniversary is **later** than the opening date's anniversary; no published figure says how much later, so every date after that stays UNRESOLVED (`ANNIVERSARY_NOT_RECORDED`) until this or `first_billing_cycle_on` is recorded |
| The date the first billing cycle began | `first_billing_cycle_on` on the card holding | Places the anniversary exactly (same month and day, a year on) |
| The day each billing cycle starts | `billing_cycle_day` on the card holding | Lets the program check and compute when a requested change took effect |
| "I asked to switch my housing option on ... " / "it shows as ... from ..." (**before** the first card anniversary on or after 2027-01-01) | a holding of `election.bilt-palladium.housing-tiered-points` or `...housing-flex-bilt-cash`: `requested_on` = the day asked, `valid_from` = the day the issuer shows it taking effect | A switch takes effect on the **first day of the next billing cycle**, never on the request day. If only the request day is known, record `requested_on` and leave `valid_from` out: the program computes the date from `billing_cycle_day`, or keeps the switch UNRESOLVED (`ELECTION_EFFECTIVE_DATE_NOT_RECORDED`). Never put the request day in `valid_from` |
| "I made the Legacy Election on ..." | a holding of `election.bilt-palladium.legacy-election` | One record. It carries Flexible Bilt Cash, the $200 Bilt Cash and the $400 hotel credit. Must start before that anniversary, **and** the cardholder's active Rewards Option must be Flexible Bilt Cash when it is made: record that housing holding too. Without a confirmed Flexible Bilt Cash record in effect on the election's start, the arrangement is UNRESOLVED (`ELECTION_TERMS_UNVERIFIED`); with Housing-only in effect then, `ELECTION_NOT_PERMITTED` |
| "I did not make a Legacy Election" (account opened before 2027, anniversary passed) | a holding of `election.bilt-palladium.refreshed-arrangement`, `valid_from` = the transition anniversary | Carries Housing-only and the $600. Never record it because the Legacy Election record is merely missing |
| "I left the Legacy Election; I asked on ..., it took effect on ..." | `set_holding` on the legacy-election holding with `exit_requested_on` = the day asked, then `end_holding` (`ended_on` = the day before it took effect), then `refreshed-arrangement` from that day | Permanent. The exit also takes effect at the next billing cycle. The $600 starts at the next card anniversary |
| "I changed my card (upgrade / downgrade / product change)" | **nothing**: escalate (section 6) | Not modelled. Bilt's own overview says a card change moves the cardholder to the refreshed benefits even if they opted out on the current card, and upgrades reset the Card Anniversary Date while downgrades do not (DISC-03-04; `docs/ELECTIONS.md`, "Product changes") |
| Account opened in 2027 or later | nothing | Refreshed from opening, automatically |

Never record `election.bilt-palladium.annual-credits-legacy` or `...annual-credits-600`: the annual benefits are not a choice of their own (`ELECTION_NOT_SELECTABLE`). After the transition anniversary, do not record a housing option either; end the old one on the day before the anniversary.

## 1. Inputs and context
- The profile name and the person's holding of the card (`python3 -m prices status --profile <p>`).
- The option the owner says is in effect, **and since when**. If the owner does not know since when, leave `valid_from` out; the program treats the election as unknown before the day the owner confirmed it.
- For cards whose options change at an anniversary (Bilt): **the date the account was opened**, and **the card anniversary the issuer shows** (or the date the first billing cycle began). Ask for both. Never use the date the card was first recorded here, and never treat the opening date as the anniversary.
- For a switch the owner asked for: **the request day and the effective day** as the issuer shows them, or the billing-cycle start day.
- See the options: `ls data/kb/entities/ | grep '^election\.'` and read the `election` block of each (`group`, `governs`, and any dates).
- See the current picture: `python3 -m prices status --profile <p>` (section "Card elections").

## 2. Permitted actions
- **Add the opening date, anniversary, first billing cycle or cycle day** to the card holding: `set_holding` with the whole card holding record plus `"opened_on"`, `"anniversary_on"`, `"first_billing_cycle_on"` and/or `"billing_cycle_day"`. (`set_holding` replaces the record: copy every existing field.)
- **Record an election:** `set_holding` with a new holding whose `entity` is the option entity, `valid_from` = the date the owner says it took effect.
- **Change an election** (the owner switched options): end the old one with `end_holding`, `ended_on` = the last day it applied; then record the new one with `valid_from` = the next day. Between the two changesets the report briefly shows the group as UNRESOLVED; that is expected.
- **Withdraw a record entered by mistake:** `end_holding` with `"data": {"withdrawn": true}`. The record stays on file and is never in effect on any date. A confirmed record needs the owner's attestation; an unconfirmed one may be withdrawn by a maintainer.
- `state: confirmed` needs an attestation whose `by` is exactly the profile's `owner`. Without it, record `unconfirmed` (it counts as UNRESOLVED) and ask the owner.

**Not permitted:** approving option definitions you wrote, attested or submitted (section 8); recording an option for someone who has not said so; recording "the default"; editing an option entity's `election` block without a reviewer; editing the Bilt rules or candidates to add a condition (the tables own them); recording elections for Eric or Todd without their own statement; editing files by hand.

## 3. Source and evidence requirements
The owner's statement or account page, summarized in the attestation `statement`. The option definitions themselves cite Argon's content (`source_note`); a personal election never substitutes for that.

## 4. Output: the changeset
One changeset per fact; save as a file; `python3 -m prices apply <file>`.

```json
{"id": "cs-YYYYMMDD-NNN-set-holding", "op": "set_holding", "author": "...", "date": "YYYY-MM-DD",
 "reason": "Owner reported their housing rewards option.", "profile": "<profile>",
 "data": {"holding": {"id": "el-housing-1", "entity": "election.bilt-palladium.housing-tiered-points",
                      "state": "confirmed", "valid_from": "YYYY-MM-DD"}},
 "attestation": {"by": "<owner exactly as in profile.json>", "on": "YYYY-MM-DD", "statement": "What the owner said."}}
```
```json
{"id": "cs-YYYYMMDD-NNN-set-holding", "op": "set_holding", "author": "...", "date": "YYYY-MM-DD",
 "reason": "Owner gave the account opening date.", "profile": "<profile>",
 "data": {"holding": {"id": "<card holding id>", "entity": "card.bilt-palladium", "state": "confirmed",
                      "valid_from": "YYYY-MM-DD", "opened_on": "YYYY-MM-DD"}},
 "attestation": {"by": "<owner>", "on": "YYYY-MM-DD", "statement": "..."}}
```
```json
{"id": "cs-YYYYMMDD-NNN-end-holding", "op": "end_holding", "author": "...", "date": "YYYY-MM-DD", "reason": "...",
 "profile": "<profile>", "target": "el-housing-1", "data": {"ended_on": "YYYY-MM-DD"},
 "attestation": {"by": "<owner>", "on": "YYYY-MM-DD", "statement": "..."}}
```
Withdraw: same as the last one with `"data": {"withdrawn": true}` instead of `ended_on`.

## 5. Validation (done by the program)
- Only the owner can confirm; a rejected changeset changes nothing and prints `REJECTED` with a code.
- Lint warns `CONFLICTING_ELECTIONS` when two different options of one group overlap in time, `ELECTION_WITHOUT_CARD`, `ELECTION_START_NOT_RECORDED`, `ELECTION_EFFECTIVE_DATE_INVALID` (`valid_from` not after `requested_on`), `ELECTION_DEFINITION_NOT_APPROVED`; errors on `opened_on` after `valid_from`, `first_billing_cycle_on` not after `opened_on`, `billing_cycle_day` outside 1-31, card facts on a non-card holding, or request dates on a non-election holding.
- The engine, for each date: one confirmed election in effect and allowed by the option's terms → only that option's rules can apply. Anything else → every option that could apply is UNRESOLVED and one of these flags says why:

| Flag | Meaning | Do this |
|---|---|---|
| `ELECTION_NOT_RECORDED` | The card is held and no election is recorded | Ask the owner which option, since when |
| `CONFLICTING_ELECTIONS` | Two options in effect on the same date | Ask the owner; end or withdraw the wrong one |
| `UNCONFIRMED_ELECTION` | Recorded but not confirmed | Get the owner's confirmation |
| `ELECTION_START_NOT_RECORDED` | No `valid_from`; before the owner confirmed it, unknown | Ask since when, if it matters |
| `ANNIVERSARY_NOT_RECORDED` | The answer depends on the card anniversary, and `opened_on` is missing or (Bilt) does not place it; for Bilt this lasts indefinitely after the opening date's anniversary | Ask the card anniversary the issuer shows (or the first billing cycle); add `anniversary_on` or `first_billing_cycle_on` |
| `ELECTION_EFFECTIVE_DATE_INVALID` | The recorded dates contradict "takes effect at the next billing cycle" (start on or before the request, or not a cycle start). Nothing near the record is concluded, including its loss | Correct `valid_from` / `valid_to` to the issuer-effective dates |
| `ELECTION_EFFECTIVE_DATE_NOT_RECORDED` | A change was requested; its effective day is neither recorded nor computable | Record `valid_from` (or `valid_to`) as the issuer shows it, or `billing_cycle_day` |
| `ELECTION_DEFINITION_NOT_APPROVED` | The option definitions have no valid independent approval: nothing in the group is established | A reviewer runs section 8 |
| `ELECTION_NOT_PERMITTED` | The record contradicts the option's published terms (e.g. Flex for an account opened in 2027, or $600 before this account's 2027 anniversary) | Re-check dates with the owner; escalate if the account really shows it |
| `ELECTION_NOT_SELECTABLE` | A record of an option that is never chosen on its own (Bilt annual benefits) | Withdraw it; record the Legacy Election or the refreshed arrangement instead |
| `ELECTION_SUPERSEDED` (info) | A housing choice left on file after the arrangement took over | End it on the day before the change |
| `ELECTION_TERMS_UNVERIFIED` | A term cannot be checked (anniversary not placed, the Flexible Bilt Cash prerequisite not shown). **Changed in Step 04B:** this used to be an info flag that still established the option on the owner's word; it is now UNRESOLVED | Record the missing fact the flag names |
| `MULTIPLE_CARD_ACCOUNTS` | Two holdings of the same card in effect | Escalate: elections are recorded per person |
| `ELECTION_WITHOUT_CARD` | An election but no card held | Record the card, or end the election |

## 6. Failure and escalation
Escalate to the coordinator, changing nothing, when: the owner's account shows an option the definitions do not describe; the owner says an option applies on a date its terms forbid; two accounts of the same card are held; or an option's terms look wrong. Option definitions are content: Argon decides, a reviewer applies.

## 7. How completion is independently established
- `APPLIED` for each changeset; `python3 -m prices lint` shows 0 errors and no new `CONFLICTING_ELECTIONS`.
- `python3 -m prices status --profile <p>` → "Card elections": the group shows `IN EFFECT <the option>`. Only that option's benefits can be ESTABLISHED; the other options' benefits are NOT_AVAILABLE.
- `python3 -m prices status --profile <p> --as-of <a day before valid_from>`: the election is not in effect then.
- `python3 -m prices timeline --profile <p>` shows each switch on its day.
- A worked example with every command and its output: `python3 scripts/demo_elections.py`.

## 8. Approving option definitions (reviewer only; Step 04B)
An option's `election` block is a published-terms claim. Until a reviewer **other than** its author and attester approves exactly those terms, every group that contains it is UNRESOLVED (`ELECTION_DEFINITION_NOT_APPROVED`). Any later `revise_entity` of the block drops the approval with the old terms; an `approval` key cannot be written in through `add_entity` or `revise_entity`.

1. Read the option file and its sources; check the terms against the published terms.
2. Get the digest of exactly what you read: `python3 -c "from prices.store import Store; from prices.elections import terms_digest; print(terms_digest(Store.load('.').entities['<option id>']))"`.
3. Apply, with your own name as author and attester:
```json
{"id": "cs-YYYYMMDD-NNN-approve-election", "op": "approve_election", "target": "<option id>", "author": "<reviewer>",
 "date": "YYYY-MM-DD", "reason": "Terms checked against <sources>.", "data": {"terms": "<digest>"},
 "attestation": {"by": "<reviewer, as in vocab promotion_reviewers>", "on": "YYYY-MM-DD", "statement": "What was checked."}}
```
Refusals: `NOT_INDEPENDENT` (you wrote or attested the terms), `TERMS_CHANGED` (the terms differ from the digest), `TERMS_PROVENANCE_MISSING` (the terms predate provenance; revise them through the pipeline first). The six Bilt definitions were revised by engineering in Step 04B and attested by "Commissioning build"; they await this step.
