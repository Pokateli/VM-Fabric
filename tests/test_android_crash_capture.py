#!/usr/bin/env python3
"""Pure offline tests: crash diagnostics cannot change the guest or overrun output."""
import importlib.util
import contextlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"profiles/android-arm64/scripts/capture-crash.py"
BOOT=ROOT/"profiles/android-arm64/scripts/boot-restored.sh"
spec=importlib.util.spec_from_file_location("vmfabric_android_crash",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class AndroidCrashCaptureTests(unittest.TestCase):
    def test_allowlist_and_traversal_blocked(self):
        self.assertIsNotNone(m.ALLOW_TOMBSTONE.fullmatch("tombstone_12"))
        self.assertIsNone(m.ALLOW_TOMBSTONE.fullmatch("../tombstone_12"))
        self.assertIsNone(m.ALLOW_TOMBSTONE.fullmatch("tombstone_12/../../data"))
    def test_uses_only_readonly_adb_and_bounded_logs(self):
        calls=[]
        def fake(adb,serial,args,timeout=22,limit=512*1024):
            calls.append(args)
            if args==["shell","ls","-t","/data/tombstones"]:
                return {"rc":0,"stdout":b"../bad\ntombstone_03\n","stderr":b""}
            if args[-1]=="/data/tombstones/tombstone_03":
                return {"rc":0,"stdout":b"Fatal signal 11 SIGSEGV system_server ShortcutParser\n","stderr":b""}
            return {"rc":0,"stdout":b"system_server ShortcutService SIGSEGV SECRET=example_canary_123\n","stderr":b""}
        with tempfile.TemporaryDirectory() as d,patch.object(m,"adb_run",side_effect=fake):
            proof=Path(d)
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):
                m.collect(Path("/fake/adb"),"emulator-5554",proof)
            output=stream.getvalue()
            self.assertTrue((proof/"newest-tombstone.txt").is_file())
            self.assertTrue((proof/"crash-analysis.json").is_file())
            self.assertIn("ANDROID_DIAGNOSTICS_COLLECTED",output)
            self.assertIn("ANDROID_CRASH_CLASS=",output)
            self.assertNotIn("SECRET=example_canary_123",output)
            self.assertNotIn("ANDROID_CRASH_LINE=",output)
            self.assertEqual(len(calls),6)
            for args in calls:
                self.assertNotIn("rm",args)
                self.assertNotIn("mv",args)
                self.assertNotIn("push",args)
                self.assertNotIn("pull",args)
    def test_exit_trap_collects_before_qemu_shutdown(self):
        code=BOOT.read_text()
        self.assertIn('trap finish EXIT',code)
        self.assertLess(code.index('capture-crash.py'),code.index('  cleanup\n  exit "$rc"'))
        self.assertIn('ANDROID_SHORTCUT_TEST:-baseline}" != "observe"',code)
        self.assertIn("Observe control must run outside Safe Mode",code)

if __name__=="__main__":unittest.main()
