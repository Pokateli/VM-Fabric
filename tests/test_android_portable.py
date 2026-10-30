#!/usr/bin/env python3
"""Synthetic offline Android-arm64 private-kit roundtrip and tampering tests.

No Google image bytes, Android binaries, or network access are used.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/"profiles/android-arm64/scripts/portable-kit.py"
PARTS=(
 "sdk/system-images/android-28/google_apis/arm64-v8a/system.img",
 "sdk/system-images/android-28/google_apis/arm64-v8a/vendor.img",
 "sdk/system-images/android-28/google_apis/arm64-v8a/kernel-ranchu",
 "sdk/system-images/android-28/google_apis/arm64-v8a/source.properties",
 "sdk/emulator/qemu/linux-x86_64/qemu-system-aarch64-headless",
 "sdk/emulator/.pinned",
 "sdk/platform-tools/adb",
 "build/ramdisk-wrap.img",
 "build/userdata-arm64.qcow2",
 "upstream-src/scripts/40-bringup.sh",
 "proof/RESULT.txt",
)
PROPS="AndroidVersion.ApiLevel=28\nSystemImage.Abi=arm64-v8a\nSystemImage.TagId=google_apis\n"

class AndroidPortableKitTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.home=Path(t.name)
        self.src=self.home/"source"
        self.chunks=self.home/"chunks"
        for name in PARTS:
            target=self.src/name
            target.parent.mkdir(parents=True,exist_ok=True)
            payload=(name+" synthetic-only").encode()
            if name.endswith("source.properties"):payload=PROPS.encode()
            if name.endswith("emulator/.pinned"):payload=b"16489710\n"
            if name.endswith("proof/RESULT.txt"):payload=b"PASS_REAL_ANDROID_ARM64_TCG_BOOT\n"
            target.write_bytes(payload)
        # Root model contains a private SDK cache which must not be transported.
        (self.src/"sdk/dl").mkdir()
        (self.src/"sdk/dl/stale.zip").write_bytes(b"stale" * 128)

    def call(self,action,a,b):
        return subprocess.run([sys.executable,str(PACK),action,str(a),str(b)],
                              text=True,capture_output=True)

    def test_exact_abi_roundtrip_and_skip_download_caches(self):
        x=self.call("pack",self.src,self.chunks)
        self.assertEqual(x.returncode,0,x.stderr)
        manifest=json.loads((self.chunks/"android-arm64-parts.json").read_text())
        self.assertEqual(manifest["abi"],"arm64-v8a")
        self.assertTrue(manifest["private"])
        self.assertEqual(len(manifest["parts"]),1)
        dest=self.home/"restore"
        y=self.call("unpack",self.chunks,dest)
        self.assertEqual(y.returncode,0,y.stderr)
        for name in PARTS:
            self.assertEqual((dest/name).read_bytes(),(self.src/name).read_bytes())
        self.assertFalse((dest/"sdk/dl/stale.zip").exists())

    def test_refuses_synthetic_unverified_boot_proof(self):
        (self.src/"proof/RESULT.txt").write_text("BOOT_STARTED_BUT_NO_PACKAGE_SERVICE\n")
        x=self.call("pack",self.src,self.chunks)
        self.assertNotEqual(x.returncode,0)
        self.assertIn("Refuse to pack Android",x.stderr)

    def test_refuses_wrong_abi(self):
        p=self.src/"sdk/system-images/android-28/google_apis/arm64-v8a/source.properties"
        p.write_text(PROPS.replace("arm64-v8a","x86_64"))
        x=self.call("pack",self.src,self.chunks)
        self.assertNotEqual(x.returncode,0)
        self.assertIn("Wrong Android guest",x.stderr)

    def test_detects_transport_corruption(self):
        x=self.call("pack",self.src,self.chunks)
        self.assertEqual(x.returncode,0,x.stderr)
        p=self.chunks/"part-000.bin"
        with p.open("r+b") as f:
            f.seek(30)
            orig=f.read(1)
            f.seek(30)
            f.write(bytes([orig[0]^0x80]))
        y=self.call("unpack",self.chunks,self.home/"restore")
        self.assertNotEqual(y.returncode,0)
        self.assertFalse((self.home/"restore/proof/RESULT.txt").is_file())

if __name__=="__main__":
    unittest.main()
