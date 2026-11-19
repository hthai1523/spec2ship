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

> Status: **0.5.0 preview.** Two parts are not yet verified end-to-end: live Figma capture, and Harness executing a
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

| Requirement | Why | Installer | Tested with |
|---|---|---|---|
| Claude Code | plugin host | checks only | 2.1.321 |
| Python ≥ 3.9 | local helper scripts (stdlib only) | winget / brew / apt | 3.14.5 |
| Node.js ≥ 20 | runs the **bundled** read-only Figma bridge (no download) | winget / brew / apt | 24.16.0 |
| Git (Windows: Git Bash) | hook launcher | winget / brew / apt | 2.54.0 |
| [claude-code-harness](https://github.com/Chachamaru127/claude-code-harness) plugin | task ledger, Work, Review | `claude plugin install` | 4.12.11 (≥ 4.0 accepted) |
| Figma Desktop + the bundled "Spec2Ship Figma Bridge (read-only)" plugin | design capture (the browser version cannot run development plugins) | winget / brew cask; plugin import is manual | — |
| `pdftotext` (poppler) or `pypdf`, optional | more reliable PDF text extraction | `pip install --user pypdf` | poppler (Git for Windows) |

## Install manually

```text
/plugin marketplace add Chachamaru127/claude-code-harness
/plugin install harness@claude-code-harness-marketplace

/plugin marketplace add hthai1523/spec2ship        # this repository (it is its own marketplace)
/plugin install spec2ship@spec2ship-marketplace
```

Restart Claude Code after installing. For a local checkout, use `/plugin marketplace add /path/to/spec2ship`, or
`claude --plugin-dir /path/to/spec2ship` for a single session.

### Update

```text
/plugin marketplace update spec2ship-marketplace
/plugin update spec2ship@spec2ship-marketplace
```

Restart Claude Code to apply. Release notes: [CHANGELOG](CHANGELOG.md).

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

Figma and the BA document are each optional. Requirements need a source: a BA document or written instructions.

| Inputs | Command |
|---|---|
| BA only | `/spec2ship --ba docs/BA/customer-management.pdf` |
| Figma + written requirements | `/spec2ship <figma-url> Add a customer list with search and paging` |
| Written requirements only | `/spec2ship Add a customer list with search and paging` |

Without Figma, UI requirements are listed as unmapped (`figma_unavailable`). Without a BA document, the instructions
are saved as `.spec2ship/inputs/developer-requirements.md` and cited like a BA document.

Installed plugin commands are namespaced: type `/spec2ship:spec2ship-setup`, `/spec2ship:spec2ship-approve`, and so on.
The short forms below may also resolve when they are unambiguous. The approve command was verified only in
namespaced form.

| Command | Purpose |
|---|---|
| `/spec2ship [<figma-url>] [--ba <path>] [instructions]` | full workflow up to plan approval |
| `/spec2ship-setup` | checks every prerequisite and lists exactly what is missing |
| `/spec2ship-analyze [ba\|figma\|repo\|mapping]` | (re)run analysis parts |
| `/spec2ship-plan [change]` | generate/update spec, RTM, Harness plan; present for approval |
| `/spec2ship:spec2ship-approve <hash>` | developer-only approval of the reviewed plan |
| `/spec2ship-work [all\|task]` | hand off to Harness and run Harness Work |
| `/spec2ship-review` | Harness review + traceability review |
| `/spec2ship-verify` | project-native checks, per-criterion evidence, report |
| `/spec2ship-status` | state, artifacts, approval, Harness progress, next step |
| `/spec2ship:spec2ship-auto <idea>` | auto mode: idea → Figma design → Harness → tests → visual match, no prompts |

## Auto mode (preview)

```text
/spec2ship:spec2ship-auto Customer list with search and paging --max-rounds 3 --threshold 0.92
```

One command runs the whole loop without further prompts:

1. Requirements from the idea. Open questions become recorded assumptions.
2. Claude draws one frame per screen on a new page of the open Figma file and exports reference PNGs.
3. Plan, then automatic approval. The approval is labeled `auto-mode`; your typed command is what authorized it.
4. Harness implements the tasks (`harness-work all --no-commit`).
5. Project tests, then a Playwright screenshot of every screen and `visual-compare` against its Figma frame.
6. If anything fails, a fix round adds tasks for the differences and Harness runs again, up to `--max-rounds`.

It stops at **COMPLETED** (tests pass, every criterion has evidence, every screen reaches the similarity threshold)
or **BLOCKED** (round limit reached, or something needs you). A `Stop` hook keeps Claude going between steps,
with a bounded number of continuations.

Requirements beyond the normal setup:
- **A Figma MCP server that can draw, named `figma-mcp-go`,** with its plugin running in Figma Desktop. The bundled
  bridge is read-only on purpose. The designer agent has no delete tools and draws only on its own page.
- **Pillow** (`pip install pillow`) for `visual-compare`. Playwright in the project; if missing, the plan adds it.
- **Permission to edit files and run the project's commands without prompts.** Use a throwaway branch or worktree.
  If Claude Code stops the loop early, raise `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` (for example 60).

`visual-compare` scales each screenshot to the frame width and counts pixels that differ by more than a tolerance.
Browsers and Figma render text differently, so 1.0 is never reached. Treat the default 0.92 as a starting point.
Auto mode never pushes, deploys, or commits.

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
with no model calls and no network beyond localhost (93 tests). It covers:
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

- **Figma capture:** live design capture with Figma Desktop running has not been tested end-to-end yet. The bridge
  was verified up to `No plugin connected`.
- **Figma plugin build:** the plugin's build output (`vendor/figma-bridge/plugin/dist`) must be built by a maintainer
  (`bash vendor/figma-bridge/build.sh plugin`). Until it is committed, preflight reports `figma-plugin` as missing.
- **Harness execution:** `/harness-work` has not been run end-to-end on a handed-off plan in a real session. The
  Plans.md format was verified against the Harness 4.12.11 sources.
- **Model-dependent quality:** requirement extraction, mapping and planning depend on the model. The CLI validates
  structure and citations, not business correctness.
- **BA parsing:** PDF tables are detected heuristically from layout, so complex tables may become paragraphs. There is
  no OCR. DOCX page numbers are estimates.
- **Figma plugin limits:** it runs only in Figma Desktop, not in the browser. While it runs, any local process can
  read the open design through `127.0.0.1:3994`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `[FAIL] harness` | install/enable claude-code-harness, restart Claude Code |
| `[FAIL] node-runtime` | install Node.js 20+ (the installer can do it), restart Claude Code |
| `[FAIL] figma-plugin` | update Spec2Ship; maintainers: `bash vendor/figma-bridge/build.sh plugin` |
| figma tools missing in `/mcp` | check Node.js 20+, restart Claude Code |
| `No plugin connected` / `list_files` is empty | open Figma Desktop, open the file, run "Spec2Ship Figma Bridge (read-only)" |
| `[WARN] figma-other-server` mentions DMCA | you still have `@vkhanhqui/figma-mcp-go` configured; Spec2Ship does not use it |
| `OCR_REQUIRED` | export a text PDF/DOCX/Markdown or OCR the PDF locally |
| `section '...' not found` / `possible hallucination` | the requirement's citation does not match the parsed BA; fix the citation |
| `Plan hash mismatch` | the plan changed after review; run `/spec2ship-plan` and approve the new hash |
| `No developer approval intent` | type `/spec2ship:spec2ship-approve <hash>` yourself (hooks must be enabled) |
| Harness Work blocked by Spec2Ship | approved scope in Plans.md changed; restore from `.spec2ship/execution/Plans.md.bak-*` or re-plan |

## Hướng dẫn nhanh (Tiếng Việt)

1. **Cài đặt bằng một lệnh.** Script tự kiểm tra và chỉ cài những gì còn thiếu, hỏi trước mỗi bước:
   - Windows: tải `install/install.ps1` (lệnh ở mục [Quick install](#quick-install-one-command)), rồi chạy
     `powershell -ExecutionPolicy Bypass -File install-spec2ship.ps1`.
   - macOS/Linux: `bash install-spec2ship.sh`.

   Muốn chỉ kiểm tra mà không cài gì thì thêm `-CheckOnly` (Windows) hoặc `--check-only` (macOS/Linux).

   Nếu cài tay trong Claude Code:
   ```text
   /plugin marketplace add Chachamaru127/claude-code-harness
   /plugin install harness@claude-code-harness-marketplace
   /plugin marketplace add hthai1523/spec2ship
   /plugin install spec2ship@spec2ship-marketplace
   ```
   Cài xong thì khởi động lại Claude Code.
2. **Figma:**
   - Không cần cấu hình MCP. Bridge đọc Figma (bản chỉ đọc) đã có sẵn trong plugin, chạy bằng Node.js 20+ và không
     tải thêm gì.
   - Chỉ cần nhập plugin vào Figma Desktop một lần: *Plugins → Development → Import plugin from manifest…*, chọn file
     `vendor/figma-bridge/plugin/manifest.json` trong thư mục plugin. Lệnh `/spec2ship:spec2ship-setup` in ra đường
     dẫn chính xác.
   - Mỗi lần dùng: mở file thiết kế rồi chạy **Spec2Ship Figma Bridge (read-only)**.
3. **Kiểm tra:** chạy `/spec2ship:spec2ship-setup`. Lệnh này liệt kê những gì còn thiếu.
4. **Xem demo:** `python examples/customer-management/run-demo.py` chạy toàn bộ luồng trên dữ liệu mẫu trong khoảng
   2 giây, không cần Claude hay Figma.
5. **Chạy thật:** `/spec2ship <figma-url> --ba docs/BA/tai-lieu.docx`.
   - Figma và tài liệu BA đều có thể bỏ, nhưng phải có BA hoặc mô tả yêu cầu: `/spec2ship --ba docs/BA/tai-lieu.docx`,
     `/spec2ship <figma-url> <mô tả yêu cầu>` hoặc `/spec2ship <mô tả yêu cầu>`.
   - Tài liệu BA có thể là PDF, DOCX hoặc Markdown, viết bằng tiếng Việt hoặc tiếng Anh.
   - Các file kết quả mặc định bằng tiếng Anh; trích dẫn giữ nguyên ngôn ngữ gốc.
6. **Duyệt kế hoạch:** đọc `spec.md`, `Plans.md` và RTM, rồi **tự gõ** `/spec2ship:spec2ship-approve <mã-hash>`.
   Claude không thể duyệt thay anh/chị.
7. **Thực thi và kiểm chứng:** chạy `/spec2ship-work` để giao việc cho Harness, sau đó `/spec2ship-review` và
   `/spec2ship-verify`. Báo cáo cuối nằm ở `.spec2ship/reports/report.md`.
8. **Chế độ auto:** `/spec2ship:spec2ship-auto <ý tưởng>` chạy một mạch từ ý tưởng, vẽ design trên Figma, giao Harness
   code, chạy test, rồi so ảnh chụp app với Figma. Nếu còn khác thì tự sửa thêm vòng, tối đa `--max-rounds`. Cần thêm
   một Figma MCP có quyền ghi tên `figma-mcp-go`, Pillow, và cho phép Claude sửa file, chạy lệnh mà không hỏi. Xem mục
   [Auto mode](#auto-mode-preview).
9. **Đo hiệu quả trên ticket thật:** xem [docs/EVALUATION.md](docs/EVALUATION.md).
10. **Cập nhật plugin:** `/plugin marketplace update spec2ship-marketplace`, rồi
   `/plugin update spec2ship@spec2ship-marketplace`.

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
