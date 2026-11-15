# PRICES — continuation document

Update this file at the end of every work session. Last updated 2026-11-15 by Claude Fable 5.2 after the ENG-01 recurring-credits commission (branch `dev/eng-01-recurring-credits`, from `dev/argon-content-intake` at 8039477; `main` unchanged).

## Coordinator continuity

For project leadership, architecture decisions, model responsibilities, office-move resilience, and unresolved coordination decisions, read `docs/coordination/BRADLEY_COORDINATOR_STATE.md` before resuming substantive PRICES work.

## What exists
A working, tested foundation: eligibility engine, validation, changeset pipeline, discovery planners, goal reports, maintainer procedures, successor-test harness. 10 researched rules. Two synthetic profiles. Eric's profile with two confirmed statuses. Details: `STATUS.md`. Design: `docs/ARCHITECTURE.md`.

Added 2026-11-14: card architecture (six role references per card), network-tier baselines and card exclusions that derive nothing, an applicability report, and CSV tables in `tables/` that are a view of the store and a validated authoring input. Demonstrated on invented cards only (`fixtures/`). No real card is loaded. Read `docs/RELATIONAL_TABLES.md`; results in `docs/commissions/results/2026-11-14-fable-relational-foundation-RESULTS.md`.

Added 2026-11-15 (fourth commission, ENG-01): structured recurring credits. A `credit` block on a card-benefit rule holds the published terms; the allowance period for any date is computed (calendar year, half, quarter, month, card anniversary, multi-year); a person's balance exists only as an owner-confirmed record for one period. A published allowance is never a personal balance. Demonstrated on invented data only (`fixtures/synthetic-credits/`); no real credit has structured terms and Argon's candidates were not edited. Read `docs/RECURRING_CREDITS.md`, then `docs/operations/OP-13-recurring-credits.md`. Results: `docs/commissions/results/2026-11-15-fable-eng-01-recurring-credits-RESULTS.md`.

Added 2026-11-15 (third commission): Argon's Bilt Palladium and Chase Sapphire Reserve content, candidate-only (113 proposed candidates, none promoted), integrated by replaying Argon's changesets; and cardholder elections (ENG-02) so mutually exclusive Bilt options can never both apply. Read `docs/ELECTIONS.md`, then `docs/operations/OP-12-card-elections.md`. Results: `docs/commissions/results/2026-11-15-fable-argon-intake-bilt-elections-RESULTS.md`.

Added 2026-11-14 (second commission): earned benefits. A public `earns` rule, a person's dated progress per account and qualifying year, and the benefit as it actually sits on the account are separate records; reaching a threshold gives eligibility, never possession. Demonstrated on invented data only (`fixtures/synthetic-earned/`). No real earn rule or personal earned fact is loaded. Read `docs/EARNED_ENTITLEMENTS.md`, then `docs/operations/OP-11-earned-benefits.md`. Results: `docs/commissions/results/2026-11-14-fable-earned-entitlements-RESULTS.md`.

## How to run it
Needs Python 3.9+ only. From the project root:

```
python3 -m unittest discover -s tests      # expect: Ran 327 tests ... OK
python3 -m prices lint                     # expect: lint: 0 error(s), 1 warning(s)  (Eric's Aeroplan 25K has no expiry date yet)
python3 -m prices status --profile synthetic-demo --as-of 2026-11-12
python3 -m prices tables status            # expect: "no" twice
python3 -m prices --root fixtures/synthetic-cards cards --profile synthetic-alex --as-of 2026-11-14
python3 -m prices --root fixtures/synthetic-earned earned --profile synthetic-alex --as-of 2027-03-10
python3 scripts/demo_earned.py             # expect: DEMO COMPLETE  (earned benefits, before and after, on a throwaway copy)
python3 scripts/mutation_check_earned.py   # expect: 17 of 17 mutations caught
python3 scripts/compare_with_baseline.py   # expect: BASELINE COMPARISON: PASS  (needs git; compares with 8039477, the commit before ENG-01)
python3 scripts/verify_argon_intake.py     # expect: ARGON INTAKE: PASS  (needs git)
python3 scripts/demo_elections.py          # expect: DEMO COMPLETE  (Bilt elections on a throwaway copy)
python3 scripts/mutation_check_elections.py  # expect: 13 of 13 mutations caught
python3 -m prices --root fixtures/synthetic-credits credits --profile synthetic-alex --as-of 2027-03-10
python3 scripts/demo_credits.py            # expect: DEMO COMPLETE  (recurring credits, before and after, on a throwaway copy)
python3 scripts/mutation_check_credits.py  # expect: 23 of 23 mutations caught  (about three minutes)
python3 scripts/verify_export.py           # expect: TEST F: PASS
python3 scripts/verify_clean_checkout.py   # expect: CLEAN CHECKOUT: PASS  (tests the committed state only)
```

If the tests or lint fail on a fresh copy, stop and fix that before anything else.

## What has been tested
Acceptance tests A, B, C, E, F, H, I pass. D passed for one discovery chain. G passed for one run of Claude Haiku 5.5. J (card applicability) and K (tables) pass on invented data. L and M (earned benefits) pass on invented data. N (cardholder elections) passes on invented people and the real Bilt definitions. O and P (recurring credits) pass on invented data. The maintenance procedures OP-10 (tables), OP-11 (earned benefits), OP-12 (card elections) and OP-13 (recurring credits) have not been run by a lower-capability model. See the tables in `STATUS.md`.

## What remains unresolved
- Two owner-confirmed holdings are now recorded for Eric: Marriott Titanium and Aeroplan 25K (activated through Marriott on November 11). Other cards, statuses, memberships and balances are not yet imported.
- No person has reviewed the 10 rules.
- `dev/fable-integration` has not been reviewed or merged to `main`.
- No real card, organization, tier or card benefit is loaded. The roster in Argon's proposal is unconfirmed and was not ingested.
- Household sharing (authorized user, guest, companion) is undecided and unbuilt.
- No real earned-benefit rule exists and no personal earned fact is recorded for anyone. Only calendar-year thresholds on one card account are supported; other period types are refused until built. Limits: `docs/EARNED_ENTITLEMENTS.md` section 8.
- If `prices/earned.py` is edited, run `python3 scripts/mutation_check_earned.py`; a line saying STALE means the script must be updated to match.
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
After ENG-01 (see the results file of 2026-11-15 for ENG-01): Argon enters credit terms for the candidates that fit; the structures that do not fit are listed in `docs/RECURRING_CREDITS.md` section 6, each with what it would need. ENG-03 and ENG-04 were deliberately not started.

After the Argon intake (see the results file of 2026-11-15): Argon confirms the Bilt election definitions; a reviewer then decides on promotion candidate by candidate; ENG-01, ENG-03 and ENG-04 were deliberately not started.

After earned benefits (see the last section of the earned-entitlements results file): (1) a lower-model test of OP-11 on the synthetic fixture, alongside the OP-10 test still outstanding; (2) the period types Argon's real rules need (cardmember year, rolling 12 months), each as its own tested step; (3) the household-sharing decision, which earned companion and guest benefits will run into first; (4) a read-only table view of earn rules if Argon wants them in the tables.

From the relational foundation, still open: see section 8 of that results file. In short: (1) a lower-model test of OP-10 on the synthetic fixture; (2) the real card roster as products only, through the tables, as candidates; (3) a household-sharing decision; (4) read-only table views for programs and bridges; (5) source snapshots; (6) reconcile the Session 1 discovery commission. Not yet: earn-stack arithmetic.

## After that, in order
1. A person spot-checks the rules; remove "Commissioning build" from `promotion_reviewers`.
2. Re-verify the Hyatt rules before 2026-12-20 (OP-01, or OP-06 if the offer is not renewed).
3. Repeat the successor test with the weakest model that will really be used, three runs (`successor_test/README.md`).
4. Add goal tags for objectives Eric actually has (`data/kb/vocab.json`, `tags`).
5. Engineering candidates, only if the need shows up: balance-versus-price checks; page snapshots for evidence; "any N of" conditions.

## Rules for whoever continues
- Records change only through `python3 -m prices apply`, or through `python3 -m prices tables import` for card tables (OP-10). Never by hand.
- Offered is not earned and earned is not held. Never record a personal achievement, activation, balance or date that the owner did not give; write `unknown` where a date is not known (OP-11).
- Published is not personal. Never record a credit balance, a use, or a term the source does not state; an empty cell means "the source does not say" (OP-13).
- No election, no option. Never record a cardholder's election, or a card's opening date, that the owner did not give (OP-12).
- Do not weaken a test to make it pass.
- Commit after each working step: `git add -A && git commit -m "..."`.
- Keep this file and `STATUS.md` truthful.
