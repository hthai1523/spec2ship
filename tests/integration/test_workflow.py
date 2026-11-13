"""End-to-end vertical slice through the CLI and the hook handler (no network, no model)."""
import json
from pathlib import Path
import os
import subprocess
import sys
import unittest

from unittest import mock

from tests.helpers import FIGMA_URL, REPO, TempProject, run_cli
from s2s import preflight, repo_analyzer


def hook(mode, payload, env):
    res = subprocess.run([sys.executable, str(REPO / "scripts" / "hook.py"), mode], input=json.dumps(payload),
                         capture_output=True, text=True, encoding="utf-8", env={**os.environ, **env}, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout) if res.stdout.strip() else None


class VerticalSlice(unittest.TestCase):
    def setUp(self):
        self.tp = TempProject()
        self.p = self.tp.project

    def tearDown(self):
        self.tp.cleanup()

    def cli(self, *args, **kw):
        return run_cli(self.p, *args, **kw)

    def _to_plan_review(self):
        code, out, err = self.cli("init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
        self.assertEqual(code, 0, err)
        code, out, err = self.cli("preflight")
        self.assertEqual(code, 0, out + err)
        code, out, err = self.cli("figma-check", "--open-file-name", "Customer Management", "--node-found", "yes")
        self.assertEqual(json.loads(out)["match"], "high")
        code, out, err = self.cli("parse-ba")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["state"], "ANALYSIS")
        code, out, err = self.cli("repo-analyze")
        self.assertEqual(code, 0, err)
        self.tp.copy_run_fixtures()
        code, out, err = self.cli("validate", "--stage", "plan")
        self.assertEqual(code, 0, out)
        code, out, err = self.cli("plan-review")
        self.assertEqual(code, 0, out + err)
        return json.loads(out)

    def test_full_slice_with_approval_gate(self):
        review = self._to_plan_review()
        self.assertEqual(review["state"], "PLAN_REVIEW")
        self.assertEqual(review["tasks"], 6)
        self.assertEqual(review["rtm_metrics"]["mapped_to_design"], 3)
        self.assertEqual(review["rtm_metrics"]["deferred_or_rejected"], 1)
        ws = self.tp.ws
        spec = (ws / "planning" / "spec.md").read_text(encoding="utf-8")
        for h in ("## Overview", "## Functional Requirements", "## Acceptance Criteria", "## Open Questions", "## Out of Scope"):
            self.assertIn(h, spec)
        self.assertIn("REQ-CUS-004 Search performance (deferred)", spec)
        preview = (ws / "planning" / "Plans.md").read_text(encoding="utf-8")
        self.assertIn("| Task | 内容 | DoD | Depends | Status |", preview)
        root_plans_before = (self.p / "Plans.md").read_text(encoding="utf-8")

        # Work cannot start: no handoff before approval
        code, _, err = self.cli("handoff")
        self.assertEqual(code, 1)
        self.assertIn("approved plan", err)
        # Claude cannot approve without the developer's typed intent
        code, _, err = self.cli("approve", review["plan_hash_short"])
        self.assertEqual(code, 1)
        self.assertIn("No developer approval intent", err)
        # Model attempts to forge intent are denied by the hook
        env = {"CLAUDE_CONFIG_DIR": str(self.tp.cfg)}
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Write", "tool_input": {"file_path": str(ws / ".approval-intent.json")}}, env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Skill", "tool_input": {"skill": "spec2ship:spec2ship-approve"}}, env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        # Developer types /spec2ship-approve -> UserPromptSubmit records intent
        self.assertIsNone(hook("prompt", {"cwd": str(self.p), "prompt": f"/spec2ship-approve {review['plan_hash_short']}"}, env))
        self.assertTrue((ws / ".approval-intent.json").exists())
        # Wrong hash is rejected (and intent kept for retry)
        code, _, err = self.cli("approve", "deadbeefdead")
        self.assertIn("Plan hash mismatch", err)
        code, out, err = self.cli("approve", review["plan_hash_short"], "--approver", "dev")
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["state"], "APPROVED")
        self.assertFalse((ws / ".approval-intent.json").exists())
        # Root Plans.md untouched until handoff
        self.assertEqual((self.p / "Plans.md").read_text(encoding="utf-8"), root_plans_before)

        code, out, err = self.cli("handoff")
        self.assertEqual(code, 0, err)
        info = json.loads(out)
        self.assertEqual(info["state"], "EXECUTION")
        self.assertEqual(info["task_map"]["1.1"], "2.1")
        root_plans = (self.p / "Plans.md").read_text(encoding="utf-8")
        self.assertTrue(root_plans.startswith(root_plans_before.rstrip("\n")))
        self.assertIn("User note: keep this line.", root_plans)

        # Guard allows Harness work for the unchanged approved plan
        self.assertIsNone(hook("pretool", {"cwd": str(self.p), "tool_name": "Skill", "tool_input": {"skill": "claude-code-harness:harness-work"}}, env))
        self.assertIsNone(hook("prompt", {"cwd": str(self.p), "prompt": "/harness-work all"}, env))
        # Harness marks progress (status-only change) -> still allowed
        progressed = root_plans.replace("| cc:TODO |", "| cc:完了 [1234567] |")
        progressed = progressed.replace("| 1.2  | Logout | test passes | 1.1 | cc:完了 [1234567] |", "| 1.2  | Logout | test passes | 1.1 | cc:TODO |")
        (self.p / "Plans.md").write_text(progressed, encoding="utf-8")
        code, out, _ = self.cli("guard")
        self.assertEqual(code, 0, out)
        # Scope edited after approval -> blocked
        (self.p / "Plans.md").write_text(progressed.replace("Customer detail screen", "Customer detail and export screen"), encoding="utf-8")
        blocked = hook("prompt", {"cwd": str(self.p), "prompt": "/harness-work all"}, env)
        self.assertEqual(blocked["decision"], "block")
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Skill", "tool_input": {"skill": "breezing"}}, env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        # Harness 5.x namespace (plugin renamed to `harness`) is guarded the same way
        for prompt_text in ("/harness:harness-work all", "/claude-code-harness:harness-work all"):
            self.assertEqual(hook("prompt", {"cwd": str(self.p), "prompt": prompt_text}, env)["decision"], "block", prompt_text)
        denied = hook("pretool", {"cwd": str(self.p), "tool_name": "Skill", "tool_input": {"skill": "harness:harness-work"}}, env)
        self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
        (self.p / "Plans.md").write_text(progressed, encoding="utf-8")

        # Review -> verification with evidence rules
        self.assertEqual(self.cli("transition", "REVIEW")[0], 0)
        self.assertEqual(self.cli("transition", "VERIFICATION")[0], 0)
        code, out, _ = self.cli("record-evidence", "--criterion", "AC-CUS-001-01", "--status", "PASS", "--method", "llm-review", "--note", "code reads right")
        self.assertEqual(json.loads(out)["recorded"]["status"], "REVIEWED")
        code, _, err = self.cli("record-evidence", "--criterion", "AC-CUS-001-02", "--status", "PASS", "--method", "unit-test")
        self.assertEqual(code, 1)
        code, _, err = self.cli("record-evidence", "--criterion", "AC-CUS-001-02", "--status", "PASS", "--method", "unit-test", "--command", "npm test", "--exit-code", "1")
        self.assertIn("not a pass", err)
        for ac in ("AC-CUS-001-02", "AC-CUS-002-01", "AC-CUS-002-02", "AC-CUS-003-01"):
            code, _, err = self.cli("record-evidence", "--criterion", ac, "--status", "PASS", "--method", "unit-test",
                                    "--command", "npm test -- customers", "--exit-code", "0", "--file", "tests/customers.test.js")
            self.assertEqual(code, 0, err)
        self.cli("record-check", "--name", "unit tests", "--layer", "unit", "--command", "npm test", "--exit-code", "0", "--status", "PASS")
        self.cli("record-check", "--name", "build", "--layer", "build", "--status", "NOT_RUN", "--summary", "no tsconfig")
        # AC-CUS-001-01 only REVIEWED -> cannot complete
        code, _, err = self.cli("transition", "COMPLETED")
        self.assertEqual(code, 1)
        self.assertIn("2/3 in-scope requirements are verified", err)
        code, out, _ = self.cli("report")
        m = json.loads(out)["metrics"]
        self.assertEqual((m["verified"], m["implemented"], m["criteria_pass"], m["criteria_reviewed_only"]), (2, 3, 4, 1))
        report = (self.tp.ws / "reports" / "report.md").read_text(encoding="utf-8")
        self.assertIn("### Verified (all acceptance criteria PASS with evidence) (2)", report)
        self.assertIn("### Implemented, not fully verified (1)", report)
        self.assertIn("### Deferred (1)", report)
        self.assertIn("| build | build | `-` | NOT_RUN |", report)
        # Real evidence for the remaining criterion -> complete
        self.cli("record-evidence", "--criterion", "AC-CUS-001-01", "--status", "PASS", "--method", "integration-test",
                 "--file", "tests/customers.test.js", "--test", "search by partial name")
        code, out, err = self.cli("transition", "COMPLETED")
        self.assertEqual(code, 0, err)

    def test_edit_after_review_requires_new_review(self):
        review = self._to_plan_review()
        spec = self.tp.ws / "planning" / "spec.md"
        spec.write_text(spec.read_text(encoding="utf-8") + "\nDeveloper edit.\n", encoding="utf-8")
        (self.tp.ws / ".approval-intent.json").write_text(json.dumps({"at": "2999-01-01T00:00:00+00:00"}), encoding="utf-8")
        code, _, err = self.cli("approve", review["plan_hash_short"])
        self.assertIn("Plan hash mismatch", err)
        # re-review keeps the developer's spec edits (not overwritten)
        code, out, _ = self.run_replan()
        self.assertIn("Developer edit.", spec.read_text(encoding="utf-8"))
        self.assertTrue(json.loads(out)["spec"]["preserved_user_edits"])

    def run_replan(self):
        self.cli("transition", "PLANNING", "--reason", "developer edited spec")
        return self.cli("plan-review")

    def test_blocking_question_needs_explicit_acceptance(self):
        self.cli("init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
        self.cli("preflight")
        self.cli("parse-ba")
        self.tp.copy_run_fixtures()
        rp = self.tp.ws / "analysis" / "requirements.json"
        data = json.loads(rp.read_text(encoding="utf-8"))
        data["requirements"][1]["ambiguities"][0]["blocking"] = True
        rp.write_text(json.dumps(data), encoding="utf-8")
        code, out, _ = self.cli("plan-review")
        h = json.loads(out)["plan_hash_short"]
        self.assertEqual(len(json.loads(out)["blocking_questions"]), 1)
        env = {"SPEC2SHIP_REQUIRE_APPROVAL_INTENT": "0"}
        code, _, err = self.cli("approve", h, env=env)
        self.assertIn("Unresolved blocking questions", err)
        code, out, err = self.cli("approve", h, "--accept-open-questions", env=env)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(json.loads(out)["approval"]["accepted_open_questions"]), 1)

    def test_existing_run_is_preserved(self):
        self.cli("init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
        code, _, err = self.cli("init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        first = json.loads((self.tp.ws / "state.json").read_text(encoding="utf-8"))["run_id"]
        code, _, err = self.cli("init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md", "--force-new")
        self.assertEqual(code, 0, err)
        self.assertTrue((self.tp.ws / "archive" / first / "state.json").exists())


class HookLauncher(unittest.TestCase):
    """run-hook.sh as Claude Code invokes it (bash), including the MSYS path case found in live testing."""

    def setUp(self):
        import shutil as _sh
        self.bash = _sh.which("bash")
        if not self.bash:
            self.skipTest("bash not available")
        self.tp = TempProject()

    def tearDown(self):
        self.tp.cleanup()

    def _run(self, mode, payload, extra_env=None, script="run-hook.sh"):
        env = {**os.environ, **(extra_env or {})}
        return subprocess.run([self.bash, str(REPO / "scripts" / script), mode], input=json.dumps(payload),
                              capture_output=True, text=True, encoding="utf-8", env=env, timeout=60)

    def test_denies_state_edit_through_launcher(self):
        run_cli(self.tp.project, "init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
        payload = {"cwd": str(self.tp.project), "tool_name": "Edit",
                   "tool_input": {"file_path": str(self.tp.ws / "state.json")}}
        for env in ({}, {"MSYS_NO_PATHCONV": "1"}):
            res = self._run("pretool", payload, env)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(res.stdout)["hookSpecificOutput"]["permissionDecision"], "deny", (env, res.stderr))
        bash_payload = {"cwd": str(self.tp.project), "tool_name": "Bash",
                        "tool_input": {"command": "python -c \"import json; json.dump({}, open('.spec2ship/state.json','w'))\""}}
        self.assertEqual(json.loads(self._run("pretool", bash_payload).stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        read_payload = {"cwd": str(self.tp.project), "tool_name": "Bash", "tool_input": {"command": "cat .spec2ship/state.json"}}
        self.assertEqual(self._run("pretool", read_payload).stdout.strip(), "")

    def test_fails_open_on_internal_error(self):
        # A broken Python environment must not block the user's tool calls.
        res = self._run("pretool", {"cwd": str(self.tp.project), "tool_name": "Bash", "tool_input": {"command": "ls"}},
                        {"PYTHONHOME": str(self.tp.tmp / "no-such-python-home")})
        self.assertEqual(res.returncode, 0)
        self.assertIn("spec2ship hook warning", res.stderr)
        self.assertEqual(res.stdout.strip(), "")


NODE_OK = {"ok": True, "version": "v24.0.0", "detail": "Node v24.0.0"}


class PreflightAndInputs(unittest.TestCase):
    def test_missing_harness_blocks_bundled_figma_ok(self):
        tp = TempProject(with_figma=False, harness_version=None)
        try:
            run_cli(tp.project, "init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
            with mock.patch.object(preflight, "node_runtime", return_value=NODE_OK):
                code, out, _ = run_cli(tp.project, "preflight")
            self.assertEqual(code, 2)
            self.assertIn("[FAIL] harness", out)
            self.assertIn("/plugin install harness@claude-code-harness-marketplace", out)
            self.assertIn("[OK  ] figma-mcp-config: bundled with Spec2Ship: npx -y @vkhanhqui/figma-mcp-go@0.1.3", out)
            self.assertIn("mcp__plugin_spec2ship_figma-mcp-go__", out)
            st = json.loads((tp.ws / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(st["state"], "BLOCKED")
        finally:
            tp.cleanup()

    def test_bundled_server_needs_node(self):
        tp = TempProject(with_figma=False)
        try:
            with mock.patch.object(preflight, "node_runtime", return_value={"ok": False, "detail": "node not found on PATH"}):
                code, out, _ = run_cli(tp.project, "preflight", "--no-record")
            self.assertEqual(code, 2)
            self.assertIn("[FAIL] node-runtime", out)
            self.assertIn("Install Node.js 20+", out)
        finally:
            tp.cleanup()

    def test_missing_bundle_blocks(self):
        tp = TempProject(with_figma=False)
        try:
            with mock.patch.object(preflight, "bundled_figma_server", return_value=None):
                code, out, _ = run_cli(tp.project, "preflight", "--no-record")
            self.assertEqual(code, 2)
            self.assertIn("[FAIL] figma-mcp-config", out)
            self.assertIn("/plugin update spec2ship@spec2ship-marketplace", out)
        finally:
            tp.cleanup()

    def test_figma_plugin_import_path_is_printed(self):
        tp = TempProject(with_figma=False)
        try:
            built = {**preflight.bundled_figma_server(), "figma_plugin_built": True}
            with mock.patch.object(preflight, "node_runtime", return_value=NODE_OK), \
                    mock.patch.object(preflight, "bundled_figma_server", return_value=built):
                code, out, _ = run_cli(tp.project, "preflight", "--no-record")
            self.assertEqual(code, 0, out)
            manifest = str(REPO / "vendor" / "figma-bridge" / "plugin" / "manifest.json")
            self.assertIn(f"[OK  ] figma-plugin: Figma plugin to import: {manifest}", out)
            self.assertIn("Spec2Ship Figma Bridge (read-only)", out)
        finally:
            tp.cleanup()

    def test_user_figma_mcp_go_is_flagged(self):
        tp = TempProject()  # writes a project .mcp.json with the user's own figma-mcp-go
        try:
            with mock.patch.object(preflight, "node_runtime", return_value=NODE_OK):
                code, out, _ = run_cli(tp.project, "preflight", "--no-record")
            self.assertIn("[WARN] figma-other-server", out)
            self.assertIn("DMCA", out)
            self.assertIn("claude mcp remove figma-mcp-go", out)
        finally:
            tp.cleanup()

    def test_bundled_config_runs_vendored_server_without_npx(self):
        b = preflight.bundled_figma_server()
        self.assertTrue(b["server_exists"], b)
        self.assertFalse(b["uses_npx"])
        self.assertEqual(b["port"], 3994)
        self.assertTrue(b["server_path"].endswith(str(Path("vendor") / "figma-bridge" / "dist" / "server.mjs")))

    def test_invalid_inputs_fail_clearly(self):
        tp = TempProject()
        try:
            code, _, err = run_cli(tp.project, "init", "--figma", "https://example.com/x", "--ba", "docs/BA/customer-management.md")
            self.assertIn("Not a figma.com URL", err)
            code, _, err = run_cli(tp.project, "init", "--figma", FIGMA_URL, "--ba", "docs/BA/missing.pdf")
            self.assertIn("BA document not found", err)
            code, _, err = run_cli(tp.project, "init", "--figma", FIGMA_URL, "--ba", "package.json")
            self.assertIn("Unsupported BA format", err)
            self.assertFalse((tp.ws / "state.json").exists())
        finally:
            tp.cleanup()

    def test_scanned_pdf_blocks_analysis(self):
        tp = TempProject()
        try:
            import shutil
            from tests.helpers import FIXTURES
            shutil.copy(FIXTURES / "ba" / "scanned.pdf", tp.project / "docs" / "BA" / "scanned.pdf")
            run_cli(tp.project, "init", "--figma", FIGMA_URL, "--ba", "docs/BA/scanned.pdf")
            run_cli(tp.project, "preflight")
            code, out, _ = run_cli(tp.project, "parse-ba")
            self.assertEqual(code, 3)
            self.assertEqual(json.loads(out)["state"], "BLOCKED")
        finally:
            tp.cleanup()


class RepoAnalyzerTests(unittest.TestCase):
    def test_detects_stack_and_skips_secrets(self):
        tp = TempProject()
        try:
            (tp.project / "server.key").write_text("PRIVATE KEY SHOULD NOT BE LISTED", encoding="utf-8")
            a = repo_analyzer.analyze(tp.project)
            for fw in ("Express", "React"):
                self.assertIn(fw, a["frameworks"])
            self.assertIn("Prisma", a["data"])
            self.assertIn("Jest", a["testing"])
            self.assertEqual(a["package_managers"], ["npm"])
            self.assertEqual(a["commands"]["test"], ["npm test"])
            self.assertEqual(a["commands"]["lint"], ["npm run lint"])
            self.assertIn("prisma/migrations", a["database"]["migrations_dirs"])
            self.assertIn("prisma/schema.prisma", a["database"]["schema_files"])
            paths = {(r["method"], r["path"]) for r in a["api"]["routes"]}
            self.assertIn(("GET", "/api/customers"), paths)
            self.assertEqual(a["ci"], [".github/workflows/ci.yml"])
            self.assertTrue(repo_analyzer._is_secret(".env"))
            self.assertTrue(repo_analyzer._is_secret(".env.production"))
            self.assertTrue(repo_analyzer._is_secret("server.key"))
            md = repo_analyzer.to_markdown(a)
            self.assertNotIn("PRIVATE KEY", md)
            self.assertNotIn("server.key", json.dumps(a))
        finally:
            tp.cleanup()


if __name__ == "__main__":
    unittest.main()
