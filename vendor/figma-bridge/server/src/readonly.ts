// Spec2Ship read-only build (not part of upstream gethopp/figma-mcp-bridge).
// Only tools that read the open Figma document are registered, accepted over /rpc,
// or (in the plugin) executed. Everything that edits the design, the selection/viewport,
// runs scripts or writes local files is removed.

export const READ_ONLY_TOOLS: ReadonlySet<string> = new Set([
  "list_files",
  "get_document",
  "get_selection",
  "get_layout_tree",
  "get_node",
  "get_prototype_connections",
  "trace_prototype_flow",
  "get_styles",
  "get_metadata",
  "get_design_context",
  "get_variable_defs",
  "get_screenshot",
  "get_motion_styles",
  "get_node_motion",
]);

export function isReadOnlyTool(name: string): boolean {
  return READ_ONLY_TOOLS.has(name);
}

export const READ_ONLY_REFUSAL =
  "This tool is not available in the Spec2Ship read-only Figma bridge (design edits are disabled).";

/** Wraps an McpServer so that `tool(name, ...)` silently skips every non read-only tool. */
export function readOnlyServer<T extends { tool: (...args: any[]) => unknown }>(server: T): T {
  return new Proxy(server, {
    get(target, prop, receiver) {
      if (prop === "tool") {
        return (name: string, ...rest: unknown[]) =>
          isReadOnlyTool(name) ? (target.tool as (...a: unknown[]) => unknown).call(target, name, ...rest) : undefined;
      }
      const value = Reflect.get(target, prop, receiver);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
}
