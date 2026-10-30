#!/usr/bin/env python3
"""Prepare a writable throwaway Android ARM64 session over a verified restored kit.

Do not run QEMU against the preserved base /data QCOW2: its bytes and SHA-256
must remain immutable so future sessions can start cleanly. Requires qemu-img
installed on host. This does not boot the guest or claim repeat-boot success.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

def sha256(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def prepare(root, session):
    root=root.resolve()
    session=session.resolve()
    base=root/"build/userdata-arm64.qcow2"
    ramdisk=root/"build/ramdisk-wrap.img"
    dex=root/"build/dex"
    kit_emulator=root/"sdk/emulator/qemu/linux-x86_64/qemu-system-aarch64-headless"
    if not all(p.is_file() for p in (base,ramdisk,kit_emulator,dex/"stub.dex",dex/"wdctl.dex")):
        raise ValueError("Missing full restored ARM64 kit (data, ramdisk, DEX helpers, emulator)")
    sdkprops=root/"sdk/system-images/android-28/google_apis/arm64-v8a/source.properties"
    if not sdkprops.is_file() or "SystemImage.Abi=arm64-v8a" not in sdkprops.read_text():
        raise ValueError("Refuse non-ARM64 system image")
    proof=root/"proof"
    if (proof/"STABILITY_RESULT.txt").read_text().strip()!="PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE":
        raise ValueError("Unstable source kit")
    if (proof/"GUI_RESULT.txt").read_text().strip()!="LAUNCHER_HOME_EVIDENCE":
        raise ValueError("No trusted Android Launcher3 proof")
    if session==root or root in session.parents:
        raise ValueError("Session must reside outside immutable restored kit")
    if session.exists():
        raise ValueError("Session destination already exists; refuse overwriting")
    meta=json.loads(subprocess.check_output(["qemu-img","info","-f","qcow2","--output=json",str(base)],text=True,timeout=60))
    if meta.get("format")!="qcow2":
        raise ValueError("Not QCOW2")
    output=session/"build"
    try:
        output.mkdir(parents=True)
        (output/"ramdisk-wrap.img").symlink_to(ramdisk)
        # 40-bringup.sh expects the already-compiled media stub and watchdog.
        # Reusing their immutable DEX files avoids needing a JDK in ChatGPT.
        (output/"dex").symlink_to(dex,target_is_directory=True)
        oat=root/"build/oat"
        if oat.is_dir():
            (output/"oat").symlink_to(oat,target_is_directory=True)
        overlay=output/"userdata-arm64.qcow2"
        subprocess.run(["qemu-img","create","-f","qcow2","-F","qcow2","-b",str(base),str(overlay)],
                       check=True,timeout=120)
        record={"format":"vmfabric-android-arm64-session-v1","guest_abi":"arm64-v8a",
                "base_image":str(base),"base_sha256":sha256(base),
                "session_build_dir":str(output),"system_image":str(sdkprops.parent),
                "startup":"not_started","base_immutable":True}
        (session/"session.json").write_text(json.dumps(record,indent=2)+"\n")
        print("PREPARED_ANDROID_ARM64_QCOW2_OVERLAY="+str(overlay))
    except Exception:
        import shutil
        shutil.rmtree(session)
        raise

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kit",type=Path,required=True)
    ap.add_argument("--session",type=Path,required=True)
    args=ap.parse_args()
    try:prepare(args.kit,args.session)
    except (ValueError,OSError,subprocess.CalledProcessError,
            subprocess.TimeoutExpired,KeyError,json.JSONDecodeError) as e:
        ap.exit(1,str(e)+"\n")
