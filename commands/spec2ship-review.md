---
description: Review the implementation against the approved spec, Figma mapping and RTM (Harness Review + Spec2Ship traceability review)
argument-hint: (no arguments)
---

# /spec2ship-review

`S2S` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec2ship.py"`.

1. `S2S status`; require EXECUTION or REVIEW, approval current, and no Plans.md drift. Run `S2S guard`; if it
   fails, stop and explain.
2. If state is EXECUTION: every Spec2Ship task in Plans.md should be `cc:完了`. List any that are not and ask whether
   to continue reviewing a partial implementation. Then `S2S transition REVIEW`.
3. Run Harness review: the `harness-review` skill (`harness:harness-review` on Harness 5.x,
   `claude-code-harness:harness-review` on 4.x; the preflight `harness` line names it) with `code`. Summarize its verdict.
4. Spec2Ship review (use the `acceptance-reviewer` agent for an independent read):
   - For each in-scope requirement, find the changed files/functions implementing it (`git diff` against the base
     branch). Write `mappings/code-evidence.json` as
     `{"requirements": {"REQ-...": ["path/file.ts:functionName", ...]}}` — only entries you actually saw.
   - Check business rules and acceptance criteria against the code; UI against Figma node context.
   - Flag orphan changes (code not traceable to an approved requirement) and scope creep.
   - LLM review findings are **REVIEWED**, never PASS. Record with
     `S2S record-check --name "spec2ship review" --layer review --status REVIEWED --summary "<one line>"`.
5. Regenerate `S2S render rtm`. Present findings (blocking vs non-blocking). If fixes are needed, return to
   `/spec2ship-work` for the affected tasks; otherwise `S2S transition VERIFICATION` and suggest `/spec2ship-verify`.
