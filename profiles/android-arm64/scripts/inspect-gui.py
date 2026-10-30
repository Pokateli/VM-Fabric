#!/usr/bin/env python3
"""Diagnose real Android ARM64 surface and obtain ADB screencap without a GUI claim.

This script runs in the same isolated netns as the emulator. The top-level
systemReady gate is separate and is never weakened by a blank framebuffer.
PNG filter bytes are decoded via stdlib to detect truly black screenshots.
"""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import time
import zlib

PNG=b"\x89PNG\r\n\x1a\n"

def inspect_png(data):
    if not data.startswith(PNG): raise ValueError("Not PNG")
    at=8; compressed=[]; dims=None
    while at+12<=len(data):
        size=struct.unpack(">I",data[at:at+4])[0]
        kind=data[at+4:at+8];start=at+8;end=start+size
        if end+4>len(data):raise ValueError("Truncated PNG")
        payload=data[start:end]
        if kind==b"IHDR":
            w,h,bits,typ,comp,filt,interlace=struct.unpack(">IIBBBBB",payload)
            if not (0<w<=4096 and 0<h<=4096 and w*h<=16_777_216
                    and bits==8 and typ in (2,6) and comp==0 and
                    filt==0 and interlace==0):
                raise ValueError("Unsupported PNG image layout")
            dims=(w,h,3 if typ==2 else 4)
        elif kind==b"IDAT":compressed.append(payload)
        elif kind==b"IEND":break
        at=end+4
    if not dims or not compressed:raise ValueError("Missing PNG payload")
    w,h,c=dims;rowbytes=w*c
    raw=zlib.decompress(b"".join(compressed),bufsize=h*(rowbytes+1))
    if len(raw)!=h*(rowbytes+1):raise ValueError("Unexpected PNG raster size")
    previous=bytearray(rowbytes)
    visible=0
    colors=set()
    pos=0
    for _ in range(h):
        filtertype=raw[pos];pos+=1
        row=bytearray(raw[pos:pos+rowbytes]);pos+=rowbytes
        if filtertype>4:raise ValueError("Bad PNG filter")
        for n in range(rowbytes):
            a=row[n-c] if n>=c else 0
            b=previous[n]
            ul=previous[n-c] if n>=c else 0
            if filtertype==1:predict=a
            elif filtertype==2:predict=b
            elif filtertype==3:predict=(a+b)//2
            elif filtertype==4:
                p=a+b-ul
                dist=(abs(p-a),abs(p-b),abs(p-ul))
                predict=(a,b,ul)[dist.index(min(dist))]
            else:predict=0
            row[n]=(row[n]+predict)&255
        for i in range(0,rowbytes,c):
            rgb=tuple(row[i:i+3])
            if rgb!=(0,0,0):visible+=1
            if len(colors)<100:colors.add(rgb)
        previous=row
    return {"width":w,"height":h,"visible_pixels":visible,
            "distinct_sample_colors":len(colors),"all_black":visible==0}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sdk-root",type=Path,required=True)
    p.add_argument("--proof-dir",type=Path,required=True)
    p.add_argument("--serial",default="emulator-5554")
    a=p.parse_args()
    proof=a.proof_dir
    proof.mkdir(parents=True,exist_ok=True)
    adb=a.sdk_root/"platform-tools/adb"
    logs=[]
    def adb_cmd(*args,timeout=60):
        try:
            r=subprocess.run([str(adb),"-s",a.serial,*args],capture_output=True,timeout=timeout)
            return r.returncode,r.stdout,r.stderr
        except (subprocess.TimeoutExpired,OSError) as exc:
            return 124,b"",str(exc).encode()
    for label,cmd in (
        ("boot_completed",("shell","getprop","sys.boot_completed")),
        ("surfaceflinger",("shell","service","check","SurfaceFlinger")),
        ("display",("shell","wm","size")),
        ("focus",("shell","dumpsys","window","windows")),
        ("launcher_resolution",("shell","cmd","package","resolve-activity","--brief",
                                "-a","android.intent.action.MAIN",
                                "-c","android.intent.category.HOME")),
        ("wake",("shell","input","keyevent","224")),
        ("home",("shell","input","keyevent","3")),
        ("home_launch",("shell","am","start","-a","android.intent.action.MAIN",
                        "-c","android.intent.category.HOME"))):
        rc,stdout,stderr=adb_cmd(*cmd,timeout=45)
        logs.append({"check":label,"exit":rc,
                     "stdout":stdout.decode(errors="replace")[:6000],
                     "stderr":stderr.decode(errors="replace")[:1500]})
    # Give the launcher and software renderer time to draw after waking LCD.
    time.sleep(12)
    status="NO_SCREENSHOT"
    for attempt in (1,2):
        rc,data,err=adb_cmd("exec-out","screencap","-p",timeout=90)
        log={"check":f"screenshot_{attempt}","exit":rc,"bytes":len(data),
             "stderr":err.decode(errors="replace")[:1000]}
        if rc==0 and data.startswith(PNG):
            dst=proof/("android-screen.png" if attempt==2 else "android-screen-first.png")
            dst.write_bytes(data)
            try:
                stats=inspect_png(data)
                log.update(stats)
                status="BLACK_FRAMEBUFFER" if stats["all_black"] else "VISIBLE_FRAMEBUFFER_NOT_PROVEN_LAUNCHER"
                if not stats["all_black"]:
                    logs.append(log)
                    break
            except ValueError as exc:
                status="UNRECOGNIZED_PNG"
                log["parse_error"]=str(exc)
        logs.append(log)
        if attempt==1:time.sleep(15)
    (proof/"gui-inspection.json").write_text(json.dumps(logs,indent=2)+"\n")
    (proof/"GUI_RESULT.txt").write_text(status+"\n")
    print("ANDROID_GUI_STATUS="+status,flush=True)

if __name__=="__main__":
    main()
