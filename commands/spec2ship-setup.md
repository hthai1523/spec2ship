---
description: Check every Spec2Ship prerequisite (Python, Node.js, PDF extractor, claude-code-harness, bundled figma-mcp-go server and its Figma Desktop plugin) and list exactly what is missing
argument-hint: (no arguments)
---

# /spec2ship-setup

`S2S` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec2ship.py"` (use `python` on Windows if needed).

1. Run `S2S preflight` from the project root (results are saved to the run only when a run exists). Show every
   line, grouped OK / WARN / FAIL, with the suggested fix.
2. Check Figma yourself by calling `mcp__plugin_spec2ship_figma-mcp-go__get_metadata`.
   - **Spec2Ship bundles the server.** Its `.mcp.json` runs `npx -y @vkhanhqui/figma-mcp-go@0.1.3`; Claude Code starts
     it with the plugin and npx downloads the package on first start. No `claude mcp add` is needed.
   - **Tool not available:** the server did not start. The usual cause is Node.js 18+/npx missing (see
     `node-runtime` in preflight) or no network on first start. Check `/mcp`, fix the cause, restart Claude Code.
   - **Error / plugin not connected:** Figma Desktop is closed, or the plugin is not running.
     - Once per machine: Figma Desktop → Plugins → Development → Import plugin from manifest → select the manifest
       path printed on the preflight `figma-plugin` line (`plugins/manifest.json` in the Spec2Ship folder).
     - Then open the design file and run "Figma MCP Go".
     - The browser version of Figma cannot import development plugins.
   - **Success:** report the open file name and the current page. Do not call write tools.
   - If a run exists, record the outcome with `S2S figma-check ...` (see /spec2ship step 4).
3. Do **not** install anything, edit settings, or add or remove MCP servers yourself. Print the exact commands for
   the developer to run:
   - **Everything at once:** the installer in the plugin folder checks each item and installs only what is missing,
     asking before each install.
     - Windows: `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/install/install.ps1"`
     - macOS/Linux: `bash "${CLAUDE_PLUGIN_ROOT}/install/install.sh"`
   - **Harness:** `/plugin marketplace add Chachamaru127/claude-code-harness` and
     `/plugin install harness@claude-code-harness-marketplace`.
   - **Node.js 20+**, if `node-runtime` failed.
   - **Other Figma servers:** if preflight reports `figma-other-server`, the developer's own figma-mcp-go can stay:
     instances share port 1994 (one leader, the others follow). Removing it is optional.
4. Summarize: READY / READY WITH WARNINGS / BLOCKED, the list of what is still missing, and the next command
   (`/spec2ship <figma-url> --ba <path>`; Figma and the BA document are each optional, see README).
