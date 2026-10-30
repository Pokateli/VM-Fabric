#!/usr/bin/env python3
"""Observe actual ADB + PackageManager stability after Android systemReady.

'Service package: not found' MUST NEVER count as found. A momentary service
registration is not a stable Android userland. Requires repeated successful
checks over a bounded observation window; saves structured evidence on failure.
Experimental Google Android 9 ARM64 guest only. No shell injections, no network.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time

SERVICE_FOUND=re.compile(r"^Service package: found\s*$")
def parse_service(text):
    return bool(SERVICE_FOUND.fullmatch(text.strip()))

def run_adb(adb,serial,command,timeout=15):
    try:
        p=subprocess.run([str(adb),"-s",serial,*command],capture_output=True,
                         text=True,timeout=timeout)
        return {"exit":p.returncode,"stdout":p.stdout.strip()[:700],
                "stderr":p.stderr.strip()[:500]}
    except (subprocess.TimeoutExpired,OSError) as e:
        return {"exit":124,"stdout":"","stderr":str(e)[:500]}

def verify(adb,serial,output,checks,interval):
    if checks<3 or interval<5:raise ValueError("too few stability observations")
    output.mkdir(parents=True,exist_ok=True)
    samples=[]
    stable=True
    first_pid=None
    for i in range(checks):
        a=run_adb(adb,serial,["get-state"])
        b=run_adb(adb,serial,["shell","getprop","ro.product.cpu.abi"])
        c=run_adb(adb,serial,["shell","getprop","init.svc.zygote"])
        d=run_adb(adb,serial,["shell","service","check","package"],timeout=25)
        pid=run_adb(adb,serial,["shell","pidof","system_server"],timeout=25)
        if i==0:
            first_pid=pid["stdout"] if pid["exit"]==0 else None
        same_server=(pid["exit"]==0 and bool(first_pid) and
                     pid["stdout"]==first_pid and first_pid.isdecimal())
        ok=(a["exit"]==0 and a["stdout"]=="device" and
            b["exit"]==0 and b["stdout"]=="arm64-v8a" and
            c["exit"]==0 and c["stdout"]=="running" and
            d["exit"]==0 and parse_service(d["stdout"]) and same_server)
        samples.append({"sample":i+1,"time":int(time.time()),"adb":a,
                        "abi":b,"zygote":c,"package":d,
                        "system_server_pid":pid,"same_server":same_server,"passed":ok})
        print(f"ANDROID_STABILITY_SAMPLE={i+1}/{checks} "+("PASS" if ok else "FAIL"),
              flush=True)
        if not ok:stable=False
        if i<checks-1:time.sleep(interval)
    report={"schema":2,"first_system_server_pid":first_pid,"sample_count":checks,"interval_seconds":interval,
            "window_seconds":(checks-1)*interval,
            "stable":stable,"observations":samples}
    (output/"stability-report.json").write_text(json.dumps(report,indent=2)+"\n")
    (output/"STABILITY_RESULT.txt").write_text(
        "PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE\n" if stable else
        "FAIL_UNSTABLE_ANDROID_ARM64_PACKAGE_SERVICE\n")
    if not stable:raise SystemExit(87)
    print("PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE",flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sdk-root",type=Path,required=True)
    p.add_argument("--proof-dir",type=Path,required=True)
    p.add_argument("--serial",default="emulator-5554")
    p.add_argument("--checks",type=int,default=5)
    p.add_argument("--interval",type=int,default=20)
    a=p.parse_args()
    if not 3<=a.checks<=12 or not 5<=a.interval<=60:p.error("invalid sampling limits")
    verify(a.sdk_root/"platform-tools/adb",a.serial,a.proof_dir,a.checks,a.interval)
