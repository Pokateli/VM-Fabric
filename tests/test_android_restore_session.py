#!/usr/bin/env python3
"""Synthetic no-binary test of safe Android ARM64 data overlay restore."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"profiles/android-arm64/scripts/prepare-restore.py"
spec=importlib.util.spec_from_file_location("vmfabric_android_prepare_restore",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class RestoreSessionTests(unittest.TestCase):
    def setUp(self):
        f=tempfile.TemporaryDirectory()
        self.addCleanup(f.cleanup)
        self.home=Path(f.name)
        self.root=self.home/"kit"
        paths={
          "build/userdata-arm64.qcow2":b"FAKE_BASE_DISK",
          "build/ramdisk-wrap.img":b"FAKE_RAMDISK",
          "sdk/emulator/qemu/linux-x86_64/qemu-system-aarch64-headless":b"FAKE_EMULATOR",
          "sdk/system-images/android-28/google_apis/arm64-v8a/source.properties":b"AndroidVersion.ApiLevel=28\nSystemImage.Abi=arm64-v8a\n",
          "proof/STABILITY_RESULT.txt":b"PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE\n",
          "proof/GUI_RESULT.txt":b"LAUNCHER_HOME_EVIDENCE\n"
        }
        for p,data in paths.items():
            dest=self.root/p
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(data)
    def create_overlay(self,cmd,**kw):
        self.assertEqual(cmd[:6],["qemu-img","create","-f","qcow2","-F","qcow2"])
        Path(cmd[-1]).write_bytes(b"FAKE_OVERLAY")
        return SimpleNamespace(returncode=0)
    def test_original_image_is_not_modified_by_new_session(self):
        dest=self.home/"session"
        with patch.object(m.subprocess,"check_output",return_value='{"format":"qcow2"}'),\
             patch.object(m.subprocess,"run",side_effect=self.create_overlay):
            m.prepare(self.root,dest)
        self.assertEqual((self.root/"build/userdata-arm64.qcow2").read_bytes(),b"FAKE_BASE_DISK")
        self.assertEqual((dest/"build/userdata-arm64.qcow2").read_bytes(),b"FAKE_OVERLAY")
        self.assertTrue((dest/"build/ramdisk-wrap.img").is_symlink())
        manifest=json.loads((dest/"session.json").read_text())
        self.assertTrue(manifest["base_immutable"])
        self.assertEqual(manifest["guest_abi"],"arm64-v8a")
    def test_refuses_overwrite_and_nested_sessions(self):
        dest=self.home/"session"
        dest.mkdir()
        with self.assertRaisesRegex(ValueError,"already exists"):
            m.prepare(self.root,dest)
        with self.assertRaisesRegex(ValueError,"outside immutable"):
            m.prepare(self.root,self.root/"session")
    def test_requires_stable_launch_proof(self):
        (self.root/"proof/GUI_RESULT.txt").write_text("BLACK_FRAMEBUFFER\n")
        with self.assertRaisesRegex(ValueError,"Launcher3"):
            m.prepare(self.root,self.home/"session")

if __name__=="__main__":unittest.main()
