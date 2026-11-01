#!/usr/bin/env python3
"""Restore a PRIVATE Android ARM64 kit from an already-downloaded Release ZIP.

No network, GitHub API, credentials or cloud storage. Requires original
Release .zip and matching .zip.sha256 sidecar supplied as local files.
The output is published only after SHA256, strict ZIP member verification,
private-kit internal shard SHA256 and ARM64 SDK verification all succeed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent
PART=re.compile(r"part-[0-9]{3}\.bin\Z")
MAX_ARCHIVE_BYTES=2*1024**3
MAX_EXPANDED_SHARDS=3*1024**3
MAX_INDEX_BYTES=512*1024

def sha_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(4*1024**2),b""):
            h.update(chunk)
    return h.hexdigest()

def verify_sidecar(archive,checksum):
    # GitHub release archiver emits: <hex SHA256><two spaces><basename>\n
    if archive.stat().st_size>MAX_ARCHIVE_BYTES or archive.stat().st_size<=0:
        raise ValueError("Unexpected Release archive size")
    if checksum.stat().st_size>256:
        raise ValueError("Invalid sidecar size")
    data=checksum.read_text(encoding="ascii").strip()
    fields=data.split("  ")
    if len(fields)!=2 or fields[1]!=archive.name or not re.fullmatch(r"[0-9a-fA-F]{64}",fields[0]):
        raise ValueError("SHA256 sidecar must contain the exact local archive filename")
    if sha_file(archive)!=fields[0].lower():
        raise ValueError("Release ZIP SHA256 mismatch")
    return fields[0].lower()

def extract_shards(archive,parts_dir):
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        if not 2<=len(entries)<=129:
            raise ValueError("Unexpected private Android shard member count")
        names=[i.filename for i in entries]
        if len(names)!=len(set(names)) or names.count("android-arm64-parts.json")!=1:
            raise ValueError("Missing or duplicate Android shard manifest")
        if any(n!="android-arm64-parts.json" and PART.fullmatch(n) is None for n in names):
            raise ValueError("ZIP contains an unexpected path or member")
        total=0
        for item in entries:
            mode=(item.external_attr>>16)&0o170000
            if item.is_dir() or mode in (0o120000,0o040000) or item.file_size<0:
                raise ValueError("Refuse directories or symlinks in private archive")
            if item.filename=="android-arm64-parts.json" and item.file_size>MAX_INDEX_BYTES:
                raise ValueError("Oversized shard index")
            total+=item.file_size
            if total>MAX_EXPANDED_SHARDS:
                raise ValueError("Android private shard ZIP exceeds bounded size")
        index=json.loads(z.read("android-arm64-parts.json"))
        if (index.get("format")!="vmfabric-android-arm64-tcg-private-v1" or
            index.get("private") is not True or index.get("abi")!="arm64-v8a"):
            raise ValueError("Wrong private Android ARM64 manifest")
        shards=index.get("parts",[])
        if not isinstance(shards,list) or not 1<=len(shards)<=128:
            raise ValueError("Wrong private Android shard count")
        required=["android-arm64-parts.json"]
        for i,item in enumerate(shards):
            if not isinstance(item,dict) or item.get("name")!=f"part-{i:03d}.bin":
                raise ValueError("Invalid private Android shard numbering")
            if not isinstance(item.get("size"),int) or item["size"]<=0:
                raise ValueError("Invalid private Android shard size")
            required.append(item["name"])
        if set(names)!=set(required):
            raise ValueError("ZIP members differ from signed release shard manifest")
        parts_dir.mkdir(mode=0o700)
        for name in required:
            item=z.getinfo(name)
            if name!="android-arm64-parts.json" and item.file_size!=shards[int(name[5:8])]["size"]:
                raise ValueError("ZIP member size disagrees with shard manifest")
            with z.open(item) as source, (parts_dir/name).open("xb") as dest:
                shutil.copyfileobj(source,dest,1024*1024)
        return len(shards)

def restore(archive,checksum,target):
    archive=archive.resolve(strict=True)
    checksum=checksum.resolve(strict=True)
    target=target.absolute()
    if target.exists() or target.is_symlink():
        raise ValueError("Refusing to replace an existing restored Android directory")
    if not target.parent.is_dir() or target.parent.is_symlink():
        raise ValueError("Target parent must exist and not be a symlink")
    digest=verify_sidecar(archive,checksum)
    # Temporary shards and restored SDK live on the same filesystem as final
    # destination. No second cloud copy or orphaned unverified destination.
    with tempfile.TemporaryDirectory(prefix=".vmfabric-private-",dir=target.parent) as d:
        staging=Path(d)
        count=extract_shards(archive,staging/"parts")
        restored=staging/"restored"
        cmd=[sys.executable,str(HERE/"portable-kit.py"),"unpack",str(staging/"parts"),str(restored)]
        subprocess.run(cmd,check=True,timeout=1800,capture_output=True,text=True)
        subprocess.run([sys.executable,str(HERE/"verify.py"),"--target",str(restored)],
                       check=True,timeout=60,capture_output=True,text=True)
        if target.exists() or target.is_symlink():
            raise ValueError("Restore destination appeared while validating")
        os.rename(restored,target)
    return {"status":"RESTORED_PRIVATE_ANDROID_ARM64","source_zip_sha256":digest,
            "verified_shards":count,"target":str(target),
            "next":"python3 vmfabric.py doctor android-arm64 --target "+str(target)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--sha256",type=Path,required=True)
    p.add_argument("--target",type=Path,required=True)
    args=p.parse_args()
    try:
        result=restore(args.archive,args.sha256,args.target)
    except (OSError,ValueError,zipfile.BadZipFile,UnicodeError,
            subprocess.CalledProcessError,subprocess.TimeoutExpired) as exc:
        p.exit(2,"Private Android kit restore refused: "+str(exc)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
