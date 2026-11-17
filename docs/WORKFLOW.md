# Workflow

```mermaid
stateDiagram-v2
    [*] --> INIT: init
    INIT --> PREFLIGHT: preflight
    PREFLIGHT --> ANALYSIS: parse-ba
    PREFLIGHT --> BLOCKED: failed checks / OCR required
    ANALYSIS --> REQUIREMENT_REVIEW: plan-review (auto)
    REQUIREMENT_REVIEW --> PLANNING: plan-review (auto)
    PLANNING --> PLAN_REVIEW: plan-review (valid)
    PLAN_REVIEW --> PLANNING: change request
    PLAN_REVIEW --> APPROVED: developer /spec2ship:spec2ship-approve <hash>
    APPROVED --> EXECUTION: handoff to Harness Plans.md
    APPROVED --> PLANNING: scope change (approval revoked)
    EXECUTION --> REVIEW
    EXECUTION --> PLANNING: scope change (approval revoked)
    REVIEW --> VERIFICATION
    REVIEW --> EXECUTION: fixes
    VERIFICATION --> EXECUTION: fixes (retry limit)
    VERIFICATION --> COMPLETED: all in-scope requirements verified
    BLOCKED --> PREFLIGHT: unblock
```

## CLI cheat sheet (`python3 scripts/spec2ship.py ...`)

| Step | Command | Writes |
|---|---|---|
| start | `init [--figma URL] [--ba PATH ...] [--instructions T] [--force-new]` (needs `--ba` or `--instructions`) | state.json, run.json |
| checks | `preflight`, `figma-check --open-file-name N --node-found yes\|no` or `--error MSG` | state.preflight / figma_check |
| BA | `parse-ba` (exit 3 = OCR required) | analysis/ba-normalized.json |
| repo | `repo-analyze` | analysis/repository-analysis.{json,md} |
| validate | `validate [--stage plan\|approve]` | — |
| review | `plan-review` | planning/spec.md, Plans.md preview, mappings/rtm.json, reports/rtm.md |
| approve | `approve <hash> [--accept-open-questions]` (needs developer intent) | state.approval |
| execute | `handoff` | Harness Plans.md (marked section), backup, task map |
| guard | `guard` (exit 4 = blocked) | — |
| evidence | `record-evidence ...`, `record-check ...` | verification/verification.json |
| report | `report`, `render spec\|plans\|rtm\|all` | reports/report.md |
| misc | `status`, `transition STATE`, `unblock`, `parse-file PATH`, `figma-url URL` | |

## Resume

Every command reloads `state.json` and re-checks prerequisites. `status` reports changed/missing BA inputs (hash
comparison), whether the approval is still current, and Harness Plans.md drift.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SPEC2SHIP_WORKSPACE` | `.spec2ship` | workspace location |
| `SPEC2SHIP_MAX_RETRIES` | 3 | verification → execution loop limit |
| `SPEC2SHIP_REQUIRE_APPROVAL_INTENT` | 1 | set 0 only in CI/headless automation where no developer types the command |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | where Harness installation is detected |
