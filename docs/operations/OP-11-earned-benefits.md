# OP-11  Record a person's progress toward an earned benefit, the benefit itself, and its use

**ops:** `record_progress` / `record_entitlement` / `record_usage` / `revise_entitlement` / `correct_entry`

**Use when:** a card offers something for reaching a threshold in a year (a status, a certificate, a credit), and a person's own progress, the benefit actually landing on their account, or their use of it must be recorded or corrected.

**The one idea to hold on to.** Three different things, three different records. Never fill in one from another.

| What | Where it lives | Who can say so |
|---|---|---|
| The **public rule**: "75,000 in a calendar year on this card earns X" | a rule of kind `earns` (OP-03 to add one) | a cited source |
| The person's **progress** in one year on one of their own accounts | `record_progress` | the owner (confirmed) or anyone (unconfirmed) |
| The **benefit actually on the account**, with its own dates and balance | `record_entitlement`, `record_usage` | the owner (confirmed) or anyone (unconfirmed) |

Reaching the threshold makes the person **eligible**. Only an entitlement record makes the benefit **held**. Nothing is ever assumed in between.

## 1. Inputs and context
- The profile name and the **holding id of that person's own card account** (see `python3 -m prices status --profile <p>`). Each account is separate, even two of the same card.
- The qualifying year (`cycle`, four digits) and the `measure` named in the rule's `earn` block.
- What the owner said or showed, and **the date each figure refers to**.
- See the current picture first: `python3 -m prices earned --profile <p>`.

## 2. Permitted actions
- **A progress figure** (`record_progress`): one reading = one number as of one date. Add readings; never edit old ones.
  - `observed_on` is the date the figure refers to (the statement date), not today.
  - The owner knows only "I reached it some time in 2026": write `"observed_on": "unknown"` and `"value_kind": "at_least"`. **Do not pick a date.**
  - The year-end total: add `"final": true` (dated December 31; only accepted after the year has ended).
- **A benefit on the account** (`record_entitlement`): only when the owner confirms it is actually there (or record it `unconfirmed`).
  - `effective_from` and `expires_on` are **what the account shows**. If either is not known, write the word `"unknown"`. **Do not copy the rule's general term and do not calculate a date.**
  - For a benefit that needs a separate activation, enrollment or linking step: record it only after the owner says that step was done.
  - For a credit, give `allowance` exactly as the account shows it.
- **A use of a credit** (`record_usage`): amount and date of each use. The program computes what remains; never type a "remaining" number anywhere.
- **Fixing a wrong reading or use** (`correct_entry`): the old entry is kept and marked superseded; give the replacement in the same changeset.
- **Fixing dates, ending early, or withdrawing an entitlement** (`revise_entitlement`): set `expires_on`, or `ended_on` + `end_reason`, or `"state": "superseded"` to withdraw a record entered by mistake.
- `state: confirmed` always needs an `attestation` whose `by` is exactly the profile's `owner`. Without it, record `unconfirmed` (it will count as UNRESOLVED) and escalate to the owner.

**Not permitted:** editing files under `profiles/` by hand; recording a benefit because "the threshold was met so it must be there"; recording one person's progress or benefit under another person; adding one account's spending to another's; carrying a figure from one year into the next; recording passwords, card numbers or account numbers.

## 3. Source and evidence requirements
The owner's own statement, account page or screenshot, reported in the attestation `statement`. Put a short pointer in `basis` ("October statement"). The public rule needs its own cited evidence through the usual route (OP-03, OP-04); a personal record never substitutes for it.

## 4. Output: the changeset
One changeset per fact. Save each as a file and apply it with `python3 -m prices apply <file>`.

```json
{
  "id": "cs-YYYYMMDD-NNN-record-progress",
  "op": "record_progress",
  "author": "...", "date": "YYYY-MM-DD", "reason": "Owner reported October statement total.",
  "profile": "<profile>",
  "data": {"account": "<holding id of the card>", "measure": "<measure from the rule>", "cycle": "2027",
           "reading": {"id": "r-2027-10", "value": 79400, "observed_on": "2027-10-31", "state": "confirmed", "basis": "October statement"}},
  "attestation": {"by": "<owner exactly as in profile.json>", "on": "YYYY-MM-DD", "statement": "What the owner said or showed."}
}
```
```json
{
  "id": "cs-YYYYMMDD-NNN-record-entitlement",
  "op": "record_entitlement",
  "author": "...", "date": "YYYY-MM-DD", "reason": "Owner confirmed the status is on the account.",
  "profile": "<profile>",
  "data": {"entitlement": {"id": "e-2027-<short-name>", "rule": "<earns rule id>", "account": "<holding id of the card>", "cycle": "2027",
                           "state": "confirmed", "effective_from": "YYYY-MM-DD or unknown", "expires_on": "YYYY-MM-DD or unknown",
                           "allowance": {"amount": 300, "unit": "units"}, "basis": "Account page"}},
  "attestation": {"by": "<owner>", "on": "YYYY-MM-DD", "statement": "..."}
}
```
(`allowance` only for a consumable credit.)
```json
{"id": "cs-YYYYMMDD-NNN-record-usage", "op": "record_usage", "author": "...", "date": "YYYY-MM-DD", "reason": "...",
 "profile": "<profile>", "target": "<entitlement id>",
 "data": {"usage": {"id": "u-2027-12-02", "amount": 140, "used_on": "2027-12-02", "state": "confirmed", "basis": "Airfare"}},
 "attestation": {"by": "<owner>", "on": "YYYY-MM-DD", "statement": "..."}}
```
```json
{"id": "cs-YYYYMMDD-NNN-correct-entry", "op": "correct_entry", "author": "...", "date": "YYYY-MM-DD", "reason": "...",
 "profile": "<profile>",
 "data": {"record": "qualification", "id": "<qualification id>", "entry": "<reading id to withdraw>",
          "replacement": {"id": "r-2027-10b", "value": 74400, "observed_on": "2027-10-31", "state": "confirmed", "basis": "Re-read"}},
 "attestation": {"by": "<owner>", "on": "YYYY-MM-DD", "statement": "..."}}
```
For a usage entry: `"record": "entitlement"`, `"id": "<entitlement id>"`, `"entry": "<usage id>"`. Leave `replacement` out to withdraw without replacing.
```json
{"id": "cs-YYYYMMDD-NNN-revise-entitlement", "op": "revise_entitlement", "author": "...", "date": "YYYY-MM-DD", "reason": "...",
 "profile": "<profile>", "target": "<entitlement id>",
 "data": {"set": {"expires_on": "2028-11-30"}},
 "attestation": {"by": "<owner>", "on": "YYYY-MM-DD", "statement": "..."}}
```
Other `set` examples: `{"ended_on": "2028-06-30", "end_reason": "Account closed"}`; `{"state": "superseded"}` (withdraw). The rule, account and cycle of a record can never be changed: withdraw it and record a new one.

## 5. Validation (done by the program)
- The account is that person's own holding and is the card the rule is about; the measure belongs to a sourced `earns` rule.
- Dates: none in the future; a reading falls inside its qualifying year; an entitlement does not start before its qualifying year or end before it starts; use falls inside the entitlement's own dates.
- Confirmation only by the owner; an attestation is not dated after the change.
- No duplicates: the same figure for the same date, the same use, or a second record for the same benefit, account and year is refused.
- Confirmed use cannot exceed the allowance.
- A rejected changeset changes no record. `REJECTED` and a code are printed, and the attempt is logged.

## 6. Failure and escalation
| Message | What it means | Do this |
|---|---|---|
| `OWNER_ATTESTATION_REQUIRED`, `ATTESTATION_REQUIRED` | You do not have the owner's confirmation | Record as `unconfirmed`, ask the owner |
| `UNKNOWN_ACCOUNT` | That holding is not this person's | Check the profile; record the card first (OP-07). Never use another person's account |
| `UNKNOWN_MEASURE`, `UNKNOWN_RULE` | No sourced `earns` rule covers this | Stop. The public rule must exist first (OP-03) |
| `MISSING_DATA` on a date | A date was left out | Write the date, or the word `unknown`. Do not guess |
| `FUTURE_DATE`, `OUT_OF_CYCLE`, `BAD_DATES`, `OUT_OF_TERM` | A date is impossible | Re-read the source. Last year's figure belongs to last year's cycle |
| `FINAL_BEFORE_PERIOD_END` | The year is not over | Record an ordinary reading instead |
| `DUPLICATE_READING`, `DUPLICATE_USAGE`, `DUPLICATE_INSTANCE` | It is already on file | Nothing to do. For a real second use on the same day, say so in `basis` |
| `USAGE_EXCEEDS_ALLOWANCE` | Use would exceed the credit | Check amounts with the owner; correct the allowance first if the account shows a different one |
| `FIELD_NOT_REVISABLE` | Rule, account or cycle cannot be changed | Withdraw the record and enter a new one |

Escalate to the coordinator, and change nothing, when the report shows any of: `CONFLICTING_PROGRESS`, `CONFLICTING_QUALIFICATION`, `CONFLICTING_ENTITLEMENTS`, `ACCOUNT_NOT_HELD`, or when the owner's account shows something the public rule does not explain.

## 7. How completion is independently established
- Each changeset prints `APPLIED`; `python3 -m prices lint` shows 0 errors.
- `python3 -m prices earned --profile <p>` shows, for the account and year: the reading under "progress on file", the ACHIEVEMENT line, and the ENTITLEMENT line with the dates and the credit numbers you were given. **ACHIEVED means eligible. Only ENTITLEMENT = ACTIVE means usable.**
- `python3 -m prices earned --profile <p> --as-of <a date before the figure>` does **not** show the benefit as achieved or active on that earlier date.
- `python3 -m prices audit --last 5` lists your changesets. Earlier versions of changed records are in `data/audit/previous/`.
- A worked example with every command and its output: `python3 scripts/demo_earned.py`.
