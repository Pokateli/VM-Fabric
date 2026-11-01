#!/usr/bin/env python3
"""Android ARM64 live PackageManager readiness must not pass 'not found'."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"profiles/android-arm64/scripts/verify.py"
spec=importlib.util.spec_from_file_location("android_live_verify",FILE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AndroidLiveVerifyTests(unittest.TestCase):
    def test_exact_found_only(self):
        self.assertTrue(module.package_service_ready(0,"Service package: found\n"))
        for raw in (
            "Service package: not found\n",
            "Service package: found but restarted",
            "Service other: found\n",
            "",
            "not found",
            "Service package: found\nService package: not found",
        ):
            with self.subTest(text=raw):
                self.assertFalse(module.package_service_ready(0,raw))
    def test_nonzero_exit_even_when_found(self):
        self.assertFalse(module.package_service_ready(1,"Service package: found"))
        self.assertFalse(module.package_service_ready(124,"Service package: found"))

if __name__=="__main__":
    unittest.main()
