#!/usr/bin/env python3
"""Tiny11 cache and public-shard import tests; no Windows image in CI."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
IMPORT=ROOT/"profiles/tiny11/scripts/import-ready.py"
FILES=("tiny11-ready-zstd.qcow2","OVMF_CODE.fd","OVMF_VARS.fd",
       "tiny11-ready-manifest.json","ready-credentials.txt","SHA256SUMS")

def digest(x):
    return hashlib.sha256(x).hexdigest()

class Tiny11ImportTests(unittest.TestCase):
    def test_symlink_cache_no_duplicate_disk(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"source"
            source.mkdir()
            for name in FILES:
                (source/name).write_bytes(("SYNTHETIC "+name).encode())
            target=root/"deployed"
            subprocess.run([sys.executable,str(IMPORT),str(source),str(target)],check=True)
            for name in FILES:
                self.assertTrue((target/name).is_symlink())
                self.assertEqual((target/name).read_bytes(),(source/name).read_bytes())
            subprocess.run([sys.executable,str(IMPORT),str(source),str(target)],check=True)
            self.assertFalse(any(x.suffix==".qcow2" and not x.is_symlink() for x in target.iterdir()))

    def test_streamed_zip_shard_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data={name:("SYNTHETIC "+name).encode() for name in FILES}
            data["tiny11-ready-zstd.qcow2"]=b"WIN11_TEST_ONLY_NOT_WINDOWS"*1024
            buf=io.BytesIO()
            with tarfile.open(fileobj=buf,mode="w:") as t:
                for name,body in data.items():
                    entry=tarfile.TarInfo(name)
                    entry.size=len(body)
                    t.addfile(entry,io.BytesIO(body))
            tarbytes=buf.getvalue()
            # 2 parts intentionally exercise streaming and boundary handling.
            pivot=len(tarbytes)//2
            parts=[tarbytes[:pivot],tarbytes[pivot:]]
            index={"format":"tiny11-ready-public-parts-v1","unencrypted":True,
                   "members":{n:{"size":len(x),"sha256":digest(x)} for n,x in data.items()},
                   "parts":[{"name":f"part-{i:03d}.bin","size":len(x),"sha256":digest(x)}
                            for i,x in enumerate(parts)]}
            with zipfile.ZipFile(root/"tiny11-ready-index.zip","w") as z:
                z.writestr("ready-parts.json",json.dumps(index))
            for i,part in enumerate(parts):
                with zipfile.ZipFile(root/f"tiny11-ready-shard-{i:03d}.zip","w") as z:
                    z.writestr(f"part-{i:03d}.bin",part)
            target=root/"installed"
            subprocess.run([sys.executable,str(IMPORT),str(root),str(target)],check=True)
            for name,x in data.items():
                self.assertEqual((target/name).read_bytes(),x)

    def test_no_windows_command_injection(self):
        command=[sys.executable,str(ROOT/"vmfabric.py"),"run","tiny11","--command","id"]
        proc=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(proc.returncode,2)
        self.assertIn("do not support Bash",proc.stderr)

if __name__=="__main__":
    unittest.main()
