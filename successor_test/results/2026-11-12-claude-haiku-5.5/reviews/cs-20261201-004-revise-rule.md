# Downstream review: cs-20261201-004-revise-rule

## What changed

Rule `hyatt-challenge-via-aeroplan-elite` (World of Hyatt 90-day status challenge for Aeroplan elites):

- `valid_to`: 2026-12-31 -> 2026-11-30 (registration deadline moved; the official Hyatt offer page says registration closed on November 30, 2026).
- `restrictions`: "Register by December 31, 2026" replaced with "Register by November 30, 2026; the offer page says registration is now closed".
- `review_by`: 2026-12-31 (about one month, because the offer has an end date).
- Evidence added: `ev-hyatt-aeroplan-challenge-offer-20261201` (official, Hyatt, retrieved 2026-12-01).

Who qualifies and what is granted did not change.

## Impact on profile synthetic-acquired (copied exactly)

```
impact on profile synthetic-acquired:
    can_get:hyatt.globalist: CONDITIONAL -> NOT_AVAILABLE
       relied on by: have:hyatt.globalist
    have:hyatt.aeroplan_challenge: ESTABLISHED -> NOT_AVAILABLE
       relied on by: can_get:hyatt.globalist, have:hyatt.globalist
    have:hyatt.globalist: CONDITIONAL -> NOT_AVAILABLE
```

## Impact on profile synthetic-demo (copied exactly)

```
impact on profile synthetic-demo:
    can_get:hyatt.globalist: CONDITIONAL -> NOT_AVAILABLE
       relied on by: have:hyatt.globalist
    have:hyatt.aeroplan_challenge: CONDITIONAL -> NOT_AVAILABLE
       relied on by: can_get:hyatt.globalist, have:hyatt.globalist
    have:hyatt.globalist: CONDITIONAL -> NOT_AVAILABLE
```

## Relied on by

- `have:hyatt.globalist` (both profiles) and `can_get:hyatt.globalist` (synthetic-acquired, synthetic-demo) depend on `have:hyatt.aeroplan_challenge`.

## Suggested follow-up

- synthetic-acquired: ask the owner whether the challenge was registered before November 30, 2026, and record the answer through the owner (OP-07). Run backward discovery for `hyatt.globalist` to find routes that do not depend on the closed registration.
- synthetic-demo: ask the owner whether the challenge was ever registered. Run backward discovery for `hyatt.globalist`.
- Both: watch whether Hyatt renews the offer for 2027 (already an open question on the rule).
