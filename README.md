# Spec2Ship

**BA documents + Figma design + your existing repo → an approved, traceable fullstack plan, executed by
[claude-code-harness](https://github.com/Chachamaru127/claude-code-harness), verified with evidence.**

Spec2Ship is a Claude Code plugin.
- **Inputs:** a business-analysis document (PDF, DOCX or Markdown, in English or Vietnamese), a Figma design, and your
  repository.
- **Outputs:** source-cited requirements, a requirement ↔ design mapping, a specification, a Requirement Traceability
  Matrix (RTM) and a Harness `Plans.md` task plan.
- **Approval first:** nothing is implemented until a developer approves the exact plan.
- **After approval:** execution is delegated to claude-code-harness. Spec2Ship then records review and test evidence
  and writes a delivery report that keeps *implemented*, *verified*, *blocked* and *deferred* apart.

> Status: **0.3.0 preview.** Two parts are not yet verified end-to-end: live Figma capture, and Harness executing a
> handed-off plan. See [What is tested](#what-is-tested) and [Limitations](#limitations).
>
> **New in 0.3.0:**
> - The Figma bridge is a **vendored, read-only** build of the MIT project
>   [figma-mcp-bridge](https://github.com/gethopp/figma-mcp-bridge). Nothing is downloaded at runtime, and design edits
>   are impossible.
> - One-command installer, an offline demo, and a measurement guide.
>
> Vietnamese quick start: [Hướng dẫn nhanh](#hướng-dẫn-nhanh-tiếng-việt).

## Quick install (one command)

The installer checks every prerequisite and installs only what is missing. It asks before each install, and its
check-only mode installs nothing.

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/hthai1523/spec2ship/main/install/install.ps1 -OutFile install-spec2ship.ps1
powershell -ExecutionPolicy Bypass -File install-spec2ship.ps1            # add -CheckOnly to only report
```

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/hthai1523/spec2ship/main/install/install.sh -o install-spec2ship.sh
bash install-spec2ship.sh                                                 # add --check-only to only report
```

Then restart Claude Code and run `/spec2ship:spec2ship-setup` in your project. It lists anything still missing, and
the Figma manifest path to import.

## Prerequisites

| Requirement | Why | Tested with |
|---|---|---|
| Claude Code — CLI or the VS Code extension | plugin host | CLI 2.1.319 (the extension flow is [not yet verified](#limitations)) |
| `claude` CLI on PATH — only for the one-command installer | the install scripts call `claude plugin ...`; not needed for the extension's `/plugins` UI | CLI 2.1.322 |
| Python ≥ 3.9 on PATH (`python3` or `python`) | local helper scripts (stdlib only) | 3.14.5 |
| [Harness](https://github.com/Chachamaru127/claude-code-harness) plugin (`harness`, formerly `claude-code-harness`) | task ledger, Work, Review | Plans.md format verified on 4.12.11; 5.16.0 installs and is detected but not yet verified end-to-end (≥ 4.0 accepted) |
| Node.js ≥ 18 with `npx` | runs the **bundled** figma-mcp-go MCP server | Node 24.16.0 |
| figma-mcp-go plugin in Figma Desktop (one-time import) | bridge between Figma Desktop and the MCP server | figma-mcp-go 0.1.3 |
| `pdftotext` (poppler) or `pip install pypdf` — optional | reliable PDF text extraction | poppler `pdftotext` (Git for Windows build) |
| `bash` | hook launcher | Git Bash on Windows |

## Install manually

**One command** — adds both marketplaces and installs Harness + Spec2Ship (safe to re-run):

```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/hthai1523/spec2ship/main/scripts/install.ps1 | iex
```
```bash
# macOS / Linux / Git Bash
curl -fsSL https://raw.githubusercontent.com/hthai1523/spec2ship/main/scripts/install.sh | bash
```

Run it in a terminal; both scripts need the `claude` CLI on PATH, and you should read a script before piping it into a
shell (they are short: `scripts/install.ps1`, `scripts/install.sh`). Inside a Claude Code **CLI** session you can
prefix the command with `!` to run it there. Restart Claude Code afterwards, then run `/spec2ship:spec2ship-setup`.
To install from a local checkout or fork, set `SPEC2SHIP_SOURCE` first
(e.g. `$env:SPEC2SHIP_SOURCE='D:\src\spec2ship'` or `SPEC2SHIP_SOURCE=/path bash scripts/install.sh`).

### Install from the VS Code extension

Installing the extension does **not** put `claude` on your PATH and the `!` shell shortcut is CLI-only, so the one-command
installer does not run from the chat box. Use the plugin manager instead (no `claude` on PATH needed):

1. In the chat box type `/plugins` to open **Manage plugins**.
2. **Marketplaces** tab: add `Chachamaru127/claude-code-harness`, then `hthai1523/spec2ship`.
3. **Plugins** tab: click **Install** on `harness`, then on `spec2ship`; choose **Install for you** to use them in every project.
4. Restart the VS Code window, then type `/spec2ship:spec2ship-setup`.

Add both marketplaces *before* installing, otherwise Spec2Ship's Harness prerequisite is missing. The extension shares
`~/.claude/settings.json` with the CLI, so either one sees what the other installed. If you installed the standalone
CLI as well, you can also run the one-command installer in the extension's integrated terminal (``Ctrl+` ``).

> These extension steps follow the official documentation; the project itself has only been verified on the CLI (see
> [Limitations](#limitations)).

<details><summary>Manual install on the CLI (the same steps, one by one)</summary>

Type these in a Claude Code **CLI** session:

```text
/plugin marketplace add Chachamaru127/claude-code-harness
/plugin marketplace add hthai1523/spec2ship        # this repository (it is its own marketplace)
/plugin install spec2ship@spec2ship-marketplace    # also installs Harness: it is a declared dependency
```

Harness is a declared dependency of Spec2Ship, so with its marketplace already added the last command pulls it in
automatically. Claude Code does not add a dependency's *marketplace* by itself, which is why both `marketplace add`
lines are needed. To install Harness on its own: `/plugin install harness@claude-code-harness-marketplace`.
(Upstream renamed the plugin from `claude-code-harness` to `harness`; the repository keeps its old name.)

Local checkout: `/plugin marketplace add /path/to/spec2ship`, or `claude --plugin-dir /path/to/spec2ship` for a
single session.
</details>

### Update

CLI:

```text
/plugin marketplace update spec2ship-marketplace
/plugin update spec2ship@spec2ship-marketplace
```

VS Code extension: `/plugins` → **Marketplaces** tab → click the refresh icon on `spec2ship-marketplace` (and on
`claude-code-harness-marketplace` if you want a newer Harness), then check the **Plugins** tab.

Restart Claude Code (or the VS Code window) to apply. Release notes: [CHANGELOG](CHANGELOG.md).

### Figma setup

**No MCP configuration needed.**
- **What is bundled:** Spec2Ship ships a read-only build of
  [gethopp/figma-mcp-bridge](https://github.com/gethopp/figma-mcp-bridge) v0.0.26 (MIT) in
  [`vendor/figma-bridge`](vendor/figma-bridge/UPSTREAM.md): source, patch, lockfile and the built server.
- **How it runs:** Claude Code starts it with `node` when the plugin is enabled. Nothing is downloaded, and no Figma
  token or API quota is used.
- **Tools:** they appear as `mcp__plugin_spec2ship_figma-bridge__*`; check with `/mcp`.
- **Read-only:** the server exposes only 14 read tools, its local endpoint refuses everything else, and the Figma
  plugin itself refuses every edit.

One step has to happen inside Figma Desktop:

1. Once per machine: Figma Desktop → *Plugins → Development → Import plugin from manifest…* → select
   `vendor/figma-bridge/plugin/manifest.json` inside the installed Spec2Ship plugin folder.
   `/spec2ship:spec2ship-setup` prints the exact path.
2. Each time you use Spec2Ship: open the design file and run **Spec2Ship Figma Bridge (read-only)**.

The bridge listens on `127.0.0.1:3994`. If you also run figma-mcp-bridge or figma-mcp-go yourself (port 1994),
they do not interfere.

## Try it: offline demo (2 seconds)

```bash
python examples/customer-management/run-demo.py
```

The demo runs the real CLI and hooks on a sample ticket: an EN/VI BA document, an Express + Prisma repo and a Harness
`Plans.md`. Prepared files stand in for the model's output. The demo shows:
- citation validation;
- the plan hash;
- the approval gate: Claude cannot approve, the developer's typed command can;
- handoff into Harness `Plans.md` with existing content preserved;
- the scope guard;
- the evidence rules (an LLM review is never counted as a PASS);
- the delivery report.

Outputs are committed in [`examples/customer-management/expected/`](examples/customer-management/expected/). See
[examples/customer-management](examples/customer-management/README.md).

## Usage

```text
/spec2ship https://www.figma.com/design/FILE_KEY/customer-management?node-id=12-345 --ba docs/BA/customer-management.pdf
```

1. **Preflight:** Harness, Node.js, the bundled Figma bridge and its Figma plugin, PDF extractor, git state.
2. **BA parsing (local):** requirements with page/section/line citations, acceptance criteria and open questions.
3. **Figma context:** the open file is matched by file key, and only relevant nodes and prototype flows are read.
   This produces the requirement ↔ node mapping, with evidence and confidence.
4. **Repository analysis:** stack, project-native commands, API routes, migrations, tests.
5. **Plan review:** `spec.md`, `tasks.json`, the Harness `Plans.md` preview and the RTM. Then Spec2Ship **stops for
   review**.
6. **Approval:** you type `/spec2ship:spec2ship-approve <plan-hash>`. Claude cannot do this for you.
7. **Execution:** `/spec2ship-work` hands the approved tasks to Harness (`/harness-work`, `/breezing`).
8. **Verification:** `/spec2ship-review` and `/spec2ship-verify` record evidence and produce the RTM and
   `reports/report.md`.

Installed plugin commands are namespaced: type `/spec2ship:spec2ship-setup`, `/spec2ship:spec2ship-approve`, and so on.
The short forms below may also resolve when they are unambiguous. The approve command was verified only in
namespaced form.

| Command | Purpose |
|---|---|
| `/spec2ship <figma-url> --ba <path>` | full workflow up to plan approval |
| `/spec2ship-setup` | checks every prerequisite and lists exactly what is missing |
| `/spec2ship-analyze [ba\|figma\|repo\|mapping]` | (re)run analysis parts |
| `/spec2ship-plan [change]` | generate/update spec, RTM, Harness plan; present for approval |
| `/spec2ship:spec2ship-approve <hash>` | developer-only approval of the reviewed plan |
| `/spec2ship-work [all\|task]` | hand off to Harness and run Harness Work |
| `/spec2ship-review` | Harness review + traceability review |
| `/spec2ship-verify` | project-native checks, per-criterion evidence, report |
| `/spec2ship-status` | state, artifacts, approval, Harness progress, next step |

## How the approval gate works

- **Plan hash:** `plan-review` computes a SHA-256 over the requirements (scope), mapping, tasks and `spec.md`. You
  approve that hash.
- **Approval intent:**
  - A `UserPromptSubmit` hook records your typed `/spec2ship:spec2ship-approve`. The `approve` step refuses to run
    without it.
  - A `PreToolUse` hook stops Claude from invoking the approve command and from writing the intent or state files.
- **Handoff and scope guard:**
  - Handoff writes a marked section into Harness `Plans.md`; existing content is preserved and a backup is kept.
  - A hook blocks `/harness-work`, `/breezing` and `/harness-loop` if the approved task scope in `Plans.md` or the
    planning artifacts change afterwards. Harness status-marker updates are ignored.
- **These hooks are workflow guardrails, not a security mechanism.** They keep Claude from skipping review by mistake
  or by following injected text.
  - **Fail-open:** if a hook cannot run, it allows the action rather than locking you out of Claude Code. In that
    case the scope guard is off, but approval itself still fails closed.
  - **Not protected:** they do not protect against someone with shell access.
  - Details: [SECURITY.md](SECURITY.md).

## Artifacts (`.spec2ship/`)

- **Files:**
  - `state.json`, `run.json`;
  - `analysis/`: ba-normalized, requirements, figma-context, repository-analysis;
  - `mappings/`: figma-mapping, rtm, code-evidence;
  - `planning/`: spec.md, tasks.json, Plans.md preview, architecture, api-contract, database-impact;
  - `verification/verification.json`;
  - `reports/`: rtm.md, report.md.
- **Git:** Spec2Ship does not edit `.gitignore`. Add `.spec2ship/` to keep intermediates out of Git, or commit
  `planning/spec.md`, `reports/` and `verification/` deliberately.
- **Location:** override it with `SPEC2SHIP_WORKSPACE`.

## Supported BA formats

| Format | Structure | Source references |
|---|---|---|
| Markdown | headings, lists, tables, links, code | section + line |
| DOCX | headings (styles/outline level), lists, tables, hyperlinks | section; page estimated from Word page-break markers |
| PDF (text) | numbered headings, paragraphs, lists, simple layout tables | page + section |
| PDF (scanned) | detected; run is blocked with an OCR notice (no OCR built in) | — |

## What is tested

Run `python -m unittest discover -s tests -t .`. The suite has unit, artifact-validation, integration and smoke tests,
with no model calls and no network beyond localhost (77 tests). It covers:
- parsers: EN/VI fixtures, scanned PDF, built-in PDF fallback;
- Figma URL handling and file-key matching;
- the state machine;
- schema and cross-reference validation: hallucinated citations, orphan tasks, cycles, coverage;
- the Harness adapter: render, renumber, merge, drift, detection;
- the full CLI vertical slice with the hook gate;
- repository analysis and plugin layout;
- **the built Figma bridge:** it is started, it exposes only the read tools, and write calls are refused over MCP and
  over its local RPC endpoint;
- the offline demo.

`claude plugin validate .` passes.

Verified live in real Claude Code sessions:
- **Install:** from GitHub (`/plugin marketplace add hthai1523/spec2ship`) into a clean config; the test suite passes
  on the installed copy.
- **Figma bridge (0.3.0):**
  - It starts with the plugin through `${CLAUDE_PLUGIN_ROOT}` and exposes exactly the 14 read tools as
    `mcp__plugin_spec2ship_figma-bridge__*`.
  - `get_metadata` returns `No plugin connected` while Figma Desktop's plugin is not running.
- **BA analysis:** `/spec2ship:spec2ship-analyze ba` on the Vietnamese DOCX and the English PDF produced 4
  requirements, every one citing a real document, page, section and quote. It raised 8 open questions and left
  `src/` untouched.
- **Approval:** a developer-typed `/spec2ship:spec2ship-approve <hash>` approves a plan through the hook.
- **Harness handoff:** the plan was handed off into a Plans.md next to the installed Harness 4.12.11, and
  `/claude-code-harness:harness-work` was blocked after the approved scope was edited.

See [docs/INTEGRATION.md](docs/INTEGRATION.md). To measure real tickets against manual work, use
[docs/EVALUATION.md](docs/EVALUATION.md).

## Limitations

- The live Figma path was verified only up to the bridge check (`plugin not connected`); end-to-end design capture
  with Figma Desktop running has not been tested yet.
- The bundled server is fetched from npm by `npx` on first start (pinned version, but still a runtime download);
  offline machines need the package in the npm cache.
- The bundled figma-mcp-go server also exposes Figma write tools; Spec2Ship never calls them, but they are visible
  to Claude in the session (normal permission prompts apply).
- Harness execution itself (`/harness-work` on a handed-off plan) has not been run end-to-end in a real session;
  the Plans.md format was verified against Harness 4.12.11 sources.
- Requirement extraction, mapping and planning quality depend on the model; the CLI validates structure and
  citations, not business correctness.
- Everything above was verified on the Claude Code CLI. In the **VS Code extension** these are not yet verified: the
  `/plugins` install flow (taken from the official docs), the `/mcp` server check, and whether the approval hooks
  (`UserPromptSubmit` / `PreToolUse`) run there. Until then, run `/spec2ship:spec2ship-approve` on the CLI if the
  gate does not behave as described.
- The one-command installer was tested against local sources in clean Claude Code config directories, not yet through
  the public `raw.githubusercontent.com` URLs.
- PDF tables are detected heuristically from layout; complex tables may become paragraphs. No OCR.
- DOCX page numbers are estimates.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `[FAIL] harness` | install/enable Harness: `/plugin install harness@claude-code-harness-marketplace` (in the VS Code extension: `/plugins` → *Plugins* tab), restart Claude Code |
| `Plugin "claude-code-harness" not found in marketplace` | the plugin was renamed: use `harness@claude-code-harness-marketplace` |
| `Dependency "harness@..." not found ... Is the "claude-code-harness-marketplace" marketplace added?` | run `/plugin marketplace add Chachamaru127/claude-code-harness` first (extension: `/plugins` → *Marketplaces* tab), or use the one-command installer |
| `claude: command not found` (terminal, after installing the VS Code extension) | the extension does not add `claude` to PATH: install the standalone CLI, or use `/plugins` in the chat box instead of the script |
| Installed in the extension but the plugin / `/spec2ship:...` commands are missing | restart the VS Code window; check `/plugins` → *Plugins* tab shows `harness` and `spec2ship` enabled |
| `[FAIL] node-runtime` | install Node.js 18+ (bundled figma-mcp-go is started with `npx`), restart Claude Code |
| figma tools missing in `/mcp` | check Node/npx and network for the first `npx` download; restart Claude Code |
| `plugin not connected` | open Figma Desktop, open the file, run the figma-mcp-go plugin |
| `OCR_REQUIRED` | export a text PDF/DOCX/Markdown or OCR the PDF locally |
| `section '...' not found` / `possible hallucination` | the requirement's citation does not match the parsed BA; fix the citation |
| `Plan hash mismatch` | the plan changed after review; run `/spec2ship-plan` and approve the new hash |
| `No developer approval intent` | type `/spec2ship:spec2ship-approve <hash>` yourself (hooks must be enabled) |
| Harness Work blocked by Spec2Ship | approved scope in Plans.md changed; restore from `.spec2ship/execution/Plans.md.bak-*` or re-plan |

## Hướng dẫn nhanh (Tiếng Việt)

1. **Cài đặt** — chọn một trong ba cách. Plugin Harness đã đổi tên từ `claude-code-harness` thành `harness` (tên repo
   trên GitHub vẫn là `claude-code-harness`).

   **a) Một lệnh (cần `claude` CLI trong PATH; chạy lại nhiều lần vẫn an toàn):**
   ```powershell
   # Windows (PowerShell)
   irm https://raw.githubusercontent.com/hthai1523/spec2ship/main/scripts/install.ps1 | iex
   ```
   ```bash
   # macOS / Linux / Git Bash
   curl -fsSL https://raw.githubusercontent.com/hthai1523/spec2ship/main/scripts/install.sh | bash
   ```
   Lệnh này thêm cả hai marketplace rồi cài Harness và Spec2Ship. Nên đọc script (`scripts/install.ps1`, `scripts/install.sh`)
   trước khi chạy. Trong phiên Claude Code **CLI** có thể gõ `!` trước lệnh; trên extension thì **không** dùng được `!`,
   hãy chọn cách c) bên dưới.

   **b) Claude Code CLI, cài tay** — gõ trong phiên Claude Code:
   ```text
   /plugin marketplace add Chachamaru127/claude-code-harness
   /plugin marketplace add hthai1523/spec2ship
   /plugin install spec2ship@spec2ship-marketplace
   ```
   Harness được cài kèm vì là phụ thuộc khai báo sẵn, nhưng marketplace của Harness phải được thêm trước.

   **c) Extension Claude Code (VS Code)** — dùng giao diện, không cần `claude` trong PATH:
   1. Trong ô chat gõ `/plugins` để mở **Manage plugins**.
   2. Tab **Marketplaces**: thêm lần lượt `Chachamaru127/claude-code-harness` và `hthai1523/spec2ship`.
   3. Tab **Plugins**: bấm **Install** cho `harness` rồi `spec2ship`; chọn **Install for you** để dùng cho mọi dự án.
   4. Khi cần cập nhật: tab **Marketplaces** → biểu tượng làm mới (refresh) của từng marketplace.

   Extension và CLI dùng chung `~/.claude/settings.json`, nên cài bên nào thì bên kia cũng thấy. Cài extension **không**
   đưa lệnh `claude` vào PATH, và ký tự `!` (chạy lệnh trong phiên) chỉ có ở CLI. Cần chạy lệnh shell thì mở terminal
   tích hợp (``Ctrl+` ``). Thao tác trên extension dựa theo tài liệu chính thức; phần kiểm chứng của dự án (hook duyệt
   kế hoạch, v.v.) mới chạy thật trên CLI.

   Khởi động lại Claude Code (hoặc cửa sổ VS Code) sau khi cài. Máy cần Python 3.9+, Node.js 18+ và bash (Windows: Git Bash).
2. **Figma:** không cần cấu hình MCP, vì server figma-mcp-go đã được đóng gói sẵn trong plugin. Chỉ cần nhập plugin
   figma-mcp-go vào Figma Desktop một lần (*Plugins → Development → Import plugin from manifest…*, dùng `manifest.json`
   trong `plugin.zip` từ [releases](https://github.com/vkhanhqui/figma-mcp-go/releases)), rồi chạy plugin đó trong file
   thiết kế mỗi lần dùng.
3. **Kiểm tra:** `/spec2ship:spec2ship-setup`.
4. **Chạy:** `/spec2ship <figma-url> --ba docs/BA/tai-lieu.docx`. Tài liệu BA có thể ở dạng PDF, DOCX hoặc Markdown,
   viết bằng tiếng Việt hoặc tiếng Anh. Các file kết quả mặc định viết bằng tiếng Anh, còn trích dẫn giữ nguyên ngôn
   ngữ gốc.
5. **Duyệt kế hoạch:** đọc `spec.md`, `Plans.md` và RTM, rồi **tự gõ** `/spec2ship:spec2ship-approve <mã-hash>`.
   Claude không thể duyệt thay anh/chị.
7. **Thực thi và kiểm chứng:** chạy `/spec2ship-work` để giao việc cho Harness, sau đó `/spec2ship-review` và
   `/spec2ship-verify`. Báo cáo cuối nằm ở `.spec2ship/reports/report.md`.
7. **Cập nhật plugin:** CLI — `/plugin marketplace update spec2ship-marketplace`, rồi `/plugin update spec2ship@spec2ship-marketplace`.
   Extension — làm mới marketplace trong `/plugins` (tab **Marketplaces**).

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Workflow](docs/WORKFLOW.md) · [Integration contracts](docs/INTEGRATION.md) ·
[Evaluation guide](docs/EVALUATION.md) · [Security & threat model](SECURITY.md) ·
[Figma bridge provenance](vendor/figma-bridge/UPSTREAM.md) · [Product blueprint](docs/PRODUCT_BLUEPRINT.md) ·
[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## License

MIT, see [LICENSE](LICENSE).
- **Figma bridge:** `vendor/figma-bridge` is based on
  [figma-mcp-bridge](https://github.com/gethopp/figma-mcp-bridge), MIT, © 2026 GETHOPP LTD.
- **Other bundled packages:** their licenses are listed in
  [`vendor/figma-bridge/THIRD_PARTY_LICENSES.md`](vendor/figma-bridge/THIRD_PARTY_LICENSES.md).
