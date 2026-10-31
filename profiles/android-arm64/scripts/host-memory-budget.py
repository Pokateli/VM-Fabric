#!/usr/bin/env python3
"""Select bounded guest RAM for Android ARM64 TCG, never exceed host cgroup.

With explicit numbers, refuse configurations that would leave less than 1024 MiB
of headroom for QEMU, host processes and page cache. 'auto' requires a finite
v2 cgroup limit and is useful in a constrained ChatGPT container.
No VM launch is performed here.
"""
import argparse
from pathlib import Path
import sys

MIB=1024*1024
RESERVE_MIB=1024
MIN_MIB=1536
MAX_MIB=4096
STEP_MIB=256

def cgroup_v2(root=Path("/sys/fs/cgroup")):
    try:
        limit=(root/"memory.max").read_text().strip()
        used=int((root/"memory.current").read_text().strip())
        if not limit.isdecimal() or used < 0:
            return None
        lim=int(limit)
        if lim <= used: return (lim//MIB, (used+MIB-1)//MIB)
        return (lim//MIB, (used+MIB-1)//MIB)
    except (OSError,ValueError):
        return None

def choose(request, budget):
    req=str(request).strip()
    if budget is None:
        if req=="auto": raise ValueError("auto RAM requires finite cgroup memory.max")
        limit=used=None
    else:
        limit,used=budget
    if req=="auto":
        available=limit-used-RESERVE_MIB
        selected=min(MAX_MIB, (available//STEP_MIB)*STEP_MIB)
    else:
        if not req.isdecimal(): raise ValueError("guest RAM must be a number or auto")
        selected=int(req)
    if not MIN_MIB <= selected <= MAX_MIB:
        raise ValueError("unsafe guest RAM: must be 1536..4096 MiB with >=1024 MiB free host reserve")
    if limit is not None and limit-used-selected < RESERVE_MIB:
        raise ValueError("configured guest RAM exceeds the host cgroup budget")
    return selected

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--requested",default="4096")
    args=ap.parse_args()
    budget=cgroup_v2()
    try: value=choose(args.requested,budget)
    except ValueError as exc: ap.exit(2,str(exc)+"\\n")
    print(f"VMFABRIC_RAM_BUDGET: requested={args.requested}, cgroup_mib={budget}, guest_mib={value}",file=sys.stderr)
    print(value)

if __name__=="__main__": main()
