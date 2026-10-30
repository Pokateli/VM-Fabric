#!/usr/bin/env python3
"""Stream a VERIFIED private Android ARM64 TCG bundle into SHA256 chunks.

Usage:
  portable-kit.py pack BUNDLE_ROOT PARTS_DIRECTORY
  portable-kit.py unpack PARTS_DIRECTORY RESTORED_ROOT

Bundle layout: sdk/, build/, upstream-src/, proof/RESULT.txt.
Only a real successful ADB ABI/package-service run is eligible for packing.
The archive includes Android SDK image binaries: keep it PRIVATE and respect
the Android SDK license. Never distribute a Google system image publicly.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile

CHUNK = 384 * 1024 * 1024
FORMAT = "vmfabric-android-arm64-tcg-private-v1"
REV = "f9eecf6c0d2fcc1e255b5a6d7322b07cbe017ba9"
REQUIRED = (
    "proof/RESULT.txt",
    "proof/android-properties.txt",
    "proof/package-service.txt",
    "sdk/system-images/android-28/google_apis/arm64-v8a/system.img",
    "sdk/system-images/android-28/google_apis/arm64-v8a/vendor.img",
    "sdk/system-images/android-28/google_apis/arm64-v8a/kernel-ranchu",
    "sdk/system-images/android-28/google_apis/arm64-v8a/source.properties",
    "sdk/emulator/qemu/linux-x86_64/qemu-system-aarch64-headless",
    "sdk/emulator/.pinned",
    "sdk/platform-tools/adb",
    "build/ramdisk-wrap.img",
    "build/userdata-arm64.qcow2",
    "upstream-src/scripts/40-bringup.sh",
)
EXCLUDE = ("sdk/dl", "build/rd", "upstream-src/.git")
ROOTS = ("sdk", "build", "upstream-src", "proof")
MAX_BYTES = 40 * 1024**3
MAX_FILES = 100000

def sha_file(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4*1024*1024), b""):
            h.update(block)
    return h.hexdigest()

class PartWriter:
    def __init__(self, destination):
        self.root=destination
        self.parts=[]
        self.handle=None
        self.current_hash=None
        self.index=0
        self.total=0
        self.offset=0
    def writable(self): return True
    def write(self, data):
        data=memoryview(data)
        count=len(data)
        while data:
            if self.handle is None:
                name=f"part-{self.index:03d}.bin"
                self.handle=(self.root/name).open("xb")
                self.current_hash=hashlib.sha256()
                self.offset=0
                self.parts.append({"name":name,"size":0,"sha256":None})
            part=data[:CHUNK-self.offset]
            self.handle.write(part)
            self.current_hash.update(part)
            n=len(part)
            self.parts[-1]["size"]+=n
            self.offset+=n
            self.total+=n
            data=data[n:]
            if self.offset==CHUNK:
                self.finish_part()
        return count
    def finish_part(self):
        if self.handle:
            self.parts[-1]["sha256"]=self.current_hash.hexdigest()
            self.handle.close()
            self.handle=None
            self.index+=1
    def finish(self): self.finish_part()

class PartReader:
    def __init__(self, directory, index):
        self.root=directory
        self.parts=index["parts"]
        self.i=0
        self.handle=None
        self.remaining=0
        self.hasher=None
    def readable(self): return True
    def read(self, n=-1):
        if n is None or n<0:n=1024*1024
        if n==0:return b""
        if self.handle is None:
            if self.i==len(self.parts):return b""
            meta=self.parts[self.i]
            if meta["name"]!=f"part-{self.i:03d}.bin" or not 0<meta["size"]<=CHUNK:
                raise ValueError("Invalid shard sequence/size")
            self.handle=(self.root/meta["name"]).open("rb")
            self.remaining=meta["size"]
            self.hasher=hashlib.sha256()
        block=self.handle.read(min(self.remaining,n))
        if not block and self.remaining:raise ValueError("Truncated shard")
        self.remaining-=len(block)
        self.hasher.update(block)
        if self.remaining==0:
            if self.hasher.hexdigest()!=self.parts[self.i]["sha256"]:
                raise ValueError(f"SHA256 mismatch in shard {self.i}")
            if self.handle.read(1):
                raise ValueError("Unexpected bytes after declared shard end")
            self.handle.close()
            self.handle=None
            self.i+=1
        return block

def excluded(path):
    return any(path==x or path.startswith(x+"/") for x in EXCLUDE)

def verify_input(root):
    if not all((root/r).is_dir() for r in ROOTS):
        raise ValueError("Bundle needs sdk/, build/, upstream-src/ and proof/")
    proof=(root/"proof/RESULT.txt").read_text()
    if "PASS_REAL_ANDROID_ARM64_TCG_BOOT" not in proof.splitlines():
        raise ValueError("Refuse to pack Android without actual ADB/package-service boot proof")
    # A single marker is insufficient: require the independent captured ADB
    # ABI property and a real PackageManager service response as well.
    abi=(root/"proof/android-properties.txt").read_text().strip()
    pkg=(root/"proof/package-service.txt").read_text()
    if abi!="ANDROID_ABI=arm64-v8a" or "found" not in pkg.lower():
        raise ValueError("Refuse to pack Android without matching ADB ABI and package-service evidence")
    props=(root/"sdk/system-images/android-28/google_apis/arm64-v8a/source.properties").read_text()
    metadata=dict(s.strip().split("=",1) for s in props.splitlines() if "=" in s)
    if (metadata.get("AndroidVersion.ApiLevel")!="28" or
        metadata.get("SystemImage.Abi")!="arm64-v8a" or
        metadata.get("SystemImage.TagId")!="google_apis"):
        raise ValueError("Wrong Android guest architecture/version")
    if (root/"sdk/emulator/.pinned").read_text().strip()!="16489710":
        raise ValueError("Unexpected unpinned emulator")
    hashes={}
    for name in REQUIRED:
        p=root/name
        if not p.is_file() or p.stat().st_size<1:
            raise ValueError("Missing required ARM64 guest component: "+name)
        hashes[name]={"size":p.stat().st_size,"sha256":sha_file(p)}
    return hashes

def pack(root, dest):
    root=root.resolve()
    meta=verify_input(root)
    dest.mkdir(parents=True,exist_ok=True)
    if any(dest.iterdir()):raise ValueError("Refuse to overwrite nonempty parts directory")
    writer=PartWriter(dest)
    files=0
    total=0
    # dereference SDK-internal symlinks into actual files so the bundle is
    # independent of host sysroot paths and is restorable as regular files.
    with tarfile.open(fileobj=writer,mode="w|gz",format=tarfile.PAX_FORMAT,dereference=True) as tar:
        def filt(member):
            nonlocal files,total
            if excluded(member.name):return None
            if not (member.isfile() or member.isdir()):
                raise ValueError("Unexpected non-file in Android bundle: "+member.name)
            if member.isfile():
                files+=1
                total+=member.size
            if files>MAX_FILES or total>MAX_BYTES:
                raise ValueError("Android bundle exceeds permitted bounds")
            return member
        for name in ROOTS:
            tar.add(root/name,arcname=name,recursive=True,filter=filt)
    writer.finish()
    index={"format":FORMAT,"upstream_revision":REV,
           "private":True,"android_api":28,"abi":"arm64-v8a",
           "parts":writer.parts,"compressed_bytes":writer.total,
           "total_input_file_bytes":total,"file_count":files,
           "required_members":meta}
    (dest/"android-arm64-parts.json").write_text(json.dumps(index,indent=2)+"\n")
    print("VERIFIED ANDROID_ARM64_PRIVATE_KIT:",len(writer.parts),
          "shards, compressed",writer.total,"bytes, files",files)

def safe_name(name):
    p=PurePosixPath(name)
    if name.startswith("/") or "\\" in name or not p.parts or ".." in p.parts:
        raise ValueError("Unsafe tar path "+repr(name))
    if p.parts[0] not in ROOTS:
        raise ValueError("Unexpected tar root: "+repr(name))
    return p

def unpack(parts, root):
    parts=parts.resolve()
    index=json.loads((parts/"android-arm64-parts.json").read_text())
    if (index.get("format")!=FORMAT or index.get("abi")!="arm64-v8a" or
        index.get("upstream_revision")!=REV or index.get("private") is not True):
        raise ValueError("Unexpected private ARM64 bundle index")
    if not 1<=len(index.get("parts",[]))<=128:
        raise ValueError("Unexpected number of Android shards")
    if set(index.get("required_members",{}))!=set(REQUIRED):
        raise ValueError("Missing or unexpected image checksums")
    root.mkdir(parents=True,exist_ok=True)
    if any(root.iterdir()):raise ValueError("Restore destination must be empty")
    reader=PartReader(parts,index)
    seen=set()
    count=0
    total=0
    with tarfile.open(fileobj=reader,mode="r|gz") as tar:
        for member in tar:
            p=safe_name(member.name)
            if str(p) in seen:raise ValueError("Duplicate tar member")
            seen.add(str(p))
            target=root.joinpath(*p.parts)
            if member.isdir():
                target.mkdir(parents=True,exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError("Refuse symlinks, devices or executable hooks in archive")
            count+=1
            total+=member.size
            if count>MAX_FILES or total>MAX_BYTES:
                raise ValueError("Unpacked Android bundle exceeds limits")
            target.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(member) as source, target.open("xb") as dest:
                shutil.copyfileobj(source,dest,1024*1024)
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    # Drain gzip/tar trailer, checking SHA256 for the final part as well.
    while reader.read(1024*1024):
        pass
    if reader.i!=len(index["parts"]):
        raise ValueError("Incomplete part verification")
    for name,item in index["required_members"].items():
        p=root/name
        if not p.is_file() or p.stat().st_size!=item["size"] or sha_file(p)!=item["sha256"]:
            raise ValueError("Required guest component checksum mismatch: "+name)
    if count!=index["file_count"] or total!=index["total_input_file_bytes"]:
        raise ValueError("Extracted file count or byte total differs from index")
    verify_input(root)
    print("RESTORED verified Android ARM64 TCG bundle:",root)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("pack","unpack"))
    p.add_argument("source",type=Path)
    p.add_argument("destination",type=Path)
    args=p.parse_args()
    try:
        (pack if args.action=="pack" else unpack)(args.source,args.destination)
    except (ValueError,OSError,tarfile.TarError) as exc:
        p.exit(1,str(exc)+"\n")
