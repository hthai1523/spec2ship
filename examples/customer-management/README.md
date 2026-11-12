# Example: customer management ticket

A small ticket for a back-office app, used to demo Spec2Ship end to end.

| Folder | Contents |
|---|---|
| `ba/` | The BA document in three forms: English Markdown, English PDF (3 pages), and Vietnamese DOCX (`quan-ly-khach-hang.docx`). |
| `app/` | The existing repository: Express routes, Prisma schema and migration, Jest test, CI workflow, and a Harness `Plans.md` that already holds unrelated tasks. |
| `model-outputs/` | What Claude produces in a real run: `requirements.json`, `figma-context.json`, `figma-mapping.json` and `tasks.json`. These are prepared sample files. |
| `expected/` | The outputs of the demo, committed so you can read them without running anything: `spec.md`, the Harness plan preview, the `Plans.md` after handoff, the RTM, and the delivery report. |
| `run-demo.py` | The offline replay. |

## Demo 1: offline replay (2 seconds, no Claude, no Figma)

```bash
python examples/customer-management/run-demo.py
```

The script runs the real Spec2Ship code on a fresh copy of `app/`. The only exception is the model's work, which is
replaced by `model-outputs/`. In order, the script:

1. **Starts a run and checks prerequisites.** Preflight lists what is missing on your machine; the demo continues
   offline anyway.
2. **Checks the Figma file.** The open file is matched by file key.
3. **Parses the BA and analyzes the repository.** The stack and the test command are detected from `app/`.
4. **Validates the model outputs.** Every requirement must cite a section or page that exists in the parsed BA, every
   requirement must be covered by tasks, and the task dependencies must have no cycles.
5. **Prepares the plan for review.** It writes `spec.md`, the Harness `Plans.md` preview, the RTM and the plan hash.
6. **Applies the approval gate.**
   - Claude cannot approve on its own.
   - Writing the approval file is denied.
   - The developer's typed `/spec2ship:spec2ship-approve <hash>` is sent through the real `UserPromptSubmit` hook.
7. **Hands off to Harness.** Tasks are appended to Harness `Plans.md`; the user note is kept and tasks are renumbered
   after the existing ones. If the approved scope is edited afterwards, `/harness-work` is blocked. Harness's own status
   updates (`cc:完了`) are still allowed.
8. **Records evidence.**
   - An LLM review that claims PASS is recorded as REVIEWED.
   - Unit-test evidence with exit code 0 counts as PASS.
   - The delivery report separates verified (2) from implemented but not fully verified (1) and deferred (1)
     requirements.

## Demo 2: live, with Claude and Figma

You need:
- the plugin installed (see the main README);
- Figma Desktop running the "Spec2Ship Figma Bridge (read-only)" plugin, on a design file with a customer list,
  a create form and a detail screen.

Then:

1. Copy `app/` to a new folder and run `git init` there. Copy `ba/` into it as `docs/BA/`.
2. Open Claude Code in that folder:
   ```text
   /spec2ship <your-figma-frame-url> --ba docs/BA/quan-ly-khach-hang.docx
   ```
3. Compare what Claude extracts with `model-outputs/` and `expected/`, approve, then continue with `/spec2ship-work`.

Use [docs/EVALUATION.md](../../docs/EVALUATION.md) to record time, review findings and missed requirements against
doing the same ticket by hand.
