#!/usr/bin/env python3
"""Offline restore transport checks; never upload or require an Android SDK."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

SRC=Path(__file__).resolve().parents[1]/"profiles/android-arm64/scripts/restore-private-release.py"
spec=importlib.util.spec_from_file_location("vmfabric_android_release_restore",SRC)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def make_zip(root,additional=None,parts=None):
    archive=root/"private-kit.zip"
    if parts is None: parts=[{"name":"part-000.bin","size":4,"sha256":hashlib.sha256(b"DATA").hexdigest()}]
    manifest={"format":"vmfabric-android-arm64-tcg-private-v1",
              "private":True,"abi":"arm64-v8a","parts":parts}
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("android-arm64-parts.json",json.dumps(manifest))
        z.writestr("part-000.bin",b"DATA")
        for name,content in (additional or []):
            z.writestr(name,content)
    sidecar=root/"private-kit.zip.sha256"
    sidecar.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+"  private-kit.zip\n")
    return archive,sidecar

class PrivateAndroidRestoreTests(unittest.TestCase):
    def test_good_bundle_transport_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive,checksum=make_zip(root)
            self.assertEqual(m.verify_sidecar(archive,checksum),hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertEqual(m.extract_shards(archive,root/"parts"),1)
            self.assertEqual((root/"parts/part-000.bin").read_bytes(),b"DATA")
    def test_digest_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive,checksum=make_zip(root)
            archive.write_bytes(archive.read_bytes()+b"CORRUPTION")
            with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
                m.verify_sidecar(archive,checksum)
            dest=root/"destination"
            with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
                m.restore(archive,checksum,dest)
            self.assertFalse(dest.exists())
    def test_sidecar_must_be_exact_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive,checksum=make_zip(root)
            checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+"  different.zip\n")
            with self.assertRaisesRegex(ValueError,"exact local archive filename"):
                m.verify_sidecar(archive,checksum)
    def test_zip_path_traversal_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive,checksum=make_zip(root,[("../escape",b"SECRET")])
            with self.assertRaisesRegex(ValueError,"unexpected path"):
                m.extract_shards(archive,root/"parts")
            self.assertFalse((root.parent/"escape").exists())
    def test_unexpected_shard_numbering_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive,checksum=make_zip(root,parts=[{"name":"part-007.bin","size":4}])
            with self.assertRaisesRegex(ValueError,"numbering"):
                m.extract_shards(archive,root/"parts")
    def test_reject_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive,checksum=make_zip(root)
            dest=root/"previous"
            dest.mkdir()
            (dest/"sentinel").write_text("KEEP")
            with self.assertRaisesRegex(ValueError,"existing restored"):
                m.restore(archive,checksum,dest)
            self.assertEqual((dest/"sentinel").read_text(),"KEEP")
    def test_offline_restrictions(self):
        code=SRC.read_text()
        for forbidden in ("curl ","wget ","gh release download","upload-artifact"):
            self.assertNotIn(forbidden,code)
        self.assertIn("os.rename(restored,target)",code)
        self.assertIn("TemporaryDirectory",code)

if __name__=="__main__":unittest.main()
