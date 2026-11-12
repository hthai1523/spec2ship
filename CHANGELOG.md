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
## [0.3.0] - 2026-11-10

### Security
- **Replaced figma-mcp-go.** The GitHub repository of `@vkhanhqui/figma-mcp-go`, which 0.2.0 ran through `npx`, was
  disabled after a DMCA notice from the authors of figma-mcp-bridge. Spec2Ship no longer uses it, and preflight warns
  (`figma-other-server`) if a user still has it configured.
- **New Figma bridge.** It is a read-only fork of the original MIT project `gethopp/figma-mcp-bridge` v0.0.26, vendored
  in `vendor/figma-bridge`:
  - source, the patch against upstream, the lockfile, upstream and third-party licenses, and review notes are all in
    the repo;
  - the built `dist/server.mjs` is committed with its sha256;
  - Claude Code runs it with `node` from the plugin folder, so **nothing is downloaded at runtime**.
- **Read-only, enforced three times:**
  - the MCP server registers only 14 read tools;
  - the leader's `/rpc` endpoint returns 403 for any other tool;
  - the Figma plugin refuses every non-read request.

  Removed: all design-edit tools, `delete_nodes`, `run_script`, selection/viewport changes, and `save_screenshots`
  (which wrote local files).
- **Own port 3994** (upstream uses 1994). The plugin may connect only to `ws://localhost:3994`.

### Added
- **One-command installers:** `install/install.ps1` (Windows, winget) and `install/install.sh` (macOS/Linux,
  Homebrew/apt/dnf). Both check Claude Code, Git/Git Bash, Python 3.9+, Node.js 20+, pypdf, Figma Desktop, Harness and
  Spec2Ship, install only what is missing after asking, and support `-CheckOnly` / `--check-only`.
- **Preflight checks:**
  - `figma-plugin`: prints the exact Figma manifest path to import.
  - `figma-other-server`: notes any other Figma MCP server the user configured.
  - `/spec2ship-setup` lists everything still missing.
- **Exact file matching:** `figma-check --open-file-key`. The bridge reports file keys (`list_files`), so the open
  file is now matched exactly against the URL instead of by name.
- **`examples/customer-management/`:**
  - an EN/VI BA ticket (MD, PDF, DOCX), a sample repo, and prepared model outputs;
  - `run-demo.py`, an offline 2-second replay of the whole workflow through the real CLI and hooks;
  - the committed outputs in `expected/`.
- **Measurement guide:** `docs/EVALUATION.md` and `docs/evaluation-template.csv`, for measuring real tickets
  (manual vs. Spec2Ship).
- **Tests:** 77 automated tests in total.
  - The built bridge is started and checked (`test_figma_bridge.py`).
  - The demo must keep working.
  - The README test count must match the suite.

### Changed
- **Tool names:** skills, commands and the `figma-analyst` agent use the new bridge's names
  (`mcp__plugin_spec2ship_figma-bridge__*`). The analyst also gets `list_files`, `get_layout_tree` and the prototype
  flow readers.
- **Node.js:** requires Node.js 20+ (was 18+ with `npx`).
- **Delivery report:** the Harness ledger path is now relative to the project, so the report contains no
  machine-specific path.
- **SECURITY.md** states plainly that the hooks are fail-open workflow guardrails, not a security mechanism.

### Known gaps
- **Figma plugin build:** `vendor/figma-bridge/plugin/dist` must be built by a maintainer
  (`bash vendor/figma-bridge/build.sh plugin`) before the Figma side can be imported.
- **Not yet verified end-to-end:** live design capture with Figma Desktop, and Harness executing a handed-off plan.

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
