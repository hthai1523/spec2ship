# Spec2Ship

**BA documents + Figma design + your existing repo → an approved, traceable fullstack plan, executed by
[claude-code-harness](https://github.com/Chachamaru127/claude-code-harness), verified with evidence.**

Spec2Ship is a Claude Code plugin. It reads a business-analysis document (PDF, DOCX or Markdown, English or
Vietnamese) and a Figma design, analyzes your repository, and produces source-cited requirements, a
requirement ↔ design mapping, a specification, a Requirement Traceability Matrix (RTM) and a Harness `Plans.md`
task plan. **Nothing is implemented until a developer approves the exact plan.** Execution is delegated to
claude-code-harness; Spec2Ship then records review/test evidence and writes a delivery report that keeps
*implemented*, *verified*, *blocked* and *deferred* apart.

> Status: **0.2.0 preview — initial vertical slice.** Live Figma capture and Harness execution of a handed-off plan
> are not yet verified end-to-end. See [What is tested](#what-is-tested) and [Limitations](#limitations).
>
> **New in 0.2.0:** the figma-mcp-go MCP server is bundled — no `claude mcp add` needed. See [Figma setup](#figma-setup).
> Vietnamese quick start: [Hướng dẫn nhanh](#hướng-dẫn-nhanh-tiếng-việt).

## Prerequisites

| Requirement | Why | Tested with |
|---|---|---|
| Claude Code | plugin host | 2.1.319 |
| Python ≥ 3.9 on PATH (`python3` or `python`) | local helper scripts (stdlib only) | 3.14.5 |
| [Harness](https://github.com/Chachamaru127/claude-code-harness) plugin (`harness`, formerly `claude-code-harness`) | task ledger, Work, Review | Plans.md format verified on 4.12.11; 5.16.0 installs and is detected but not yet verified end-to-end (≥ 4.0 accepted) |
| Node.js ≥ 18 with `npx` | runs the **bundled** figma-mcp-go MCP server | Node 24.16.0 |
| figma-mcp-go plugin in Figma Desktop (one-time import) | bridge between Figma Desktop and the MCP server | figma-mcp-go 0.1.3 |
| `pdftotext` (poppler) or `pip install pypdf` — optional | reliable PDF text extraction | poppler `pdftotext` (Git for Windows build) |
| `bash` | hook launcher | Git Bash on Windows |

## Install

**One command** — adds both marketplaces and installs Harness + Spec2Ship (safe to re-run):

```powershell
# Windows (PowerShell)
irm https://raw.githubusercontent.com/XuanDuy2309/spec2ship/main/scripts/install.ps1 | iex
```
```bash
# macOS / Linux / Git Bash
curl -fsSL https://raw.githubusercontent.com/XuanDuy2309/spec2ship/main/scripts/install.sh | bash
```

Inside a Claude Code session, prefix the command with `!` to run it there. Restart Claude Code afterwards, then run
`/spec2ship:spec2ship-setup`. Both scripts need the `claude` CLI on PATH. To install from a local checkout or fork, set
`SPEC2SHIP_SOURCE` first (e.g. `$env:SPEC2SHIP_SOURCE='D:\src\spec2ship'` or `SPEC2SHIP_SOURCE=/path bash scripts/install.sh`).

<details><summary>Manual install (the same steps, one by one)</summary>

```text
/plugin marketplace add Chachamaru127/claude-code-harness
/plugin marketplace add XuanDuy2309/spec2ship        # this repository (it is its own marketplace)
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

```text
/plugin marketplace update spec2ship-marketplace
/plugin update spec2ship@spec2ship-marketplace
```

Restart Claude Code to apply. Release notes: [CHANGELOG](CHANGELOG.md).

### Figma setup

**No MCP configuration needed.** Spec2Ship bundles the figma-mcp-go MCP server (plugin `.mcp.json`, pinned to
`@vkhanhqui/figma-mcp-go@0.1.3`, MIT). Claude Code starts it automatically when the plugin is enabled; its tools
appear as `mcp__plugin_spec2ship_figma-mcp-go__*` (check with `/mcp`). The first start downloads the package via
`npx`, so Node.js 18+ and network access are needed once.

One step cannot be bundled because it lives inside Figma Desktop:

1. Download `plugin.zip` from [figma-mcp-go releases](https://github.com/vkhanhqui/figma-mcp-go/releases) and unzip it.
2. Figma Desktop → *Plugins → Development → Import plugin from manifest…* → select `manifest.json` (once per machine).
3. Each time you use Spec2Ship: open the design file and run the figma-mcp-go plugin.

Already configured figma-mcp-go yourself (e.g. in `~/.mcp.json`)? It can stay: instances elect one leader on
`127.0.0.1:1994` and the others act as followers, so they do not conflict (verified with 0.1.3). You may remove
your own entry.

Run `/spec2ship:spec2ship-setup` to check everything.

## Usage

```text
/spec2ship https://www.figma.com/design/FILE_KEY/customer-management?node-id=12-345 --ba docs/BA/customer-management.pdf
```

1. Preflight (Harness, Figma MCP + bridge, PDF extractor, git state).
2. BA parsing (local) → requirements with page/section/line citations, acceptance criteria, open questions.
3. Figma context (only relevant nodes) → requirement ↔ node mapping with evidence and confidence.
4. Repository analysis → stack, project-native commands, API routes, migrations, tests.
5. `spec.md`, `tasks.json`, Harness `Plans.md` preview and RTM → **stop for review**.
6. You type `/spec2ship:spec2ship-approve <plan-hash>` (Claude cannot do this for you).
7. `/spec2ship-work` hands the approved tasks to Harness (`/harness-work`, `/breezing`).
8. `/spec2ship-review`, `/spec2ship-verify` → evidence, RTM, `reports/report.md`.

Installed plugin commands are namespaced: type `/spec2ship:spec2ship-setup`, `/spec2ship:spec2ship-approve`, etc.
(the short forms below may also resolve when unambiguous; the approve command was verified only in namespaced form).

| Command | Purpose |
|---|---|
| `/spec2ship <figma-url> --ba <path>` | full workflow up to plan approval |
| `/spec2ship-setup` | dependency / integration checks with fixes |
| `/spec2ship-analyze [ba\|figma\|repo\|mapping]` | (re)run analysis parts |
| `/spec2ship-plan [change]` | generate/update spec, RTM, Harness plan; present for approval |
| `/spec2ship:spec2ship-approve <hash>` | developer-only approval of the reviewed plan |
| `/spec2ship-work [all\|task]` | hand off to Harness and run Harness Work |
| `/spec2ship-review` | Harness review + traceability review |
| `/spec2ship-verify` | project-native checks, per-criterion evidence, report |
| `/spec2ship-status` | state, artifacts, approval, Harness progress, next step |

## How the approval gate works

- `plan-review` computes a SHA-256 over requirements (scope), mapping, tasks and `spec.md`. You approve that hash.
- A `UserPromptSubmit` hook records your typed `/spec2ship:spec2ship-approve`; the `approve` step refuses without it, and a
  `PreToolUse` hook blocks Claude from invoking the approve command or writing the intent file.
- Handoff writes a marked section into Harness `Plans.md` (existing content preserved, backup kept). A hook blocks
  `/harness-work`, `/breezing` and `/harness-loop` if the approved task scope in `Plans.md` or the planning artifacts
  change afterwards (Harness status-marker updates are ignored).
- These are guardrails inside Claude Code, not a security boundary against a user with shell access.

## Artifacts (`.spec2ship/`)

`state.json`, `run.json`, `analysis/` (ba-normalized, requirements, figma-context, repository-analysis),
`mappings/` (figma-mapping, rtm, code-evidence), `planning/` (spec.md, tasks.json, Plans.md preview, architecture,
api-contract, database-impact), `verification/verification.json`, `reports/` (rtm.md, report.md).
Spec2Ship does not edit `.gitignore`: add `.spec2ship/` to keep intermediates out of Git, or commit
`planning/spec.md`, `reports/` and `verification/` deliberately. Override the location with `SPEC2SHIP_WORKSPACE`.

## Supported BA formats

| Format | Structure | Source references |
|---|---|---|
| Markdown | headings, lists, tables, links, code | section + line |
| DOCX | headings (styles/outline level), lists, tables, hyperlinks | section; page estimated from Word page-break markers |
| PDF (text) | numbered headings, paragraphs, lists, simple layout tables | page + section |
| PDF (scanned) | detected; run is blocked with an OCR notice (no OCR built in) | — |

## What is tested

`python -m unittest discover -s tests -t .` — unit, artifact-validation, integration and smoke tests (no network,
no model calls): parsers (EN/VI fixtures, scanned PDF, built-in PDF fallback), Figma URL handling, state machine,
schema + cross-reference validation (hallucinated citations, orphan tasks, cycles, coverage), Harness adapter
(render/renumber/merge/drift/detection), the full CLI vertical slice with the hook gate, repository analysis, and
plugin layout, bundled MCP config (67 tests). `claude plugin validate .` passes.

Verified live in real Claude Code 2.1.319 sessions:
- install from GitHub (`/plugin marketplace add hthai1523/spec2ship`) into a clean config; the test suite passes on
  the installed copy;
- the bundled figma-mcp-go server starts with the plugin and exposes `mcp__plugin_spec2ship_figma-mcp-go__*`
  (`get_metadata` → `plugin not connected` while Figma Desktop's plugin is not running);
- two figma-mcp-go instances coexist (leader/follower on `127.0.0.1:1994`);
- developer-typed `/spec2ship:spec2ship-approve <hash>` approves a plan through the hook;
- handoff into a Plans.md alongside the installed Harness 4.12.11, and `/claude-code-harness:harness-work` blocked
  after the approved scope was edited.

See [docs/INTEGRATION.md](docs/INTEGRATION.md).

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
- PDF tables are detected heuristically from layout; complex tables may become paragraphs. No OCR.
- DOCX page numbers are estimates.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `[FAIL] harness` | install/enable Harness: `/plugin install harness@claude-code-harness-marketplace`, restart Claude Code |
| `Plugin "claude-code-harness" not found in marketplace` | the plugin was renamed: use `harness@claude-code-harness-marketplace` |
| `Dependency "harness@..." not found ... Is the "claude-code-harness-marketplace" marketplace added?` | run `/plugin marketplace add Chachamaru127/claude-code-harness` first, or use the one-command installer |
| `[FAIL] node-runtime` | install Node.js 18+ (bundled figma-mcp-go is started with `npx`), restart Claude Code |
| figma tools missing in `/mcp` | check Node/npx and network for the first `npx` download; restart Claude Code |
| `plugin not connected` | open Figma Desktop, open the file, run the figma-mcp-go plugin |
| `OCR_REQUIRED` | export a text PDF/DOCX/Markdown or OCR the PDF locally |
| `section '...' not found` / `possible hallucination` | the requirement's citation does not match the parsed BA; fix the citation |
| `Plan hash mismatch` | the plan changed after review; run `/spec2ship-plan` and approve the new hash |
| `No developer approval intent` | type `/spec2ship:spec2ship-approve <hash>` yourself (hooks must be enabled) |
| Harness Work blocked by Spec2Ship | approved scope in Plans.md changed; restore from `.spec2ship/execution/Plans.md.bak-*` or re-plan |

## Hướng dẫn nhanh (Tiếng Việt)

1. **Cài đặt bằng một lệnh** (cần `claude` CLI trong PATH; chạy lại nhiều lần vẫn an toàn):
   ```powershell
   # Windows (PowerShell)
   irm https://raw.githubusercontent.com/XuanDuy2309/spec2ship/main/scripts/install.ps1 | iex
   ```
   ```bash
   # macOS / Linux / Git Bash
   curl -fsSL https://raw.githubusercontent.com/XuanDuy2309/spec2ship/main/scripts/install.sh | bash
   ```
   Lệnh này thêm cả hai marketplace rồi cài Harness và Spec2Ship. Đang ở trong Claude Code thì gõ `!` trước lệnh.
   Cài tay: `/plugin marketplace add Chachamaru127/claude-code-harness`, rồi
   `/plugin marketplace add XuanDuy2309/spec2ship`, rồi `/plugin install spec2ship@spec2ship-marketplace`
   (Harness được cài kèm vì là phụ thuộc khai báo sẵn). Lưu ý: plugin Harness đã đổi tên từ `claude-code-harness`
   thành `harness`.
   Khởi động lại Claude Code. Máy cần Python 3.9+, Node.js 18+ và bash (Windows: Git Bash).
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
6. **Thực thi và kiểm chứng:** `/spec2ship-work` (giao việc cho Harness), sau đó `/spec2ship-review` và
   `/spec2ship-verify`. Báo cáo cuối nằm ở `.spec2ship/reports/report.md`.
7. **Cập nhật plugin:** `/plugin marketplace update spec2ship-marketplace`, rồi `/plugin update spec2ship@spec2ship-marketplace`.

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Workflow](docs/WORKFLOW.md) · [Integration contracts](docs/INTEGRATION.md) ·
[Security & threat model](SECURITY.md) · [Product blueprint](docs/PRODUCT_BLUEPRINT.md) ·
[Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
