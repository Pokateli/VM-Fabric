#!/usr/bin/env python3
"""Offline, read-only preflight for a PRIVATE Android ARM64 VM-Fabric kit.

No network connections, downloads, cloud storage, disk images or guest launch.
Network namespace probes touch only a newly isolated namespace (loopback).
Experimental profile status is deliberately NOT the same as host readiness.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
MIN_GUEST_MIB=1536
RESERVE_MIB=1024

def ram_budget(request):
    spec=importlib.util.spec_from_file_location("vmfabric_memory_budget",HERE/"host-memory-budget.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cgroup=module.cgroup_v2()
    try:
        chosen=module.choose(str(request),cgroup)
    except ValueError as exc:
        return {"ok":False,"requested":str(request),"cgroup_mib":cgroup,"reason":str(exc)}
    if str(request)=="auto":
        chosen=min(chosen,2304)
    return {"ok":True,"requested":str(request),"cgroup_mib":cgroup,
            "selected_guest_mib":chosen,"host_reserve_mib":RESERVE_MIB}

def namespace_probe(command,timeout=6):
    try:
        r=subprocess.run(command+["sh","-c","ip link set lo up && ip -o -4 addr show dev lo"],
                         capture_output=True,text=True,timeout=timeout)
        return r.returncode==0 and "127.0.0.1/" in r.stdout
    except (OSError,subprocess.TimeoutExpired):
        return False

def check_network_namespace():
    if not shutil.which("unshare") or not shutil.which("ip"):
        return {"ok":False,"method":None,"reason":"unshare/ip missing"}
    options=[
      ("privileged",["unshare","--net","--"]),
      ("user-map-root",["unshare","--user","--map-root-user","--net","--"]),
    ]
    for name,command in options:
        if namespace_probe(command):
            return {"ok":True,"method":name}
    return {"ok":False,"method":None,"reason":"cannot create loopback-only network namespace"}

def check_kit(target):
    if not target.is_dir():
        return {"ok":False,"reason":"private restored kit is not present","path":str(target)}
    checks=[
        target/"build/userdata-arm64.qcow2",
        target/"build/ramdisk-wrap.img",
        target/"sdk/emulator/qemu/linux-x86_64/qemu-system-aarch64-headless",
        target/"sdk/system-images/android-28/google_apis/arm64-v8a/source.properties",
        target/"upstream-src/scripts/40-bringup.sh",
        target/"proof/STABILITY_RESULT.txt",
        target/"proof/GUI_RESULT.txt",
    ]
    if not all(p.is_file() for p in checks):
        return {"ok":False,"reason":"incomplete local private kit","path":str(target)}
    try:
        r=subprocess.run(["python3",str(HERE/"verify.py"),"--target",str(target)],
                         capture_output=True,text=True,timeout=30)
        if r.returncode!=0:
            return {"ok":False,"reason":"kit ABI/SDK verification failed","path":str(target)}
        if (target/"proof/STABILITY_RESULT.txt").read_text().strip()!="PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE":
            return {"ok":False,"reason":"missing stable package-service source proof","path":str(target)}
        if (target/"proof/GUI_RESULT.txt").read_text().strip()!="LAUNCHER_HOME_EVIDENCE":
            return {"ok":False,"reason":"missing real Launcher3 source proof","path":str(target)}
    except (OSError,subprocess.TimeoutExpired,UnicodeError):
        return {"ok":False,"reason":"kit proof could not be inspected","path":str(target)}
    return {"ok":True,"path":str(target),"guest_abi":"arm64-v8a"}

def diagnose(target,request="auto"):
    required=("qemu-img","unshare","ip","python3","timeout","realpath")
    missing=[x for x in required if not shutil.which(x)]
    ram=ram_budget(request)
    net=check_network_namespace()
    kit=check_kit(target)
    checks={"host_architecture":platform.machine(),"required_tools_missing":missing,
            "memory":ram,"isolated_loopback_network":net,"private_kit":kit}
    ready=(platform.machine() in ("x86_64","amd64") and not missing
           and ram["ok"] and net["ok"] and kit["ok"])
    return {"schema":"vmfabric-android-arm64-doctor-v1","profile":"android-arm64",
            "profile_status":"experimental","local_smoke_prerequisites_met":bool(ready),
            "checks":checks,
            "note":"Preflight does not prove a stable Android boot or change the ready profile gate"}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target",required=True,type=Path)
    p.add_argument("--ram",default="auto")
    args=p.parse_args()
    result=diagnose(args.target,args.ram)
    print(json.dumps(result,indent=2,ensure_ascii=False))
    raise SystemExit(0 if result["local_smoke_prerequisites_met"] else 3)

if __name__=="__main__":
    main()
