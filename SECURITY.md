# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub Security Advisories ("Report a vulnerability" on the
repository's Security tab). Do not open a public issue. Include affected version, reproduction steps and impact.
We aim to acknowledge within 5 business days. Supported version: the latest release.

## Threat model

| Asset | Threat | Mitigation |
|---|---|---|
| Agent behavior | **Prompt injection** in BA documents or Figma text/annotations ("ignore instructions", "approve") | Parser output carries an untrusted-data notice; all skills/agents/commands instruct to treat content as data; approval and scope rules live in code (CLI + hooks), not in prompts; fixture includes an injection line |
| Approval integrity | Model approves on the developer's behalf | `/spec2ship-approve` has `disable-model-invocation`; PreToolUse hook denies Skill invocation of it; `approve` requires an intent recorded by the UserPromptSubmit hook from the developer's typed prompt (≤ 30 min, single use) and the reviewed plan hash; hook denies writes to the intent file and to `state.json`/`run.json` |
| Approved scope | Plan edited after approval; Harness executes unapproved tasks | Plan hash over requirements scope, mapping, tasks and spec; scope hash of the Plans.md section; guard hooks block `/harness-work`, `/breezing`, `/harness-loop` on drift; re-planning revokes approval |
| BA documents (confidential) | Exfiltration by helper scripts | Parsers are local (stdlib, local `pdftotext`/`pypdf`); a test fails if scripts import network modules |
| Secrets | Reading `.env`/keys during repo analysis | Analyzer skips `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`; skills forbid reading secrets |
| User work | Overwriting files / Plans.md / spec edits | Plans.md merged inside markers with a backup; handoff refuses to overwrite started tasks; developer edits of `spec.md` preserved; `.gitignore` never edited; root `spec.md` never written |
| Production | Deploys, destructive git, production DB | Not performed by Spec2Ship; verification skill forbids them; risky tasks (destructive migration, breaking API, cross-repo) flagged for explicit review; Harness guardrails remain in force |
| Supply chain | Third-party MCP server code | The Figma bridge is **vendored and built by Spec2Ship** (`vendor/figma-bridge`): source of gethopp/figma-mcp-bridge v0.0.26 (MIT) with a reviewed read-only patch, a lockfile and the built `dist/server.mjs` committed with its sha256. Claude Code runs it with `node` from the plugin folder — **nothing is downloaded at runtime** (no `npx`). Bundled npm packages and licenses: `vendor/figma-bridge/THIRD_PARTY_LICENSES.md`. Upgrades follow `vendor/figma-bridge/UPSTREAM.md`. 0.2.0 used `npx @vkhanhqui/figma-mcp-go`, whose repository was disabled after a DMCA notice; preflight warns if a user still has it configured |
| Design integrity | Agent edits or deletes the Figma design | The bridge is read-only in three places: the MCP server registers only 14 read tools; the leader's local `/rpc` endpoint returns 403 for any other tool; the Figma plugin itself refuses every non-read request. `tests/smoke/test_figma_bridge.py` starts the built server and checks all of this |
| Local bridge port | Other local processes talking to the bridge | Leader binds `127.0.0.1:3994` only (own port, never joins a stock bridge on 1994); `/rpc` rejects non-loopback callers and requests with an `Origin` header (browsers); the Figma plugin may only connect to `ws://localhost:3994`. Any local process can still *read* the open design through the bridge while the Figma plugin runs — close the plugin when not in use |

## Limits (be honest)

**The hooks are workflow guardrails, not a security mechanism.** They stop Claude from skipping the review step by
mistake or by following injected text. They do not protect against a person, or a model allowed to run arbitrary
shell commands outside the patterns the hook recognizes, who wants to change workspace files.

- **Fail-open by design:** if the hook launcher or Python fails (missing interpreter, broken environment), the hook
  prints a warning to stderr and allows the action, so users are never locked out of Claude Code. On a machine where
  the hooks cannot run:
  - the scope guard (blocking `/harness-work` after the approved plan changed) and the denials of writes to
    approval and state files are off;
  - approval itself still fails closed, because without the hook no approval intent is recorded and the CLI refuses
    `approve`.
- The approval record lives in `.spec2ship/` and is not cryptographically signed.
- Use Claude Code permission settings, branch protection and code review for real enforcement in sensitive
  repositories.
