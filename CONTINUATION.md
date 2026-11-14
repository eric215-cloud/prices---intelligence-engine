# PRICES — continuation document

Update this file at the end of every work session. Last updated 2026-11-14 by Claude Fable 5.2 after the relational foundation commission (branch `dev/fable-integration`; `main` unchanged).

## Coordinator continuity

For project leadership, architecture decisions, model responsibilities, office-move resilience, and unresolved coordination decisions, read `docs/coordination/BRADLEY_COORDINATOR_STATE.md` before resuming substantive PRICES work.

## What exists
A working, tested foundation: eligibility engine, validation, changeset pipeline, discovery planners, goal reports, maintainer procedures, successor-test harness. 10 researched rules. Two synthetic profiles. Eric's profile with two confirmed statuses. Details: `STATUS.md`. Design: `docs/ARCHITECTURE.md`.

Added 2026-11-14: card architecture (six role references per card), network-tier baselines and card exclusions that derive nothing, an applicability report, and CSV tables in `tables/` that are a view of the store and a validated authoring input. Demonstrated on invented cards only (`fixtures/`). No real card is loaded. Read `docs/RELATIONAL_TABLES.md`; results in `docs/commissions/results/2026-11-14-fable-relational-foundation-RESULTS.md`.

## How to run it
Needs Python 3.9+ only. From the project root:

```
python3 -m unittest discover -s tests      # expect: Ran 144 tests ... OK
python3 -m prices lint                     # expect: lint: 0 error(s), 1 warning(s)  (Eric's Aeroplan 25K has no expiry date yet)
python3 -m prices status --profile synthetic-demo --as-of 2026-11-12
python3 -m prices tables status            # expect: "no" twice
python3 -m prices --root fixtures/synthetic-cards cards --profile synthetic-alex --as-of 2026-11-14
python3 scripts/verify_export.py           # expect: TEST F: PASS
python3 scripts/verify_clean_checkout.py   # expect: CLEAN CHECKOUT: PASS  (tests the committed state only)
```

If the tests or lint fail on a fresh copy, stop and fix that before anything else.

## What has been tested
Acceptance tests A, B, C, E, F, H, I pass. D passed for one discovery chain. G passed for one run of Claude Haiku 5.5. J (card applicability) and K (tables) pass on invented data. The table maintenance procedure OP-10 has not been run by a lower-capability model. See the tables in `STATUS.md`.

## What remains unresolved
- Two owner-confirmed holdings are now recorded for Eric: Marriott Titanium and Aeroplan 25K (activated through Marriott on November 11). Other cards, statuses, memberships and balances are not yet imported.
- No person has reviewed the 10 rules.
- `dev/fable-integration` has not been reviewed or merged to `main`.
- No real card, organization, tier or card benefit is loaded. The roster in Argon's proposal is unconfirmed and was not ingested.
- Household sharing (authorized user, guest, companion) is undecided and unbuilt.
- `tables/` must stay in step with `data/`. `python3 -m prices apply` re-exports it automatically; anything that changes `data/` another way must be followed by `python3 -m prices tables export`, or the test `test_committed_tables_match_the_live_store` fails.
- Rules reach `review_by` on 2026-12-20 (two Hyatt rules; the Hyatt offer itself ends 2026-12-31), 2027-02-12 (five transfer and award rules), 2027-05-12 and 2027-11-12.
- 13 forward-discovery cells are open (`python3 -m prices discover forward --profile synthetic-demo`). Two candidates await a reviewer.
- Open questions are recorded on individual rules, notably: what happens to a matched Aeroplan 25K if Marriott Titanium lapses; the validity of JAL Crystal reached through Marriott.

## Next highest-value task
**Continue the real-holdings import.** Two statuses are recorded from Eric's explicit statements; the full portfolio remains incomplete.

1. Reconcile Eric's remaining cards, program memberships, elite tiers, expiration dates and transferable-points balances against EEP/connected records; confirm material uncertainties. No passwords, card numbers or account numbers.
2. For each, check an entity exists (`ls data/kb/entities/`); if not, add it with `add_entity`.
3. Record each with `set_holding` in profile `eric`, carrying Eric's own existing or newly provided attestation (card OP-07). Never invent an attestation.
4. Run `python3 -m prices status --profile eric` and `python3 -m prices discover forward --profile eric --budget 10`.
5. Research those tasks (procedure in `docs/DISCOVERY.md`). This grows the knowledge base around what Eric actually holds, which keeps maintenance small.

## Engineering commissions suggested next
See section 8 of the results file. In short: (1) a lower-model test of OP-10 on the synthetic fixture; (2) the real card roster as products only, through the tables, as candidates; (3) a household-sharing decision; (4) read-only table views for programs and bridges; (5) source snapshots; (6) reconcile the Session 1 discovery commission. Not yet: earn-stack arithmetic.

## After that, in order
1. A person spot-checks the rules; remove "Commissioning build" from `promotion_reviewers`.
2. Re-verify the Hyatt rules before 2026-12-20 (OP-01, or OP-06 if the offer is not renewed).
3. Repeat the successor test with the weakest model that will really be used, three runs (`successor_test/README.md`).
4. Add goal tags for objectives Eric actually has (`data/kb/vocab.json`, `tags`).
5. Engineering candidates, only if the need shows up: balance-versus-price checks; page snapshots for evidence; "any N of" conditions.

## Rules for whoever continues
- Records change only through `python3 -m prices apply`, or through `python3 -m prices tables import` for card tables (OP-10). Never by hand.
- Do not weaken a test to make it pass.
- Commit after each working step: `git add -A && git commit -m "..."`.
- Keep this file and `STATUS.md` truthful.
