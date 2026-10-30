#!/usr/bin/env python3
"""Pin/validate opt-in legacy HWUI renderer workaround for Android 9 ARM64."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"profiles/android-arm64/scripts/patch-hwui-experiment.py"

class AndroidHwuiExperimentTests(unittest.TestCase):
    def test_legacy_gl_experiment_does_not_mutate_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            script=Path(td)/"40-bringup.sh"
            original="#!/bin/sh\nstop zygote; start zygote\n"
            script.write_text(original)
            base=subprocess.run([sys.executable,str(SCRIPT),str(script)],capture_output=True,text=True)
            self.assertEqual(base.returncode,0,base.stderr)
            self.assertEqual(script.read_text(),original)
            for _ in range(2):
                result=subprocess.run([sys.executable,str(SCRIPT),str(script),
                                        "--mode","legacy-opengl"],
                                      capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            edited=script.read_text()
            self.assertEqual(edited.count("setprop debug.hwui.renderer opengl"),1)
            self.assertTrue(edited.index("setprop debug.hwui.renderer opengl")<
                            edited.index("stop zygote; start zygote"))
    def test_refuses_unknown_upstream_script(self):
        with tempfile.TemporaryDirectory() as td:
            script=Path(td)/"40-bringup.sh"
            script.write_text("start zygote\n")
            p=subprocess.run([sys.executable,str(SCRIPT),str(script),
                              "--mode","legacy-opengl"],capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("Pinned zygote",p.stderr)
if __name__=="__main__":
    unittest.main()
