#!/usr/bin/env python3
"""Offline tests for explicit no-network Android ARM64 ChatGPT smoke entrypoint."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"profiles/android-arm64/scripts/run-chat-smoke.sh"
HERE=SCRIPT.parent

class AndroidChatSmokeTests(unittest.TestCase):
    def test_bash_syntax_and_missing_arguments(self):
        p=subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        p=subprocess.run(["bash",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(p.returncode,2)
        self.assertIn("Usage:",p.stderr)
    def test_never_download_or_mutate_private_base(self):
        code=SCRIPT.read_text()
        self.assertNotIn("gh release download",code)
        self.assertNotIn("curl ",code)
        self.assertNotIn("wget ",code)
        self.assertNotIn("apt-get",code)
        self.assertNotIn("upload-artifact",code)
        self.assertNotIn("rm -rf",code)
        self.assertIn('[[ ! -e "$SESSION" && ! -L "$SESSION" ]]',code)
        self.assertIn('prepare-restore.py',code)
        self.assertIn('ANDROID_SHORTCUT_TEST=observe',code)
        self.assertLess(code.index('prepare-restore.py'),code.index('boot-restored.sh'))
    def test_memory_and_netns_hard_gates_before_disk(self):
        code=SCRIPT.read_text()
        self.assertIn('(( EUID == 0 ))',code)
        self.assertIn("unshare --net -- bash -c 'ip link set lo up'",code)
        self.assertIn("unshare --user --map-root-user --net -- bash -c 'ip link set lo up'",code)
        self.assertIn("ANDROID_NETNS=user-map-root",code)
        self.assertIn('host-memory-budget.py',code)
        self.assertIn('--requested "$RAM"',code)
        self.assertIn('if [[ "$RAM" == auto ]] && (( MEM > 2304 )); then',code)
        self.assertIn('MEM=2304',code)
        self.assertIn('"${NETNS[@]}" bash -Eeuo pipefail -c',code)
        self.assertLess(code.index('host-memory-budget.py'),code.index('prepare-restore.py'))
        self.assertLess(code.index("Host disallows isolated network namespace"),
                        code.index('prepare-restore.py'))
    def test_legacy_unverified_profile_remains_experimental(self):
        import json
        p=json.loads((ROOT/"profiles/android-arm64/profile.json").read_text())
        self.assertEqual(p["status"],"experimental")
        self.assertEqual(p["runtime"],[])
        self.assertEqual(p["minimum_guest_ram_mib"],4096)

if __name__=="__main__":unittest.main()
