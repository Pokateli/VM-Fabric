#!/usr/bin/env python3
"""Deploy a cached, immutable Tiny11 QCOW2 or stream a verified GitHub shard kit.

Input: extracted ready kit directory, directory with raw 384MiB shards plus
ready-parts.json, or 20 downloaded ZIP shard artifacts and index ZIP.
A locally cached ready QCOW2 is symlinked to avoid copying 8GiB.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import zipfile

FILES = frozenset(("tiny11-ready-zstd.qcow2", "OVMF_CODE.fd", "OVMF_VARS.fd",
                   "tiny11-ready-manifest.json", "ready-credentials.txt", "SHA256SUMS"))
PART_SIZE = 384 * 1024 * 1024

class Parts(io.RawIOBase):
    def __init__(self, root, index):
        self.root, self.index = root, index
        self.position = 0
        self.handle = None
        self.wrapper = None
        self.left = 0
        self.hash = None

    def readable(self):
        return True

    def read(self, length=-1):
        if length is None or length < 0:
            length = 1024 * 1024
        if length == 0:
            return b""
        if self.handle is None:
            if self.position == len(self.index["parts"]):
                return b""
            item = self.index["parts"][self.position]
            name = f"part-{self.position:03d}.bin"
            if item["name"] != name or not (0 < item["size"] <= PART_SIZE):
                raise ValueError("Invalid part name or part size")
            raw = self.root/name
            if raw.is_file():
                self.handle = raw.open("rb")
            else:
                choices = (self.root/f"tiny11-ready-shard-{self.position:03d}.zip",
                           self.root/f"tiny11-ready-public-shard-{self.position:03d}.zip")
                archive = next((p for p in choices if p.is_file()), None)
                if archive is None:
                    raise FileNotFoundError(name)
                self.wrapper = zipfile.ZipFile(archive)
                self.handle = self.wrapper.open(name)
            self.left = item["size"]
            self.hash = hashlib.sha256()
        block = self.handle.read(min(length, self.left))
        if not block and self.left:
            raise ValueError(f"Truncated shard {self.position:03d}")
        self.left -= len(block)
        self.hash.update(block)
        if self.left == 0:
            if self.hash.hexdigest() != self.index["parts"][self.position]["sha256"]:
                raise ValueError(f"SHA256 mismatch in shard {self.position:03d}")
            self.handle.close()
            if self.wrapper:
                self.wrapper.close()
            self.handle = self.wrapper = None
            self.position += 1
            print(f"Verified shard {self.position}/{len(self.index['parts'])}", flush=True)
        return block

def load_index(src):
    raw = src/"ready-parts.json"
    if raw.is_file():
        data = raw.read_text()
    else:
        choices = (src/"tiny11-ready-index.zip", src/"tiny11-ready-public-index.zip")
        archive = next((p for p in choices if p.is_file()), None)
        if archive is None:
            raise ValueError("Missing ready-parts.json or ready-index ZIP")
        with zipfile.ZipFile(archive) as zipped:
            data = zipped.read("ready-parts.json").decode("utf-8")
    index = json.loads(data)
    if index.get("format") != "tiny11-ready-public-parts-v1" or not index.get("unencrypted"):
        raise ValueError("Unexpected Tiny11 transport format")
    if set(index.get("members", {})) != FILES:
        raise ValueError("Unsafe or incomplete member list")
    if not (1 <= len(index.get("parts", [])) <= 96):
        raise ValueError("Unexpected shard count")
    return index

def deploy(source, dest):
    source = source.resolve()
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if source == dest:
        raise ValueError("Source and destination must differ")
    if all((source/name).is_file() for name in FILES):
        for name in sorted(FILES):
            target, src = dest/name, source/name
            if target.is_symlink() and target.resolve() == src:
                continue
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"Refuse to overwrite: {target}")
            target.symlink_to(src)
        print(f"REUSED local Tiny11 base without copying: {source}", flush=True)
        return
    index = load_index(source)
    stream = Parts(source, index)
    seen = set()
    with tarfile.open(fileobj=stream, mode="r|") as tar:
        for member in tar:
            if member.name not in FILES or member.name in seen or not member.isfile():
                raise ValueError("Unexpected or unsafe tar member")
            if member.size != index["members"][member.name]["size"]:
                raise ValueError("Tar member size mismatch")
            seen.add(member.name)
            target = dest/member.name
            temp = dest/(member.name+".part")
            if target.exists() or target.is_symlink() or temp.exists():
                raise FileExistsError(f"Refuse overwrite: {target}")
            h = hashlib.sha256()
            try:
                with tar.extractfile(member) as source_file, temp.open("xb") as dest_file:
                    for block in iter(lambda: source_file.read(4 * 1024 * 1024), b""):
                        dest_file.write(block)
                        h.update(block)
                if h.hexdigest() != index["members"][member.name]["sha256"]:
                    raise ValueError(f"Reconstructed SHA256 mismatch: {member.name}")
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
            print(f"VERIFIED {member.name}: {member.size} bytes", flush=True)
    if seen != FILES or stream.position != len(index["parts"]):
        raise ValueError("Incomplete Tiny11 transport")
    print("DEPLOYED Tiny11 ready disk from verified shards")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    p.add_argument("destination", type=Path)
    args = p.parse_args()
    deploy(args.source, args.destination)
