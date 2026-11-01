#!/usr/bin/env python3
"""Verify the ABI and pinned Android ARM64 emulator bundle; never label an x86 image as ARM."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

def check(target, live=False):
    root=target.resolve()
    sdk=root/"sdk"
    img=sdk/"system-images/android-28/google_apis/arm64-v8a"
    emulator=sdk/"emulator/qemu/linux-x86_64/qemu-system-aarch64-headless"
    adb=sdk/"platform-tools/adb"
    for path in (img/"system.img",img/"vendor.img",img/"kernel-ranchu",img/"ramdisk.img",emulator,adb):
        if not path.is_file() or path.stat().st_size==0:
            raise ValueError("Missing real Android ARM64 SDK asset: "+str(path))
    source=(img/"source.properties").read_text()
    properties=dict(line.strip().split("=",1) for line in source.splitlines() if "=" in line)
    if (properties.get("SystemImage.Abi")!="arm64-v8a" or
        properties.get("AndroidVersion.ApiLevel")!="28" or
        properties.get("SystemImage.TagId")!="google_apis"):
        raise ValueError("Wrong Android ABI or SDK release: "+str(properties))
    if (sdk/"emulator/.pinned").read_text().strip()!="16489710":
        raise ValueError("Emulator build ID differs from pinned and patch-verified emulator")
    if not (root/"build/ramdisk-wrap.img").is_file():
        raise ValueError("Missing ARM64 boot ramdisk; first run 20-build-ramdisk.sh")
    result={"platform":"android","guest_abi":"arm64-v8a","android_api":28,
            "emulator_build":"16489710","mode":"TCG","bundle_verified":True}
    if live:
        p=subprocess.run([str(adb),"-s","emulator-5554","shell",
                          "getprop","ro.product.cpu.abi"],
                         capture_output=True,text=True,timeout=120)
        abi=p.stdout.strip()
        if p.returncode!=0 or abi!="arm64-v8a":
            raise ValueError("ADB did not verify genuine Android ARM64: "+p.stderr[:300])
        p=subprocess.run([str(adb),"-s","emulator-5554","shell",
                          "service","check","package"],
                         capture_output=True,text=True,timeout=120)
        if p.returncode!=0 or p.stdout.strip()!="Service package: found":
            raise ValueError("Android package service is not ready: "+p.stdout[:300])
        result["adb_proof"]=True
        result["package_service"]="found"
    print(json.dumps(result,indent=2))
if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target",type=Path,required=True)
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    try:check(args.target,args.live)
    except (OSError,ValueError,subprocess.TimeoutExpired) as e:
        raise SystemExit(str(e))
