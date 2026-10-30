#!/usr/bin/env python3
"""Test isolated opt-in Android 9 ShortcutService safe-mode investigation."""
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"profiles/android-arm64/scripts/patch-safemode-experiment.py"

class ShortcutSafeModeTests(unittest.TestCase):
    def test_opt_in_patched_copy_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/"upstream/40-bringup.sh"
            source.parent.mkdir()
            source.write_text("#!/bin/sh\nstop zygote; start zygote\n")
            isolated=Path(t)/"session/40-bringup.sh"
            isolated.parent.mkdir()
            isolated.write_bytes(source.read_bytes())
            for _ in range(2):
                r=subprocess.run([sys.executable,str(PATCH),str(isolated)],
                                 capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
            self.assertNotIn("persist.sys.safemode",source.read_text())
            code=isolated.read_text()
            self.assertEqual(code.count("setprop persist.sys.safemode 1"),1)
            self.assertLess(code.index("setprop persist.sys.safemode 1"),
                            code.index("stop zygote; start zygote"))
    def test_pinned_script_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/"40-bringup.sh"
            file.write_text("start zygote\n")
            r=subprocess.run([sys.executable,str(PATCH),str(file)],
                             capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("Unknown zygote restart site",r.stderr)
            self.assertEqual(file.read_text(),"start zygote\n")

if __name__=="__main__":unittest.main()
