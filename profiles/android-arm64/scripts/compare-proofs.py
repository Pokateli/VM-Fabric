#!/usr/bin/env python3
"""Compare verified Android ARM64 TCG proof artifacts from GitHub Actions.

Usage:
 python3 compare-proofs.py baseline=proof1.zip nojit=proof2.zip opengl=proof3.zip
Works only on diagnostic ZIPs; does not require Google system image binaries.
Reports *observations*, never equates PackageManager availability with GUI.
"""
import argparse
import json
from pathlib import Path
import re
import zipfile

def read(z,name):
    try:
        matches=[x for x in z.namelist() if x==name or x.endswith("/"+name)]
        if len(matches)!=1:return ""
        return z.read(matches[0]).decode("utf-8","replace")
    except (KeyError,OSError):return ""

def summary(path):
    with zipfile.ZipFile(path) as zip:
        raw=read(zip,"stability-report.json")
        try:stable=json.loads(raw) if raw else {}
        except json.JSONDecodeError:stable={}
        samples=stable.get("observations",[])
        if not isinstance(samples,list):samples=[]
        stable_samples=sum(1 for x in samples if x.get("passed") is True)
        pids=[x.get("system_server_pid",{}).get("stdout","") for x in samples]
        pid_changes=sum(1 for a,b in zip(pids,pids[1:]) if a and b and a!=b)
        logs=read(zip,"emulator-tail.log")
        crashes=[]
        lines=logs.splitlines()
        # Each Android tombstone starts with 'DEBUG: pid:' (a process header).
        for i,line in enumerate(lines):
            if "DEBUG: pid:" not in line:continue
            block="\n".join(lines[i:i+55])
            if "signal 11 (SIGSEGV)" not in block:continue
            source="unknown"
            if "libart.so" in block:source="ART"
            elif "libhwui.so" in block:source="HWUI"
            elif "libc.so" in block:source="libc"
            crashes.append({"process":re.search(r">>>\s*(.*?)\s*<<<",line).group(1)
                            if ">>>" in line and re.search(r">>>\s*(.*?)\s*<<<",line)
                            else "unknown","kind":source})
        proof=read(zip,"RESULT.txt")
        status=read(zip,"STABILITY_RESULT.txt").strip()
        gui=read(zip,"GUI_RESULT.txt").strip()
        return {"boot_marked":"PASS_REAL_ANDROID_ARM64_TCG_BOOT" in proof.splitlines(),
                "arm64":"ANDROID_ABI=arm64-v8a" in read(zip,"android-properties.txt").splitlines(),
                "stable":(status=="PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE"
                          and len(samples)>=5 and stable_samples==len(samples)
                          and len(set(pids))==1 and all(pids)),
                "samples":len(samples),"passes":stable_samples,
                "system_server_pid_changes":pid_changes,
                "art_segv":sum(1 for x in crashes if x["kind"]=="ART"),
                "hwui_segv":sum(1 for x in crashes if x["kind"]=="HWUI"),
                "gui":gui or "not-recorded"}

def report(inputs):
    data={name:summary(path) for name,path in inputs}
    heading=["Variant","ARM64 ADB","Stable PackageManager","PID changes",
             "ART SIGSEGV","HWUI SIGSEGV","GUI result"]
    lines=["| "+" | ".join(heading)+" |",
           "|"+"|".join("---" for _ in heading)+"|"]
    for name,d in data.items():
        vals=[name,"yes" if d["arm64"] else "unconfirmed",
              f'{d["passes"]}/{d["samples"]} samples' + (" stable" if d["stable"] else " unstable"),
              str(d["system_server_pid_changes"]),str(d["art_segv"]),str(d["hwui_segv"]),d["gui"]]
        lines.append("| "+" | ".join(vals)+" |")
    return "\n".join(lines)+"\n"

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("artifacts",nargs="+")
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    pairs=[]
    for part in args.artifacts:
        if "=" not in part:p.error("Expected NAME=/path/to/actions-proof.zip")
        name,path=part.split("=",1)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}",name):p.error("Invalid variant label")
        path=Path(path)
        if not path.is_file():p.error("Missing artifact: "+str(path))
        pairs.append((name,path))
    text=report(pairs)
    if args.output:args.output.write_text(text)
    print(text)
