"""Auto mode: developer authorization, automatic approval, fix-round handoff, Stop-hook continuation, visual check."""
import json
import os
import subprocess
import sys
import unittest

from tests.helpers import REPO, TempProject, run_cli

try:
    from PIL import Image, ImageDraw  # type: ignore
except ImportError:  # pragma: no cover
    Image = None

IDEA = "Customer list screen with search and paging"


def hook(mode, payload, env):
    res = subprocess.run([sys.executable, str(REPO / "scripts" / "hook.py"), mode], input=json.dumps(payload),
                         capture_output=True, text=True, encoding="utf-8", env={**os.environ, **env}, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout) if res.stdout.strip() else None


class AutoMode(unittest.TestCase):
    def setUp(self):
        self.tp = TempProject()
        self.p = self.tp.project
        self.ws = self.tp.ws
        self.env = {"CLAUDE_CONFIG_DIR": str(self.tp.cfg)}

    def tearDown(self):
        self.tp.cleanup()

    def cli(self, *args):
        return run_cli(self.p, *args)

    def authorize(self):
        self.assertIsNone(hook("prompt", {"cwd": str(self.p), "prompt": f"/spec2ship:spec2ship-auto {IDEA}"}, self.env))

    def start(self, *extra):
        self.authorize()
        code, out, err = self.cli("init", "--auto", "--instructions", IDEA, *extra)
        self.assertEqual(code, 0, err)
        return json.loads(out)

    def to_plan_review(self):
        self.start("--ba", "docs/BA/customer-management.md")
        self.cli("preflight")
        self.cli("parse-ba")
        self.tp.copy_run_fixtures()
        code, out, err = self.cli("plan-review")
        self.assertEqual(code, 0, out + err)
        return json.loads(out)

    # -------------------------------------------------------------- authorization

    def test_auto_needs_the_developers_typed_command(self):
        code, _, err = self.cli("init", "--auto", "--instructions", IDEA)
        self.assertNotEqual(code, 0)
        self.assertIn("No developer authorization for auto mode", err)
        self.assertFalse((self.ws / "state.json").exists())

    def test_model_cannot_forge_auto_authorization(self):
        ws = self.ws
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Write", "tool_input": {"file_path": str(ws / ".auto-intent.json")}}, self.env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Bash", "tool_input": {"command": "echo {} > .spec2ship/.auto-intent.json"}}, self.env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Skill", "tool_input": {"skill": "spec2ship:spec2ship-auto"}}, self.env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_init_auto_records_limits_and_consumes_authorization(self):
        res = self.start("--max-rounds", "2", "--threshold", "0.9")
        self.assertEqual(res["auto"]["max_rounds"], 2)
        self.assertEqual(res["auto"]["threshold"], 0.9)
        self.assertFalse((self.ws / ".auto-intent.json").exists())
        st = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(st["retries"]["max"], 2)
        # the design is drawn later, so no 'unavailable' Figma context is pre-written
        self.assertFalse((self.ws / "analysis" / "figma-context.json").exists())
        code, out, _ = self.cli("--json", "status")
        self.assertIn("preflight", json.loads(out)["auto"]["next_step"])

    # -------------------------------------------------------------- approval and fix rounds

    def test_approve_auto_only_in_auto_runs(self):
        run_cli(self.p, "init", "--ba", "docs/BA/customer-management.md")
        self.cli("preflight")
        self.cli("parse-ba")
        self.tp.copy_run_fixtures()
        self.cli("plan-review")
        code, _, err = self.cli("approve", "--auto")
        self.assertNotEqual(code, 0)
        self.assertIn("not in auto mode", err)

    def test_auto_approval_and_fix_round_keep_harness_progress(self):
        review = self.to_plan_review()
        code, out, err = self.cli("approve", "--auto")
        self.assertEqual(code, 0, err)
        appr = json.loads(out)["approval"]
        self.assertEqual((appr["approver"], appr["mode"]), ("auto-mode", "auto"))
        self.assertEqual(appr["plan_hash"][:12], review["plan_hash_short"])
        code, out, err = self.cli("handoff")
        self.assertEqual(code, 0, err)
        first = json.loads(out)["task_map"]
        plans = self.p / "Plans.md"
        done_task = first["1.1"]
        text = plans.read_text(encoding="utf-8")
        row_start = text.index(f"| {done_task} |")
        row_end = text.index("\n", row_start)
        plans.write_text(text[:row_start] + text[row_start:row_end].replace("cc:TODO", "cc:完了 [abc1234]") + text[row_end:], encoding="utf-8")
        self.assertEqual(self.cli("transition", "REVIEW")[0], 0)
        self.assertEqual(self.cli("transition", "VERIFICATION")[0], 0)
        # fix round: back to execution, add a task, re-plan, auto-approve, hand off again
        self.assertEqual(self.cli("transition", "EXECUTION")[0], 0)
        tasks_p = self.ws / "planning" / "tasks.json"
        tasks = json.loads(tasks_p.read_text(encoding="utf-8"))
        last = max(ph["number"] for ph in tasks["phases"])
        any_req = tasks["phases"][0]["tasks"][0]["requirement_ids"] or ["REQ-CUS-001"]
        tasks["phases"].append({"number": last + 1, "title": "Fix round 1", "tasks": [
            {"id": f"{last + 1}.1", "title": "Match list header spacing to the Figma frame", "requirement_ids": any_req,
             "layer": "frontend", "dod": "`visual-compare` passes for customer-list", "depends": []}]})
        tasks_p.write_text(json.dumps(tasks), encoding="utf-8")
        code, out, err = self.cli("plan-review")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.cli("approve", "--auto")[0], 0)
        code, out, err = self.cli("handoff")
        self.assertEqual(code, 0, err)
        text = plans.read_text(encoding="utf-8")
        self.assertIn("cc:完了 [abc1234]", text)  # Harness progress kept
        self.assertIn("Match list header spacing", text)
        st = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(st["auto"]["approvals"], 2)
        self.assertEqual(st["retries"]["verification"], 1)

    def test_fix_rounds_are_limited(self):
        self.start("--max-rounds", "0", "--ba", "docs/BA/customer-management.md")
        self.cli("preflight")
        self.cli("parse-ba")
        self.tp.copy_run_fixtures()
        self.cli("plan-review")
        self.cli("approve", "--auto")
        self.cli("handoff")
        self.cli("transition", "REVIEW")
        self.cli("transition", "VERIFICATION")
        code, _, err = self.cli("transition", "EXECUTION")
        self.assertNotEqual(code, 0)
        self.assertIn("Retry limit (0)", err)

    # -------------------------------------------------------------- Stop hook

    def test_stop_hook_keeps_auto_run_going_and_is_bounded(self):
        self.assertIsNone(hook("stop", {"cwd": str(self.p)}, self.env))  # no run
        self.start()
        out = hook("stop", {"cwd": str(self.p)}, self.env)
        self.assertEqual(out["decision"], "block")
        self.assertIn("preflight", out["reason"])
        for _ in range(5):
            hook("stop", {"cwd": str(self.p)}, self.env)
        paused = hook("stop", {"cwd": str(self.p)}, self.env)  # 7th continuation without leaving INIT
        self.assertNotIn("decision", paused)
        self.assertIn("paused", paused["systemMessage"])

    def test_stop_hook_silent_for_normal_and_finished_runs(self):
        run_cli(self.p, "init", "--ba", "docs/BA/customer-management.md")
        self.assertIsNone(hook("stop", {"cwd": str(self.p)}, self.env))
        self.tp.cleanup()
        self.tp = TempProject()
        self.p, self.ws, self.env = self.tp.project, self.tp.ws, {"CLAUDE_CONFIG_DIR": str(self.tp.cfg)}
        self.start()
        self.cli("preflight")
        st = json.loads((self.ws / "state.json").read_text(encoding="utf-8"))
        if st["state"] != "BLOCKED":
            self.cli("transition", "BLOCKED", "--reason", "test")
        self.assertIsNone(hook("stop", {"cwd": str(self.p)}, self.env))

    # -------------------------------------------------------------- preflight

    def test_preflight_auto_requires_a_figma_writer(self):
        code, out, _ = run_cli(self.p, "preflight", "--no-record", "--auto")
        self.assertIn("[OK  ] auto-figma-writer", out)  # TempProject configures a server named figma-mcp-go
        (self.p / ".mcp.json").unlink()
        code, out, _ = run_cli(self.p, "preflight", "--no-record", "--auto")
        self.assertIn("[FAIL] auto-figma-writer", out)
        self.assertEqual(code, 2)


@unittest.skipIf(Image is None, "Pillow not installed")
class VisualCompare(unittest.TestCase):
    def setUp(self):
        self.tp = TempProject()
        self.p, self.ws = self.tp.project, self.tp.ws
        self.assertIsNone(hook("prompt", {"cwd": str(self.p), "prompt": f"/spec2ship-auto {IDEA}"}, {"CLAUDE_CONFIG_DIR": str(self.tp.cfg)}))
        run_cli(self.p, "init", "--auto", "--instructions", IDEA)
        (self.ws / "design" / "screens").mkdir(parents=True)
        (self.ws / "verification" / "screens").mkdir(parents=True)

    def tearDown(self):
        self.tp.cleanup()

    def screen(self, draw_actual, scale=1):
        ref = Image.new("RGB", (400, 300), "white")
        d = ImageDraw.Draw(ref)
        d.rectangle([0, 0, 399, 48], fill="#1f2937")
        d.rectangle([24, 80, 376, 120], outline="#9ca3af")
        ref.save(self.ws / "design" / "screens" / "list.png")
        act = draw_actual(ref.copy())
        if scale != 1:
            act = act.resize((act.width * scale, act.height * scale))
        act.save(self.ws / "verification" / "screens" / "list.png")
        (self.ws / "design" / "screens.json").write_text(json.dumps({"schema_version": "1.0", "screens": [
            {"id": "list", "node_id": "1:2", "route": "/", "width": 400, "height": 300, "reference": "design/screens/list.png"}]}),
            encoding="utf-8")

    def test_identical_and_2x_screenshots_match(self):
        self.screen(lambda im: im, scale=2)
        code, out, _ = run_cli(self.p, "visual-compare")
        self.assertEqual(code, 0, out)
        self.assertIn("MATCH", out)
        ver = json.loads((self.ws / "verification" / "verification.json").read_text(encoding="utf-8"))
        self.assertEqual(ver["checks"][-1]["name"], "visual:list")
        self.assertEqual(ver["checks"][-1]["status"], "PASS")
        self.assertTrue((self.ws / "verification" / "screens" / "list.diff.png").exists())

    def test_missing_header_does_not_match(self):
        def no_header(im):
            ImageDraw.Draw(im).rectangle([0, 0, 399, 120], fill="white")
            return im
        self.screen(no_header)
        code, out, _ = run_cli(self.p, "--json", "visual-compare")
        self.assertEqual(code, 1)
        res = json.loads(out)
        self.assertFalse(res["ok"])
        self.assertLess(res["screens"][0]["score"], 0.92)

    def test_missing_screenshot_is_not_run(self):
        self.screen(lambda im: im)
        (self.ws / "verification" / "screens" / "list.png").unlink()
        code, out, _ = run_cli(self.p, "--json", "visual-compare")
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["screens"][0]["status"], "NOT_RUN")


if __name__ == "__main__":
    unittest.main()
