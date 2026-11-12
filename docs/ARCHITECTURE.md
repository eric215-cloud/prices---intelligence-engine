# Architecture

## One-paragraph version

Records are JSON files. A deterministic engine reads rules and one person's holdings and derives a status for every entity. Nothing changes a record except a validated changeset. AI is used only outside the program, to read sources and write changesets and candidates; the program decides what follows from them.

```
            research (AI or person, outside the program)
                 |  changesets only
                 v
  work/*.json -> changes.py: validate -> apply to copy -> lint -> impact -> write + audit
                                                   |
        data/kb (rules, entities, evidence)  <-----+-----> profiles/<p>/holdings
        data/candidates (quarantine)                              |
                 |                                                |
                 +------------------> engine.py <-----------------+
                                         |
               status / explain / timeline / review / goal / discover
```

## Modules

| File | Lines | Job |
|---|---|---|
| `schema.py` + `schema.json` | ~100 + schema | Shape of every record and changeset. Small validator, no dependency |
| `store.py` | ~150 | Load and save JSON files as `{path: object}`. Interprets nothing |
| `engine.py` | ~370 | Derive statuses with inspectable derivations |
| `lint.py` | ~220 | Whole-store checks: references, evidence policy, contradictions, negation cycles |
| `review.py` | ~60 | Compare two dates; list downstream consequences; timeline |
| `changes.py` | ~345 | The only write path: operations, staging, impact report, audit log |
| `discovery.py` | ~190 | Coverage ledger and research-task planners; novelty check |
| `goals.py` | ~155 | Objective -> tagged targets -> five-section report |
| `cli.py` | ~325 | Commands |

## The four kinds of knowledge are stored apart

| Category | Stored as | Trusted when |
|---|---|---|
| Sourced rules | `data/kb/rules/` + `data/kb/evidence/` | `verification.status` is `verified`, which lint allows only with one official source or two independent reputable secondary sources |
| Personal qualifications | `profiles/<p>/holdings/`, `metrics/` | `state` is `confirmed`, which needs the owner's attestation |
| Derived entitlements | Never stored. Computed on demand | Every leaf of the derivation is a confirmed fact and every rule on it is verified |
| Unresolved possibilities | `data/candidates/`, unverified rules, unconfirmed holdings | Never. They can only produce `UNRESOLVED` |

## How the engine decides

Two kinds of statement ("atoms") exist for every entity:

- `have:X` — the person holds or is entitled to X today.
- `can_get:X` — the person is eligible to acquire X but has not.

Rules come in three kinds:

| Kind | Meaning | Lasts |
|---|---|---|
| `grants` | While the condition holds, the person has the output | Only while the condition holds |
| `acquire` | While the condition holds, the person may obtain the output. Having it requires a holding record | Per the rule's `retention` terms |
| `transfer` | One currency can be converted into another | While the source currency is held |

Conditions are built from `holds`, `metric >=`, `all`, `any` and `not holds`.

The engine runs the same forward-chaining four times, allowing more assumptions each time:

| Level | May assume | An atom derivable here is |
|---|---|---|
| E | nothing | `ESTABLISHED` |
| C | actions the person could take, acquisitions they are eligible for | `CONDITIONAL` (the assumptions are the to-do list) |
| P | unconfirmed holdings, unverified rules | used for exclusions only |
| U | everything above, plus candidates when asked | `UNRESOLVED` (the assumptions are what to confirm) |

Anything derivable at no level is `NOT_AVAILABLE`.

Each derivation starts from base facts and grows upward (least fixed point), keeping the derivation with the fewest assumptions. Consequences:

- **Cycles cannot create anything.** A loop of rules with no base fact under it is never reached. Tested in `tests/test_c_i_evidence_cycles.py`.
- **No chain-length limit.** Chains end when no rule adds anything new. A 60-step chain is tested.
- **Missing is never satisfied.** An absent holding contributes nothing at level E. An unconfirmed one contributes only at P and U.
- **Every result explains itself.** `explain` prints the chain down to holdings, with rule ids and evidence ids.

Exclusions (`not holds X`) are evaluated in layers so that X is fully decided first; a rule that excludes something depending on its own output is rejected by lint and ignored by the engine.

## Acquisition is not retention

A status obtained through an `acquire` rule becomes a holding with its own dates and a pointer `acquired_via` to the rule. When the original qualification later lapses, the rule's `retention.mode` decides:

| `retention.mode` | After the source lapses | Flag |
|---|---|---|
| `fixed_term` | Stays `ESTABLISHED` until its own `valid_to` | `SOURCE_LAPSED_FIXED_TERM` (info: renewal needs another path) |
| `while_qualified` | Becomes `UNRESOLVED`, with dependents named | `RETENTION_CONDITION_FAILED` |
| `unknown` | Becomes `UNRESOLVED` | `RETENTION_TERMS_UNKNOWN` |

The engine never deletes or ends a holding. It reports; a person confirms the real account state (OP-07). `retain_when` lets a rule state a retention condition different from the acquisition condition.

The brief's Marriott Titanium → Aeroplan 25K case is in the live data with the real terms. The official page does not say what happens to a matched 25K if Titanium lapses, so the rule's mode is `unknown` and the engine answers `UNRESOLVED` with a flag. See `python3 -m prices timeline --profile synthetic-acquired --until 2028-02-01`.

## Time

Every evaluation takes an as-of date. Holdings and rules have `valid_from` / `valid_to`. Verified rules have `review_by`; past it they still apply but raise `STALE_RULE` in every report that uses them. `timeline` evaluates at each date on which anything can change and prints the differences.

## Discovery

See `docs/DISCOVERY.md`. The key structure is the coverage ledger: one cell per (entity, question). The planners emit a research task for every empty or stale cell in reach, so the set of questions grows as the knowledge base grows. Findings enter as candidates and stay quarantined until a named reviewer promotes them.

## Goals

A goal's text is mapped to vocabulary tags by keyword (or tags are passed explicitly). Entities carrying those tags are evaluated and sorted into five sections: established, conditional, worth researching, current promotions, actually available. The last two come only from dated observations; when there are none the report says so. Prices are shown only where recorded with a source.

## Write path

`changes.stage()` validates the changeset, applies it to an in-memory copy, lints the copy, then evaluates every profile before and after and reports what got weaker. `changes.apply()` writes files only if every step passed, and appends to `data/audit/log.jsonl` either way. Limits enforced per operation are listed on the operation cards.

## What is deliberately absent

No database, no web server, no scheduler, no AI call inside the program, no account access, no automated booking or transfers. See `docs/DECISIONS.md` for why.
