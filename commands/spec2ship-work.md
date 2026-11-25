---
description: Hand the approved Spec2Ship plan to claude-code-harness (Plans.md) and run Harness Work on approved tasks only
argument-hint: [all|<harness-task-number>]
---

# /spec2ship-work

`S2S` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec2ship.py"`. Arguments: `$ARGUMENTS` (default `all`).

Spec2Ship does not implement tasks itself. Execution belongs to claude-code-harness.

1. `S2S status`. Require state APPROVED or EXECUTION with `approval_current: true`. Otherwise explain what is
   missing (`/spec2ship-plan`, `/spec2ship:spec2ship-approve <hash>`) and stop.
2. If not yet handed off (state APPROVED), run `S2S handoff`. It appends a marked Spec2Ship section to the Harness
   `Plans.md` (existing content is preserved and backed up under `.spec2ship/execution/`), renumbers phases to avoid
   collisions, and records the task map. Show the developer the task map (local id → Harness task number).
3. Uncommitted user changes (see preflight `git`) must not be overwritten: if there are any, list them and ask
   whether to proceed.
4. Invoke Harness: the `harness-work` skill, prefixed with the plugin name from the preflight `harness` line
   (`harness:harness-work` on Harness 5.x, `claude-code-harness:harness-work` on 4.x), with `all` or the mapped Harness task number(s)
   (e.g. `/harness-work 2.1`). For many independent tasks the developer may prefer `/breezing all`. Spec2Ship's
   hook blocks these if the approved scope in Plans.md was modified.
   If the Harness skill is unavailable, stop and point to `/spec2ship-setup` — never implement tasks directly.
5. Do not expand scope. If Harness work reveals a needed change in behavior or scope, stop and run
   `/spec2ship-plan` with the change (re-approval required).
6. When Harness reports the tasks done, run `S2S status` to show Harness task markers, then suggest
   `/spec2ship-review`.
