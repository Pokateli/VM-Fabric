#!/usr/bin/env python3
"""Android ARM64 profile static security and ABI checks (no Google SDK needed)."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import vmfabric

class AndroidArm64Tests(unittest.TestCase):
    def test_profile_requires_genuine_arm64(self):
        p,folder=vmfabric.load_profile("android-arm64")
        self.assertEqual(p["architecture"],"aarch64")
        self.assertEqual(p["host_architecture"],"x86_64")
        self.assertEqual(p["abi"],"arm64-v8a")
        self.assertEqual(p["driver"],"google-emulator-qemu-aarch64-tcg")
        self.assertEqual(p["acceleration"],"tcg")
        self.assertEqual(p["status"],"experimental")
        self.assertEqual(p["runtime"],[])
        for key in ("bootstrap_script","verify_script","run_script"):
            self.assertTrue(vmfabric.script_path(p,folder,key).is_file())

    def test_no_accidental_launch_of_unverified_android(self):
        p,_=vmfabric.load_profile("android-arm64")
        with self.assertRaisesRegex(ValueError,"execution disabled"):
            vmfabric.ready(p)
        x=subprocess.run([sys.executable,str(ROOT/"vmfabric.py"),"run","android-arm64"],
                         text=True,capture_output=True)
        self.assertEqual(x.returncode,2)
        self.assertIn("execution disabled",x.stderr)

    def test_no_x86_android_or_kvm(self):
        p,_=vmfabric.load_profile("android-arm64")
        self.assertNotIn("kvm",p["acceleration"])
        self.assertEqual(p["upstream"]["commit"],"f9eecf6c0d2fcc1e255b5a6d7322b07cbe017ba9")
        v=(ROOT/"profiles/android-arm64/scripts/verify.py").read_text()
        self.assertIn("system-images/android-28/google_apis/arm64-v8a",v)
        self.assertIn("SystemImage.Abi",v)
        self.assertIn("AndroidVersion.ApiLevel",v)
        self.assertIn("SystemImage.TagId",v)
        self.assertIn('"arm64-v8a"',v)
        source=(ROOT/".github/workflows/build-android-arm64.yml").read_text()
        self.assertIn("ANDROID_I_WANT_MY_TCG",source)
        self.assertIn("unshare --net",source)
        self.assertIn("ro.product.cpu.abi",source)
        self.assertIn("PASS_REAL_ANDROID_ARM64_TCG_BOOT",source)

if __name__=="__main__":
    unittest.main()
