#!/usr/bin/env python3
"""Experimental Android 9 legacy HWUI/OpenGL renderer selection on ARM64 TCG.

In Android P, debug.hwui.renderer=opengl selects classic OpenGL HWUI rather than
Skia OpenGL (skiagl), potentially avoiding crashes in Skia's GrGLProgramBuilder.
Set the property INSIDE the guest before the pinned zygote restart. Do not alter
the shipped system image, existing libhwui, or Android core files.

This is strictly opt-in. 'baseline' never modifies anything.
"""
import argparse
from pathlib import Path
import sys
ANCHOR="stop zygote; start zygote"
INJECT="setprop debug.hwui.renderer opengl\n"+ANCHOR
def apply(script,mode):
    code=script.read_text()
    if code.count(ANCHOR)!=1:
        raise ValueError("Pinned zygote restart site not found exactly once")
    if mode=="baseline":
        print("HWUI_PROFILE=baseline (unchanged)")
        return
    if mode!="legacy-opengl":raise ValueError("Unsupported HWUI renderer")
    if code.count(INJECT)==1 and code.count("setprop debug.hwui.renderer opengl")==1:
        print("HWUI_PROFILE=legacy-opengl already applied")
        return
    if "setprop debug.hwui.renderer" in code:
        raise ValueError("Unexpected existing HWUI renderer override")
    script.write_text(code.replace(ANCHOR,INJECT))
    print("HWUI_PROFILE=legacy-opengl: switch from SkiaGL to legacy HWUI on next zygote start")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("bringup",type=Path)
    p.add_argument("--mode",choices=("baseline","legacy-opengl"),default="baseline")
    a=p.parse_args()
    try:apply(a.bringup,a.mode)
    except (OSError,ValueError) as exc:p.exit(2,str(exc)+"\n")
