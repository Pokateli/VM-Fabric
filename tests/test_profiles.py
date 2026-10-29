#!/usr/bin/env python3
"""Tests for VM-Fabric profile registry without booting a VM."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import vmfabric


class ProfilesTest(unittest.TestCase):
    def test_debian_ready(self):
        p, folder = vmfabric.load_profile("debian13")
        self.assertEqual(p["status"], "ready")
        self.assertEqual(p["release_tag"], "debian13-v1.2.0-fabric")
        self.assertIn("github", p["runtime"])
        self.assertTrue(vmfabric.script_path(p, folder, "run_script").is_file())

    def test_tiny11_is_intentionally_disabled(self):
        p, _ = vmfabric.load_profile("tiny11")
        with self.assertRaisesRegex(ValueError, "execution disabled"):
            vmfabric.ready(p)

    def test_reject_path_traversal(self):
        for value in ("../debian13", "/tmp", "debian13/../../secret", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    vmfabric.load_profile(value)

    def test_source_checksum_is_independent_of_legacy(self):
        p, _ = vmfabric.load_profile("debian13")
        self.assertEqual(p["bundle_asset"], "debian13-qemu-bundle.tar.gz")
        self.assertNotIn("Debian13-ChatGPT-VM", p["release_tag"])
        self.assertTrue(vmfabric.script_path(p, ROOT / "profiles" / p["id"], "build_script").is_file())

    def test_cli_listing_and_disabling(self):
        proc = subprocess.run([sys.executable, str(ROOT / "vmfabric.py"), "list"],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("debian13", proc.stdout)
        self.assertIn("tiny11", proc.stdout)
        disabled = subprocess.run(
            [sys.executable, str(ROOT / "vmfabric.py"), "run", "tiny11", "--command", "echo test"],
            capture_output=True, text=True)
        self.assertEqual(disabled.returncode, 2)
        self.assertIn("execution disabled", disabled.stderr)


if __name__ == "__main__":
    unittest.main()
