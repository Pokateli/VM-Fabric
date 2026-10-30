#!/usr/bin/env python3
"""Regression tests for the real Android ARM64 init failure seen in GitHub run 41042485490."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATCH=ROOT/"profiles/android-arm64/scripts/patch-guest-selinux.py"
GATE=ROOT/"profiles/android-arm64/scripts/boot-gate.sh"

class AndroidBootRecovery(unittest.TestCase):
    def test_early_selinux_patch_is_pinned_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            launcher=Path(tmp)/"30-launch.sh"
            before='  -memory "$MEM" -cores "$CORES" -no-window -no-audio'
            launcher.write_text("#!/bin/sh\n"+before+"\n")
            for _ in range(2):
                proc=subprocess.run([sys.executable,str(PATCH),str(launcher)],
                                    capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
            after=launcher.read_text()
            self.assertEqual(after.count("-selinux permissive"),1)
            self.assertNotIn(before,after)
            # Unknown upstream revisions must fail closed (no write).
            launcher.write_text("#!/bin/sh\n-messed-up-new-emulator-arguments\n")
            proc=subprocess.run([sys.executable,str(PATCH),str(launcher)],
                                capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn("Unexpected launcher contents",proc.stderr)

    def test_stopped_guest_fails_fast_instead_of_waiting_for_adb(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"src/scripts").mkdir(parents=True)
            (root/"src/scripts/40-bringup.sh").write_text("#!/bin/sh\nsleep 20\n")
            (root/"build").mkdir()
            (root/"build/emu.log").write_text(
                "[6.653] init: restorecon failed of /init failed: Operation not permitted\n"
                "[6.654] init: Reboot start, reason: reboot, rebootTarget: bootloader\n"
                "Reboot failed -- System halted\n")
            result=subprocess.run(
                ["bash",str(GATE),str(root/"src"),str(root/"build"),str(root/"proof")],
                capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,83,result.stdout+result.stderr)
            self.assertEqual((root/"proof/boot-gate-result.txt").read_text().strip(),
                             "GUEST_FATAL_EARLY_INIT_STOP")
            self.assertIn("restorecon failed", (root/"proof/guest-fatal.txt").read_text())

if __name__=="__main__":
    unittest.main()
