#!/usr/bin/env python3
"""Android PackageManager stability: never mistake 'not found' for ready."""
import importlib.util
from pathlib import Path
import json
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"profiles/android-arm64/scripts/verify-stable-ready.py"
spec=importlib.util.spec_from_file_location("android_verify_stable",SRC)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def sample(stdout,rc=0):
    return {"stdout":stdout,"stderr":"","exit":rc}

class AndroidStableTests(unittest.TestCase):
    def test_exact_match_not_found_cannot_pass(self):
        self.assertTrue(module.parse_service("Service package: found\r\n"))
        for bad in ("Service package: not found","Service package: found later",
                    "Service package: not found; found", "", "service package: found"):
            self.assertFalse(module.parse_service(bad))

    def test_stability_report_rejects_flapping_package_service(self):
        counter={"n":0}
        def fake(_adb,_serial,command,timeout=15):
            if command==["get-state"]:return sample("device")
            if command[-1]=="ro.product.cpu.abi":return sample("arm64-v8a")
            if command[-1]=="init.svc.zygote":return sample("running")
            if command[-2:]==["pidof","system_server"]:return sample("1777")
            if command[-2:]==["check","package"]:
                counter["n"]+=1
                return sample("Service package: not found" if counter["n"]==3
                              else "Service package: found")
            raise AssertionError(command)
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(module,"run_adb",side_effect=fake),mock.patch.object(module.time,"sleep"):
                with self.assertRaises(SystemExit) as raised:
                    module.verify(Path("adb"),"emulator-5554",Path(td),5,20)
            self.assertEqual(raised.exception.code,87)
            report=json.loads((Path(td)/"stability-report.json").read_text())
            self.assertFalse(report["stable"])
            self.assertEqual([x["passed"] for x in report["observations"]],
                             [True,True,False,True,True])
            self.assertIn("FAIL_UNSTABLE",(Path(td)/"STABILITY_RESULT.txt").read_text())

    def test_service_pid_restart_causes_failure_even_if_package_found(self):
        counter={"pid":0}
        def fake(_adb,_serial,command,timeout=15):
            if command==["get-state"]:return sample("device")
            if command[-1]=="ro.product.cpu.abi":return sample("arm64-v8a")
            if command[-1]=="init.svc.zygote":return sample("running")
            if command[-2:]==["check","package"]:return sample("Service package: found")
            if command[-2:]==["pidof","system_server"]:
                counter["pid"]+=1
                return sample("1888" if counter["pid"]>=3 else "1777")
            raise AssertionError(command)
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(module,"run_adb",side_effect=fake),mock.patch.object(module.time,"sleep"):
                with self.assertRaises(SystemExit) as raised:
                    module.verify(Path("adb"),"emulator-5554",Path(td),5,20)
            self.assertEqual(raised.exception.code,87)
            report=json.loads((Path(td)/"stability-report.json").read_text())
            self.assertFalse(report["stable"])
            self.assertEqual([x["same_server"] for x in report["observations"]],
                             [True,True,False,False,False])

    def test_stable_service_requires_five_confirmed_samples(self):
        def fake(_adb,_serial,command,timeout=15):
            if command==["get-state"]:return sample("device")
            if command[-1]=="ro.product.cpu.abi":return sample("arm64-v8a")
            if command[-1]=="init.svc.zygote":return sample("running")
            if command[-2:]==["pidof","system_server"]:return sample("1777")
            if command[-2:]==["check","package"]:return sample("Service package: found")
            raise AssertionError(command)
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(module,"run_adb",side_effect=fake),mock.patch.object(module.time,"sleep"):
                module.verify(Path("adb"),"emulator-5554",Path(td),5,20)
            report=json.loads((Path(td)/"stability-report.json").read_text())
            self.assertTrue(report["stable"])
            self.assertEqual(report["window_seconds"],80)
            self.assertEqual(sum(x["passed"] for x in report["observations"]),5)

if __name__=="__main__":
    unittest.main()
