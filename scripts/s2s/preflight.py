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

FIGMA_PACKAGE = "@vkhanhqui/figma-mcp-go"
FIGMA_MARKER = "figma-mcp-go"
# Tool-name prefix of the server bundled in this plugin's .mcp.json (Claude Code: mcp__plugin_<plugin>_<server>__<tool>)
BUNDLED_TOOL_PREFIX = "mcp__plugin_spec2ship_figma-mcp-go__"
NODE_MIN_MAJOR = 18  # figma-mcp-go package.json engines.node >= 18


def bundled_figma_server() -> dict[str, Any] | None:
    """The figma-mcp-go server shipped in the plugin's own .mcp.json (started by Claude Code with the plugin)."""
    cfg = _servers_from(_load(PLUGIN_ROOT / ".mcp.json")).get(FIGMA_MARKER)
    if not cfg:
        return None
    blob = " ".join([str(cfg.get("command", "")), *map(str, cfg.get("args", []) or [])])
    m = re.search(r"figma-mcp-go@([\w.\-]+)", blob)
    version = m.group(1) if m else None
    return {"name": FIGMA_MARKER, "source": f"{PLUGIN_ROOT / '.mcp.json'} (bundled with Spec2Ship)", "command": blob,
            "package_version": version, "pinned": bool(version and version != "latest"),
            "tool_prefix": BUNDLED_TOOL_PREFIX}


def node_runtime() -> dict[str, Any]:
    node, npx = shutil.which("node"), shutil.which("npx")
    if not node or not npx:
        return {"ok": False, "detail": f"node={'found' if node else 'missing'}, npx={'found' if npx else 'missing'}"}
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return {"ok": False, "detail": "node --version failed"}
    m = re.match(r"v(\d+)", out)
    major = int(m.group(1)) if m else 0
    return {"ok": major >= NODE_MIN_MAJOR, "version": out, "detail": f"Node {out}, npx found"}


def _servers_from(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("mcpServers") or {}


def _load(p: Path) -> dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def find_figma_mcp(project_root: Path) -> list[dict[str, Any]]:
    """Return configured MCP servers that run figma-mcp-go (project .mcp.json, user and local scopes)."""
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
            if FIGMA_MARKER in blob or FIGMA_MARKER in name:
                m = re.search(r"figma-mcp-go@([\w.\-]+)", blob)
                version = m.group(1) if m else None
                found.append({
                    "name": name,
                    "source": src,
                    "command": blob.strip(),
                    "package_version": version,
                    "pinned": bool(version and version != "latest"),
                })
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
    user_figma = find_figma_mcp(project_root)
    figma = ([bundled] if bundled else []) + user_figma
    node = node_runtime()
    if bundled:
        add("figma-mcp-config", "ok" if bundled["pinned"] else "warn",
            f"bundled with Spec2Ship: {bundled['command']} (tools {bundled['tool_prefix']}*)",
            None if bundled["pinned"] else "Bundled server should be pinned to a tested version.")
        if user_figma:
            add("figma-mcp-duplicate", "ok",
                f"You also configured '{user_figma[0]['name']}' ({user_figma[0]['source']}). Both can run: figma-mcp-go "
                "elects one leader on 127.0.0.1:1994 and other instances act as followers. You may remove your own entry.")
        if node["ok"]:
            add("node-runtime", "ok", node["detail"])
        else:
            add("node-runtime", "fail", f"{node['detail']} — the bundled figma-mcp-go server is started with npx.",
                f"Install Node.js {NODE_MIN_MAJOR}+ (https://nodejs.org) and restart Claude Code.", blocking=True)
    elif not user_figma:
        add("figma-mcp-config", "fail", "No MCP server running figma-mcp-go is configured for this project.",
            f"Reinstall Spec2Ship (it bundles the server) or add it: `claude mcp add figma-mcp-go -s project -- npx -y {FIGMA_PACKAGE}@<version>`.",
            blocking=True)
    else:
        f0 = user_figma[0]
        add("figma-mcp-config", "ok" if f0["pinned"] else "warn", f"'{f0['name']}' from {f0['source']}: {f0['command']}",
            None if f0["pinned"] else f"Pin the package version (e.g. {FIGMA_PACKAGE}@<tested-version>) instead of an unpinned/@latest npx install.")
    add("figma-bridge", "pending",
        "Still required once per machine: in Figma Desktop import the figma-mcp-go plugin (Plugins → Development → "
        "Import plugin from manifest, plugin.zip from github.com/vkhanhqui/figma-mcp-go/releases) and run it in the "
        "design file. Check by calling `get_metadata`; 'plugin not connected' means it is not running.")

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
    return {"ok": not blocking, "checks": checks, "harness": h, "figma_servers": figma, "git": g}


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
