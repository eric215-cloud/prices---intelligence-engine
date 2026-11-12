# PRICES — continuation document

Update this file at the end of every work session. Last updated 2026-11-12 by the commissioning build.

## What exists
A working, tested foundation: eligibility engine, validation, changeset pipeline, discovery planners, goal reports, maintainer procedures, successor-test harness. 10 researched rules. Two synthetic profiles. An empty profile for Eric. Details: `STATUS.md`. Design: `docs/ARCHITECTURE.md`.

## How to run it
Needs Python 3.9+ only. From the project root:

```
python3 -m unittest discover -s tests      # expect: Ran 94 tests ... OK
python3 -m prices lint                     # expect: lint: 0 error(s), 0 warning(s)
python3 -m prices status --profile synthetic-demo --as-of 2026-11-12
python3 scripts/verify_export.py           # expect: TEST F: PASS
```

If the tests or lint fail on a fresh copy, stop and fix that before anything else.

## What has been tested
Acceptance tests A, B, C, E, F, H, I pass. D passed for one discovery chain. G passed for one run of Claude Haiku 5.5. See the table in `STATUS.md`.

## What remains unresolved
- Eric's real holdings are not in the system.
- No person has reviewed the 10 rules.
- Rules reach `review_by` on 2026-12-20 (two Hyatt rules; the Hyatt offer itself ends 2026-12-31), 2027-02-12 (five transfer and award rules), 2027-05-12 and 2027-11-12.
- 13 forward-discovery cells are open (`python3 -m prices discover forward --profile synthetic-demo`). Two candidates await a reviewer.
- Open questions are recorded on individual rules, notably: what happens to a matched Aeroplan 25K if Marriott Titanium lapses; the validity of JAL Crystal reached through Marriott.

## Next highest-value task
**Load Eric's real holdings.** Until then the system reasons about invented people.

1. Ask Eric for each card, program membership, elite tier with expiry date, and transferable-points balance he wants tracked. No passwords, card numbers or account numbers.
2. For each, check an entity exists (`ls data/kb/entities/`); if not, add it with `add_entity`.
3. Record each with `set_holding` in profile `eric`, carrying Eric's attestation (card OP-07).
4. Run `python3 -m prices status --profile eric` and `python3 -m prices discover forward --profile eric --budget 10`.
5. Research those tasks (procedure in `docs/DISCOVERY.md`). This grows the knowledge base around what Eric actually holds, which keeps maintenance small.

## After that, in order
1. A person spot-checks the rules; remove "Commissioning build" from `promotion_reviewers`.
2. Re-verify the Hyatt rules before 2026-12-20 (OP-01, or OP-06 if the offer is not renewed).
3. Repeat the successor test with the weakest model that will really be used, three runs (`successor_test/README.md`).
4. Add goal tags for objectives Eric actually has (`data/kb/vocab.json`, `tags`).
5. Engineering candidates, only if the need shows up: balance-versus-price checks; page snapshots for evidence; "any N of" conditions.

## Rules for whoever continues
- Records change only through `python3 -m prices apply`. Never by hand.
- Do not weaken a test to make it pass.
- Commit after each working step: `git add -A && git commit -m "..."`.
- Keep this file and `STATUS.md` truthful.
