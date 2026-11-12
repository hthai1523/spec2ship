"""Runs the bundled read-only Figma bridge (vendor/figma-bridge/dist/server.mjs) and checks it cannot edit designs.

Needs Node.js 20+; skipped otherwise. Uses a free localhost port, never the production port 3994.
"""
import json
import shutil
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request

from tests.helpers import REPO

SERVER = REPO / "vendor" / "figma-bridge" / "dist" / "server.mjs"
READ_TOOLS = {"list_files", "get_document", "get_selection", "get_layout_tree", "get_node", "get_prototype_connections",
              "trace_prototype_flow", "get_styles", "get_metadata", "get_design_context", "get_variable_defs",
              "get_screenshot", "get_motion_styles", "get_node_motion"}
WRITE_SAMPLES = ["delete_nodes", "set_text_content", "create_frame", "set_solid_fill", "run_script", "save_screenshots",
                 "import_html_layers", "set_selection"]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ReadOnlyBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("node not available")
        cls.port = _free_port()
        import os
        env = {**os.environ, "FIGMA_BRIDGE_PORT": str(cls.port), "FIGMA_BRIDGE_HOST": "127.0.0.1"}
        cls.proc = subprocess.Popen([node, str(SERVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=env)
        cls._id = 0
        init = cls.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                       "clientInfo": {"name": "spec2ship-test", "version": "0"}})
        cls.server_info = init["result"]["serverInfo"]
        cls.notify("notifications/initialized")
        cls.tools = {t["name"] for t in cls.call("tools/list")["result"]["tools"]}
        for _ in range(50):  # wait for the leader HTTP endpoint
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/ping", timeout=1).read()
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "proc", None):
            cls.proc.stdin.close()
            try:
                cls.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.proc.kill()
            cls.proc.stdout.close()
            cls.proc.stderr.close()

    @classmethod
    def notify(cls, method):
        cls.proc.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode())
        cls.proc.stdin.flush()

    @classmethod
    def call(cls, method, params=None):
        cls._id += 1
        msg = {"jsonrpc": "2.0", "id": cls._id, "method": method, "params": params or {}}
        cls.proc.stdin.write((json.dumps(msg) + "\n").encode())
        cls.proc.stdin.flush()
        return json.loads(cls.proc.stdout.readline())

    def rpc(self, tool):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/rpc", method="POST",
                                     data=json.dumps({"tool": tool, "nodeIds": ["1:2"], "params": {}}).encode())
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def test_identity(self):
        self.assertEqual(self.server_info["name"], "spec2ship-figma-bridge")
        self.assertTrue(self.server_info["version"].endswith("-spec2ship.1"))

    def test_only_read_tools_are_exposed(self):
        self.assertEqual(self.tools, READ_TOOLS)

    def test_write_tool_call_is_rejected_over_mcp(self):
        res = self.call("tools/call", {"name": "delete_nodes", "arguments": {"nodeIds": ["1:2"]}})
        body = res.get("result") or res.get("error")
        self.assertIn("not found", json.dumps(body))

    def test_leader_rpc_refuses_write_tools(self):
        for tool in WRITE_SAMPLES:
            status, body = self.rpc(tool)
            self.assertEqual(status, 403, tool)
            self.assertIn("read-only", body["error"])

    def test_leader_rpc_forwards_reads(self):
        status, body = self.rpc("get_metadata")
        self.assertEqual(status, 200)
        self.assertIn("No plugin connected", body["error"])  # no Figma in tests: the read reached the bridge

    def test_read_without_figma_reports_plugin_missing(self):
        res = self.call("tools/call", {"name": "get_metadata", "arguments": {}})
        self.assertIn("No plugin connected", res["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
