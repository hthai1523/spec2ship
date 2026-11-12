import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FIXTURES, fake_claude_config
from s2s import harness_adapter as ha
from s2s.common import Spec2ShipError

TASKS = json.loads((FIXTURES / "run" / "tasks.json").read_text(encoding="utf-8"))


class RenderTests(unittest.TestCase):
    def test_section_format_matches_harness_v2(self):
        text = ha.render_section(TASKS, "s2s-20260101-000000-abcdef", "f" * 64, ".spec2ship/planning/spec.md")
        self.assertIn(ha.HEADER, text)
        self.assertIn("## Phase 1: Customer data and API (Spec2Ship)", text)
        self.assertIn("Purpose: Backend, API and database support", text)
        rows = ha.parse_rows(text)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r["status"] == "cc:TODO" for r in rows))
        r12 = next(r for r in rows if r["task"] == "1.2")
        self.assertIn("[REQ-CUS-001]", r12["content"])
        self.assertIn("[tdd:required]", r12["content"])
        self.assertEqual(r12["depends"], "1.1")
        r22 = next(r for r in rows if r["task"] == "2.2")
        self.assertIn("\\|", r22["content"])  # pipe escaped, table not broken

    def test_renumber(self):
        shifted, mapping = ha.renumber(TASKS, 3)
        self.assertEqual(mapping["1.1"], "4.1")
        self.assertEqual(shifted["phases"][1]["tasks"][0]["depends"], ["4.2"])
        self.assertEqual(TASKS["phases"][0]["number"], 1)  # original untouched

    def test_scope_hash_ignores_status(self):
        text = ha.render_section(TASKS, "s2s-20260101-000000-abcdef", "f" * 64)
        h = ha.scope_hash(text)
        self.assertEqual(h, ha.scope_hash(text.replace("| cc:TODO |", "| cc:完了 [a1b2c3d] |", 1)))
        self.assertNotEqual(h, ha.scope_hash(text.replace("jest tests for name", "no tests for name")))


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "proj"
        shutil.copytree(FIXTURES / "sample-repo", self.root)
        self.ws = self.root / ".spec2ship"
        self.run = "s2s-20260101-000000-abcdef"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_appends_and_preserves_existing(self):
        before = (self.root / "Plans.md").read_text(encoding="utf-8")
        info = ha.handoff(self.root, self.ws, TASKS, self.run, "a" * 64, ".spec2ship/planning/spec.md")
        after = (self.root / "Plans.md").read_text(encoding="utf-8")
        self.assertTrue(after.startswith(before.rstrip("\n")))
        self.assertIn("User note: keep this line.", after)
        self.assertEqual(info["phase_offset"], 1)
        self.assertEqual(info["task_map"]["1.1"], "2.1")
        self.assertIn("## Phase 3: Customer screens (Spec2Ship)", after)
        self.assertTrue(Path(info["backup"]).exists())
        self.assertEqual(ha.drift(self.root, self.run, info["scope_hash"])["status"], "ok")

    def test_redo_handoff_reuses_offset_and_refuses_after_progress(self):
        info = ha.handoff(self.root, self.ws, TASKS, self.run, "a" * 64, None)
        info2 = ha.handoff(self.root, self.ws, TASKS, self.run, "b" * 64, None, info)
        text = (self.root / "Plans.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("spec2ship:begin"), 1)
        self.assertEqual(info2["task_map"], info["task_map"])
        p = self.root / "Plans.md"
        p.write_text(re.sub(r"^(\| 2\.1 \|.*)\| cc:TODO \|$", r"\1| cc:WIP |", text, count=1, flags=re.M), encoding="utf-8")
        self.assertEqual(ha.read_statuses(self.root, self.run)["2.1"], "cc:WIP")
        with self.assertRaisesRegex(Spec2ShipError, "already started"):
            ha.handoff(self.root, self.ws, TASKS, self.run, "c" * 64, None, info)

    def test_creates_plans_when_absent_and_detects_drift(self):
        (self.root / "Plans.md").unlink()
        info = ha.handoff(self.root, self.ws, TASKS, self.run, "a" * 64, None)
        text = (self.root / "Plans.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Customer Management Plans.md\n\n作成日:"))
        self.assertIsNone(info["backup"])
        self.assertEqual(info["task_map"]["1.1"], "1.1")
        (self.root / "Plans.md").write_text(text.replace("Customer detail screen", "Customer detail + export screen"), encoding="utf-8")
        self.assertEqual(ha.drift(self.root, self.run, info["scope_hash"])["status"], "changed")
        statuses = ha.read_statuses(self.root, self.run)
        self.assertEqual(statuses["2.3"], "cc:TODO")

    def test_plans_directory_config(self):
        (self.root / ".claude-code-harness.config.yaml").write_text('plansDirectory: ".claude/memory"\n', encoding="utf-8")
        self.assertEqual(ha.plans_path(self.root), (self.root / ".claude" / "memory" / "Plans.md").resolve())
        (self.root / ".claude-code-harness.config.yaml").write_text('plansDirectory: "../outside"\n', encoding="utf-8")
        with self.assertRaises(Spec2ShipError):
            ha.plans_path(self.root)


class DetectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.old = os.environ.get("CLAUDE_CONFIG_DIR")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_detects_installed(self):
        os.environ["CLAUDE_CONFIG_DIR"] = str(fake_claude_config(self.tmp))
        h = ha.detect_harness()
        self.assertTrue(h["compatible"], h)
        self.assertEqual(h["version"], "4.12.11")
        self.assertNotIn("warning", h)

    def test_detects_renamed_plugin(self):
        """Harness 5.x ships as plugin `harness` (renamed from `claude-code-harness`)."""
        os.environ["CLAUDE_CONFIG_DIR"] = str(fake_claude_config(self.tmp, "5.16.0", plugin_name="harness"))
        h = ha.detect_harness()
        self.assertTrue(h["installed"], h)
        self.assertTrue(h["compatible"], h)
        self.assertEqual(h["key"], "harness@claude-code-harness-marketplace")
        self.assertIn("not in the tested list", h["warning"])

    def test_old_and_untested_versions(self):
        os.environ["CLAUDE_CONFIG_DIR"] = str(fake_claude_config(self.tmp, "3.9.0"))
        self.assertFalse(ha.detect_harness()["compatible"])
        shutil.rmtree(self.tmp / "claude-config")
        os.environ["CLAUDE_CONFIG_DIR"] = str(fake_claude_config(self.tmp, "4.13.0"))
        h = ha.detect_harness()
        self.assertTrue(h["compatible"])
        self.assertIn("not in the tested list", h["warning"])

    def test_missing_and_disabled(self):
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.tmp / "none")
        self.assertFalse(ha.detect_harness()["installed"])
        cfg = fake_claude_config(self.tmp)
        os.environ["CLAUDE_CONFIG_DIR"] = str(cfg)
        (cfg / "settings.json").write_text(json.dumps({"enabledPlugins": {"claude-code-harness@claude-code-harness-marketplace": False}}), encoding="utf-8")
        h = ha.detect_harness()
        self.assertFalse(h["compatible"])
        self.assertIn("disabled", " ".join(h["issues"]))


if __name__ == "__main__":
    unittest.main()
