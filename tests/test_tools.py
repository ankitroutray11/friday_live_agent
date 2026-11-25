import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import tools


class TestFridayTools(unittest.TestCase):
    def setUp(self):
        self.orig_ws = tools.DEFAULT_WORKSPACE
        self.tmp = tempfile.mkdtemp(prefix="friday_ws_")
        tools.DEFAULT_WORKSPACE = self.tmp

    def tearDown(self):
        tools.DEFAULT_WORKSPACE = self.orig_ws

    def test_blocked_destructive_commands(self):
        res = tools.run_command("shutdown /s /t 0")
        self.assertIn("blocked by safety policy", res)

    def test_workspace_boundary_enforced(self):
        res = tools.read_file(r"C:\Windows\System32\drivers\etc\hosts")
        self.assertIn("outside workspace", res)

    def test_write_and_read_within_workspace(self):
        w_res = tools.write_file("hello.txt", "world")
        self.assertIn("Successfully saved", w_res)
        r_res = tools.read_file("hello.txt")
        self.assertIn("world", r_res)


if __name__ == "__main__":
    unittest.main()
