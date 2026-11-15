# OP-12  Record a cardholder's election between mutually exclusive card options

**ops:** `set_holding` / `end_holding` (on an election option, and `opened_on` on the card holding)

**Use when:** a card makes its holder choose between options that cannot both apply, and you need to record which one this person has, change it, or fix a wrong record. Today: Bilt Palladium housing rewards (housing-only tiered points **or** Flexible Bilt Cash) and Bilt Palladium annual credits (legacy $200 Bilt Cash + $400 hotel credit **or** $600 Bilt Cash from the first 2027-or-later card anniversary).

**The one idea to hold on to.** If no election is recorded, **none** of the options is applied: each one that could apply shows as UNRESOLVED. Never record an option because another one is missing, because it is "the default", or because it seems likely. Record only what the owner says.

| What | Where it lives | Who can say so |
|---|---|---|
| The **options** and which rules each one governs | entities of kind `election` (`data/kb/entities/election.*`) | content (Argon); changing one needs a reviewer |
| The **account opening date** (gives the anniversary) | `opened_on` on the person's card holding | the owner |
| The person's **election** of one option, from a date | a holding of that option entity | the owner (confirmed) or anyone (unconfirmed) |

## 1. Inputs and context
- The profile name and the person's holding of the card (`python3 -m prices status --profile <p>`).
- The option the owner says is in effect, **and since when**. If the owner does not know since when, leave `valid_from` out; the program treats the election as unknown before the day the owner confirmed it.
- For cards whose options change at an anniversary (Bilt annual credits): **the date the account was opened**. Ask for it. Never use the date the card was first recorded here instead.
- See the options: `ls data/kb/entities/ | grep '^election\.'` and read the `election` block of each (`group`, `governs`, and any dates).
- See the current picture: `python3 -m prices status --profile <p>` (section "Card elections").

## 2. Permitted actions
- **Add the opening date** to the card holding: `set_holding` with the whole card holding record plus `"opened_on": "YYYY-MM-DD"`. (`set_holding` replaces the record: copy every existing field.)
- **Record an election:** `set_holding` with a new holding whose `entity` is the option entity, `valid_from` = the date the owner says it took effect.
- **Change an election** (the owner switched options): end the old one with `end_holding`, `ended_on` = the last day it applied; then record the new one with `valid_from` = the next day. Between the two changesets the report briefly shows the group as UNRESOLVED; that is expected.
- **Withdraw a record entered by mistake:** `end_holding` with `"data": {"withdrawn": true}`. The record stays on file and is never in effect on any date. A confirmed record needs the owner's attestation; an unconfirmed one may be withdrawn by a maintainer.
- `state: confirmed` needs an attestation whose `by` is exactly the profile's `owner`. Without it, record `unconfirmed` (it counts as UNRESOLVED) and ask the owner.

**Not permitted:** recording an option for someone who has not said so; recording "the default"; editing an option entity's `election` block without a reviewer; editing the Bilt rules or candidates to add a condition (the tables own them); recording elections for Eric or Todd without their own statement; editing files by hand.

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
- Lint warns `CONFLICTING_ELECTIONS` when two different options of one group overlap in time, `ELECTION_WITHOUT_CARD`, `ELECTION_START_NOT_RECORDED`; errors on `opened_on` after `valid_from`, or on a non-card holding.
- The engine, for each date: one confirmed election in effect and allowed by the option's terms → only that option's rules can apply. Anything else → every option that could apply is UNRESOLVED and one of these flags says why:

| Flag | Meaning | Do this |
|---|---|---|
| `ELECTION_NOT_RECORDED` | The card is held and no election is recorded | Ask the owner which option, since when |
| `CONFLICTING_ELECTIONS` | Two options in effect on the same date | Ask the owner; end or withdraw the wrong one |
| `UNCONFIRMED_ELECTION` | Recorded but not confirmed | Get the owner's confirmation |
| `ELECTION_START_NOT_RECORDED` | No `valid_from`; before the owner confirmed it, unknown | Ask since when, if it matters |
| `ANNIVERSARY_NOT_RECORDED` | The answer depends on the card anniversary and `opened_on` is missing | Ask the opening date; add `opened_on` |
| `ELECTION_NOT_PERMITTED` | The record contradicts the option's published terms (e.g. Flex for an account opened in 2027, or $600 before this account's 2027 anniversary) | Re-check dates with the owner; escalate if the account really shows it |
| `ELECTION_TERMS_UNVERIFIED` (info) | Stands on the owner's word; a term could not be checked (usually no `opened_on`) | Add `opened_on` when known |
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
