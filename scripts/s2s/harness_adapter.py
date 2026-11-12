"""Thin adapter around Chachamaru127/claude-code-harness.

Everything Spec2Ship knows about Harness lives in this module so upstream
changes are handled in one place. Verified against claude-code-harness 4.12.11:

* Plans.md task ledger, v2 5-column table:
  ``| Task | 内容 | DoD | Depends | Status |`` with markers ``cc:TODO``,
  ``cc:WIP``, ``cc:完了`` (optionally ``cc:完了 [hash]``), ``blocked``,
  ``pm:依頼中``, ``pm:確認済``.
* Phase headings ``## Phase N: <name>`` with optional ``Purpose:`` line.
* Plans.md location: project root, overridable with ``plansDirectory`` in
  ``.claude-code-harness.config.yaml``.
* Execution entry points (skills): ``/harness-work [all|<task>]``,
  ``/breezing``, ``/harness-loop``, ``/harness-review``, ``/harness-sync``.

Spec2Ship never executes tasks itself. It only writes an approved, marked
section into the Harness ledger and reads task markers back.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .common import Spec2ShipError, now_iso, sha256_text, today, write_text

TESTED_VERSIONS = ["4.12.11"]
MIN_VERSION = (4, 0, 0)
PLUGIN_NAME = "harness"  # current upstream name (renamed from "claude-code-harness" in the 5.x line)
PLUGIN_NAMES = ("harness", "claude-code-harness")  # accepted names, newest first
HEADER = "| Task | 内容 | DoD | Depends | Status |"
SEPARATOR = "|------|------|-----|---------|--------|"
DONE_MARKERS = ("cc:完了", "pm:確認済")
EXEC_SKILLS = ("harness-work", "breezing", "harness-loop")

_BEGIN_RE = re.compile(r"^<!-- spec2ship:begin run=(?P<run>[\w-]+) plan=(?P<plan>[0-9a-f]+) -->\s*$", re.M)
_END_TMPL = "<!-- spec2ship:end run={run} -->"


# --------------------------------------------------------------------- detection

def claude_config_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def _parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(x) for x in nums[:3]) if nums else (0,)


def _enabled_state(key: str, project_root: Path | None) -> bool | None:
    files = [claude_config_dir() / "settings.json"]
    if project_root:
        files += [project_root / ".claude" / "settings.json", project_root / ".claude" / "settings.local.json"]
    state = None
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ep = data.get("enabledPlugins") or {}
        if key in ep:
            state = bool(ep[key])
    return state


def detect_harness(project_root: Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"installed": False, "compatible": False, "issues": [], "tested_versions": TESTED_VERSIONS}
    ip = claude_config_dir() / "plugins" / "installed_plugins.json"
    try:
        data = json.loads(ip.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        result["issues"].append(f"Cannot read {ip}; is Claude Code's plugin system initialized?")
        return result
    entries = []
    for key, installs in (data.get("plugins") or {}).items():
        if key.split("@", 1)[0] in PLUGIN_NAMES:
            for inst in installs if isinstance(installs, list) else [installs]:
                entries.append((key, inst))
    if not entries:
        result["issues"].append("Harness (plugin `harness`, formerly `claude-code-harness`) is not installed.")
        return result
    key, inst = sorted(entries, key=lambda e: _parse_version(e[1].get("version", "")))[-1]
    path = Path(inst.get("installPath", ""))
    version = inst.get("version", "")
    result.update({"installed": True, "key": key, "version": version, "install_path": str(path), "scope": inst.get("scope")})
    required = [path / "skills" / s / "SKILL.md" for s in ("harness-plan", "harness-work", "harness-review", "harness-sync")]
    missing = [str(p.relative_to(path)) for p in required if not p.exists()]
    if missing:
        result["issues"].append(f"Harness install is missing expected skills: {', '.join(missing)}")
    if _parse_version(version) < MIN_VERSION:
        result["issues"].append(f"Harness {version} is older than the minimum supported 4.0.0.")
    elif version not in TESTED_VERSIONS:
        result["warning"] = f"Harness {version} is not in the tested list {TESTED_VERSIONS}; Plans.md format will be re-checked."
    enabled = _enabled_state(key, project_root)
    result["enabled"] = enabled
    if enabled is False:
        result["issues"].append(f"{key} is installed but disabled (enabledPlugins).")
    result["compatible"] = not result["issues"]
    return result


def plans_path(project_root: Path) -> Path:
    cfg = project_root / ".claude-code-harness.config.yaml"
    directory = "."
    if cfg.exists():
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^\s*plansDirectory\s*:\s*['\"]?([^'\"#]+?)['\"]?\s*(#.*)?$", line)
            if m:
                directory = m.group(1).strip() or "."
                break
    target = (project_root / directory).resolve()
    root = project_root.resolve()
    if root != target and root not in target.parents:
        raise Spec2ShipError(f"plansDirectory '{directory}' points outside the project; refusing to write there.")
    return target / "Plans.md"


# ---------------------------------------------------------------------- rendering

def _cell(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).replace("|", "\\|").strip()


def task_content(t: dict[str, Any]) -> str:
    parts = [t["title"]]
    if t["requirement_ids"]:
        parts.append("[" + ", ".join(t["requirement_ids"]) + "]")
    if t.get("files"):
        parts.append("files: " + ", ".join(t["files"]))
    if t.get("risk"):
        parts.append(f"[risk:{t['risk']}]")
    parts.extend(f"[{tag}]" for tag in t.get("tags", []))
    return " ".join(parts)


def renumber(tasks: dict[str, Any], offset: int) -> tuple[dict[str, Any], dict[str, str]]:
    """Shift phase numbers by offset so they don't collide with existing Harness phases."""
    mapping: dict[str, str] = {}
    for ph in tasks["phases"]:
        for t in ph["tasks"]:
            p, n = t["id"].split(".")
            mapping[t["id"]] = f"{int(p) + offset}.{n}"
    out = json.loads(json.dumps(tasks))
    for ph in out["phases"]:
        ph["number"] += offset
        for t in ph["tasks"]:
            t["id"] = mapping[t["id"]]
            t["depends"] = [mapping[d] for d in t["depends"]]
    return out, mapping


def render_section(tasks: dict[str, Any], run_id: str, plan_hash: str, spec_rel: str | None = None,
                   statuses: dict[str, str] | None = None) -> str:
    statuses = statuses or {}
    lines = [f"<!-- spec2ship:begin run={run_id} plan={plan_hash[:12]} -->"]
    for ph in tasks["phases"]:
        lines.append(f"## Phase {ph['number']}: {ph['title']} (Spec2Ship)")
        lines.append("")
        if ph.get("purpose"):
            lines.append(f"Purpose: {_cell(ph['purpose'])}")
            lines.append("")
        if spec_rel:
            lines.append(f"Spec: `{spec_rel}` (approved Spec2Ship sub-spec; requirement IDs trace to it)")
            lines.append("")
        lines.append(HEADER)
        lines.append(SEPARATOR)
        for t in ph["tasks"]:
            deps = ", ".join(t["depends"]) if t["depends"] else "-"
            status = statuses.get(t["id"], "cc:TODO")
            lines.append(f"| {t['id']} | {_cell(task_content(t))} | {_cell(t['dod'])} | {deps} | {status} |")
        lines.append("")
    lines.append(_END_TMPL.format(run=run_id))
    return "\n".join(lines) + "\n"


def render_standalone(tasks: dict[str, Any], run_id: str, plan_hash: str, spec_rel: str | None = None) -> str:
    head = f"# {tasks['project']} Plans.md\n\n作成日: {today()}\n\n---\n\n"
    return head + render_section(tasks, run_id, plan_hash, spec_rel)


# ------------------------------------------------------------------------ parsing

_ROW_RE = re.compile(r"^\|\s*(\d+\.\d+[\w-]*)\s*\|(.*)\|\s*$")


def _split_row(rest: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", rest)]


def parse_rows(text: str) -> list[dict[str, str]]:
    rows = []
    for line in text.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        cells = _split_row(m.group(2))
        if len(cells) >= 4:
            rows.append({"task": m.group(1), "content": cells[0], "dod": cells[1], "depends": cells[2], "status": cells[3]})
    return rows


def max_phase_number(text: str) -> int:
    nums = [int(x) for x in re.findall(r"^#{2,4}\s+Phase\s+(\d+)", text, re.M)]
    nums += [int(r["task"].split(".")[0]) for r in parse_rows(text)]
    return max(nums, default=0)


def find_section(text: str, run_id: str | None = None) -> tuple[int, int, str, str] | None:
    for m in _BEGIN_RE.finditer(text):
        if run_id and m.group("run") != run_id:
            continue
        end_marker = _END_TMPL.format(run=m.group("run"))
        end = text.find(end_marker, m.end())
        if end == -1:
            raise Spec2ShipError(f"Plans.md has a spec2ship:begin marker for {m.group('run')} without a matching end marker.")
        end += len(end_marker)
        if end < len(text) and text[end] == "\n":
            end += 1
        return m.start(), end, m.group("run"), m.group("plan")
    return None


def scope_hash(section_text: str) -> str:
    """Hash of task scope (id, content, DoD, depends) ignoring status markers Harness updates."""
    rows = parse_rows(section_text)
    canon = "\n".join(f"{r['task']}|{r['content']}|{r['dod']}|{r['depends']}" for r in rows)
    return sha256_text(canon)


def read_statuses(project_root: Path, run_id: str) -> dict[str, str]:
    p = plans_path(project_root)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    sec = find_section(text, run_id)
    if not sec:
        return {}
    return {r["task"]: r["status"] for r in parse_rows(text[sec[0]:sec[1]])}


def is_done(status: str) -> bool:
    return any(status.startswith(m) for m in DONE_MARKERS)


# ------------------------------------------------------------------------ handoff

def handoff(project_root: Path, ws: Path, tasks: dict[str, Any], run_id: str, plan_hash: str,
            spec_rel: str | None, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write the approved plan into the Harness Plans.md ledger, preserving all other content."""
    target = plans_path(project_root)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    sec = find_section(existing, run_id) if existing else None
    if sec:
        current_rows = parse_rows(existing[sec[0]:sec[1]])
        started = [r["task"] for r in current_rows if r["status"] != "cc:TODO"]
        if started:
            raise Spec2ShipError(
                "Harness already started tasks from this run ("
                + ", ".join(started)
                + "). Reconcile Plans.md manually; Spec2Ship will not overwrite task progress."
            )
        offset = (previous or {}).get("phase_offset", 0)
        without = existing[: sec[0]] + existing[sec[1]:]
    else:
        offset = max_phase_number(existing) if existing else 0
        without = existing
    shifted, mapping = renumber(tasks, offset)
    section = render_section(shifted, run_id, plan_hash, spec_rel)
    backup = None
    if existing:
        backup_dir = ws / "execution"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"Plans.md.bak-{now_iso().replace(':', '').replace('+', 'Z')[:17]}"
        shutil.copy2(target, backup)
        if sec:
            new_text = existing[: sec[0]] + section + existing[sec[1]:]
        else:
            sep = "" if without.endswith("\n\n") else ("\n" if without.endswith("\n") else "\n\n")
            new_text = without + sep + section
    else:
        new_text = f"# {tasks['project']} Plans.md\n\n作成日: {today()}\n\n---\n\n" + section
    write_text(target, new_text)
    return {
        "plans_path": str(target),
        "backup": str(backup) if backup else None,
        "phase_offset": offset,
        "task_map": mapping,
        "scope_hash": scope_hash(section),
        "handoff_at": now_iso(),
        "next_commands": ["/harness-work all", "/breezing all"],
    }


def drift(project_root: Path, run_id: str, recorded_scope_hash: str) -> dict[str, Any]:
    target = plans_path(project_root)
    if not target.exists():
        return {"status": "missing", "detail": f"{target} not found"}
    text = target.read_text(encoding="utf-8")
    sec = find_section(text, run_id)
    if not sec:
        return {"status": "missing", "detail": "Spec2Ship section not found in Plans.md"}
    h = scope_hash(text[sec[0]:sec[1]])
    if h != recorded_scope_hash:
        return {"status": "changed", "detail": "Task scope in Plans.md differs from the approved plan (status changes are ignored)."}
    return {"status": "ok"}
