#!/usr/bin/env python3
"""Ensure Android ARM64 nested shell and readiness gate cannot regress.

The 2026-10-30 GitHub workflow failed before QEMU launch when an apostrophe
inside a YAML single-quoted bash -c payload ended the shell string early.
"""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
FLOW=ROOT/".github/workflows/build-android-arm64.yml"

class AndroidWorkflowSafetyTests(unittest.TestCase):
    def test_netns_nested_bash_c_has_no_unescaped_apostrophe(self):
        text=FLOW.read_text()
        start='unshare --net -- bash -Eeuo pipefail -c '+"'"
        end="' _ \"$RUNNER_TEMP/android-arm-tcg\""
        self.assertEqual(text.count(start),1)
        begin=text.index(start)+len(start)
        finish=text.index(end,begin)
        body=text[begin:finish]
        self.assertNotIn("'",body,"single quote breaks surrounding shell -c command")
        # Strip YAML indentation and assert the payload parses as bash.
        script="\n".join(line[14:] if line.startswith(" "*14) else line
                         for line in body.splitlines())
        check=subprocess.run(["bash","-n","-c",script],capture_output=True,text=True)
        self.assertEqual(check.returncode,0,check.stderr)
        self.assertIn("verify-stable-ready.py",script)

    def test_exact_package_manager_gate_not_false_positive(self):
        text=FLOW.read_text()
        self.assertNotIn("grep -qi found",text.split("run: |")[-1])
        self.assertIn("grep -Eq",text)
        self.assertIn("PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE",text)
        self.assertIn("qemu-img check -f qcow2",text)

if __name__=="__main__":
    unittest.main()
