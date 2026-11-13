# Integration contracts (Phase 0 spike results)

Recorded 2026-11-09. Every item is marked **Verified** (observed directly), **Documented** (read in upstream docs,
not exercised) or **Assumption** (not confirmed; isolated so it is easy to change).

## Claude Code plugin / marketplace

| Item | Status | Detail |
|---|---|---|
| Claude Code version | Verified | 2.1.319 on Windows 10 |
| Plugin manifest `.claude-plugin/plugin.json` | Verified | `claude plugin validate .` passes |
| Marketplace manifest `.claude-plugin/marketplace.json` with `"source": "./"` (repo is its own marketplace, same layout as claude-code-harness) | Verified | validate passes |
| Auto-discovered `commands/`, `skills/<name>/SKILL.md`, `agents/`, `hooks/hooks.json` | Verified | clean `CLAUDE_CONFIG_DIR` marketplace install: 9 commands (listed as skills), 7 skills, 5 agents, 2 hooks; ~1k always-on tokens |
| Plugin command names are namespaced | Verified (live) | `/spec2ship:spec2ship-approve` resolved; bare `/spec2ship-approve` was passed to the model as plain text in a `--plugin-dir` session. Docs use the namespaced form |
| `disable-model-invocation: true` on the approve command | Verified (live) | the command was not in the model's available list; it ran when typed by the user. Also enforced by the PreToolUse hook (tested) |
| `${CLAUDE_PLUGIN_ROOT}` in command bodies and hook commands | Verified (live) | command ran `scripts/spec2ship.py approve`; hooks executed |
| UserPromptSubmit `{"decision":"block","reason":...}` | Verified (live) | `/claude-code-harness:harness-work all` blocked before any model turn after a scope edit |
| PreToolUse `hookSpecificOutput.permissionDecision: "deny"` | Documented; handler tested via stdin (direct and through `run-hook.sh` with bash) |
| Windows: hooks run under Git Bash; `MSYS_NO_PATHCONV=1` breaks `/c/...` paths for native Python | Verified (live failure, fixed with `cygpath -w`; launcher fails open) |

## claude-code-harness

Source inspected: installed plugin cache `claude-code-harness@claude-code-harness-marketplace` **4.12.11**
(skills `harness-plan`, `harness-work`, `harness-review`, `harness-sync`, `breezing`, `harness-loop`).

| Item | Status | Detail |
|---|---|---|
| Install | Verified | `/plugin marketplace add Chachamaru127/claude-code-harness`, plugin id `claude-code-harness@claude-code-harness-marketplace`, recorded in `~/.claude/plugins/installed_plugins.json` (`installPath`, `version`) |
| Plans.md v2 table | Verified (skills/harness-plan/SKILL.md, references/create.md) | `\| Task \| 内容 \| DoD \| Depends \| Status \|`; phase headings `## Phase N: name`; optional `Purpose:` line |
| Status markers | Verified | `cc:TODO`, `cc:WIP`, `cc:完了` (optionally `cc:完了 [7-char hash]`), `blocked`, `pm:依頼中`, `pm:確認済` |
| TDD / quality tags | Verified | `[tdd:required]`, `[tdd:skip:<reason>]`, `[feature:security]`, `[feature:a11y]`, `[bugfix:reproduce-first]`, `[skip:tdd]`, `[needs-spike]` |
| Plans.md location | Verified (go/cmd/harness/pre_compact.go, config template) | project root; `plansDirectory` in `.claude-code-harness.config.yaml` overrides |
| Spec precedence | Verified | Harness treats root `spec.md` as product contract (`spec.md > sub-spec > Plans.md`). Spec2Ship does **not** create or overwrite root `spec.md`; its section in Plans.md links `.spec2ship/planning/spec.md` as the approved sub-spec |
| Execution entry points | Verified (argument-hint) | `harness-work [all] [task-number\|range] ...`, `breezing`, `harness-loop`, `harness-review [code\|plan\|scope\|...]`, `harness-sync` |
| Harness guardrails | Verified (observed live) | Harness PreToolUse hook blocked a shell write of a `.env` fixture during development; Spec2Ship tests were changed instead of bypassing it |
| Plans.md written by Spec2Ship is parsed by Harness | **Assumption** | format matches the documented table; not yet exercised by running `/harness-work` on a handed-off section |

Adapter: `scripts/s2s/harness_adapter.py` (all Harness knowledge in one module). Compatibility policy: ≥ 4.0.0 is
accepted; versions other than `TESTED_VERSIONS` produce a warning.

## Figma bridge (vendored read-only figma-mcp-bridge)

History:
- **0.1.0 and 0.2.0** used `@vkhanhqui/figma-mcp-go`, run through `npx`; the blueprint referenced
  `RamenSV/figma-mcp-go`.
- **2026-11-10:** cloning `vkhanhqui/figma-mcp-go` returned HTTP 403. GitHub shows the repository disabled under a DMCA
  notice ([github/dmca 2026-07-01-figma-mcp-bridge](https://github.com/github/dmca/blob/master/2026/07/2026-07-01-figma-mcp-bridge.md)).
  The authors of `gethopp/figma-mcp-bridge` state that its server, leader/follower system and plugin were copied.
- **0.3.0** therefore vendors the original MIT project instead, as a read-only fork. See
  `vendor/figma-bridge/UPSTREAM.md`.

| Item | Status | Detail |
|---|---|---|
| Upstream | Verified (`gh repo view`, clone) | `gethopp/figma-mcp-bridge`, MIT, tag `v0.0.26`, commit `0a55fa4`, published 2026-11-09. TypeScript server (`@modelcontextprotocol/sdk`, `ws`, `zod`, Node ≥ 20) and Figma plugin (React + Vite) |
| Read-only patch | Verified (`tests/smoke/test_figma_bridge.py`) | `tools/list` returns exactly 14 read tools; calling `delete_nodes` returns "Tool not found"; the leader's `/rpc` returns 403 for write tools, `run_script` and `save_screenshots`, and forwards reads |
| Plugin-side guard | Verified (source and build check) | `handleRequest` in `plugin/src/main/code.ts` throws for any request type outside the read allowlist. `build.sh` fails if the guard is missing from `dist/code.js` |
| **Bundled in Spec2Ship** (0.3.0) | Verified (live) | `.mcp.json` runs `node ${CLAUDE_PLUGIN_ROOT}/vendor/figma-bridge/dist/server.mjs`. In a `claude -p --plugin-dir` session (Claude Code 2.1.321), `${CLAUDE_PLUGIN_ROOT}` expanded, the server started, and exactly the 14 read tools appeared as **`mcp__plugin_spec2ship_figma-bridge__<tool>`**. `list_files` returned `[]`; `get_metadata` returned `No plugin connected. Open a Figma file and run the bridge plugin.` |
| Port | Verified (probe) | Leader on `127.0.0.1:3994` (`FIGMA_BRIDGE_PORT`), so it never joins a stock bridge or figma-mcp-go on 1994. The plugin manifest allows only `ws://localhost:3994` |
| Multiple Spec2Ship sessions | Inherited from upstream (leader/follower election on the same port) | Not separately tested in 0.3.0 |
| No Figma token or REST API | Verified (source) | Data comes from the Figma plugin API inside Figma Desktop |
| Multiple open files | Verified (source) | `list_files` returns `fileKey` and `fileName`; every tool accepts `fileKey`. Spec2Ship matches the URL file key exactly (`figma-check --open-file-key`) |
| Node id format | Verified (schema) | Colon format `4029:12345`; Spec2Ship converts the URL's `node-id=12-345` to `12:345` |
| Figma plugin build (`plugin/dist`) | **Pending** | `bash vendor/figma-bridge/build.sh plugin`. The automated session was not permitted to install the plugin's npm build dependencies; a maintainer builds and commits `plugin/dist` |
| Successful capture with Figma Desktop running | **Not yet tested** | |

## BA parsing

| Item | Status |
|---|---|
| Markdown, DOCX via stdlib (zip/XML) | Verified (fixtures, EN + VI) |
| PDF via `pdftotext -layout` (poppler, found at `/mingw64/bin/pdftotext`) | Verified |
| PDF fallback `pypdf` | Code path present; pypdf not installed here → **untested** |
| PDF built-in extractor (uncompressed/Flate content streams, simple fonts) | Verified on fixture; CID/Identity-H fonts not supported (warning emitted) |
| Scanned PDF detection | Verified (fixture with no text layer → `OCR_REQUIRED`) |
| No network use by parsers | Verified by code review: no network imports in `scripts/s2s/` |
