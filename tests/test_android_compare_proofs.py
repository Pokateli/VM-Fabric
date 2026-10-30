#!/usr/bin/env python3
"""Ensure Android ARM64 proof comparisons never promote intermittent services."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SRC=Path(__file__).resolve().parents[1]/"profiles/android-arm64/scripts/compare-proofs.py"
spec=importlib.util.spec_from_file_location("android_compare",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def artifact(path,pids,status):
    samples=[{"passed":pid=="1613","system_server_pid":{"stdout":pid}}
             for pid in pids]
    files={"stability-report.json":json.dumps({"observations":samples}),
           "STABILITY_RESULT.txt":status,
           "android-properties.txt":"ANDROID_ABI=arm64-v8a\n",
           "emulator-tail.log":("DEBUG: pid: 1613, tid: 1793, name: Binder >>> system_server <<<\n"
                               "DEBUG: signal 11 (SIGSEGV)\n"
                               "DEBUG: #00 pc libart.so art::RememberForGcArgumentVisitor::Visit\n"),
           "GUI_RESULT.txt":"BLACK_FRAMEBUFFER\n"}
    with zipfile.ZipFile(path,"w") as z:
        for name,s in files.items():z.writestr(name,s)

class CompareTests(unittest.TestCase):
    def test_interrupted_android_is_not_reported_stable(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"unstable.zip"
            artifact(p,["1613","1613","2405","2405","2405"],
                     "FAIL_UNSTABLE_ANDROID_ARM64_PACKAGE_SERVICE")
            s=m.summary(p)
            self.assertFalse(s["stable"])
            self.assertEqual(s["system_server_pid_changes"],1)
            self.assertEqual(s["art_segv"],1)
            self.assertEqual(s["hwui_segv"],0)
            self.assertEqual(s["gui"],"BLACK_FRAMEBUFFER")
    def test_stable_gate_requires_exact_marker_and_identical_pids(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"marked-but-flapping.zip"
            artifact(p,["1613","1613","2405","2405","2405"],
                     "PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE")
            self.assertFalse(m.summary(p)["stable"])
            artifact(p,["1613"]*5,"PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE")
            self.assertTrue(m.summary(p)["stable"])
if __name__=="__main__":
    unittest.main()
