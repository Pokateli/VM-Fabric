#!/usr/bin/env python3
"""Android ARM64 local-only ADB console for an already running goldfish/ranchu guest.

The emulator's adb endpoint must be private to the local process namespace.
All operations use a fixed adb argv; never execute guest-supplied shell text.
"""
import argparse
import re
from pathlib import Path
import subprocess

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("status","screenshot","tap","sendkey","powerdown"))
    p.add_argument("--bundle",type=Path,required=True)
    p.add_argument("--output",type=Path)
    p.add_argument("--keys",default="")
    p.add_argument("--dx",type=int,default=0)
    p.add_argument("--dy",type=int,default=0)
    a=p.parse_args()
    bundle=a.bundle.resolve()
    adb=bundle/"sdk/platform-tools/adb"
    if not adb.is_file():p.error("Android SDK adb not deployed")
    def run(*args,timeout=90):
        result=subprocess.run([str(adb),"-s","emulator-5554",*args],
                              capture_output=True,timeout=timeout)
        if result.returncode:
            raise SystemExit("ADB failed: "+result.stderr.decode("utf-8","replace")[:400])
        return result.stdout
    if a.action=="status":
        state=run("get-state",timeout=15).decode().strip()
        abi=run("shell","getprop","ro.product.cpu.abi").decode().strip()
        if abi!="arm64-v8a":raise SystemExit("Refuse non-ARM64 Android device: "+repr(abi))
        print("Android ADB:",state," ABI:",abi)
        print("Android API:",run("shell","getprop","ro.build.version.sdk").decode().strip())
        print("Boot complete:",run("shell","getprop","sys.boot_completed").decode().strip())
    elif a.action=="screenshot":
        if not a.output:p.error("screenshot requires --output")
        dst=a.output.resolve()
        if dst.exists():raise SystemExit("Refusing to overwrite existing image")
        data=run("exec-out","screencap","-p",timeout=120)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):raise SystemExit("Android screenshot did not return a PNG")
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(data)
        print("Captured Android screenshot",dst,len(data),"bytes")
    elif a.action=="tap":
        if not (0<=a.dx<=4095 and 0<=a.dy<=4095):
            p.error("tap coordinates outside screen-safe range 0..4095")
        run("shell","input","tap",str(a.dx),str(a.dy))
        print("Tap",a.dx,a.dy)
    elif a.action=="sendkey":
        if not re.fullmatch(r"[A-Z0-9_]{1,48}",a.keys):
            p.error("Android key event must use A-Z/0-9/_ (e.g. KEYCODE_HOME)")
        run("shell","input","keyevent",a.keys)
        print("Key",a.keys)
    elif a.action=="powerdown":
        run("shell","reboot","-p")
        print("Requested Android guest shutdown")
if __name__=="__main__":main()
