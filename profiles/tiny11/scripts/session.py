#!/usr/bin/env python3
"""Save or restore a STOPPED Tiny11 writable session (QCOW2 overlay + UEFI NVRAM).

Never snapshots a live QEMU guest. Base image must be available separately.
Snapshot contains Windows user data, treat as private/sensitive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(8*1024*1024),b""):h.update(b)
    return h.hexdigest()

def ensure_stopped(root):
    s=root/"qemu-monitor.sock"
    if s.is_socket():
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(1)
                client.connect(str(s))
                raise RuntimeError("Refuse snapshot/restore while QEMU monitor is alive; shut down guest first")
        except (ConnectionRefusedError,FileNotFoundError,OSError) as exc:
            if isinstance(exc,RuntimeError):raise
    # Do not rely on stale pid files or stale AF_UNIX socket names alone.

def qimg():
    home=os.getenv("QEMU_HOME")
    if home:
        p=Path(home)
        binary=p/"bin/qemu-img"
        ld=p/"lib/ld-linux-x86-64.so.2"
        if binary.is_file() and ld.is_file():
            return [str(ld),"--library-path",str(p/"lib"),str(binary)]
        if binary.is_file():return [str(binary)]
    binary=shutil.which("qemu-img")
    if not binary:raise RuntimeError("qemu-img missing; set QEMU_HOME to portable QEMU root")
    return [binary]

def check_overlay(path):
    subprocess.run(qimg()+["check","-f","qcow2",str(path)],check=True,stdout=subprocess.DEVNULL)

def copy_file(src,dst):
    if dst.exists() or dst.is_symlink():raise FileExistsError(dst)
    part=dst.with_name(dst.name+".partial")
    if part.exists():raise FileExistsError(part)
    try:
        with src.open("rb") as i,part.open("xb") as o:
            shutil.copyfileobj(i,o,8*1024*1024)
        os.replace(part,dst)
    finally:
        part.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("save","restore"))
    p.add_argument("--vm-dir",type=Path,required=True)
    p.add_argument("--snapshot-dir",type=Path,required=True)
    a=p.parse_args()
    root=a.vm_dir.resolve()
    snap=a.snapshot_dir.resolve()
    if root==snap:raise SystemExit("Snapshot cannot be the VM directory")
    ensure_stopped(root)
    manifest=json.loads((root/"tiny11-ready-manifest.json").read_text())
    base=root/manifest["disk"]
    if not base.is_file():raise SystemExit("Missing immutable base QCOW2")
    base_sha=manifest["disk_sha256"]
    target_overlay=root/"tiny11-session.qcow2"
    target_vars=root/"OVMF_VARS-session.fd"
    if a.action=="save":
        if snap.exists():raise SystemExit("Refuse to overwrite an existing session snapshot")
        if not target_overlay.is_file() or not target_vars.is_file():
            raise SystemExit("No saved interactive Tiny11 session overlay/NVRAM found")
        check_overlay(target_overlay)
        snap.mkdir(parents=True)
        copy_file(target_overlay,snap/"work.qcow2")
        copy_file(target_vars,snap/"OVMF_VARS-session.fd")
        info={"schema":1,"base_sha256":base_sha,
              "overlay_sha256":digest(snap/"work.qcow2"),
              "uefi_sha256":digest(snap/"OVMF_VARS-session.fd"),
              "contains_private_guest_data":True}
        (snap/"snapshot.json").write_text(json.dumps(info,indent=2)+"\n")
        print("SAVED private Tiny11 overlay and NVRAM to",snap)
        return
    info=json.loads((snap/"snapshot.json").read_text())
    if info.get("schema")!=1 or info.get("base_sha256")!=base_sha:
        raise SystemExit("Snapshot belongs to a different Windows base image")
    for filename,field in (("work.qcow2","overlay_sha256"),
                           ("OVMF_VARS-session.fd","uefi_sha256")):
        if digest(snap/filename)!=info[field]:
            raise SystemExit("Snapshot hash mismatch: "+filename)
    if target_overlay.exists() or target_vars.exists():
        raise SystemExit("VM session already exists. Refusing to overwrite it")
    copy_file(snap/"work.qcow2",target_overlay)
    copy_file(snap/"OVMF_VARS-session.fd",target_vars)
    # Work overlays record an ABSOLUTE backing path. Rebase metadata ONLY after
    # confirming the referenced base hash; do not flatten/rewrite the base image.
    subprocess.run(qimg()+["rebase","-u","-f","qcow2","-F","qcow2",
                           "-b",str(base.resolve()),str(target_overlay)],check=True)
    check_overlay(target_overlay)
    print("RESTORED Tiny11 session; original base unchanged")

if __name__=="__main__":
    try:main()
    except (OSError,RuntimeError,subprocess.CalledProcessError) as e:
        raise SystemExit(str(e))
