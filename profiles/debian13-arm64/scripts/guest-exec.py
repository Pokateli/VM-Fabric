#!/usr/bin/env python3
"""Run a script in an offline Debian QEMU VM through its serial root console."""
import argparse
import os
import pty
import re
import secrets
import select
import signal
import subprocess
import sys
import time
import tty
from pathlib import Path

ANSI = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
PROMPT = re.compile(rb"root@[A-Za-z0-9_.-]+:[^\r\n]{0,120}#\s")
FIRSTBOOT = (b"Press any key to proceed", b"Please enter the new timezone")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", required=True, type=Path)
    inp = ap.add_mutually_exclusive_group(required=True)
    inp.add_argument("--command")
    inp.add_argument("--script", type=Path)
    ap.add_argument("--log", type=Path, default=Path("guest-console.log"))
    ap.add_argument("--output", type=Path, default=Path("guest-output.txt"))
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    if not 30 <= args.timeout <= 3600:
        ap.error("--timeout must be between 30 and 3600 seconds")
    bundle = args.bundle.resolve()
    if not (bundle / "start.sh").is_file() or not (bundle / "sharefiles").is_dir():
        ap.error(f"Incomplete VM directory: {bundle}")
    if args.script is not None:
        contents = args.script.read_bytes()
    else:
        contents = ("#!/usr/bin/env bash\nset -eo pipefail\n" + args.command + "\n").encode("utf-8")
    if not contents or len(contents) > 1_000_000 or b"\0" in contents:
        ap.error("Script must be nonempty, <= 1MB, and contain no NUL bytes")
    contents = contents.replace(b"\r\n", b"\n")
    token = secrets.token_hex(12).upper()
    payload_name = f"v{token[:12].lower()}.sh"
    payload = bundle / "sharefiles" / payload_name
    if payload.exists():
        ap.error("Temporary guest script path already exists")
    payload.write_bytes(contents)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    master = -1
    slave = -1
    proc = None
    sent = False
    result = None
    transcript = bytearray()
    error = None
    begin = ("GUEST_BEGIN_" + token).encode()
    finish = re.compile(rb"(?:^|\n)GUEST_RESULT_" + token.encode()
                        + rb"_RC=([0-9]+)(?:\n|$)")
    deadline = time.monotonic() + args.timeout
    try:
        master, slave = pty.openpty()
        tty.setraw(slave)  # Disable software flow control on serial console.
        proc = subprocess.Popen([str(bundle / "start.sh")], stdin=slave,
                                stdout=slave, stderr=slave,
                                start_new_session=True, close_fds=True)
        os.close(slave)
        slave = -1
        with args.log.open("wb") as logfile:
            while time.monotonic() < deadline:
                if proc.poll() is not None and result is None:
                    error = f"QEMU exited before guest command ({proc.returncode})"
                    break
                ready, _, _ = select.select([master], [], [], 0.5)
                if not ready:
                    if result is not None and proc.poll() is not None:
                        break
                    continue
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                logfile.write(data)
                logfile.flush()
                transcript.extend(data)
                if len(transcript) > 16_000_000:
                    error = "Guest console log exceeds 16 MB"
                    break
                clean = re.sub(rb"\r+\n?", b"\n", ANSI.sub(b"", bytes(transcript)))
                if not sent and any(x in clean for x in FIRSTBOOT):
                    error = "Interactive firstboot wizard detected"
                    break
                if not sent and PROMPT.search(clean):
                    # Script is loaded from the read-only VirtIO FAT disk.
                    serial = (
                        "mkdir -p /mnt/dual-vm-run; share_ready=0; "
                        "for blk in /dev/vd[a-z] /dev/vd[a-z][0-9]* "
                        "/dev/sd[a-z] /dev/sd[a-z][0-9]*; do "
                        "test -b \"$blk\" || continue; "
                        "if mount -t vfat -o ro \"$blk\" /mnt/dual-vm-run 2>/dev/null; then "
                        f"if test -f /mnt/dual-vm-run/{payload_name}; then share_ready=1; break; fi; "
                        "umount /mnt/dual-vm-run; "
                        "fi; done; "
                        "if [ \"$share_ready\" -eq 1 ]; then "
                        f"printf '\\nGUEST_BEGIN_{token}\\n'; "
                        f"bash /mnt/dual-vm-run/{payload_name}; rc=$?; "
                        "else echo 'Unable to mount guest share' >&2; rc=125; fi; "
                        f"printf '\\nGUEST_RESULT_{token}_RC=%s\\n' \"$rc\"; "
                        "sync; systemctl poweroff\n"
                    )
                    os.write(master, serial.encode("ascii"))
                    sent = True
                if sent and result is None:
                    match = finish.search(clean)
                    if match:
                        result = int(match.group(1))
                if result is not None and proc.poll() is not None:
                    break
        clean = re.sub(rb"\r+\n?", b"\n", ANSI.sub(b"", bytes(transcript)))
        start = re.search(rb"(?:^|\n)" + re.escape(begin) + rb"\n", clean)
        end = finish.search(clean, start.end()) if start else None
        output = clean[start.end():end.start()] if start and end else b""
        args.output.write_bytes(output.lstrip(b"\n"))
        if result is None:
            print("FAIL: " + (error or "Guest command timed out"), file=sys.stderr)
            print("Console: " + str(args.log), file=sys.stderr)
            return 1
        if proc.poll() is None:
            try:
                proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                error = "Guest finished but QEMU did not shut down"
        if error:
            print("FAIL: " + error, file=sys.stderr)
            return 1
        if proc.returncode != 0:
            print(f"FAIL: QEMU exit code {proc.returncode}", file=sys.stderr)
            return 1
        print(f"GUEST_OK: mode=batch rc={result} console={args.log} output={args.output}")
        if output:
            print(output.decode("utf-8", errors="replace"))
        return 0 if result == 0 else (result if result <= 125 else 1)
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        if master != -1:
            os.close(master)
        if slave != -1:
            os.close(slave)
        payload.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
