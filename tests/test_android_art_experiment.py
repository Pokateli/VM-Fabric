#!/usr/bin/env python3
"""Conservative pinned ART no-JIT experiment, never applied to baseline."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"profiles/android-arm64/scripts/patch-art-experiment.py"

class AndroidArtExperimentTests(unittest.TestCase):
    def test_baseline_is_read_only_and_opt_in_nojit_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            sh=Path(temp)/"40-bringup.sh"
            text="#!/bin/sh\n# restart zygote\nstop zygote; start zygote\n"
            sh.write_text(text)
            baseline=subprocess.run([sys.executable,str(SCRIPT),str(sh)],
                                    capture_output=True,text=True)
            self.assertEqual(baseline.returncode,0,baseline.stderr)
            self.assertEqual(sh.read_text(),text)
            for _ in range(2):
                p=subprocess.run([sys.executable,str(SCRIPT),str(sh),
                                  "--mode","nojit"],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
            updated=sh.read_text()
            self.assertEqual(updated.count("setprop dalvik.vm.usejit false"),1)
            self.assertEqual(updated.count("stop zygote; start zygote"),1)
            self.assertLess(updated.index("setprop dalvik.vm.usejit false"),
                            updated.index("stop zygote; start zygote"))

    def test_refuses_changed_upstream_zygote_script(self):
        with tempfile.TemporaryDirectory() as temp:
            sh=Path(temp)/"40-bringup.sh"
            sh.write_text("reboot\n")
            p=subprocess.run([sys.executable,str(SCRIPT),str(sh),"--mode","nojit"],
                             capture_output=True,text=True)
            self.assertNotEqual(p.returncode,0)
            self.assertIn("unexpected",p.stderr.lower())
            self.assertEqual(sh.read_text(),"reboot\n")

if __name__=="__main__":
    unittest.main()
