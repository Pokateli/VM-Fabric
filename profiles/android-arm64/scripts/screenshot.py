#!/usr/bin/env python3
"""Request PNG screencap from an Android emulator connected on local ADB."""
import argparse
from pathlib import Path
import subprocess
import sys

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    adb=a.bundle.resolve()/"sdk/platform-tools/adb"
    if not adb.is_file():raise SystemExit("No SDK ADB tool in selected Android bundle")
    output=a.output.resolve()
    if output.exists():raise SystemExit("Refuse to overwrite screenshot")
    proc=subprocess.run([str(adb),"-s","emulator-5554","exec-out","screencap","-p"],
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
    if proc.returncode or not proc.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit("Android GUI screenshot is not ready: "+proc.stderr.decode(errors="replace")[:400])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(proc.stdout)
    print("Screenshot:",output,"bytes",len(proc.stdout))
if __name__=="__main__":main()
