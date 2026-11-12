#!/usr/bin/env python3
"""Offline replay of the Spec2Ship workflow on the sample "customer management" ticket.

No Claude session, Figma or network is needed. The steps Claude performs in a real run (requirement extraction,
Figma capture, mapping, task planning) are replaced by the prepared files in `model-outputs/`. Everything else is
the real Spec2Ship code:
- BA parsing (`ba/`) and repository analysis (`app/`);
- validation, including the check that every citation exists in the parsed BA;
- plan hash and approval through the real UserPromptSubmit hook;
- Harness Plans.md handoff and the scope guard;
- evidence rules and the delivery report.

    python examples/customer-management/run-demo.py            # works in a fresh temp copy
    python examples/customer-management/run-demo.py --out DIR  # keep the result in DIR (must not exist)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]
CLI = [sys.executable, str(PLUGIN / "scripts" / "spec2ship.py")]
HOOK = [sys.executable, str(PLUGIN / "scripts" / "hook.py")]
FIGMA_URL = "https://www.figma.com/design/AbCdEf1234567890/customer-management?node-id=12-345"


def step(title: str) -> None:
    print(f"\n=== {title} ===")


def s2s(project: Path, *args: str, ok=(0,)) -> dict | str:
    r = subprocess.run(CLI + ["--project-root", str(project), "--json", *args], capture_output=True, text=True,
                       encoding="utf-8")
    if r.returncode not in ok:
        print(r.stdout, r.stderr, sep="\n")
        raise SystemExit(f"step failed: spec2ship {' '.join(args)} (exit {r.returncode})")
    try:
        return json.loads(r.stdout)
    except ValueError:
        return r.stdout


def hook(mode: str, payload: dict) -> dict | None:
    r = subprocess.run(HOOK + [mode], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8")
    return json.loads(r.stdout) if r.stdout.strip() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="directory to create for the demo project (default: a new temp dir)")
    a = ap.parse_args()
    project = Path(a.out).resolve() if a.out else Path(tempfile.mkdtemp(prefix="spec2ship-demo-")) / "app"
    if project.exists():
        raise SystemExit(f"{project} already exists")
    shutil.copytree(HERE / "app", project)
    shutil.copytree(HERE / "ba", project / "docs" / "BA")
    ws = project / ".spec2ship"

    step("1. Start a run (Figma URL + BA document)")
    s2s(project, "init", "--figma", FIGMA_URL, "--ba", "docs/BA/customer-management.md")
    pre = s2s(project, "preflight", ok=(0, 2))
    for c in pre["checks"]:
        print(f"  [{c['status']:>7}] {c['name']}")
    if not pre["ok"]:
        print("  Preflight is BLOCKED on this machine (see above). The demo continues offline anyway.")
        s2s(project, "unblock", "--reason", "offline demo")

    step("2. Figma bridge check (recorded as if list_files/get_metadata had answered)")
    fc = s2s(project, "figma-check", "--open-file-name", "Customer Management", "--open-file-key", "AbCdEf1234567890",
             "--node-found", "yes")
    print(f"  match: {fc['match']} ({fc['reason']})")

    step("3. Parse the BA document and analyze the repository (real code)")
    s2s(project, "parse-ba")
    ba = json.loads((ws / "analysis" / "ba-normalized.json").read_text(encoding="utf-8"))
    doc = ba["documents"][0] if "documents" in ba else ba
    print(f"  BA: {doc.get('document')} language={doc.get('language')} blocks={doc.get('stats', {}).get('blocks')}")
    s2s(project, "repo-analyze")
    repo = json.loads((ws / "analysis" / "repository-analysis.json").read_text(encoding="utf-8"))
    print(f"  repo: frameworks={repo['frameworks']} test={repo['commands'].get('test')}")

    step("4. Model outputs (prepared files standing in for Claude) + validation")
    for name, sub in (("requirements.json", "analysis"), ("figma-context.json", "analysis"),
                      ("figma-mapping.json", "mappings"), ("tasks.json", "planning")):
        shutil.copy(HERE / "model-outputs" / name, ws / sub / name)
    v = s2s(project, "validate", "--stage", "plan")
    print("  " + (v if isinstance(v, str) else json.dumps(v))[:300].replace("\n", "\n  "))

    step("5. Plan review: spec.md, Harness Plans.md preview, RTM, plan hash")
    review = s2s(project, "plan-review")
    print(f"  tasks={review['tasks']} phases={review['phases']} rtm={review['rtm_metrics']}")
    print(f"  approve with: {review['approve_with']}")

    step("6. Approval gate")
    r = subprocess.run(CLI + ["--project-root", str(project), "approve", review["plan_hash_short"]],
                       capture_output=True, text=True, encoding="utf-8")
    print(f"  Claude runs `approve` by itself -> exit {r.returncode}: {r.stderr.strip()[:110]}...")
    denied = hook("pretool", {"cwd": str(project), "tool_name": "Write",
                              "tool_input": {"file_path": str(ws / ".approval-intent.json")}})
    print(f"  model tries to forge the approval file -> {denied['hookSpecificOutput']['permissionDecision']}")
    hook("prompt", {"cwd": str(project), "prompt": f"/spec2ship:spec2ship-approve {review['plan_hash_short']}"})
    print("  developer types /spec2ship:spec2ship-approve <hash> (sent through the real UserPromptSubmit hook)")
    ap_res = s2s(project, "approve", review["plan_hash_short"], "--approver", "demo-developer")
    print(f"  state: {ap_res['state']}")

    step("7. Handoff to claude-code-harness Plans.md (existing content preserved)")
    ho = s2s(project, "handoff", "--skip-harness-check")
    print(f"  state: {ho['state']}  task ids: {ho['task_map']}")
    plans = (project / "Plans.md").read_text(encoding="utf-8")
    print(f"  user note kept: {'User note: keep this line.' in plans}")
    edited = plans.replace("Customer detail screen", "Customer detail and export screen")
    (project / "Plans.md").write_text(edited, encoding="utf-8", newline="\n")
    blocked = hook("prompt", {"cwd": str(project), "prompt": "/harness-work all"})
    print(f"  scope edited after approval -> /harness-work {blocked['decision'] if blocked else 'allowed'}")
    # Stand-in for Harness execution: Harness marks tasks done in Plans.md (a status-only change).
    done = plans.replace("| cc:TODO |", "| cc:完了 [1234567] |").replace(
        "| 1.2  | Logout | test passes | 1.1 | cc:完了 [1234567] |", "| 1.2  | Logout | test passes | 1.1 | cc:TODO |")
    (project / "Plans.md").write_text(done, encoding="utf-8", newline="\n")
    allowed = hook("prompt", {"cwd": str(project), "prompt": "/harness-work all"})
    print(f"  Harness marks the tasks cc:完了 (status only) -> guard {'allows' if allowed is None else 'blocks'} further work")

    step("8. Review + verification with evidence rules")
    s2s(project, "transition", "REVIEW")
    s2s(project, "transition", "VERIFICATION")
    r = s2s(project, "record-evidence", "--criterion", "AC-CUS-001-01", "--status", "PASS", "--method", "llm-review",
            "--note", "code reads right")
    print(f"  LLM review claimed PASS -> recorded as {r['recorded']['status']} (never PASS without a test)")
    for ac in ("AC-CUS-001-02", "AC-CUS-002-01", "AC-CUS-002-02", "AC-CUS-003-01"):
        s2s(project, "record-evidence", "--criterion", ac, "--status", "PASS", "--method", "unit-test",
            "--command", "npm test -- customers", "--exit-code", "0", "--file", "tests/customers.test.js")
    s2s(project, "record-check", "--name", "unit tests", "--layer", "unit", "--command", "npm test", "--exit-code", "0",
        "--status", "PASS")
    rep = s2s(project, "report")
    m = rep["metrics"]
    print(f"  verified={m['verified']} implemented={m['implemented']} criteria_pass={m['criteria_pass']} "
          f"reviewed_only={m['criteria_reviewed_only']}")

    step("Result")
    for rel in ("planning/spec.md", "planning/Plans.md", "reports/rtm.md", "reports/report.md"):
        print(f"  {ws / rel}")
    print(f"  Harness ledger: {project / 'Plans.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
