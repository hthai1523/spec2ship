"""spec2ship CLI: deterministic workflow operations used by the plugin's commands."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from . import __version__, artifacts, ba_parser, docs_render, figma, harness_adapter, preflight, repo_analyzer, state
from .common import (
    WORKSPACE_DIRS, Spec2ShipError, canonical_json, now_iso, read_json, sha256_file, sha256_text,
    workspace_path, write_json, write_text,
)

INTENT_FILE = ".approval-intent.json"
INTENT_MAX_AGE_MIN = 30


# ------------------------------------------------------------------------ helpers

def _ctx(args: argparse.Namespace) -> tuple[Path, Path]:
    root = Path(args.project_root).resolve()
    return root, workspace_path(root, args.workspace)


def _out(args: argparse.Namespace, data: Any, text: str | None = None) -> None:
    if getattr(args, "json", False) or text is None:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(text)


def _strip_status(reqs: dict[str, Any]) -> dict[str, Any]:
    c = json.loads(json.dumps(reqs))
    c.pop("generated_at", None)
    for r in c.get("requirements", []):
        # progress statuses don't change scope; deferring/rejecting a requirement does
        if r.get("status") not in artifacts.OUT_OF_SCOPE:
            r.pop("status", None)
    return c


def plan_hash(ws: Path) -> str:
    parts = []
    for rel, kind in (("analysis/requirements.json", "req"), ("mappings/figma-mapping.json", "json"),
                      ("planning/tasks.json", "json"), ("planning/spec.md", "text")):
        p = ws / rel
        if not p.exists():
            parts.append(f"{rel}:missing")
        elif kind == "req":
            parts.append(rel + ":" + canonical_json(_strip_status(read_json(p))))
        elif kind == "json":
            parts.append(rel + ":" + canonical_json(read_json(p)))
        else:
            parts.append(rel + ":" + p.read_text(encoding="utf-8").replace("\r\n", "\n"))
    return sha256_text("\n".join(parts))


def _project_name(ws: Path, root: Path) -> str:
    t = ws / "planning" / "tasks.json"
    if t.exists():
        try:
            return read_json(t).get("project") or root.name
        except Spec2ShipError:
            pass
    return root.name


# ---------------------------------------------------------------------- commands

def cmd_init(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    url_info = figma.parse_figma_url(args.figma)
    bas = []
    for b in args.ba:
        p = Path(b)
        p = p if p.is_absolute() else (root / p)
        p = p.resolve()
        if not p.exists():
            raise Spec2ShipError(f"BA document not found: {b}")
        if p.suffix.lower() not in ba_parser.SUPPORTED:
            raise Spec2ShipError(f"Unsupported BA format '{p.suffix}' for {b}. Supported: .pdf, .docx, .md")
        try:
            shown = p.relative_to(root).as_posix()
        except ValueError:
            shown = str(p)
        bas.append({"path": shown, "abs_path": str(p), "sha256": sha256_file(p), "format": ba_parser.SUPPORTED[p.suffix.lower()]})
    if (ws / "state.json").exists():
        if not args.force_new:
            st = state.load(ws)
            raise Spec2ShipError(
                f"A Spec2Ship run already exists ({st['run_id']}, state {st['state']}). Use /spec2ship-status to resume, "
                "or pass --force-new to archive it and start over."
            )
        old = state.load(ws)
        archive = ws / "archive" / old["run_id"]
        archive.mkdir(parents=True, exist_ok=True)
        for item in list(ws.iterdir()):
            if item.name == "archive":
                continue
            shutil.move(str(item), str(archive / item.name))
    for d in WORKSPACE_DIRS:
        (ws / d).mkdir(parents=True, exist_ok=True)
    inputs = {"figma": url_info, "ba": bas, "instructions": args.instructions or "", "project_root": str(root)}
    st = state.create(ws, inputs)
    write_json(ws / "run.json", {"run_id": st["run_id"], "created_at": now_iso(), "inputs": inputs,
                                 "workspace": str(ws), "spec2ship_version": __version__})
    gi = root / ".gitignore"
    rel_ws = os.path.relpath(ws, root).replace("\\", "/")
    ignored = gi.exists() and any(l.strip().rstrip("/") in (rel_ws, "/" + rel_ws) for l in gi.read_text(encoding="utf-8", errors="replace").splitlines())
    res = {"run_id": st["run_id"], "workspace": str(ws), "figma": url_info, "ba": [b["path"] for b in bas], "state": st["state"],
           "gitignore_hint": None if ignored else f"Spec2Ship does not edit .gitignore. Add '{rel_ws}/' to keep intermediate artifacts out of Git, or commit planning/ and reports/ deliberately."}
    _out(args, res)
    return 0


def cmd_preflight(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    res = preflight.run(root)
    if (ws / "state.json").exists() and not args.no_record:
        st = state.load(ws)
        st["preflight"] = {"at": now_iso(), "ok": res["ok"], "checks": res["checks"]}
        if st["state"] == "INIT":
            state.transition(st, "PREFLIGHT", "preflight run")
        if st["state"] == "PREFLIGHT" and not res["ok"]:
            state.transition(st, "BLOCKED", "preflight failed: " + "; ".join(c["name"] for c in res["checks"] if c["blocking"] and c["status"] == "fail"))
        state.save(ws, st)
        res["state"] = st["state"]
    _out(args, res, preflight.to_text(res))
    return 0 if res["ok"] else 2


def cmd_figma_check(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    url_info = st["inputs"]["figma"]
    rec: dict[str, Any] = {"at": now_iso()}
    if args.error:
        rec.update({"ready": False, "error": args.error,
                    "fix": "Open Figma Desktop, open the referenced file, run 'Spec2Ship Figma Bridge (read-only)' (Plugins → Development), then retry."})
    else:
        m = figma.match_open_file(url_info, args.open_file_name, args.open_file_key)
        if args.user_confirmed:
            m = {"match": "user_confirmed", "reason": "Developer confirmed the open file is the referenced design."}
        rec.update({"ready": True, "open_file_name": args.open_file_name, "open_file_key": args.open_file_key, **m})
        if url_info.get("node_id"):
            rec["node_id"] = url_info["node_id"]
            rec["node_found"] = {"yes": True, "no": False}.get(args.node_found or "", None)
    st["figma_check"] = rec
    state.save(ws, st)
    _out(args, rec)
    return 0 if rec.get("ready") else 2


def cmd_parse_ba(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    docs, problems = [], []
    for b in st["inputs"]["ba"]:
        p = Path(b["abs_path"])
        if p.exists() and sha256_file(p) != b["sha256"]:
            problems.append(f"{b['path']} changed since the run started; requirements must be re-extracted")
            b["sha256"] = sha256_file(p)
        ir = ba_parser.parse_document(p)
        docs.append(ir)
    write_json(ws / "analysis" / "ba-normalized.json", {"schema_version": "1.0", "generated_at": now_iso(), "documents": docs})
    ocr = [d["document"] for d in docs if d["ocr_required"]]
    summary = {
        "documents": [{"document": d["document"], "format": d["format"], "language": d["language"], "pages": d.get("pages"),
                       "extractor": d["extractor"], "blocks": d["stats"]["blocks"], "ocr_required": d["ocr_required"],
                       "warnings": d["warnings"]} for d in docs],
        "output": str(ws / "analysis" / "ba-normalized.json"),
        "problems": problems,
    }
    if st["state"] == "PREFLIGHT":
        if ocr:
            state.transition(st, "BLOCKED", f"OCR required for: {', '.join(ocr)}")
        else:
            state.transition(st, "ANALYSIS", "BA parsed")
    state.save(ws, st)
    summary["state"] = st["state"]
    _out(args, summary)
    return 3 if ocr else 0


def cmd_repo_analyze(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    target = Path(args.root).resolve() if args.root else root
    a = repo_analyzer.analyze(target)
    write_json(ws / "analysis" / "repository-analysis.json", a)
    write_text(ws / "analysis" / "repository-analysis.md", repo_analyzer.to_markdown(a))
    _out(args, {"output": str(ws / "analysis" / "repository-analysis.md"), "frameworks": a["frameworks"],
                "languages": a["languages"], "commands": a["commands"], "package_managers": a["package_managers"],
                "notes": a["notes"]})
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    rep = artifacts.validate_workspace(ws, args.stage)
    lines = [f"ERROR   {e}" for e in rep.errors] + [f"WARNING {w}" for w in rep.warnings]
    lines.append("VALID" if rep.ok else f"INVALID ({len(rep.errors)} error(s))")
    _out(args, rep.as_dict(), "\n".join(lines))
    return 0 if rep.ok else 1


def _render_spec(ws: Path, root: Path, st: dict[str, Any]) -> dict[str, Any]:
    reqs = read_json(ws / "analysis" / "requirements.json")
    text = docs_render.render_spec(reqs, _project_name(ws, root))
    target = ws / "planning" / "spec.md"
    gen = st.setdefault("generated", {})
    if target.exists() and gen.get("spec_sha") and sha256_file(target) != gen["spec_sha"]:
        alt = ws / "planning" / "spec.generated.md"
        write_text(alt, text)
        return {"spec": str(target), "preserved_user_edits": True, "regenerated_copy": str(alt)}
    write_text(target, text)
    gen["spec_sha"] = sha256_file(target)
    return {"spec": str(target), "preserved_user_edits": False}


def _harness_statuses(root: Path, st: dict[str, Any]) -> dict[str, str]:
    if not st.get("harness"):
        return {}
    return harness_adapter.read_statuses(root, st["run_id"])


def _build_rtm(ws: Path, root: Path, st: dict[str, Any]) -> dict[str, Any]:
    reqs = read_json(ws / "analysis" / "requirements.json")
    mp = read_json(ws / "mappings" / "figma-mapping.json") if (ws / "mappings" / "figma-mapping.json").exists() else None
    tasks = read_json(ws / "planning" / "tasks.json") if (ws / "planning" / "tasks.json").exists() else None
    ver = read_json(ws / "verification" / "verification.json") if (ws / "verification" / "verification.json").exists() else None
    code = read_json(ws / "mappings" / "code-evidence.json") if (ws / "mappings" / "code-evidence.json").exists() else None
    rtm = docs_render.build_rtm(reqs, mp, tasks, (st.get("harness") or {}).get("task_map"), _harness_statuses(root, st), ver,
                                (code or {}).get("requirements"))
    write_json(ws / "mappings" / "rtm.json", rtm)
    write_text(ws / "reports" / "rtm.md", docs_render.render_rtm_md(rtm))
    return rtm


def cmd_render(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    out: dict[str, Any] = {}
    if args.what in ("spec", "all"):
        out["spec"] = _render_spec(ws, root, st)
    if args.what in ("plans", "all"):
        tasks = read_json(ws / "planning" / "tasks.json")
        text = harness_adapter.render_standalone(tasks, st["run_id"], plan_hash(ws), "planning/spec.md")
        write_text(ws / "planning" / "Plans.md", text)
        out["plans_preview"] = str(ws / "planning" / "Plans.md")
    if args.what in ("rtm", "all"):
        out["rtm"] = _build_rtm(ws, root, st)["metrics"]
    state.save(ws, st)
    _out(args, out)
    return 0


def _blocking_questions(ws: Path) -> list[str]:
    reqs = read_json(ws / "analysis" / "requirements.json")
    qs = []
    for r in reqs["requirements"]:
        if r["status"] in artifacts.OUT_OF_SCOPE:
            continue
        for q in r.get("ambiguities", []):
            if q["blocking"] and not q.get("resolution"):
                qs.append(f"{r['id']} {q['id']}: {q['question']}")
    return qs


def cmd_plan_review(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    if st["state"] in ("ANALYSIS",):
        state.transition(st, "REQUIREMENT_REVIEW", "analysis artifacts ready")
    if st["state"] == "REQUIREMENT_REVIEW":
        state.transition(st, "PLANNING", "planning started")
    if st["state"] in ("APPROVED", "EXECUTION"):
        state.transition(st, "PLANNING", "plan regenerated after approval (scope change)")
    if st["state"] != "PLANNING":
        raise Spec2ShipError(f"Cannot prepare plan review from state {st['state']}.")
    spec_info = _render_spec(ws, root, st)
    rep = artifacts.validate_workspace(ws, "approve")
    if not rep.ok:
        state.save(ws, st)
        _out(args, {"ok": False, **rep.as_dict()}, "\n".join(f"ERROR   {e}" for e in rep.errors) + "\nPlan is not reviewable; fix the errors above.")
        return 1
    tasks = read_json(ws / "planning" / "tasks.json")
    ph = plan_hash(ws)
    write_text(ws / "planning" / "Plans.md", harness_adapter.render_standalone(tasks, st["run_id"], ph, "planning/spec.md"))
    rtm = _build_rtm(ws, root, st)
    state.transition(st, "PLAN_REVIEW", "plan ready for developer review")
    st["plan_review"] = {"at": now_iso(), "plan_hash": ph}
    state.save(ws, st)
    n_tasks = sum(len(p["tasks"]) for p in tasks["phases"])
    blocking = _blocking_questions(ws)
    res = {"ok": True, "state": st["state"], "plan_hash": ph, "plan_hash_short": ph[:12], "tasks": n_tasks,
           "phases": len(tasks["phases"]), "warnings": rep.warnings, "blocking_questions": blocking, "spec": spec_info,
           "plans_preview": str(ws / "planning" / "Plans.md"), "rtm_metrics": rtm["metrics"],
           "approve_with": f"/spec2ship:spec2ship-approve {ph[:12]}"}
    _out(args, res)
    return 0


def _consume_intent(ws: Path) -> None:
    if os.environ.get("SPEC2SHIP_REQUIRE_APPROVAL_INTENT", "1") == "0":
        return
    p = ws / INTENT_FILE
    if not p.exists():
        raise Spec2ShipError(
            "No developer approval intent found. The developer must type /spec2ship:spec2ship-approve <plan-hash> themselves "
            "(the plugin's UserPromptSubmit hook records that intent). Claude must not approve on the developer's behalf."
        )
    data = read_json(p)
    at = _dt.datetime.fromisoformat(data["at"])
    age = (_dt.datetime.now(_dt.timezone.utc) - at).total_seconds() / 60
    p.unlink()
    if age > INTENT_MAX_AGE_MIN:
        raise Spec2ShipError(f"Approval intent is {age:.0f} minutes old; ask the developer to run /spec2ship:spec2ship-approve again.")


def cmd_approve(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    if st["state"] != "PLAN_REVIEW":
        raise Spec2ShipError(f"Nothing to approve: state is {st['state']} (expected PLAN_REVIEW). Run /spec2ship-plan.")
    current = plan_hash(ws)
    prefix = (args.plan_hash or "").strip().lower()
    if len(prefix) < 8:
        raise Spec2ShipError("Provide at least the first 8 characters of the plan hash shown at review: /spec2ship:spec2ship-approve <hash>")
    if not current.startswith(prefix):
        raise Spec2ShipError(
            f"Plan hash mismatch: you approved {prefix}, but the current plan is {current[:12]}. "
            "The plan changed after review; run /spec2ship-plan again and review the new version."
        )
    rep = artifacts.validate_workspace(ws, "approve")
    if not rep.ok:
        raise Spec2ShipError("Artifacts are invalid; cannot approve:\n" + "\n".join(rep.errors))
    blocking = _blocking_questions(ws)
    if blocking and not args.accept_open_questions:
        raise Spec2ShipError("Unresolved blocking questions:\n" + "\n".join(blocking) +
                             "\nResolve them in requirements.json, or approve with --accept-open-questions to proceed knowingly.")
    _consume_intent(ws)
    files = {rel: sha256_file(ws / rel) for rel in ("analysis/requirements.json", "mappings/figma-mapping.json", "planning/tasks.json", "planning/spec.md")}
    approval = {"approved_at": now_iso(), "approver": args.approver or os.environ.get("USER") or os.environ.get("USERNAME") or "developer",
                "plan_hash": current, "files": files, "accepted_open_questions": blocking if args.accept_open_questions else []}
    state.mark_approved(st, approval)
    state.save(ws, st)
    _out(args, {"state": st["state"], "approval": approval, "next": "/spec2ship-work hands the approved plan to Harness"})
    return 0


def _assert_approval_current(ws: Path, st: dict[str, Any]) -> None:
    appr = st.get("approval")
    if not appr:
        raise Spec2ShipError("No approved plan. Run /spec2ship-plan and have the developer approve it with /spec2ship:spec2ship-approve.")
    if plan_hash(ws) != appr["plan_hash"]:
        raise Spec2ShipError("Planning artifacts changed after approval. Run /spec2ship-plan to reconcile and get re-approval.")


def cmd_handoff(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    if st["state"] not in ("APPROVED", "EXECUTION"):
        raise Spec2ShipError(f"Handoff requires an approved plan (state is {st['state']}).")
    _assert_approval_current(ws, st)
    h = harness_adapter.detect_harness(root)
    if not h["compatible"] and not args.skip_harness_check:
        raise Spec2ShipError("Harness is not available/compatible: " + "; ".join(h["issues"]) + " Run /spec2ship-setup.")
    tasks = read_json(ws / "planning" / "tasks.json")
    spec_rel = os.path.relpath(ws / "planning" / "spec.md", root).replace("\\", "/")
    info = harness_adapter.handoff(root, ws, tasks, st["run_id"], st["approval"]["plan_hash"], spec_rel, st.get("harness"))
    st["harness"] = {**info, "version": h.get("version")}
    if st["state"] == "APPROVED":
        state.transition(st, "EXECUTION", "approved plan handed to Harness")
    state.save(ws, st)
    _out(args, {"state": st["state"], **info})
    return 0


def cmd_guard(args: argparse.Namespace) -> int:
    """Exit 0 when Harness execution of Spec2Ship tasks is allowed, 4 otherwise (message on stdout)."""
    root, ws = _ctx(args)
    ok, msg = guard_check(root, ws)
    print(msg)
    return 0 if ok else 4


def guard_check(root: Path, ws: Path) -> tuple[bool, str]:
    if not (ws / "state.json").exists():
        return True, "no Spec2Ship run"
    st = state.load(ws)
    if not st.get("harness"):
        return True, "Spec2Ship tasks have not been handed to Harness; nothing to guard"
    if not st.get("approval"):
        return False, ("Spec2Ship: the plan in Plans.md is no longer approved (state "
                       f"{st['state']}). Re-run /spec2ship-plan and /spec2ship:spec2ship-approve before Harness Work.")
    d = harness_adapter.drift(root, st["run_id"], st["harness"]["scope_hash"])
    if d["status"] == "changed":
        return False, ("Spec2Ship: task scope in Plans.md was changed after approval. Restore it from the backup or run "
                       "/spec2ship-plan to reconcile and re-approve. " + d["detail"])
    try:
        if plan_hash(ws) != st["approval"]["plan_hash"]:
            return False, "Spec2Ship: planning artifacts changed after approval; run /spec2ship-plan to reconcile and re-approve."
    except Spec2ShipError as e:
        return False, f"Spec2Ship: {e}"
    return True, "approved plan unchanged"


def cmd_status(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    arts = {rel: (ws / rel).exists() for rel in (
        "analysis/ba-normalized.json", "analysis/requirements.json", "analysis/figma-context.json", "analysis/repository-analysis.md",
        "mappings/figma-mapping.json", "planning/spec.md", "planning/tasks.json", "planning/Plans.md", "mappings/rtm.json",
        "verification/verification.json", "reports/report.md")}
    res: dict[str, Any] = {"run_id": st["run_id"], "state": st["state"], "artifacts": arts, "blockers": st.get("blockers", []),
                           "approval": bool(st.get("approval")), "figma_check": st.get("figma_check")}
    if st.get("approval"):
        res["approval_current"] = plan_hash(ws) == st["approval"]["plan_hash"]
    if st.get("harness"):
        statuses = _harness_statuses(root, st)
        counts: dict[str, int] = {}
        for s in statuses.values():
            key = "done" if harness_adapter.is_done(s) else s.split()[0] if s else "?"
            counts[key] = counts.get(key, 0) + 1
        res["harness"] = {"plans_path": st["harness"]["plans_path"], "task_status_counts": counts,
                          "drift": harness_adapter.drift(root, st["run_id"], st["harness"]["scope_hash"])}
    for b in st["inputs"].get("ba", []):
        p = Path(b["abs_path"])
        if not p.exists():
            res.setdefault("input_changes", []).append(f"{b['path']} is missing")
        elif sha256_file(p) != b["sha256"]:
            res.setdefault("input_changes", []).append(f"{b['path']} changed since analysis; re-analysis and re-approval needed")
    nxt = {
        "INIT": "/spec2ship-setup", "PREFLIGHT": "/spec2ship-analyze", "ANALYSIS": "/spec2ship-analyze (finish requirements, Figma mapping)",
        "REQUIREMENT_REVIEW": "/spec2ship-plan", "PLANNING": "/spec2ship-plan", "PLAN_REVIEW": "developer reviews, then types /spec2ship:spec2ship-approve <hash>",
        "APPROVED": "/spec2ship-work", "EXECUTION": "/harness-work all (Harness) then /spec2ship-review", "REVIEW": "/spec2ship-verify",
        "VERIFICATION": "/spec2ship-verify", "BLOCKED": "resolve blockers, then `spec2ship.py unblock`", "COMPLETED": "done — see reports/report.md",
    }
    res["next"] = nxt.get(st["state"])
    _out(args, res)
    return 0


def cmd_transition(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    if args.to.upper() in ("REVIEW", "VERIFICATION", "COMPLETED"):
        _assert_approval_current(ws, st)
    if args.to.upper() == "COMPLETED":
        rtm = _build_rtm(ws, root, st)
        m = rtm["metrics"]
        if m["verified"] != m["requirements_in_scope"]:
            raise Spec2ShipError(
                f"Cannot complete: {m['verified']}/{m['requirements_in_scope']} in-scope requirements are verified. "
                "Fix, defer with developer approval, or mark the run BLOCKED."
            )
    state.transition(st, args.to, args.reason or "")
    state.save(ws, st)
    _out(args, {"state": st["state"]})
    return 0


def cmd_unblock(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    state.unblock(st, args.reason or "")
    state.save(ws, st)
    _out(args, {"state": st["state"]})
    return 0


TEST_METHODS = {"unit-test", "integration-test", "e2e-test", "static"}


def _load_ver(ws: Path) -> dict[str, Any]:
    p = ws / "verification" / "verification.json"
    return read_json(p) if p.exists() else {"schema_version": "1.0", "checks": [], "results": []}


def cmd_record_evidence(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    if not st.get("approval"):
        raise Spec2ShipError("Evidence can only be recorded for an approved plan.")
    status = args.status.upper()
    notes = []
    if args.method == "llm-review" and status == "PASS":
        status = "REVIEWED"
        notes.append("LLM review alone is recorded as REVIEWED, not PASS.")
    if status == "PASS":
        if args.method in TEST_METHODS:
            has_cmd = args.command and args.exit_code is not None
            has_test = args.file and args.test
            if not (has_cmd or has_test):
                raise Spec2ShipError("PASS from a test needs --command and --exit-code, or --file and --test.")
            if args.exit_code not in (None, 0):
                raise Spec2ShipError(f"Exit code {args.exit_code} is not a pass.")
        elif args.method == "manual" and not args.note:
            raise Spec2ShipError("Manual PASS needs --note describing who verified what.")
    ev = {k: v for k, v in {"file": args.file, "test": args.test, "command": args.command, "exit_code": args.exit_code,
                             "result": args.result, "log_file": args.log_file, "note": args.note}.items() if v is not None}
    ver = _load_ver(ws)
    ver["results"].append({"criterion_id": args.criterion, "status": status, "method": args.method, "evidence": ev, "recorded_at": now_iso()})
    reqs = read_json(ws / "analysis" / "requirements.json")
    rep = artifacts.Report()
    artifacts.check_verification(ver, reqs, rep)
    if not rep.ok:
        raise Spec2ShipError("\n".join(rep.errors))
    write_json(ws / "verification" / "verification.json", ver)
    _out(args, {"recorded": ver["results"][-1], "notes": notes})
    return 0


def cmd_record_check(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    status = args.status.upper()
    if status == "PASS" and args.exit_code not in (0,) and args.layer != "review":
        raise Spec2ShipError("A PASS check needs --exit-code 0.")
    if args.layer == "review" and status == "PASS":
        status = "REVIEWED"
    ver = _load_ver(ws)
    rec = {k: v for k, v in {"name": args.name, "layer": args.layer, "command": args.command, "exit_code": args.exit_code,
                              "status": status, "summary": args.summary, "log_file": args.log_file, "recorded_at": now_iso()}.items() if v is not None}
    ver.setdefault("checks", []).append(rec)
    write_json(ws / "verification" / "verification.json", ver)
    _out(args, {"recorded": rec})
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    root, ws = _ctx(args)
    st = state.load(ws)
    rtm = _build_rtm(ws, root, st)
    ver = _load_ver(ws)
    text = docs_render.render_report(_project_name(ws, root), st, rtm, ver, str(root))
    write_text(ws / "reports" / "report.md", text)
    _out(args, {"report": str(ws / "reports" / "report.md"), "metrics": rtm["metrics"]})
    return 0


def cmd_parse_file(args: argparse.Namespace) -> int:
    ir = ba_parser.parse_document(Path(args.path))
    if args.output:
        write_json(Path(args.output), ir)
        print(json.dumps({"output": args.output, "blocks": ir["stats"]["blocks"], "language": ir["language"],
                          "ocr_required": ir["ocr_required"], "warnings": ir["warnings"]}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(ir, ensure_ascii=False, indent=2))
    return 3 if ir["ocr_required"] else 0


def cmd_figma_url(args: argparse.Namespace) -> int:
    print(json.dumps(figma.parse_figma_url(args.url), indent=2))
    return 0


# --------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="spec2ship", description="Spec2Ship workflow helper")
    p.add_argument("--project-root", default=os.getcwd())
    p.add_argument("--workspace", default=None, help="workspace dir (default .spec2ship or $SPEC2SHIP_WORKSPACE)")
    p.add_argument("--json", action="store_true", help="JSON output")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="validate inputs and create a run")
    s.add_argument("--figma", required=True)
    s.add_argument("--ba", required=True, action="append")
    s.add_argument("--instructions")
    s.add_argument("--force-new", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("preflight")
    s.add_argument("--no-record", action="store_true")
    s.set_defaults(fn=cmd_preflight)

    s = sub.add_parser("figma-check", help="record the result of the Figma MCP bridge check")
    s.add_argument("--open-file-name")
    s.add_argument("--open-file-key", help="fileKey reported by the bridge's list_files (decisive when present)")
    s.add_argument("--node-found", choices=["yes", "no"])
    s.add_argument("--error")
    s.add_argument("--user-confirmed", action="store_true")
    s.set_defaults(fn=cmd_figma_check)

    sub.add_parser("parse-ba").set_defaults(fn=cmd_parse_ba)

    s = sub.add_parser("repo-analyze")
    s.add_argument("--root")
    s.set_defaults(fn=cmd_repo_analyze)

    s = sub.add_parser("validate")
    s.add_argument("--stage", choices=["auto", "plan", "approve"], default="auto")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("render")
    s.add_argument("what", choices=["spec", "plans", "rtm", "all"])
    s.set_defaults(fn=cmd_render)

    sub.add_parser("plan-review").set_defaults(fn=cmd_plan_review)

    s = sub.add_parser("approve")
    s.add_argument("plan_hash")
    s.add_argument("--approver")
    s.add_argument("--accept-open-questions", action="store_true")
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("handoff")
    s.add_argument("--skip-harness-check", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(fn=cmd_handoff)

    sub.add_parser("guard").set_defaults(fn=cmd_guard)
    sub.add_parser("status").set_defaults(fn=cmd_status)

    s = sub.add_parser("transition")
    s.add_argument("to")
    s.add_argument("--reason")
    s.set_defaults(fn=cmd_transition)

    s = sub.add_parser("unblock")
    s.add_argument("--reason")
    s.set_defaults(fn=cmd_unblock)

    s = sub.add_parser("record-evidence")
    s.add_argument("--criterion", required=True)
    s.add_argument("--status", required=True, choices=["PASS", "REVIEWED", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE", "pass", "fail"])
    s.add_argument("--method", required=True, choices=["unit-test", "integration-test", "e2e-test", "manual", "llm-review", "visual", "static"])
    for opt in ("--file", "--test", "--command", "--result", "--log-file", "--note"):
        s.add_argument(opt)
    s.add_argument("--exit-code", type=int)
    s.set_defaults(fn=cmd_record_evidence)

    s = sub.add_parser("record-check")
    s.add_argument("--name", required=True)
    s.add_argument("--layer", required=True, choices=["static", "unit", "integration", "build", "review", "visual", "other"])
    s.add_argument("--status", required=True, choices=["PASS", "REVIEWED", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"])
    s.add_argument("--command")
    s.add_argument("--exit-code", type=int)
    s.add_argument("--summary")
    s.add_argument("--log-file")
    s.set_defaults(fn=cmd_record_check)

    sub.add_parser("report").set_defaults(fn=cmd_report)

    s = sub.add_parser("parse-file", help="parse one BA document without a run")
    s.add_argument("path")
    s.add_argument("--output")
    s.set_defaults(fn=cmd_parse_file)

    s = sub.add_parser("figma-url", help="parse a Figma URL")
    s.add_argument("url")
    s.set_defaults(fn=cmd_figma_url)
    return p


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except Spec2ShipError as e:
        print(f"spec2ship: error: {e}", file=sys.stderr)
        return 1
