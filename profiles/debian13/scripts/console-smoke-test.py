#!/usr/bin/env python3
"""Boot QEMU and require an automatic interactive root shell on ttyS0."""
import os
import pty
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

if len(sys.argv) not in (2, 3):
    sys.exit("Usage: console-smoke-test.py BUNDLE [LOG]")
bundle = Path(sys.argv[1]).resolve()
logpath = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else Path("boot-console.log").resolve()
master, slave = pty.openpty()
proc = subprocess.Popen([str(bundle / "start.sh")], stdin=slave, stdout=slave,
                        stderr=slave, start_new_session=True, close_fds=True)
os.close(slave)
recent = bytearray()
sent = False
success = False
kernel = None
deadline = time.monotonic() + 165
ansi = re.compile(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
shell = re.compile(rb"root@[a-zA-Z0-9_.-]+:[^\r\n]{0,100}#\s")
probe = re.compile(rb"CHATGPT_ROOT_READY:0:([A-Za-z0-9.+_-]+)")
error = None

try:
    with logpath.open("wb") as log:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                error = f"QEMU exited unexpectedly ({proc.returncode})"
                break
            ready, _, _ = select.select([master], [], [], 1.0)
            if not ready:
                continue
            try:
                block = os.read(master, 65536)
            except OSError:
                break
            if not block:
                break
            log.write(block)
            log.flush()
            recent.extend(block)
            if len(recent) > 163840:
                del recent[:-131072]
            clean = ansi.sub(b"", bytes(recent)).replace(b"\r", b"\n")
            if b"Press any key to proceed" in clean or b"Please enter the new timezone" in clean:
                error = "Interactive systemd-firstboot wizard detected"
                break
            if not sent and shell.search(clean):
                os.write(master, b'printf "CHATGPT_ROOT_READY:%s:%s\\n" "$(id -u)" "$(uname -r)"; systemctl poweroff\n')
                sent = True
            match = probe.search(clean) if sent else None
            if match:
                kernel = match.group(1).decode()
                success = True
                break
    if success:
        print(f"PASS: unattended root console, uid=0, guest kernel={kernel}, log={logpath}")
    else:
        print(f"FAIL: {error or 'root shell not reached before timeout or EOF'}; log={logpath}", file=sys.stderr)
        if recent:
            print(ansi.sub(b"", bytes(recent[-5000:])).decode(errors="replace"), file=sys.stderr)
finally:
    if proc.poll() is None:
        try:
            proc.wait(timeout=20 if success else 1)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    os.close(master)
if not success:
    sys.exit(1)
