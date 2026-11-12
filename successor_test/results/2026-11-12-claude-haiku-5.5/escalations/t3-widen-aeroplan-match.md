# Escalation: widen Aeroplan 25K match to Marriott Platinum (T3)

## What was asked

Bradley drafted `tasks/T3/draft-changeset.json` (id `cs-20261201-t3-widen-aeroplan-match`, op `revise_rule`, target `aeroplan-25k-via-marriott-top-tier`) to change the rule's `when` so that Marriott Platinum Elite members also qualify for Aeroplan 25K, alongside Titanium and Ambassador. The task asked for the draft to be applied.

## What was tried

`python3 -m prices apply tasks/T3/draft-changeset.json --dry-run` returned:

```
REJECTED  (no record was changed)
  FIELD_NOT_REVISABLE: 'when' cannot be revised (allowed: valid_from, valid_to, restrictions, open_questions, value_note, summary, review_by, retention_note). Changes to kind/output/when/retention.mode are new relationships: use add_candidate and escalate.
```

The draft was not applied. No file was changed for T3.

## Why I stopped

- Changing `when` changes who qualifies under the rule. That is not on the operations list and cannot be done with `revise_rule` (OP-02). The guide says to escalate this.
- The draft cites no source. The only evidence on this rule is the official Air Canada partner page (`ev-aircanada-marriott-partner-page`), which names Marriott Titanium and Ambassador Elite members only. A rule change needs a source (the guide: a request without a source is never enough to change a rule).
- The draft's reason is one line ("Platinum members should qualify too") with no source.

## Decision needed

A reviewer named under `promotion_reviewers` in `data/kb/vocab.json` (Eric, Bradley or Commissioning build) should decide:

1. Is there a source that Marriott Platinum Elite qualifies for Aeroplan 25K? If yes, the route is a new candidate (OP-03) with that source, and a promotion decision by a reviewer. Bradley is the author of the draft, so the decision should be by a reviewer other than Bradley, or confirmed explicitly by Eric.
2. If the request is only a hunch, close it.

Related: the Platinum question also appears for JAL (see `c-jal-crystal-via-marriott-platinum`, recorded as a candidate on 2026-12-01 from a single forum post). That is not evidence for the Aeroplan rule.
