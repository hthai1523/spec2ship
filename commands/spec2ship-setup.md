---
description: Check every Spec2Ship prerequisite (Python, Node.js, PDF extractor, claude-code-harness, bundled Figma bridge and its Figma Desktop plugin) and list exactly what is missing
argument-hint: (no arguments)
---

# /spec2ship-setup

`S2S` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/spec2ship.py"` (use `python` on Windows if needed).

1. Run `S2S preflight` from the project root (results are saved to the run only when a run exists). Show every
   line, grouped OK / WARN / FAIL, with the suggested fix.
2. Check the Figma bridge yourself by calling `mcp__plugin_spec2ship_figma-bridge__list_files`.
   - **Spec2Ship bundles the server.** It is a read-only build in `vendor/figma-bridge`, and Claude Code starts it
     with the plugin. Nothing is downloaded and no `claude mcp add` is needed.
   - **Tool not available:** the bundled server did not start. The usual cause is Node.js 20+ missing (see
     `node-runtime` in preflight). Check `/mcp`, fix the cause, restart Claude Code.
   - **Empty list or `No plugin connected`:** Figma Desktop is closed, or the plugin is not running.
     - Once per machine: Figma Desktop → Plugins → Development → Import plugin from manifest → select the manifest
       path printed on the preflight `figma-plugin` line.
     - Then open the design file and run "Spec2Ship Figma Bridge (read-only)".
     - The browser version of Figma cannot import development plugins.
   - **Success:** call `get_metadata`, then report the open file name, its file key and the current page.
   - If a run exists, record the outcome with `S2S figma-check ...` (see /spec2ship step 4).
3. Do **not** install anything, edit settings, or add or remove MCP servers yourself. Print the exact commands for
   the developer to run:
   - **Everything at once:** the installer in the plugin folder checks each item and installs only what is missing,
     asking before each install.
     - Windows: `powershell -ExecutionPolicy Bypass -File "${CLAUDE_PLUGIN_ROOT}/install/install.ps1"`
     - macOS/Linux: `bash "${CLAUDE_PLUGIN_ROOT}/install/install.sh"`
   - **Harness:** `/plugin marketplace add Chachamaru127/claude-code-harness` and
     `/plugin install claude-code-harness@claude-code-harness-marketplace`.
   - **Node.js 20+**, if `node-runtime` failed.
   - **Other Figma servers:** if preflight reports `figma-other-server`, the developer's own Figma MCP server can
     stay. It runs separately on port 1994, while Spec2Ship uses port 3994.
4. Summarize: READY / READY WITH WARNINGS / BLOCKED, the list of what is still missing, and the next command
   (`/spec2ship <figma-url> --ba <path>`).
