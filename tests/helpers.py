"""Shared test helpers."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
FIXTURES = REPO / "tests" / "fixtures"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from s2s import cli  # noqa: E402

FIGMA_URL = "https://www.figma.com/design/AbCdEf1234567890/customer-management?node-id=12-345"


def run_cli(project, *args, env=None):
    """Run the CLI in-process. Returns (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old_env = {}
    for k, v in (env or {}).items():
        old_env[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--project-root", str(project), *args])
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return code, out.getvalue(), err.getvalue()


def fake_claude_config(base: Path, harness_version="4.12.11", with_figma=True, project=None,
                       plugin_name="claude-code-harness"):
    """Create an isolated CLAUDE_CONFIG_DIR with a fake Harness install.

    ``plugin_name`` is ``claude-code-harness`` (4.x) or ``harness`` (5.x, renamed upstream)."""
    cfg = base / "claude-config"
    inst = cfg / "plugins" / "cache" / "claude-code-harness-marketplace" / plugin_name / harness_version
    for s in ("harness-plan", "harness-work", "harness-review", "harness-sync"):
        (inst / "skills" / s).mkdir(parents=True, exist_ok=True)
        (inst / "skills" / s / "SKILL.md").write_text(f"---\nname: {s}\n---\n", encoding="utf-8")
    (cfg / "plugins").mkdir(parents=True, exist_ok=True)
    (cfg / "plugins" / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {f"{plugin_name}@claude-code-harness-marketplace": [
            {"scope": "user", "installPath": str(inst), "version": harness_version}]},
    }), encoding="utf-8")
    if with_figma and project is not None:
        (project / ".mcp.json").write_text(json.dumps({"mcpServers": {"figma-mcp-go": {
            "command": "npx", "args": ["-y", "@vkhanhqui/figma-mcp-go@0.4.2"]}}}), encoding="utf-8")
    return cfg


class TempProject:
    """Copy of the sample repo + BA fixture in a temp dir, with isolated Claude config."""

    def __init__(self, with_figma=True, harness_version="4.12.11"):
        self.tmp = Path(tempfile.mkdtemp(prefix="s2s-test-"))
        self.project = self.tmp / "project"
        shutil.copytree(FIXTURES / "sample-repo", self.project)
        (self.project / "docs" / "BA").mkdir(parents=True)
        shutil.copy(FIXTURES / "ba" / "customer-management.md", self.project / "docs" / "BA" / "customer-management.md")
        self.cfg = fake_claude_config(self.tmp, harness_version, with_figma, self.project) if harness_version else None
        self._old = os.environ.get("CLAUDE_CONFIG_DIR")
        self._old_stop = os.environ.get("SPEC2SHIP_MCP_SEARCH_STOP")
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.cfg or (self.tmp / "empty-config"))
        os.environ["SPEC2SHIP_MCP_SEARCH_STOP"] = str(self.tmp)
        self.ws = self.project / ".spec2ship"

    def copy_run_fixtures(self):
        for name, sub in (("requirements.json", "analysis"), ("figma-context.json", "analysis"),
                          ("figma-mapping.json", "mappings"), ("tasks.json", "planning")):
            shutil.copy(FIXTURES / "run" / name, self.ws / sub / name)

    def cleanup(self):
        for key, old in (("CLAUDE_CONFIG_DIR", self._old), ("SPEC2SHIP_MCP_SEARCH_STOP", self._old_stop)):
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
        shutil.rmtree(self.tmp, ignore_errors=True)
