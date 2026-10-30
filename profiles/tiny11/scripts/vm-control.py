#!/usr/bin/env python3
"""Control a LOCAL running Tiny11 QEMU VM using its loopback-only HMP monitor.

Available commands: status, screenshot, wake, powerdown, sendkey. No network or guest data upload.
This controls a running QEMU process, NOT GitHub Actions and not a remote computer.
The ready QCOW2 remains immutable; launch sessions use their own QCOW2 overlay.
"""
import argparse
import re
from pathlib import Path
import socket
import sys
import time

def talk(address: Path, command: str) -> str:
    if not address.is_socket():
        raise SystemExit(f"QEMU monitor not found: {address}")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(0.8)
        try:
            conn.connect(str(address))
        except (ConnectionRefusedError, FileNotFoundError, socket.timeout) as exc:
            raise SystemExit(f"QEMU session is not running (stale monitor): {address} ({exc})")
        # The greeting and first '(qemu)' prompt may arrive in separate reads.
        # Drain it fully before sending the command, or it can be mistaken for
        # the RESPONSE prompt, producing a false empty 'info status'.
        def until_prompt(timeout=5):
            end_time=time.monotonic()+timeout
            data=bytearray()
            while time.monotonic()<end_time:
                try:
                    block=conn.recv(8192)
                except socket.timeout:
                    continue
                if not block:break
                data.extend(block)
                if data.endswith(b"(qemu) "):break
                if len(data)>256*1024:raise SystemExit("HMP reply too large")
            return data.decode("utf-8", errors="replace")
        until_prompt()
        conn.sendall((command + "\n").encode("ascii"))
        response=until_prompt()
        # Strip HMP keyboard echo and final prompt, retain command output.
        if "\r\n" in response: response=response.split("\r\n",1)[1]
        if "(qemu) " in response: response=response.rsplit("(qemu) ",1)[0]
        return response.strip()

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "screenshot", "wake", "powerdown", "sendkey", "mousemove", "mousedown", "mouseup", "click"))
    parser.add_argument("--vm-dir", type=Path, default=Path("/mnt/data/tiny11-ready"))
    parser.add_argument("--monitor", type=Path,
                        help="Unix monitor path, otherwise use VM directory qemu-monitor.sock")
    parser.add_argument("--output", type=Path, help="PNG/PPM screenshot output")
    parser.add_argument("--keys", help="QEMU key combination, e.g. ctrl-esc or meta_l-r")
    parser.add_argument("--dx", type=int, default=0, help="Relative mouse X movement")
    parser.add_argument("--dy", type=int, default=0, help="Relative mouse Y movement")
    parser.add_argument("--button", choices=("left", "middle", "right"), default="left")
    args = parser.parse_args()
    root = args.vm_dir.resolve()
    addr = (args.monitor or root / "qemu-monitor.sock").resolve()
    if args.action == "status":
        print(talk(addr, "info status"))
        print(talk(addr, "info kvm"))
        return
    if args.action == "wake":
        print(talk(addr, "system_wakeup"))
        print("Wake request sent; verify with 'status'.")
        return
    if args.action == "powerdown":
        print(talk(addr, "system_powerdown"))
        print("ACPI shutdown requested (not yet confirmed).")
        return
    if args.action == "sendkey":
        # Fixed key-name alphabet prevents injecting additional HMP commands.
        if not args.keys or not re.fullmatch(r"[A-Za-z0-9_+.-]{1,128}",args.keys):
            parser.error("--keys must contain a valid QEMU key combination")
        print(talk(addr, "sendkey "+args.keys))
        return
    if args.action in ("mousemove", "mousedown", "mouseup", "click"):
        if not (-3000 <= args.dx <= 3000 and -3000 <= args.dy <= 3000):
            parser.error("mouse movement must be in -3000..3000 pixels")
        state={"left":1, "middle":2, "right":4}[args.button]
        if args.action == "mousemove":
            print(talk(addr, f"mouse_move {args.dx} {args.dy}"))
        elif args.action == "mouseup":
            print(talk(addr, "mouse_button 0"))
        elif args.action == "mousedown":
            print(talk(addr, f"mouse_button {state}"))
        elif args.action == "click":
            if args.dx or args.dy:
                talk(addr, f"mouse_move {args.dx} {args.dy}")
            talk(addr, f"mouse_button {state}")
            print(talk(addr, "mouse_button 0"))
        return
    output = (args.output or root / "tiny11-desktop.png").resolve()
    if output.suffix.lower() not in (".png", ".ppm"):
        raise SystemExit("Screenshot output must end in .png or .ppm")
    output.parent.mkdir(parents=True, exist_ok=True)
    ppm = output if output.suffix.lower() == ".ppm" else output.with_suffix(".ppm")
    if ppm.exists():
        ppm.unlink()
    response = talk(addr, f"screendump {ppm}")
    if not ppm.exists() or ppm.stat().st_size < 1024:
        raise SystemExit("QEMU screendump failed: " + response[-1200:])
    if output.suffix.lower() == ".png":
        try:
            from PIL import Image
            with Image.open(ppm) as image:
                image.save(output)
        except ImportError:
            print("Pillow not available: leaving uncompressed PPM at", ppm)
            return
        ppm.unlink()
    print("Screenshot saved:", output, output.stat().st_size, "bytes")

if __name__ == "__main__":
    main()
