#!/usr/bin/env python3
"""Synthetic ADB CLI contract checks: does not claim a real Android boot."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/"vmfabric.py"

FAKE_ADB=r'''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if 'get-state' in args:
    print('device')
elif 'getprop' in args:
    key=args[-1]
    if key=='ro.product.cpu.abi':print(os.environ.get('FAKE_ANDROID_ABI','arm64-v8a'))
    elif key=='ro.build.version.sdk':print('28')
    elif key=='sys.boot_completed':print('1')
    else:print('running')
elif 'screencap' in args:
    sys.stdout.buffer.write(b'\x89PNG\r\n\x1a\n'+b'FAKE_SYNTHETIC_NOT_PNG_IMAGE')
elif 'input' in args:
    pass
elif 'reboot' in args:
    pass
else:
    sys.exit('Unexpected fake ADB invocation: '+str(args))
'''

class ConsoleSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        adb=self.root/"sdk/platform-tools/adb"
        adb.parent.mkdir(parents=True)
        adb.write_text(FAKE_ADB)
        adb.chmod(0o755)

    def run_console(self,action,*extra,abi="arm64-v8a"):
        env=os.environ.copy()
        env["FAKE_ANDROID_ABI"]=abi
        return subprocess.run([sys.executable,str(CLI),"console","android-arm64",
                               action,"--target",str(self.root),*extra],
                              capture_output=True,text=True,env=env)

    def test_android_status_requires_real_abi_even_when_adb_is_online(self):
        p=self.run_console("status")
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("arm64-v8a",p.stdout)
        p=self.run_console("status",abi="x86_64")
        self.assertNotEqual(p.returncode,0)
        self.assertIn("Refuse non-ARM64",p.stderr)

    def test_screenshot_routes_to_adb_not_qemu_vga(self):
        path=self.root/"screen.png"
        p=self.run_console("screenshot","--output",str(path))
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue(path.is_file())
        self.assertTrue(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        p=self.run_console("screenshot","--output",str(path))
        self.assertNotEqual(p.returncode,0)
        self.assertIn("overwrite",p.stderr)

    def test_click_and_key_use_bounded_operations(self):
        self.assertEqual(self.run_console("click","--dx","320","--dy","520").returncode,0)
        self.assertEqual(self.run_console("sendkey","--keys","KEYCODE_HOME").returncode,0)
        self.assertNotEqual(self.run_console("click","--dx","99999").returncode,0)
        self.assertNotEqual(self.run_console("sendkey","--keys","bad; injected").returncode,0)

if __name__=="__main__":
    unittest.main()
