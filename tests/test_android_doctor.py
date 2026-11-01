#!/usr/bin/env python3
"""Offline tests for Android ARM64 preflight and VM-Fabric doctor CLI."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"profiles/android-arm64/scripts/doctor.py"
spec=importlib.util.spec_from_file_location("vmfabric_android_doctor",SRC)
doctor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)
sys.path.insert(0,str(ROOT))
import vmfabric

class DoctorTests(unittest.TestCase):
    def test_missing_kit_is_explicit_and_no_runtime_claim(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"not-here"
            with patch.object(doctor,"ram_budget",return_value={"ok":True,"selected_guest_mib":2304}), \
                 patch.object(doctor,"check_network_namespace",return_value={"ok":True,"method":"user-map-root"}), \
                 patch.object(doctor.shutil,"which",return_value="/usr/bin/tool"):
                result=doctor.diagnose(target,"auto")
            self.assertFalse(result["local_smoke_prerequisites_met"])
            self.assertFalse(result["checks"]["private_kit"]["ok"])
            self.assertEqual(result["profile_status"],"experimental")
    def test_missing_qemu_never_reports_ready(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(doctor,"ram_budget",return_value={"ok":True,"selected_guest_mib":2304}), \
                 patch.object(doctor,"check_network_namespace",return_value={"ok":True,"method":"user-map-root"}), \
                 patch.object(doctor,"check_kit",return_value={"ok":True}), \
                 patch.object(doctor.shutil,"which",side_effect=lambda t: None if t=="qemu-img" else "/usr/bin/x"):
                result=doctor.diagnose(Path(d))
            self.assertIn("qemu-img",result["checks"]["required_tools_missing"])
            self.assertFalse(result["local_smoke_prerequisites_met"])
    def test_network_namespace_fallback_is_isolated(self):
        with patch.object(doctor.shutil,"which",return_value="/usr/bin/tool"), \
             patch.object(doctor,"namespace_probe",side_effect=[False,True]) as probe:
            result=doctor.check_network_namespace()
        self.assertEqual(result,{"ok":True,"method":"user-map-root"})
        self.assertEqual(probe.call_count,2)
        self.assertEqual(probe.call_args_list[1].args[0],
                         ["unshare","--user","--map-root-user","--net","--"])
    def test_namespace_probe_cannot_connect_or_modify_host(self):
        called=[]
        def run(argv,**kwargs):
            called.append(argv)
            return subprocess.CompletedProcess(argv,0,stdout="1: lo    inet 127.0.0.1/8 scope host lo\n",stderr="")
        with patch.object(doctor.subprocess,"run",side_effect=run):
            self.assertTrue(doctor.namespace_probe(["unshare","--user","--map-root-user","--net","--"]))
        self.assertIn("ip link set lo up",called[0][-1])
        self.assertNotIn("curl",str(called))
        self.assertNotIn("wget",str(called))
    def test_doctor_rejects_non_android_profile(self):
        args=argparse.Namespace(operation="doctor",profile="tiny11",target=None,ram="auto")
        with self.assertRaisesRegex(ValueError,"only for android-arm64"):
            vmfabric.launch(args)
    def test_doctor_cli_dispatches_argv_without_boot(self):
        args=argparse.Namespace(operation="doctor",profile="android-arm64",
                                target=Path("/tmp/private-kit"),ram="2304")
        with patch.object(vmfabric.subprocess,"call",return_value=3) as mocked:
            self.assertEqual(vmfabric.launch(args),3)
        argv=mocked.call_args.args[0]
        self.assertEqual(Path(argv[1]).name,"doctor.py")
        self.assertEqual(argv[2:],["--target","/tmp/private-kit","--ram","2304"])
    def test_doctor_source_is_offline_read_only(self):
        code=SRC.read_text()
        for forbidden in ("apt-get","curl ","wget ","gh release download","upload-artifact","qemu-img create"):
            self.assertNotIn(forbidden,code)
        self.assertNotIn("status=ready",code)

if __name__=="__main__":
    unittest.main()
