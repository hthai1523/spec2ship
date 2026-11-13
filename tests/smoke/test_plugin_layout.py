"""Static smoke checks of the plugin package (complements `claude plugin validate .`)."""
import json
import re
import unittest

from tests.helpers import REPO

COMMANDS = ["spec2ship", "spec2ship-setup", "spec2ship-analyze", "spec2ship-plan", "spec2ship-approve",
            "spec2ship-work", "spec2ship-review", "spec2ship-verify", "spec2ship-status"]
SKILLS = ["spec2ship-workflow", "ba-analysis", "figma-analysis", "requirement-mapping", "fullstack-planning",
          "implementation-verification", "delivery-report"]
AGENTS = ["ba-analyst", "figma-analyst", "architecture-analyst", "requirement-mapper", "acceptance-reviewer"]


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
        fm, _ = frontmatter(REPO / "commands" / "spec2ship-approve.md")
        self.assertEqual(fm.get("disable-model-invocation"), "true")

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
        self.assertEqual(len(cmds), 2)
        for c in cmds:
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/run-hook.sh", c)
        self.assertTrue((REPO / "scripts" / "run-hook.sh").exists())
        self.assertTrue((REPO / "scripts" / "hook.py").exists())

    def test_bundled_figma_bridge_is_vendored_and_referenced(self):
        servers = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertEqual(list(servers), ["figma-bridge"])
        cfg = servers["figma-bridge"]
        self.assertEqual(cfg["command"], "node", "no npx: nothing is downloaded at runtime")
        self.assertEqual(cfg["args"], ["${CLAUDE_PLUGIN_ROOT}/vendor/figma-bridge/dist/server.mjs"])
        self.assertEqual(cfg["env"]["FIGMA_BRIDGE_PORT"], "3994")
        vendor = REPO / "vendor" / "figma-bridge"
        for f in ("dist/server.mjs", "LICENSE.md", "THIRD_PARTY_LICENSES.md", "UPSTREAM.md", "spec2ship-readonly.patch",
                  "build.sh", "server/src/readonly.ts", "server/package-lock.json", "plugin/manifest.json"):
            self.assertTrue((vendor / f).is_file(), f)
        manifest = json.loads((vendor / "plugin" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["networkAccess"]["allowedDomains"], ["ws://localhost:3994"])
        self.assertIn("read-only", manifest["name"])
        self.assertIn("SPEC2SHIP_READ_ONLY_REQUESTS", (vendor / "plugin" / "src" / "main" / "code.ts").read_text(encoding="utf-8"))
        prefix = "mcp__plugin_spec2ship_figma-bridge__"
        fm, _ = frontmatter(REPO / "agents" / "figma-analyst.md")
        mcp_tools = [t.strip() for t in fm["tools"].split(",") if "mcp__" in t]
        self.assertTrue(mcp_tools and all(t.startswith(prefix) for t in mcp_tools))
        for p in list((REPO / "skills").rglob("*.md")) + list((REPO / "commands").glob("*.md")) + list((REPO / "agents").glob("*.md")):
            text = p.read_text(encoding="utf-8")
            for stale in ("figma-mcp-go", "mcp__figma-mcp-go__", "npx -y @vkhanhqui"):
                self.assertNotIn(stale, text, f"stale reference {stale!r} in {p}")

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
