#!/usr/bin/env python3
"""EXPERIMENT ONLY: ask Android 9 ShortcutService to skip package rescan.

ShortcutService.checkPackageChanges() returns early in Android Safe Mode.
The framework's safe mode flag is selected in WindowManagerService from the
documented persist.sys.safemode property. Setting it before the PINNED zygote
restart is an isolated *diagnostic* test for ART ShortcutParser crashes.
Side-effect: Safe Mode can disable third-party apps. Not a production fix.
"""
import argparse
from pathlib import Path
import sys

ANCHOR="stop zygote; start zygote"
NEW="setprop persist.sys.safemode 1\n"+ANCHOR

def patch(path):
    text=path.read_text()
    if text.count(ANCHOR)!=1:
        raise ValueError("Unknown zygote restart site: refusing patch")
    if text.count(NEW)==1 and text.count("persist.sys.safemode")==1:
        print("SHORTCUT_SAFEMODE_TEST already applied")
        return
    if "persist.sys.safemode" in text:
        raise ValueError("Unexpected previous safe mode customization")
    path.write_text(text.replace(ANCHOR,NEW))
    print("SHORTCUT_SAFEMODE_TEST=enabled_before_second_zygote")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("bringup",type=Path)
    args=p.parse_args()
    try:patch(args.bringup)
    except (ValueError,OSError) as exc:p.exit(2,str(exc)+"\n")
