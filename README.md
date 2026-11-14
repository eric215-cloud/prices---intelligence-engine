# PRICES

**P**oints, **R**ewards, **I**ncentives, **C**ards & **E**lite **S**tatus — a personal rewards intelligence engine.

It keeps sourced rules about loyalty programs, one person's actual holdings, and works out what follows: what is established, what needs an action, and what still needs confirming. It also plans research to find relationships nobody has asked about yet.

## Requirements

- Python 3.9 or newer. Nothing else. No packages to install, no network, no database, no hosted service.
- Tested on Python 3.13, Ubuntu 24.04.

## Start here

```
python3 -m unittest discover -s tests          # 143 tests, a few seconds
python3 -m prices lint                         # must print: 0 error(s)
python3 -m prices status --profile synthetic-demo --as-of 2026-11-12
python3 -m prices goal "Find promising ways for me to fly business class to Japan" --profile synthetic-demo --as-of 2026-11-12
python3 -m prices timeline --profile synthetic-acquired --as-of 2026-11-12 --until 2028-02-01
python3 -m prices discover forward --profile synthetic-demo --budget 5
```

Run every command from this directory (the one containing `prices/`, `data/` and `profiles/`).

## Where things are

| Path | What |
|---|---|
| `CONTINUATION.md` | Current state and the next task. **Read first when resuming work.** |
| `STATUS.md` | Honest status report: complete, partial, blocked, untested |
| `docs/MAINTAINER_GUIDE.md` | How to maintain the data. Written for less capable models |
| `docs/operations/` | One card per maintenance operation |
| `docs/DISCOVERY.md` | The discovery procedure |
| `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/SCHEMA.md` | Design, decision record, record formats |
| `prices/` | Source code (about 2,900 lines, standard library only) |
| `prices/schema.json` | Machine-readable schema for every record and for changesets |
| `data/kb/` | Knowledge base: entities, rules, evidence, vocabulary |
| `data/candidates/` | Unverified discoveries (never used as fact) |
| `data/coverage/ledger.json` | Which research questions have been asked, and when |
| `data/discovery_runs/` | Preserved search paths |
| `data/audit/` | Append-only log and a copy of every applied changeset |
| `profiles/eric/` | Authoritative personal records. **Empty and unverified** |
| `profiles/synthetic-*/` | Invented demonstration people. Not Eric |
| `tests/` | Automated tests, including acceptance tests A–I and the card/table tests J–K |
| `tables/` | CSV view of cards, benefits and sources; also the input to `tables import`. The store in `data/` remains the system of record |
| `docs/RELATIONAL_TABLES.md` | Card roles, network-tier baselines, applicability, and the table rules |
| `fixtures/` | Invented cards and people used to test the card tables. Not real data |
| `successor_test/` | Harness for testing whether a smaller model can maintain the system |

## Everyday use

| I want to… | Command |
|---|---|
| See everything for a person | `python3 -m prices status --profile <p>` |
| Know why something is or is not available | `python3 -m prices explain <entity> --profile <p>` |
| See what expires or changes soon | `python3 -m prices timeline --profile <p> --until YYYY-MM-DD` |
| Ask about an objective | `python3 -m prices goal "<objective>" --profile <p>` |
| Get research tasks | `python3 -m prices discover forward --profile <p>` |
| Change any record | Write a changeset, then `python3 -m prices apply <file>` (see the maintainer guide) |
| See card roles and which benefits really apply to each card | `python3 -m prices cards [--profile <p>]` |
| Edit cards and card benefits in a spreadsheet | `python3 -m prices tables export`, edit `tables/*.csv`, `python3 -m prices tables import --author NAME --date YYYY-MM-DD` (`docs/operations/OP-10-tables.md`) |
| Export the whole project | `python3 -m prices export --out prices-export.zip` |

Add `--json` before the command name for machine-readable output: `python3 -m prices --json status --profile <p>`.

## Putting real data in

`profiles/eric/` contains two owner-confirmed status holdings as of 2026-11-12: Marriott Titanium and Aeroplan 25K. Other holdings have not yet been loaded. Real records enter through `set_holding` changesets with Eric's own attestation (operation card OP-07). The knowledge base holds 10 rules, enough to exercise the software, not a survey of the loyalty world.
