"""Workflow state machine persisted in <workspace>/state.json."""
from __future__ import annotations

import os
import secrets
import datetime as _dt
from pathlib import Path
from typing import Any

from .common import Spec2ShipError, now_iso, read_json, write_json

STATES = (
    "INIT", "PREFLIGHT", "ANALYSIS", "REQUIREMENT_REVIEW", "PLANNING", "PLAN_REVIEW",
    "APPROVED", "EXECUTION", "REVIEW", "VERIFICATION", "BLOCKED", "COMPLETED",
)

# Allowed manual transitions. APPROVED is reachable only through approve().
TRANSITIONS: dict[str, set[str]] = {
    "INIT": {"PREFLIGHT"},
    "PREFLIGHT": {"ANALYSIS", "BLOCKED"},
    "ANALYSIS": {"REQUIREMENT_REVIEW", "BLOCKED"},
    "REQUIREMENT_REVIEW": {"PLANNING", "ANALYSIS", "BLOCKED"},
    "PLANNING": {"PLAN_REVIEW", "ANALYSIS", "BLOCKED"},
    "PLAN_REVIEW": {"PLANNING"},
    "APPROVED": {"EXECUTION", "PLANNING"},
    "EXECUTION": {"REVIEW", "PLANNING", "BLOCKED"},
    "REVIEW": {"VERIFICATION", "EXECUTION", "BLOCKED"},
    "VERIFICATION": {"COMPLETED", "EXECUTION", "BLOCKED"},
    "BLOCKED": set(),  # resolved via unblock()
    "COMPLETED": set(),
}

APPROVAL_REQUIRED = {"APPROVED", "EXECUTION", "REVIEW", "VERIFICATION", "COMPLETED"}
DEFAULT_MAX_RETRIES = 3


def new_run_id() -> str:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"s2s-{stamp}-{secrets.token_hex(3)}"


def state_path(ws: Path) -> Path:
    return ws / "state.json"


def load(ws: Path) -> dict[str, Any]:
    p = state_path(ws)
    if not p.exists():
        raise Spec2ShipError(f"No Spec2Ship run found at {ws}. Start one with /spec2ship [<figma-url>] [--ba <path>] [instructions].")
    return read_json(p)


def save(ws: Path, st: dict[str, Any]) -> None:
    write_json(state_path(ws), st)


def create(ws: Path, inputs: dict[str, Any]) -> dict[str, Any]:
    st = {
        "schema_version": "1.0",
        "run_id": new_run_id(),
        "state": "INIT",
        "blocked_from": None,
        "history": [{"from": None, "to": "INIT", "at": now_iso(), "reason": "run created"}],
        "inputs": inputs,
        "preflight": None,
        "figma_check": None,
        "approval": None,
        "harness": None,
        "retries": {"verification": 0, "max": int(os.environ.get("SPEC2SHIP_MAX_RETRIES", DEFAULT_MAX_RETRIES))},
        "blockers": [],
    }
    save(ws, st)
    return st


def _record(st: dict[str, Any], to: str, reason: str) -> None:
    st["history"].append({"from": st["state"], "to": to, "at": now_iso(), "reason": reason})
    st["state"] = to


def transition(st: dict[str, Any], to: str, reason: str = "") -> dict[str, Any]:
    to = to.upper()
    if to not in STATES:
        raise Spec2ShipError(f"Unknown state {to}. Valid: {', '.join(STATES)}")
    cur = st["state"]
    if to == "APPROVED":
        raise Spec2ShipError("APPROVED can only be reached through explicit developer approval (/spec2ship:spec2ship-approve).")
    if to not in TRANSITIONS[cur]:
        allowed = ", ".join(sorted(TRANSITIONS[cur])) or "(none)"
        raise Spec2ShipError(f"Illegal transition {cur} -> {to}. Allowed from {cur}: {allowed}")
    if to in APPROVAL_REQUIRED and not st.get("approval"):
        raise Spec2ShipError(f"Cannot enter {to} without an approved plan.")
    if cur == "VERIFICATION" and to == "EXECUTION":
        st["retries"]["verification"] = st["retries"].get("verification", 0) + 1
        if st["retries"]["verification"] > st["retries"].get("max", DEFAULT_MAX_RETRIES):
            raise Spec2ShipError(
                f"Retry limit ({st['retries'].get('max')}) reached for verification fixes. Mark the run BLOCKED and ask the developer."
            )
    if to == "PLANNING" and st.get("approval"):
        st["approval"] = None  # scope change: requires re-approval
        reason = (reason + "; " if reason else "") + "previous approval revoked (plan must be re-approved)"
    if to == "BLOCKED":
        st["blocked_from"] = cur
        if reason:
            st["blockers"].append(reason)
    _record(st, to, reason)
    return st


def unblock(st: dict[str, Any], reason: str = "") -> dict[str, Any]:
    if st["state"] != "BLOCKED":
        raise Spec2ShipError("Run is not BLOCKED.")
    back = st.get("blocked_from") or "PREFLIGHT"
    if back in APPROVAL_REQUIRED and not st.get("approval"):
        back = "PLANNING"
    st["blocked_from"] = None
    st["blockers"] = []
    _record(st, back, reason or "unblocked")
    return st


def mark_approved(st: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    if st["state"] != "PLAN_REVIEW":
        raise Spec2ShipError(f"Plan can only be approved in PLAN_REVIEW (current: {st['state']}). Run /spec2ship-plan first.")
    st["approval"] = approval
    _record(st, "APPROVED", f"approved by {approval.get('approver')}")
    return st
