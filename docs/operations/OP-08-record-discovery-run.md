# OP-08  Record a discovery run

**op:** `record_discovery_run`

**Use when:** you executed research tasks produced by `python3 -m prices discover ...`. Full procedure: `docs/DISCOVERY.md`.

## 1. Inputs and context
- The task list you were given (keep it). Your queries, sources and findings. Ids of candidates you added with OP-03.

## 2. Permitted actions
- Write one run record and update the coverage ledger for every cell you really investigated, including cells where you found nothing.
- Do not mark a cell you did not investigate.

## 3. Source and evidence requirements
Each step records the exact query or URL and a one-sentence finding. Candidates carry the evidence.

## 4. Output: the changeset
```json
{
  "id": "cs-YYYYMMDD-NNN-record-discovery-run",
  "op": "record_discovery_run",
  "author": "...",
  "date": "YYYY-MM-DD",
  "reason": "Forward discovery, 3 cells.",
  "data": {"run": {
    "id": "run-YYYYMMDD-<mode>-NN",
    "date": "YYYY-MM-DD",
    "mode": "forward",
    "profile": "<profile>",
    "executor": "who did the research",
    "tasks": [ "...the task objects you executed, copied from the planner output..." ],
    "steps": [ {"query": "exact query or fetched URL", "sources_seen": ["site.com"], "finding": "One sentence."} ],
    "mentions": ["Program names seen that are not entities yet"],
    "cells": [
      {"cell": "<entity>|<question>", "outcome": "found", "candidates": ["c-..."], "note": "what was and was not searched"},
      {"cell": "<entity>|<question>", "outcome": "nothing_found", "note": "searched X and Y"}
    ]
  }}
}
```

## 5. Validation (done by the program)
- Run shape; `found` cells must cite existing candidates; run id is new.

## 6. Failure and escalation
- Use outcome `inconclusive` when you could not reach a usable source; the cell will be offered again.

## 7. How completion is independently established
`APPLIED`; `data/discovery_runs/<id>.json` exists; `python3 -m prices discover forward ...` no longer lists the recorded cells.
