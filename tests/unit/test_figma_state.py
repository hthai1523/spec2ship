import unittest

from tests.helpers import FIGMA_URL  # noqa: F401
from s2s import figma, state
from s2s.common import Spec2ShipError


class FigmaUrlTests(unittest.TestCase):
    def test_design_url(self):
        info = figma.parse_figma_url(FIGMA_URL)
        self.assertEqual(info["file_key"], "AbCdEf1234567890")
        self.assertEqual(info["node_id"], "12:345")
        self.assertEqual(info["name_slug"], "customer-management")

    def test_variants(self):
        self.assertEqual(figma.parse_figma_url("https://figma.com/file/AbCdEf1234567890/X?node-id=1%3A2")["node_id"], "1:2")
        b = figma.parse_figma_url("https://www.figma.com/design/AbCdEf1234567890/branch/BrAnCh123456/Name")
        self.assertEqual(b["branch_key"], "BrAnCh123456")
        self.assertEqual(b["name_slug"], "Name")
        self.assertIsNone(figma.parse_figma_url("https://www.figma.com/design/AbCdEf1234567890")["node_id"])

    def test_invalid(self):
        for bad in ("", "http://www.figma.com/design/AbCdEf1234567890/x", "https://evil.com/design/AbCdEf1234567890/x",
                    "https://www.figma.com/community/AbCdEf1234567890", "https://www.figma.com/design/short/x",
                    "https://www.figma.com/design/AbCdEf1234567890/x?node-id=abc"):
            with self.assertRaises(Spec2ShipError, msg=bad):
                figma.parse_figma_url(bad)

    def test_open_file_match(self):
        info = figma.parse_figma_url(FIGMA_URL)
        self.assertEqual(figma.match_open_file(info, "Customer Management")["match"], "high")
        self.assertEqual(figma.match_open_file(info, "Customer Management v2")["match"], "medium")
        self.assertEqual(figma.match_open_file(info, "Golf CMS")["match"], "low")
        self.assertEqual(figma.match_open_file(info, None)["match"], "unknown")
        # A file key reported by the bridge (list_files) is decisive, whatever the name says
        self.assertEqual(figma.match_open_file(info, "Golf CMS", info["file_key"])["match"], "high")
        self.assertEqual(figma.match_open_file(info, "Customer Management", "ZZZZZZZZZZZZZZZZ")["match"], "low")


class StateTests(unittest.TestCase):
    def _st(self):
        return {"state": "INIT", "history": [], "approval": None, "retries": {"verification": 0, "max": 2}, "blockers": []}

    def test_happy_path_requires_approval(self):
        st = self._st()
        for s in ("PREFLIGHT", "ANALYSIS", "REQUIREMENT_REVIEW", "PLANNING", "PLAN_REVIEW"):
            state.transition(st, s)
        with self.assertRaisesRegex(Spec2ShipError, "explicit developer approval"):
            state.transition(st, "APPROVED")
        state.mark_approved(st, {"approver": "dev", "plan_hash": "x"})
        self.assertEqual(st["state"], "APPROVED")
        state.transition(st, "EXECUTION")

    def test_illegal_transition(self):
        st = self._st()
        with self.assertRaisesRegex(Spec2ShipError, "Illegal transition"):
            state.transition(st, "EXECUTION")

    def test_replanning_revokes_approval(self):
        st = self._st()
        st.update(state="APPROVED", approval={"approver": "dev"})
        state.transition(st, "PLANNING", "scope change")
        self.assertIsNone(st["approval"])
        self.assertIn("revoked", st["history"][-1]["reason"])

    def test_retry_limit(self):
        st = self._st()
        st.update(state="VERIFICATION", approval={"approver": "dev"})
        state.transition(st, "EXECUTION")
        st["state"] = "VERIFICATION"
        state.transition(st, "EXECUTION")
        st["state"] = "VERIFICATION"
        with self.assertRaisesRegex(Spec2ShipError, "Retry limit"):
            state.transition(st, "EXECUTION")

    def test_block_and_unblock(self):
        st = self._st()
        st["state"] = "PREFLIGHT"
        state.transition(st, "BLOCKED", "harness missing")
        self.assertEqual(st["blockers"], ["harness missing"])
        state.unblock(st)
        self.assertEqual(st["state"], "PREFLIGHT")


if __name__ == "__main__":
    unittest.main()
