#!/usr/bin/env python3
"""Experimental Android 9 ShortcutService cache isolation, never on base QCOW2.

AOSP Android 9 persists per-user shortcut state in
/data/system_ce/0/shortcut_service. Move the directory, if present, into a
fixed backup location on the THROWAWAY guest /data overlay, after stopping
zygote and before restarting it. Keep Safe Mode off.

This separates corrupted persisted shortcut state from a failure that occurs
while rescanning installed APKs. It is NOT a production fix, it MUST NOT run
against an immutable base, and it deliberately fails if the backup exists.
"""
import argparse
from pathlib import Path

ANCHOR = "stop zygote; start zygote"
BACKUP = "/data/local/tmp/vmfabric-shortcut-cache-backup"
SOURCE = "/data/system_ce/0/shortcut_service"
MARKER = "# VMFABRIC_SHORTCUT_CACHE_RESET_V1"
INJECT = f"""\
{MARKER}
stop zygote
if [ -e {BACKUP} ]; then
  echo SHORTCUT_CACHE_BACKUP_COLLISION
  exit 94
fi
if [ -d {SOURCE} ]; then
  mv {SOURCE} {BACKUP} || exit 95
  echo SHORTCUT_CACHE_MOVED=1
else
  echo SHORTCUT_CACHE_MOVED=0
fi
setprop persist.sys.safemode 0
start zygote
"""

def patch(script: Path):
    code = script.read_text()
    if code.count(MARKER) == 1 and code.count(ANCHOR) == 0:
        if code.count(INJECT) != 1:
            raise ValueError("Existing shortcut cache experiment was modified")
        print("SHORTCUT_CACHE_EXPERIMENT already applied")
        return
    if code.count(ANCHOR) != 1 or MARKER in code or BACKUP in code:
        raise ValueError("Unknown pinned zygote restart site: refusing patch")
    if "persist.sys.safemode" in code:
        raise ValueError("Safe Mode is already configured; refusing mixed experiment")
    script.write_text(code.replace(ANCHOR, INJECT))
    print("SHORTCUT_CACHE_EXPERIMENT=enabled; guest overlay only")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bringup", type=Path)
    args = ap.parse_args()
    try:
        patch(args.bringup)
    except (OSError, ValueError) as exc:
        ap.exit(2, str(exc) + "\n")
