#!/usr/bin/env python3
"""Bounded read-only crash evidence for the disposable Android 9 ARM64 guest.

On failed bring-up, collect actual adb logcat and one newest native tombstone.
No mutation, no network access, and no Actions artifact upload. Runs before QEMU
cleanup. Reads only a short allowlisted set of ADB commands and filenames.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

ALLOW_TOMBSTONE=re.compile(r"^tombstone_[0-9]{2}(?:\.pb)?$")
HIGHLIGHT=re.compile(
    r"shortcut|system_server|AndroidRuntime|FATAL|SIGSEGV|artQuick|libart|"
    r"Fatal signal|tombstone|rescan|zygote",re.I
)
def adb_run(adb,serial,args,timeout=22,limit=512*1024):
    try:
        r=subprocess.run([str(adb),"-s",serial,*args],capture_output=True,timeout=timeout)
        return {"rc":r.returncode,"stdout":r.stdout[-limit:],
                "stderr":r.stderr[-4096:]}
    except (subprocess.TimeoutExpired,OSError) as e:
        return {"rc":124,"stdout":b"","stderr":str(e).encode()[:4096]}

def collect(adb,serial,proof):
    proof.mkdir(parents=True,exist_ok=True)
    results={}
    commands={
        "guest-state": ["shell","sh","-c",
            "getprop ro.sys.safemode; getprop sys.boot_completed;"
            "getprop init.svc.zygote; service check package;"
            "ls -ld /data/system_ce/0/shortcut_service "
            "/data/system/shortcut_service.xml 2>&1 || true"],
        "logcat-crash": ["shell","logcat","-b","crash","-d","-t","600"],
        "logcat-main": ["shell","logcat","-b","main","-d","-t","1600"],
        "tombstone-names": ["shell","ls","-t","/data/tombstones"],
    }
    for label,cmd in commands.items():
        r=adb_run(adb,serial,cmd)
        results[label]={"rc":r["rc"],"bytes":len(r["stdout"])}
        if r["rc"]==0 or r["stdout"]:
            (proof/(label+".txt")).write_bytes(r["stdout"])
    names=(proof/"tombstone-names.txt")
    if names.is_file():
        for n in names.read_text(errors="replace").splitlines():
            n=n.strip()
            if ALLOW_TOMBSTONE.fullmatch(n) and not n.endswith(".pb"):
                r=adb_run(adb,serial,["shell","cat",f"/data/tombstones/{n}"],timeout=28)
                results["newest-tombstone"]={"rc":r["rc"],"bytes":len(r["stdout"]),"name":n}
                if r["stdout"]:
                    (proof/"newest-tombstone.txt").write_bytes(r["stdout"])
                break
    # Key failure lines in the always-retained Actions console log (no zip upload).
    for filename in ("logcat-crash.txt","logcat-main.txt","newest-tombstone.txt"):
        f=proof/filename
        if not f.exists():continue
        selected=[line[:450] for line in f.read_text(errors="replace").splitlines()
                  if HIGHLIGHT.search(line)]
        print(f"ANDROID_CRASH_DIAGNOSTIC={filename} matched={len(selected)}",flush=True)
        for line in selected[-35:]:
            print("ANDROID_CRASH_LINE="+line,flush=True)
    (proof/"crash-collection.json").write_text(json.dumps(
        {"schema":1,"results":results},indent=2)+"\n")
    print("ANDROID_DIAGNOSTICS_COLLECTED",flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sdk-root",type=Path,required=True)
    p.add_argument("--proof-dir",type=Path,required=True)
    p.add_argument("--serial",default="emulator-5554")
    args=p.parse_args()
    collect(args.sdk_root/"platform-tools/adb",args.serial,args.proof_dir)

if __name__=="__main__":
    main()
