#!/usr/bin/env python3
"""Patch two invalid GNU timeout calls in the pinned ARM64 bring-up script.

adbx is a shell function sourced from scripts/lib/common.sh:
  adbx() { "$ADB_BIN" -s "$SERIAL" "$@"; }
GNU timeout requires an EXECUTABLE, it cannot invoke this shell function.
Leave every other adbx invocation untouched. Fail closed on unexpected source.
"""
import argparse
from pathlib import Path
import sys

OLD_ROOT="timeout 60 adbx root >/dev/null 2>&1 || true"
NEW_ROOT='timeout 60 "$ADB_BIN" -s "$SERIAL" root >/dev/null 2>&1 || true'
OLD_WAIT="timeout 300 adbx wait-for-device"
NEW_WAIT='timeout 300 "$ADB_BIN" -s "$SERIAL" wait-for-device'

def patch(path: Path):
    code=path.read_text()
    if code.count(NEW_ROOT)==1 and code.count(NEW_WAIT)==1:
        if OLD_ROOT in code or OLD_WAIT in code:
            raise ValueError("Mixed patched/unpatched ADB timeout sites")
        print("PASS: both ADB timeout calls already executable-safe")
        return
    if code.count(OLD_ROOT)!=1 or code.count(OLD_WAIT)!=1:
        raise ValueError("Pinned upstream bring-up changed; no blind ADB patch")
    revised=code.replace(OLD_ROOT,NEW_ROOT).replace(OLD_WAIT,NEW_WAIT)
    path.write_text(revised)
    print("PATCHED: timeout now calls real SDK adb binary -s emulator-5554")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("file",type=Path)
    args=p.parse_args()
    try:patch(args.file)
    except (ValueError,OSError) as e:sys.exit(str(e))
