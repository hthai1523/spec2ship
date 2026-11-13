"""The offline example (examples/customer-management/run-demo.py) must keep working and match the docs."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO

EXAMPLE = REPO / "examples" / "customer-management"


class ExampleDemo(unittest.TestCase):
    def test_offline_demo_runs_end_to_end(self):
        with tempfile.TemporaryDirectory(prefix="s2s-demo-test-") as tmp:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "CLAUDE_CONFIG_DIR": str(Path(tmp) / "cfg"),
                   "SPEC2SHIP_MCP_SEARCH_STOP": tmp}
            r = subprocess.run([sys.executable, str(EXAMPLE / "run-demo.py"), "--out", str(Path(tmp) / "app")],
                               capture_output=True, text=True, encoding="utf-8", env=env, timeout=300)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            out = r.stdout
            self.assertIn("match: high", out)
            self.assertIn('"errors": []', out)
            self.assertIn("forge the approval file -> deny", out)
            self.assertIn("state: APPROVED", out)
            self.assertIn("user note kept: True", out)
            self.assertIn("/harness-work block", out)
            self.assertIn("guard allows further work", out)
            self.assertIn("recorded as REVIEWED", out)
            self.assertIn("verified=2 implemented=3 criteria_pass=4 reviewed_only=1", out)
            report = (Path(tmp) / "app" / ".spec2ship" / "reports" / "report.md").read_text(encoding="utf-8")
            self.assertIn("- Harness ledger: Plans.md", report)  # no machine-specific path in a shareable report

    def test_expected_outputs_are_committed_and_portable(self):
        for name in ("spec.md", "Plans.preview.md", "Plans.after-handoff.md", "rtm.md", "report.md"):
            text = (EXAMPLE / "expected" / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"[A-Za-z]:[\\/]|/Users/|/home/", f"local path in expected/{name}")

    def test_readme_test_count_matches_suite(self):
        suite = unittest.defaultTestLoader.discover(str(REPO / "tests"), top_level_dir=str(REPO))
        count = suite.countTestCases()
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        m = re.search(r"\((\d+) tests\)", readme)
        self.assertIsNotNone(m, "README must state the test count as '(N tests)'")
        self.assertEqual(int(m.group(1)), count, "update the test count in README.md and CHANGELOG.md")


if __name__ == "__main__":
    unittest.main()
