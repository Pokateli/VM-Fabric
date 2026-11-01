#!/usr/bin/env python3
"""Smoke is allowed for experimental Android, but ordinary run stays disabled."""
import argparse
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import vmfabric

class AndroidSmokeCliTests(unittest.TestCase):
    def test_explicit_smoke_dispatches_to_safe_local_script(self):
        args=argparse.Namespace(operation="smoke",profile="android-arm64",
             target=Path("/tmp/offline-kit"),session=Path("/tmp/new-session"),ram="2304")
        with patch.object(vmfabric.subprocess,"call",return_value=0) as called:
            self.assertEqual(vmfabric.launch(args),0)
        argv=called.call_args.args[0]
        self.assertEqual(argv[0],"bash")
        self.assertEqual(Path(argv[1]).name,"run-chat-smoke.sh")
        self.assertEqual(argv[2:],["--kit","/tmp/offline-kit","--session","/tmp/new-session","--ram","2304"])
    def test_other_profiles_cannot_use_experimental_smoke(self):
        for profile in ("debian13","debian13-arm64","tiny11"):
            args=argparse.Namespace(operation="smoke",profile=profile,target=None,
                session=Path("/tmp/new-session"),ram="auto")
            with self.assertRaisesRegex(ValueError,"only for android-arm64"):
                vmfabric.launch(args)
    def test_experimental_android_ordinary_run_stays_denied(self):
        p,_=vmfabric.load_profile("android-arm64")
        self.assertEqual(p["status"],"experimental")
        self.assertEqual(p["runtime"],[])
        with self.assertRaisesRegex(ValueError,"execution disabled"):
            vmfabric.ready(p)
        self.assertTrue(vmfabric.script_path(p,ROOT/"profiles/android-arm64","smoke_script").is_file())

if __name__=="__main__":unittest.main()
