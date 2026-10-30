#!/usr/bin/env python3
"""An opt-in, byte-anchored ART/JIT experiment for the isolated ARM64 TCG guest.

No changes to Google system.img or libart.so. If enabled before the pinned
upstream 40-bringup.sh runs, set the guest dalvik.vm.usejit=false before the
intentional zygote restart. DOES NOT claim to cure ART quick-trampoline faults.
The default 'baseline' leaves source exactly unchanged.
"""
import argparse
from pathlib import Path
import sys

ANCHOR="stop zygote; start zygote"
PATCH="setprop dalvik.vm.usejit false\n" + ANCHOR

def patch(script: Path, mode: str):
    source=script.read_text()
    if mode=="baseline":
        if source.count(ANCHOR)!=1:
            raise ValueError("Unexpected pinned zygote restart site")
        print("ART_PROFILE=baseline (no modification)")
        return
    if mode!="nojit":raise ValueError("Only baseline/nojit profiles are allowed")
    if source.count(PATCH)==1 and source.count("setprop dalvik.vm.usejit false")==1:
        print("ART_PROFILE=nojit already patched")
        return
    if source.count(ANCHOR)!=1 or "setprop dalvik.vm.usejit false" in source:
        raise ValueError("Pinned bring-up source has unexpected ART options")
    script.write_text(source.replace(ANCHOR,PATCH))
    print("ART_PROFILE=nojit; guest Dalvik JIT turned off before zygote restart")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("bringup",type=Path)
    p.add_argument("--mode",choices=("baseline","nojit"),default="baseline")
    a=p.parse_args()
    try:patch(a.bringup,a.mode)
    except (OSError,ValueError) as exc:
        p.exit(2,str(exc)+"\n")
