#!/usr/bin/env python3
"""Real filesystem tests for bounded, offline crash fingerprinting."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"profiles/android-arm64/scripts/analyze-crash.py"
spec=importlib.util.spec_from_file_location("vmfabric_android_crash_analysis",SCRIPT)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CrashAnalysisTests(unittest.TestCase):
    def test_shortcut_parser_art_fault_indicators(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            (d/"newest-tombstone.txt").write_text(
                "pid: 1630, tid: 1644, name: system_server >>> system_server <<<\n"
                "signal 11 (SIGSEGV)\n#00 libart.so artQuickResolutionTrampoline\n"
                "ShortcutParser.createShortcutFromManifest\n"
                "ShortcutService.rescanUpdatedPackagesLocked\n"
            )
            r=m.summarize(d)
            self.assertEqual(r["classification"],"shortcut_manifest_art_sigsegv_indicators")
            self.assertIn(1630,r["possible_pids"])
            self.assertEqual(len(r["fingerprint_sha256"]),64)
    def test_not_label_shortcut_crash_without_signal(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            (d/"logcat-main.txt").write_text("ShortcutService.checkPackageChanges\n")
            r=m.summarize(d)
            self.assertEqual(r["classification"],"shortcut_scan_indicators_no_signal")
    def test_zero_evidence_is_not_a_clean_boot_proof(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            (d/"guest-state.txt").write_text("Service package: found\n")
            r=m.summarize(d)
            self.assertEqual(r["classification"],"no_recognized_crash_markers")
            self.assertNotIn("PASS",r["classification"])
    def test_refuse_missing_or_symlink_inputs(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            with self.assertRaisesRegex(ValueError,"No recognized"):
                m.summarize(d)
            outside=d/"outside"
            outside.write_text("signal 11 SIGSEGV system_server\n")
            (d/"newest-tombstone.txt").symlink_to(outside)
            with self.assertRaisesRegex(ValueError,"No recognized"):
                m.summarize(d)
    def test_large_logs_bounded_and_fingerprint_stable(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t)
            f=d/"logcat-crash.txt"
            core=b"Fatal signal 11 SIGSEGV in system_server\n"
            f.write_bytes(b"X"*(m.MAX_BYTES_PER_FILE+20)+core)
            one=m.summarize(d)
            f.write_bytes(b"Y"*(m.MAX_BYTES_PER_FILE+20)+core)
            two=m.summarize(d)
            self.assertEqual(one["fingerprint_sha256"],two["fingerprint_sha256"])
            self.assertEqual(one["classification"],"system_server_sigsegv_indicators")

if __name__=="__main__": unittest.main()
