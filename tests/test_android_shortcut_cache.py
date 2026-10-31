#!/usr/bin/env python3
"""No-VM regression tests for a disposable Android ShortcutService experiment."""
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"profiles/android-arm64/scripts/patch-shortcut-cache-experiment.py"
BOOT=ROOT/"profiles/android-arm64/scripts/boot-restored.sh"

class ShortcutCacheTests(unittest.TestCase):
    def test_inject_once_only_and_no_base_edit(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)/"base.sh"
            copy=Path(d)/"copy.sh"
            baseline="#!/bin/sh\nstop zygote; start zygote\n"
            base.write_text(baseline)
            copy.write_text(baseline)
            for _ in range(2):
                r=subprocess.run([sys.executable,str(PATCH),str(copy)],capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(base.read_text(),baseline)
            output=copy.read_text()
            self.assertEqual(output.count("SHORTCUT_CACHE_RESET_V1"),1)
            self.assertIn("stop zygote\n",output)
            self.assertIn("start zygote\n",output)
            self.assertIn("mv /data/system_ce/0/shortcut_service /data/local/tmp/vmfabric-shortcut-cache-backup",output)
            self.assertLess(output.index("stop zygote\n"),output.index("mv /data/system_ce"))
            self.assertLess(output.index("mv /data/system_ce"),output.index("start zygote\n"))
            self.assertIn("setprop persist.sys.safemode 0",output)

    def test_fail_closed_on_modified_upstream(self):
        with tempfile.TemporaryDirectory() as d:
            script=Path(d)/"script.sh"
            for baseline in ("start zygote\n", "stop zygote; start zygote\nsetprop persist.sys.safemode 1\n"):
                script.write_text(baseline)
                r=subprocess.run([sys.executable,str(PATCH),str(script)],capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0)
                self.assertEqual(script.read_text(),baseline)

    def test_restored_boot_only_and_safemode_guard(self):
        code=BOOT.read_text()
        self.assertIn('ANDROID_SHORTCUT_TEST:-baseline}" = "cache-reset"',code)
        self.assertIn('"$SESSION/upstream-src-cache-reset"',code)
        self.assertIn('patch-shortcut-cache-experiment.py',code)
        self.assertIn('Cache reset ran in Safe Mode',code)
        self.assertIn('qemu-img check -f qcow2',code)
        self.assertIn('IMMUTABLE_BASE_QCOW2_HASH_CHANGED',code)

if __name__=="__main__": unittest.main()
