# Spec2Ship read-only Figma bridge

A read-only fork of [gethopp/figma-mcp-bridge](https://github.com/gethopp/figma-mcp-bridge), vendored and built by
Spec2Ship so that users install nothing extra and nothing is downloaded when Claude Code starts the server.

| | |
|---|---|
| Upstream | https://github.com/gethopp/figma-mcp-bridge |
| Version | tag `v0.0.26`, commit `0a55fa405545edb00b8cd856f842257facad685e` (2026-11-09) |
| License | MIT, Copyright (c) 2026 GETHOPP LTD (see `LICENSE.md`); bundled npm packages: `THIRD_PARTY_LICENSES.md` |
| Fork version | `0.0.26-spec2ship.1` |
| Changes | `spec2ship-readonly.patch` (diff against the upstream tag) |

## Why this fork

- Spec2Ship 0.2.0 ran `npx -y @vkhanhqui/figma-mcp-go@0.1.3`. That package's GitHub repository has been disabled
  following a DMCA notice from the authors of figma-mcp-bridge
  ([github/dmca 2026-07-01](https://github.com/github/dmca/blob/master/2026/07/2026-07-01-figma-mcp-bridge.md)).
  Spec2Ship no longer uses it.
- Upstream exposes 56 tools, most of which edit the design. Spec2Ship only reads designs.
- Upstream is run through `npx`, which downloads code each time it is not cached. Spec2Ship ships the built server.

## What the patch changes

1. **Read-only, enforced three times:**
   - **MCP server:** only the 14 read tools are registered (`server/src/readonly.ts`).
   - **Leader `/rpc` endpoint:** returns 403 for any other tool, whoever sends it. This covers a follower process
     started from another configuration.
   - **Figma plugin:** refuses every request that is not one of the 13 plugin-side reads. A design therefore cannot
     be modified through this bridge, even by a modified or third-party server.
2. **Removed:**
   - every `set_*`, `create_*`, layout, grouping and animation tool;
   - `delete_nodes`;
   - `set_selection` and `scroll_and_zoom_into_view`;
   - `run_script`;
   - `save_screenshots`, which wrote local files.
3. **Own port, 3994 (upstream uses 1994).** This build never joins the leader election of a stock figma-mcp-bridge
   or figma-mcp-go. The plugin manifest's `networkAccess` allows only `ws://localhost:3994`, and the leader still
   binds `127.0.0.1` only.
4. **Renamed:** plugin "Spec2Ship Figma Bridge (read-only)", id `spec2ship-figma-bridge-readonly`, editors Figma and
   Dev Mode. MCP server name `spec2ship-figma-bridge`.
5. **Constant `VERSION`**, so the server bundles into a single file (`dist/server.mjs`, Node 20+).

## Read tools kept

`list_files`, `get_document`, `get_selection`, `get_layout_tree`, `get_node`, `get_prototype_connections`,
`trace_prototype_flow`, `get_styles`, `get_metadata`, `get_design_context`, `get_variable_defs`, `get_screenshot`,
`get_motion_styles`, `get_node_motion`.

In Claude Code they appear as `mcp__plugin_spec2ship_figma-bridge__<tool>`.

## Review notes (Spec2Ship maintainers, 2026-11-10)

We read the server source: `index.ts`, `node.ts`, `election.ts`, `leader.ts`, `follower.ts`, `bridge.ts`, and the tool
registration and screenshot paths in `tools.ts`. We also read the plugin's request dispatcher and its message entry
point (`code.ts`) and its WebSocket client (`App.tsx`).

- **Network:**
  - The server listens on 127.0.0.1 only.
  - `/rpc` accepts loopback callers without an `Origin` header.
  - The plugin connects only to localhost.
  - Followers and the leader election only call the leader on localhost.
  - The only outbound fetch is in `create_image` (image URLs), which is removed in this build.
- **Filesystem:** local file reads exist only in `create_image` and `create_svg` (workspace image and SVG files), and
  file writes only in `save_screenshots`. All three are removed.
- **Not reviewed line by line:** the serializer and prototype readers (read-only data shaping), and the html-figma
  importer, which is only reachable through the removed `import_html_layers`.

## Verification

- **`dist/server.mjs`**, sha256 `6ae72386b2e430602c3603b78e893360f3b93eea49e4076b275a5bef16f258df`, built with
  esbuild 0.24.2 from `server/package-lock.json`.
  - `tools/list` returns exactly the 14 read tools; `delete_nodes` returns "Tool not found".
  - `/rpc` returns 403 for `delete_nodes`, `set_text_content`, `run_script` and `save_screenshots`, and forwards
    `get_metadata`.
  - Covered by `tests/smoke/test_figma_bridge.py`.
- **Figma plugin (`plugin/dist`):** built with `bash vendor/figma-bridge/build.sh plugin`; see the hashes below.

## Updating to a new upstream release

1. Clone the upstream repository at the new tag and apply `spec2ship-readonly.patch`. Resolve conflicts and re-check
   that the new upstream tools are classified, read versus write, in both allowlists.
2. Copy `server/` and `plugin/` sources here and run `bash vendor/figma-bridge/build.sh`.
3. Update this file (tag, commit, hashes), `THIRD_PARTY_LICENSES.md`, and the Spec2Ship CHANGELOG. Run the tests.
