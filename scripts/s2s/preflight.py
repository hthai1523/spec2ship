"""Preflight checks: runtime, BA extractors, Harness, Figma MCP config, repository state."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import harness_adapter
from .common import PLUGIN_ROOT
from .harness_adapter import claude_config_dir

FIGMA_SERVER = "figma-bridge"  # server name in the plugin's .mcp.json
# Tool-name prefix of the bundled server (Claude Code: mcp__plugin_<plugin>_<server>__<tool>)
BUNDLED_TOOL_PREFIX = f"mcp__plugin_spec2ship_{FIGMA_SERVER}__"
BRIDGE_DIR = PLUGIN_ROOT / "vendor" / "figma-bridge"
BRIDGE_PORT = 3994
NODE_MIN_MAJOR = 20  # figma-mcp-bridge server engines.node >= 20
# Other Figma bridges users may have configured themselves (detected for notices only)
OTHER_FIGMA_MARKERS = ("figma-mcp-go", "figma-mcp-bridge", "figma-bridge")
DMCA_PACKAGE = "@vkhanhqui/figma-mcp-go"


def bundled_figma_server() -> dict[str, Any] | None:
    """The read-only Figma bridge shipped in the plugin (vendor/figma-bridge, started by Claude Code via .mcp.json)."""
    cfg = _servers_from(_load(PLUGIN_ROOT / ".mcp.json")).get(FIGMA_SERVER)
    if not cfg:
        return None
    args = [str(a) for a in cfg.get("args", []) or []]
    script = next((a for a in args if a.endswith(".mjs")), "")
    server_path = Path(script.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT))) if script else None
    manifest = BRIDGE_DIR / "plugin" / "manifest.json"
    plugin_built = all((BRIDGE_DIR / "plugin" / "dist" / f).is_file() for f in ("code.js", "index.html"))
    return {"name": FIGMA_SERVER, "source": f"{PLUGIN_ROOT / '.mcp.json'} (bundled with Spec2Ship)",
            "command": " ".join([str(cfg.get("command", "")), *args]),
            "server_path": str(server_path) if server_path else None,
            "server_exists": bool(server_path and server_path.is_file()),
            "uses_npx": "npx" in str(cfg.get("command", "")),
            "figma_plugin_manifest": str(manifest), "figma_plugin_built": plugin_built,
            "port": BRIDGE_PORT, "tool_prefix": BUNDLED_TOOL_PREFIX}


def node_runtime() -> dict[str, Any]:
    node = shutil.which("node")
    if not node:
        return {"ok": False, "detail": "node not found on PATH"}
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "detail": "node --version failed"}
    m = re.match(r"v(\d+)", out)
    major = int(m.group(1)) if m else 0
    return {"ok": major >= NODE_MIN_MAJOR, "version": out, "detail": f"Node {out}"}


def _servers_from(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("mcpServers") or {}


def _load(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def find_figma_mcp(project_root: Path) -> list[dict[str, Any]]:
    """Return user-configured MCP servers that run another Figma bridge (project .mcp.json, user and local scopes)."""
    found: list[dict[str, Any]] = []
    sources: list[tuple[str, dict[str, Any]]] = []
    # Claude Code also picks up project-scope .mcp.json files from ancestor directories
    # (verified: `claude mcp get` reported ~/.mcp.json as project config for a nested project).
    stop = os.environ.get("SPEC2SHIP_MCP_SEARCH_STOP")  # test isolation: don't look above this dir
    stop_path = Path(stop).resolve() if stop else None
    for d in [project_root.resolve(), *project_root.resolve().parents]:
        f = d / ".mcp.json"
        if f.is_file():
            sources.append((str(f), _servers_from(_load(f))))
        if stop_path is not None and d == stop_path:
            break
    # With CLAUDE_CONFIG_DIR set, Claude Code keeps .claude.json inside it; otherwise it lives in the home dir.
    cj = claude_config_dir() / ".claude.json" if os.environ.get("CLAUDE_CONFIG_DIR") else Path.home() / ".claude.json"
    user = _load(cj)
    sources.append((f"{cj} (user)", _servers_from(user)))
    want = str(project_root.resolve()).replace("\\", "/").lower()
    for key, proj in (user.get("projects") or {}).items():
        if key.replace("\\", "/").lower().rstrip("/") == want.rstrip("/"):
            sources.append((f"{cj} (local: {key})", _servers_from(proj or {})))
    for src, servers in sources:
        for name, cfg in servers.items():
            blob = " ".join([str(cfg.get("command", "")), *map(str, cfg.get("args", []) or []), str(cfg.get("url", ""))])
            if any(mk in blob or mk in name for mk in OTHER_FIGMA_MARKERS):
                found.append({"name": name, "source": src, "command": blob.strip(), "dmca_disabled": DMCA_PACKAGE in blob})
    return found


def _git_state(project_root: Path) -> dict[str, Any]:
    git = shutil.which("git")
    if not git:
        return {"available": False}
    try:
        inside = subprocess.run([git, "rev-parse", "--is-inside-work-tree"], cwd=project_root, capture_output=True, text=True, timeout=20)
        if inside.returncode != 0:
            return {"available": True, "repository": False}
        branch = subprocess.run([git, "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root, capture_output=True, text=True, timeout=20)
        status = subprocess.run([git, "status", "--porcelain"], cwd=project_root, capture_output=True, text=True, timeout=30)
        changed = [l for l in status.stdout.splitlines() if l.strip()]
        return {"available": True, "repository": True, "branch": branch.stdout.strip(), "uncommitted_changes": len(changed),
                "uncommitted_sample": changed[:15]}
    except (OSError, subprocess.TimeoutExpired):
        return {"available": True, "repository": None}


def run(project_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str, fix: str | None = None, blocking: bool = False) -> None:
        checks.append({"name": name, "status": status, "detail": detail, "fix": fix, "blocking": blocking})

    py_ok = sys.version_info >= (3, 9)
    add("python", "ok" if py_ok else "fail", f"Python {sys.version.split()[0]}", "Install Python 3.9+" if not py_ok else None, not py_ok)

    pdftotext = shutil.which("pdftotext")
    try:
        import pypdf  # type: ignore  # noqa: F401
        has_pypdf = True
    except ImportError:
        has_pypdf = False
    if pdftotext or has_pypdf:
        add("pdf-extractor", "ok", "pdftotext" if pdftotext else "pypdf")
    else:
        add("pdf-extractor", "warn", "No pdftotext or pypdf; only the limited built-in PDF extractor is available.",
            "Install poppler-utils (pdftotext) or `pip install pypdf` for reliable PDF extraction (Vietnamese fonts especially).")
    add("docx-extractor", "ok", "built-in (zip/XML, stdlib)")
    add("markdown-extractor", "ok", "built-in")

    h = harness_adapter.detect_harness(project_root)
    if h["compatible"]:
        add("harness", "ok", f"{h['key']} {h['version']} at {h['install_path']}" + (f" — {h['warning']}" if h.get("warning") else ""))
    else:
        add("harness", "fail", "; ".join(h["issues"]),
            "Install Harness: `/plugin marketplace add Chachamaru127/claude-code-harness` then "
            "`/plugin install harness@claude-code-harness-marketplace` (or run scripts/install.ps1 / install.sh), "
            "restart Claude Code, and re-run /spec2ship-setup.",
            blocking=True)
    try:
        add("harness-plans-path", "ok", str(harness_adapter.plans_path(project_root)))
    except Exception as e:  # Spec2ShipError
        add("harness-plans-path", "fail", str(e), "Fix plansDirectory in .claude-code-harness.config.yaml", True)

    bundled = bundled_figma_server()
    others = find_figma_mcp(project_root)
    node = node_runtime()
    if not bundled or not bundled["server_exists"]:
        add("figma-mcp-config", "fail",
            "The bundled read-only Figma bridge is missing" + (f" ({bundled['server_path']})" if bundled else " from .mcp.json") + ".",
            "Reinstall or update Spec2Ship: `/plugin update spec2ship@spec2ship-marketplace`, then restart Claude Code.",
            blocking=True)
    else:
        add("figma-mcp-config", "ok",
            f"bundled read-only Figma bridge (no download): {bundled['command']} — tools {bundled['tool_prefix']}*, "
            f"127.0.0.1:{bundled['port']}")
        if node["ok"]:
            add("node-runtime", "ok", node["detail"])
        else:
            add("node-runtime", "fail", f"{node['detail']} — the bundled Figma bridge runs on Node.js {NODE_MIN_MAJOR}+.",
                f"Install Node.js {NODE_MIN_MAJOR}+ (https://nodejs.org, or `winget install OpenJS.NodeJS.LTS` / "
                "`brew install node`) and restart Claude Code.", blocking=True)
        if bundled["figma_plugin_built"]:
            add("figma-plugin", "ok", f"Figma plugin to import: {bundled['figma_plugin_manifest']}")
        else:
            add("figma-plugin", "fail", "The read-only Figma plugin build (vendor/figma-bridge/plugin/dist) is missing.",
                "Update Spec2Ship, or (maintainers) run `bash vendor/figma-bridge/build.sh plugin`.")
    for o in others:
        if o["dmca_disabled"]:
            add("figma-other-server", "warn",
                f"You configured '{o['name']}' ({o['source']}) with {DMCA_PACKAGE}; its GitHub repository was disabled "
                "after a DMCA notice. Spec2Ship does not use it.",
                f"Remove it unless you need it: `claude mcp remove {o['name']}`.")
        else:
            add("figma-other-server", "ok",
                f"You also configured '{o['name']}' ({o['source']}). It runs separately (port 1994); Spec2Ship only uses "
                f"its own read-only bridge on port {BRIDGE_PORT}.")
    manifest = bundled["figma_plugin_manifest"] if bundled else "vendor/figma-bridge/plugin/manifest.json"
    add("figma-bridge", "pending",
        "Once per machine, in Figma Desktop: Plugins → Development → Import plugin from manifest → "
        f"{manifest}. Then open the design file and run 'Spec2Ship Figma Bridge (read-only)'. "
        "Check by calling `get_metadata`; 'No plugin connected' means it is not running.")

    g = _git_state(project_root)
    if g.get("repository"):
        detail = f"branch {g['branch']}, {g['uncommitted_changes']} uncommitted change(s)"
        add("git", "warn" if g["uncommitted_changes"] else "ok", detail,
            "Uncommitted user changes will be preserved; consider committing or stashing before Harness Work." if g["uncommitted_changes"] else None)
    elif g.get("available"):
        add("git", "warn", "Project is not a Git repository; Harness commit/review features may be limited.", "git init (optional)")
    else:
        add("git", "warn", "git not found on PATH.")

    blocking = [c for c in checks if c["blocking"] and c["status"] == "fail"]
    return {"ok": not blocking, "checks": checks, "harness": h, "figma_servers": ([bundled] if bundled else []) + others, "git": g}


def to_text(res: dict[str, Any]) -> str:
    icon = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL", "pending": "TODO"}
    lines = ["Spec2Ship preflight", ""]
    for c in res["checks"]:
        lines.append(f"[{icon.get(c['status'], c['status'])}] {c['name']}: {c['detail']}")
        if c.get("fix") and c["status"] != "ok":
            lines.append(f"       fix: {c['fix']}")
    lines.append("")
    lines.append("RESULT: " + ("ready (complete the Figma bridge check via MCP)" if res["ok"] else "BLOCKED — fix the FAIL items above"))
    return "\n".join(lines)
