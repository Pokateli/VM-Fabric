#!/usr/bin/env python3
"""Test ChatGPT memory budget decisions without launching a guest."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/"profiles/android-arm64/scripts/host-memory-budget.py"
spec=importlib.util.spec_from_file_location("host_memory_budget",PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class AndroidHostBudgetTests(unittest.TestCase):
    def test_auto_4gib_cgroup_with_570mib_used(self):
        self.assertEqual(m.choose("auto",(4096,570)),2304)
        self.assertEqual(m.choose("2048",(4096,570)),2048)
    def test_rejects_4gib_guest_in_4gib_cgroup(self):
        with self.assertRaises(ValueError):
            m.choose("4096",(4096,570))
    def test_refuses_low_headroom(self):
        with self.assertRaises(ValueError):
            m.choose("auto",(2048,900))
        with self.assertRaises(ValueError):
            m.choose("1536",(2048,900))
    def test_no_known_cgroup_maintains_explicit_baseline_only(self):
        self.assertEqual(m.choose("4096",None),4096)
        with self.assertRaises(ValueError):
            m.choose("auto",None)
    def test_malformed_input_rejected(self):
        for value in ("0","8192","abc","2048x","-1",""):
            with self.subTest(value=value),self.assertRaises(ValueError):
                m.choose(value,(8192,1000))

if __name__=="__main__": unittest.main()
