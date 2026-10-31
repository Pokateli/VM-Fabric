#!/usr/bin/env python3
"""Offline, bounded Android ARM64 crash fingerprinting from private boot proof.

Only recognized crash markers are reported. Full logcat/tombstone lines stay on
local disk: they may contain private app data. Classification is diagnostic,
never proof of a specific ART bug or successful Android startup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

FILES = (
    "logcat-crash.txt", "logcat-main.txt", "logcat-system.txt",
    "newest-tombstone.txt", "guest-state.txt",
)
MAX_BYTES_PER_FILE = 1024 * 1024
MARKERS = {
    "sigsegv": re.compile(rb"\bSIGSEGV\b|\bsignal 11\b", re.I),
    "system_server": re.compile(rb"\bsystem_server\b", re.I),
    "shortcut_parser": re.compile(rb"ShortcutParser\.createShortcutFromManifest", re.I),
    "shortcut_service": re.compile(rb"ShortcutService\.(?:checkPackageChanges|rescanUpdatedPackagesLocked)", re.I),
    "art_resolution": re.compile(rb"artQuickResolutionTrampoline|RememberForGcArgumentVisitor", re.I),
    "zygote": re.compile(rb"\bzygote\b", re.I),
    "launcher": re.compile(rb"\bLauncher3\b|com\.android\.launcher3", re.I),
}
PID = re.compile(rb"\bpid\s*[:=]\s*([0-9]{2,7})\b", re.I)

def read_bounded(path):
    with path.open("rb") as f:
        size = path.stat().st_size
        if size > MAX_BYTES_PER_FILE:
            f.seek(size - MAX_BYTES_PER_FILE)
        return f.read(MAX_BYTES_PER_FILE)

def summarize(directory):
    if not directory.is_dir():
        raise ValueError("Crash proof directory does not exist")
    found = {}
    sources = []
    pids = set()
    for filename in FILES:
        src = directory / filename
        if not src.is_file() or src.is_symlink():
            continue
        data = read_bounded(src)
        sources.append(filename)
        for name, pattern in MARKERS.items():
            if pattern.search(data):
                found.setdefault(name, set()).add(filename)
        if filename in ("newest-tombstone.txt", "logcat-crash.txt"):
            for match in PID.finditer(data):
                pids.add(int(match.group(1)))
    if not sources:
        raise ValueError("No recognized crash proof inputs")
    flags = {k: k in found for k in MARKERS}
    if flags["sigsegv"] and flags["system_server"] and flags["shortcut_parser"] and flags["art_resolution"]:
        classification = "shortcut_manifest_art_sigsegv_indicators"
    elif flags["sigsegv"] and flags["system_server"]:
        classification = "system_server_sigsegv_indicators"
    elif flags["sigsegv"]:
        classification = "native_sigsegv_indicators"
    elif flags["shortcut_service"] or flags["shortcut_parser"]:
        classification = "shortcut_scan_indicators_no_signal"
    else:
        classification = "no_recognized_crash_markers"
    fingerprint_data = classification + "\n" + ",".join(
        marker for marker in sorted(MARKERS) if flags[marker]
    )
    return {
        "schema": 1,
        "classification": classification,
        "indicators": flags,
        "evidence_sources": {k: sorted(v) for k, v in sorted(found.items())},
        "sources_read": sources,
        "possible_pids": sorted(pids)[:25],
        "fingerprint_sha256": hashlib.sha256(fingerprint_data.encode("ascii")).hexdigest(),
        "note": "Co-occurring log markers; do not infer a shared native stack without tombstone review",
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proof-dir", type=Path, required=True)
    args = p.parse_args()
    report = summarize(args.proof_dir)
    (args.proof_dir / "crash-analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print("ANDROID_CRASH_CLASS=" + report["classification"])
    print("ANDROID_CRASH_FINGERPRINT=" + report["fingerprint_sha256"])
    print("ANDROID_CRASH_SOURCES=" + str(len(report["sources_read"])))

if __name__ == "__main__":
    main()
