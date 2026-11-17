"""The foundation viability experiment, run end to end (about twenty seconds).

It promotes real candidates ONLY in a throwaway copy, enters a second batch of real content through the unchanged
pipeline, and changes published terms there. This test fails if any of the experiment's checks stops holding, or
if the run touches the project's own data, profiles or tables.
"""
import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "experiments", "viability"))


def digest(*subs):
    h = hashlib.sha256()
    for sub in subs:
        for d, dirs, names in os.walk(os.path.join(ROOT, sub)):
            dirs.sort()
            for n in sorted(names):
                with open(os.path.join(d, n), "rb") as f:
                    h.update(os.path.relpath(os.path.join(d, n), ROOT).encode() + f.read())
    return h.hexdigest()


class TestViabilityExperiment(unittest.TestCase):
    def test_every_check_holds_and_the_project_is_untouched(self):
        import contextlib
        import io
        import run
        before = digest("data", "profiles", "tables")
        run.checks[:] = []
        run.sections[:] = []
        with contextlib.redirect_stdout(io.StringIO()):
            _p0, p1, bad = run.main()
        self.assertEqual([c["check"] for c in bad], [])
        self.assertGreaterEqual(len(run.checks), 52)
        # CHANGED 2026-11-17 (safety correction): the checks that recorded false positives now assert the corrected
        # answers on the same real content. Pin them by name so they cannot be dropped or reworded into passing.
        names = " | ".join(c["check"] for c in run.checks)
        for must in ("0.2 NO SILENT APPROVAL", "1.3 GUARD: the new-applicant welcome offer is now UNRESOLVED",
                     "3.4 ... and 6,100 PQP is NOT reported as Silver: it is UNRESOLVED", "3.4c ... and the 2026 answer, whose flight minimum the rule checks, is still ESTABLISHED",
                     "3.6 HISTORY PROTECTED", "3.11 RETIREMENT KEEPS HISTORY", "1.2 EVALUATED chain, unaffected", "2.7 CALCULATED with unchanged code"):
            self.assertIn(must, names)
        self.assertEqual(digest("data", "profiles", "tables"), before)
        m = p1["p2"]["measurements"]
        self.assertEqual((m["records"], m["records_accepted_first_time"], m["operations_refused"]), (28, 26, 3))


if __name__ == "__main__":
    unittest.main()
