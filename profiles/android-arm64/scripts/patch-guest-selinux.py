#!/usr/bin/env python3
"""Patch the PINNED throwaway ARM64 TCG launcher for Android early SELinux.

The *emulator's* '-selinux permissive' sets the guest boot mode BEFORE init
loads policy. This is NOT a host SELinux change. Production use prohibited.
"""
from pathlib import Path
import argparse
import sys

ORIGINAL='  -memory "$MEM" -cores "$CORES" -no-window -no-audio'
REPLACEMENT='  -memory "$MEM" -cores "$CORES" -selinux permissive -no-window -no-audio'

def patch(path):
    p=Path(path)
    before=p.read_text()
    if before.count(REPLACEMENT)==1 and before.count(ORIGINAL)==0:
        print("PASS existing early guest SELinux permissive mode")
        return
    if before.count(ORIGINAL)!=1 or before.count(REPLACEMENT):
        raise ValueError("Unexpected launcher contents: refuse unverified patch")
    new=before.replace(ORIGINAL,REPLACEMENT)
    p.write_text(new)
    print("PATCHED guest early SELinux mode: '-selinux permissive' (throwaway emulator only)")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("launcher",type=Path)
    args=parser.parse_args()
    try:patch(args.launcher)
    except (ValueError,OSError) as e:sys.exit(str(e))
