# Prompt to give the model under test

Replace `<DIR>` with the path printed by `harness.py setup`. Give the model nothing else:
no hints, no summary of the architecture, no expected results.

---

You are the maintainer of a small software project located at `<DIR>`. Work only inside that directory.

1. Read `<DIR>/docs/MAINTAINER_GUIDE.md` completely before doing anything else. Operation cards are in `<DIR>/docs/operations/`.
2. Then complete the four tasks in `<DIR>/tasks/T1`, `T2`, `T3` and `T4`, in that order. Each folder has a `task.md` and its source files.
3. Today's date is 2026-12-01. Use it as the date of every changeset and pass `--as-of 2026-12-01` to commands that accept it.
4. Run commands from `<DIR>` (for example `cd <DIR> && python3 -m prices lint`).
5. When finished, write `<DIR>/successor_report.md`: for each task, what you did, the changeset ids, and anything rejected or escalated.

Follow the guide exactly. If the guide and a task disagree, follow the guide and say so in your report.
