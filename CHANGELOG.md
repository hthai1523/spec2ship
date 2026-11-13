# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- One-command installers `scripts/install.ps1` and `scripts/install.sh`: add the Harness and Spec2Ship marketplaces and
  install both plugins (idempotent; `SPEC2SHIP_SOURCE` overrides the Spec2Ship source). Verified in clean Claude Code
  config directories, including a second run.
- `spec2ship` declares Harness as a plugin dependency (`dependencies` + `allowCrossMarketplaceDependenciesOn` in
  `marketplace.json`). With the Harness marketplace already added, `/plugin install spec2ship@spec2ship-marketplace`
  installs Harness too. Claude Code does not add the dependency's marketplace itself.

### Fixed
- Harness plugin was renamed upstream from `claude-code-harness` to `harness` (5.x), so the documented install command
  failed and preflight reported Harness as missing. Detection now accepts both names; the manual-typed execution-prompt
  guard also covers `/harness:harness-work` and friends. Install instructions and the preflight fix hint use `harness`.
- Harness 5.16.0 is detected but is not in the tested-version list (Plans.md format verified on 4.12.11 only).

## [0.2.0] - 2026-11-10

### Added
- figma-mcp-go MCP server bundled in the plugin (`.mcp.json`, pinned `@vkhanhqui/figma-mcp-go@0.1.3`, MIT): users no
  longer run `claude mcp add`. Tools are exposed as `mcp__plugin_spec2ship_figma-mcp-go__*` (verified live).
- Preflight `node-runtime` check (Node.js 18+ and npx, required by the bundled server) and `figma-mcp-duplicate`
  notice when the user also configured figma-mcp-go (compatible: leader/follower on 127.0.0.1:1994, verified).

### Changed
- Skills, commands and the `figma-analyst` agent use the bundled server's tool names.
- Still manual (cannot be bundled): importing and running the figma-mcp-go plugin inside Figma Desktop.

### Removed
- `.mcp.json.example` (superseded by the bundled `.mcp.json`).

### Verified
- 67 automated tests at the time of this release.

## [0.1.0] - 2026-11-10

Initial vertical slice (preview). Not yet verified end-to-end: design capture with Figma Desktop running, and
claude-code-harness executing a handed-off plan.

### Added
- Plugin + marketplace manifests (repository is its own marketplace, `spec2ship@spec2ship-marketplace`).
- Commands: `/spec2ship`, `/spec2ship-setup`, `/spec2ship-analyze`, `/spec2ship-plan`, `/spec2ship-approve`
  (developer-only, `disable-model-invocation`), `/spec2ship-work`, `/spec2ship-review`, `/spec2ship-verify`,
  `/spec2ship-status`. Installed plugin commands are namespaced, e.g. `/spec2ship:spec2ship-approve`.
- Skills: spec2ship-workflow, ba-analysis, figma-analysis, requirement-mapping, fullstack-planning,
  implementation-verification, delivery-report. Read-only agents: ba-analyst, figma-analyst, architecture-analyst,
  requirement-mapper, acceptance-reviewer.
- Local BA parser (Markdown, DOCX, PDF via pdftotext/pypdf/built-in) with page/section/line references,
  EN/VI language detection and scanned-PDF (OCR required) detection.
- JSON Schemas and cross-reference validation (citation verification against the parsed BA, Figma node existence,
  requirement coverage, orphan tasks, dependency cycles, evidence rules).
- Workflow state machine with approval hash, approval-intent hook, retry limit and re-approval on scope change.
- Harness adapter: Plans.md v2 rendering, collision-free renumbering, non-destructive merge with backup,
  status read-back, scope-drift detection; guard hooks for `/harness-work`, `/breezing`, `/harness-loop`.
- Repository analyzer (stack, package manager, project-native commands, API routes, migrations, tests, CI; skips
  secret files). RTM, spec.md and delivery-report generators.

### Verified (see docs/INTEGRATION.md)
- 64 automated tests at the time of this release (`python -m unittest discover -s tests -t .`), and
  `claude plugin validate .` passes.
- Clean-config marketplace install: `claude plugin marketplace add <path>` + `claude plugin install
  spec2ship@spec2ship-marketplace` → 9 commands, 7 skills, 5 agents, 2 hooks loaded.
- Live headless session (`claude -p --plugin-dir`): `/spec2ship:spec2ship-approve <hash>` recorded intent via the
  UserPromptSubmit hook, `${CLAUDE_PLUGIN_ROOT}` expanded in the command, run moved PLAN_REVIEW → APPROVED.
- Live: after handoff into a real Harness Plans.md and a scope edit, `/claude-code-harness:harness-work all` was
  blocked by the hook before any model turn.

### Fixed during live testing
- Hook launcher passed a `/c/...` path to Windows Python under Git Bash (`MSYS_NO_PATHCONV=1`), and a launcher error
  blocked all tool calls. It now converts paths with `cygpath -w` and fails open.
- figma-mcp-go config in an ancestor `.mcp.json` (e.g. `~/.mcp.json`) was not detected.
- Model could have hand-edited `state.json`; direct edits of `state.json`/`run.json` are now denied by the hook.
