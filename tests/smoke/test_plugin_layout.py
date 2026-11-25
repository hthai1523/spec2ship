"""Static smoke checks of the plugin package (complements `claude plugin validate .`)."""
import json
import re
import unittest

from tests.helpers import REPO

COMMANDS = ["spec2ship", "spec2ship-setup", "spec2ship-analyze", "spec2ship-plan", "spec2ship-approve",
            "spec2ship-work", "spec2ship-review", "spec2ship-verify", "spec2ship-status", "spec2ship-auto"]
SKILLS = ["spec2ship-workflow", "ba-analysis", "figma-analysis", "requirement-mapping", "fullstack-planning",
          "implementation-verification", "delivery-report", "figma-design", "visual-verification"]
AGENTS = ["ba-analyst", "figma-analyst", "architecture-analyst", "requirement-mapper", "acceptance-reviewer"]
# Auto mode draws the design through the developer's own write-capable server; only these files may name it.
FIGMA_PREFIX = "mcp__plugin_spec2ship_figma-mcp-go__"


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, text


class PluginLayout(unittest.TestCase):
    def test_manifests_agree(self):
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertEqual(entry["source"], "./")
        from s2s import __version__
        self.assertEqual(__version__, plugin["version"])
        self.assertIn(f"## [{plugin['version']}]", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_commands(self):
        for c in COMMANDS:
            fm, text = frontmatter(REPO / "commands" / f"{c}.md")
            self.assertTrue(fm.get("description"), c)
            if "spec2ship.py" in text:
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/spec2ship.py", text, c)
        for c in ("spec2ship-approve", "spec2ship-auto"):
            fm, _ = frontmatter(REPO / "commands" / f"{c}.md")
            self.assertEqual(fm.get("disable-model-invocation"), "true", c)

    def test_skills_and_agents(self):
        for s in SKILLS:
            fm, _ = frontmatter(REPO / "skills" / s / "SKILL.md")
            self.assertEqual(fm["name"], s)
            self.assertGreater(len(fm["description"]), 40)
        write_tools = re.compile(r"\b(Write|Edit|MultiEdit|NotebookEdit)\b|__(create|set|delete|rename|move|clone|group|import)_")
        for a in AGENTS:
            fm, text = frontmatter(REPO / "agents" / f"{a}.md")
            self.assertEqual(fm["name"], a)
            self.assertFalse(write_tools.search(fm["tools"]), f"{a} must be read-only: {fm['tools']}")
            self.assertIn('"unknowns"', text)

    def test_hooks_reference_existing_scripts(self):
        hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        cmds = [h["command"] for groups in hooks["hooks"].values() for g in groups for h in g["hooks"]]
        self.assertEqual(len(cmds), 3)
        self.assertEqual(sorted(hooks["hooks"]), ["PreToolUse", "Stop", "UserPromptSubmit"])
        for c in cmds:
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/run-hook.sh", c)
        self.assertTrue((REPO / "scripts" / "run-hook.sh").exists())
        self.assertTrue((REPO / "scripts" / "hook.py").exists())

    def test_bundled_figma_mcp_go_is_pinned_and_referenced(self):
        servers = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertEqual(list(servers), ["figma-mcp-go"])
        self.assertEqual(servers["figma-mcp-go"], {"command": "npx", "args": ["-y", "@vkhanhqui/figma-mcp-go@0.1.3"]})
        manifest = json.loads((REPO / "plugins" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "figma-mcp-go")
        for f in ("code.js", "index.html"):
            self.assertTrue((REPO / "plugins" / "dist" / f).is_file(), f)
        fm, _ = frontmatter(REPO / "agents" / "figma-analyst.md")
        mcp_tools = [t.strip() for t in fm["tools"].split(",") if "mcp__" in t]
        self.assertTrue(mcp_tools)
        for t in mcp_tools:
            self.assertTrue(t.startswith(FIGMA_PREFIX), t)
            self.assertRegex(t[len(FIGMA_PREFIX):], r"^(get|search|scan)_", "figma-analyst must only read")
        for p in list((REPO / "skills").rglob("*.md")) + list((REPO / "commands").glob("*.md")) + list((REPO / "agents").glob("*.md")):
            text = p.read_text(encoding="utf-8")
            for stale in ("mcp__plugin_spec2ship_figma-bridge__", "mcp__figma-mcp-go__", "Spec2Ship Figma Bridge (read-only)"):
                self.assertNotIn(stale, text, f"stale reference {stale!r} in {p}")

    def test_figma_edits_are_hook_guarded(self):
        hooks = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        matcher = hooks["hooks"]["PreToolUse"][0]["matcher"]
        self.assertIn(FIGMA_PREFIX, matcher)

    def test_figma_designer_cannot_delete(self):
        fm, _ = frontmatter(REPO / "agents" / "figma-designer.md")
        tools = [t.strip() for t in fm["tools"].split(",")]
        figma = [t for t in tools if t.startswith("mcp__")]
        self.assertTrue(figma and all(t.startswith(FIGMA_PREFIX) for t in figma))
        self.assertFalse([t for t in figma if "delete" in t or "detach" in t or "ungroup" in t], figma)
        self.assertNotIn("Bash", tools)

    def test_schemas_are_valid_json_and_referenced(self):
        for p in (REPO / "schemas").glob("*.schema.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            self.assertIn("$schema", data, p.name)

    def test_helper_scripts_make_no_network_calls(self):
        banned = re.compile(r"^\s*(import|from)\s+(urllib\.request|http\.client|socket|requests|httpx|aiohttp|ftplib|smtplib)\b|urlopen\(", re.M)
        for p in (REPO / "scripts").rglob("*.py"):
            self.assertFalse(banned.search(p.read_text(encoding="utf-8")), f"network use in {p}")

    def test_scripts_never_open_env_files(self):
        for p in (REPO / "scripts").rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"open\([^)]*\.env['\"]", p.name)


if __name__ == "__main__":
    unittest.main()
