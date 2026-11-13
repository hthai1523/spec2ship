# Implementation Plan

Source contract: `docs/PRODUCT_BLUEPRINT.md` (copy of `SPEC2SHIP_IMPLEMENTATION_BLUEPRINT.md`).

| Milestone | Scope | Status |
|---|---|---|
| M0 Integration spikes | Claude Code plugin/marketplace format, Harness 4.12.11 contracts, Figma bridge tools (figma-mcp-go in 0.1–0.2, vendored read-only figma-mcp-bridge since 0.3.0), BA extraction | Done — `docs/INTEGRATION.md` |
| M1 Requirement intelligence | BA parser + IR, requirement schema, citation validation, Figma URL/context/mapping schemas, spec.md | Done (tested) |
| M2 Planning | repository analyzer, tasks schema, Harness Plans.md rendering, plan hash, approval gate + hooks | Done (tested, live approval verified) |
| M3 Execution | handoff into Harness ledger, drift guard, status/resume, scope-change re-approval | Done for handoff/guard (live block verified); **Harness Work run on a handed-off plan not yet exercised** |
| M4 Verification/release | evidence recording rules, RTM, delivery report, security docs, marketplace packaging | Done (tested); public GitHub publication pending owner |

## Next milestones

1. **Live Figma capture** with Figma Desktop running the bundled read-only bridge plugin (build `vendor/figma-bridge/plugin/dist` first).
2. **Real Harness run**: hand off the sample plan, run `/harness-work 2.1` in a disposable repo, confirm Harness
   parses the section, updates markers, and that `status`/RTM pick them up.
3. **Model-in-the-loop evals** (`claude plugin eval`): requirement extraction on EN/VI fixtures, prompt-injection
   fixture, refusal to approve.
4. Code-evidence automation from `git diff` (currently written by the reviewer per skill instructions).
5. Optional OCR integration (local Tesseract) behind an explicit opt-in.
6. Plugin icon, publish repository, marketplace listing.

## Deferred (with rationale)

- `templates/` directory: Markdown views are generated in code to keep structure testable.
- Separate `parse-ba.py`/`validate-*.py` scripts: consolidated into one CLI (`scripts/spec2ship.py`) with subcommands.
- API/Database analyst agent: combined into `architecture-analyst` for the MVP as the blueprint allows.
