#!/usr/bin/env python3
"""Spec2Ship Claude Code hook handler.

Modes (argv[1]):
  pretool  - PreToolUse: blocks Harness execution skills when the Spec2Ship plan
             in Plans.md is unapproved or drifted; blocks the model from forging
             the developer's approval intent.
  prompt   - UserPromptSubmit: records the developer's /spec2ship-approve intent;
             blocks /harness-work etc. under the same conditions as `pretool`.

Hooks fail open on internal errors (never break the user's session) but print
a warning to stderr.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from s2s import harness_adapter  # noqa: E402
from s2s.common import now_iso, workspace_path, write_json  # noqa: E402

APPROVAL_ONLY = "Spec2Ship: only the developer can record plan approval (type /spec2ship:spec2ship-approve <hash>)."
APPROVE_PROMPT = re.compile(r"^\s*/(?:spec2ship:)?spec2ship-approve\b")
EXEC_PROMPT = re.compile(r"^\s*/(?:(?:claude-code-harness|harness):)?(?:%s)\b" % "|".join(harness_adapter.EXEC_SKILLS))


def _ws(data):
    from pathlib import Path

    root = Path(data.get("cwd") or os.getcwd())
    return root, workspace_path(root)


def _guard(data):
    from s2s.cli import guard_check

    root, ws = _ws(data)
    return guard_check(root, ws)


def _deny_pretool(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def pretool(data):
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        path = str(ti.get("file_path") or ti.get("notebook_path") or "").replace("\\", "/")
        if path.endswith("/.approval-intent.json"):
            _deny_pretool(APPROVAL_ONLY)
        elif re.search(r"/\.spec2ship/(state|run)\.json$", path):
            _deny_pretool("Spec2Ship: state.json/run.json are managed by the spec2ship CLI (approval, transitions). "
                          "Do not edit them directly; use the CLI commands.")
        return
    if tool in ("Bash", "PowerShell"):
        cmd = str(ti.get("command", ""))
        if ".approval-intent" in cmd:
            _deny_pretool(APPROVAL_ONLY)
        elif re.search(r"\.spec2ship[/\\](state|run)\.json", cmd) and re.search(
                r"(>|\btee\b|\bsed\s+-i|Set-Content|Out-File|\bmv\b|\bcp\b|Move-Item|Copy-Item|\.write|json\.dump|open\([^)]*['\"][wa])", cmd):
            _deny_pretool("Spec2Ship: state.json/run.json are managed by the spec2ship CLI; do not modify them directly.")
        return
    if tool == "Skill":
        name = str(ti.get("skill", "")).split(":")[-1]
        if name == "spec2ship-approve":
            _deny_pretool(APPROVAL_ONLY)
            return
        if name in harness_adapter.EXEC_SKILLS:
            ok, msg = _guard(data)
            if not ok:
                _deny_pretool(msg)


def prompt(data):
    text = data.get("prompt", "") or ""
    if APPROVE_PROMPT.match(text):
        root, ws = _ws(data)
        if (ws / "state.json").exists():
            write_json(ws / ".approval-intent.json", {"at": now_iso(), "prompt": text.strip()[:200]})
        return
    if EXEC_PROMPT.match(text):
        ok, msg = _guard(data)
        if not ok:
            print(json.dumps({"decision": "block", "reason": msg}))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if mode == "pretool":
            pretool(data)
        elif mode == "prompt":
            prompt(data)
    except Exception as e:  # fail open, but say so
        print(f"spec2ship hook warning: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
