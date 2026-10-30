#!/usr/bin/env python3
"""Validate a locally cached Tiny11 base and 64GiB standalone ZSTD QCOW2."""
import os
from pathlib import Path
import subprocess
import sys
if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    env = os.environ.copy()
    if not env.get("QEMU_HOME"):
        for home in (
            Path("/mnt/data/tiny11-qemu-vga-fixed/tiny11-qemu-runtime-linux-amd64"),
            Path("/mnt/data/tiny11-qemu-runtime-linux-amd64"),
        ):
            if (home/"bin/qemu-img").is_file():
                env["QEMU_HOME"] = str(home)
                break
    sys.exit(subprocess.call([sys.executable,str(root/"dual-run.py")]+sys.argv[1:],env=env))
