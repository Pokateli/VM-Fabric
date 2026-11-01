#!/usr/bin/env python3
"""VM-Fabric: profile-based virtual machine orchestration (stdlib only)."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILES = ROOT / "profiles"


def load_profile(profile_id):
    if not profile_id or not profile_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid profile ID")
    folder = PROFILES / profile_id
    manifest = folder / "profile.json"
    if not manifest.is_file():
        raise ValueError(f"Unknown profile: {profile_id}")
    profile = json.loads(manifest.read_text(encoding="utf-8"))
    if profile.get("id") != profile_id:
        raise ValueError(f"Manifest ID mismatch: {profile_id}")
    return profile, folder


def script_path(profile, folder, key):
    name = profile.get(key)
    if not isinstance(name, str) or not name:
        raise ValueError(f"{profile['id']} has no configured {key}")
    path = (folder / name).resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file():
        raise ValueError(f"Missing or unsafe {key}: {name}")
    return path


def ready(profile):
    if profile.get("status") != "ready":
        raise ValueError(f"Profile '{profile['id']}' is {profile.get('status')}; execution disabled")


def default_target(profile_id):
    return Path("/mnt/data/vm-fabric") / profile_id


def launch(args):
    p, folder = load_profile(args.profile)
    if args.operation == "list":
        raise AssertionError("list handled separately")
    if args.operation == "info":
        print(json.dumps(p, ensure_ascii=False, indent=2))
        return 0
    # Experimental profiles can be inspected, deployed and verified for development.
    # Only execution and image-building require a completed, ready profile.
    if args.operation in ("run", "build"):
        ready(p)
    if args.operation == "deploy":
        shell = script_path(p, folder, "bootstrap_script")
        dest = args.target or default_target(args.profile)
        return subprocess.call(["bash", str(shell), str(args.archive), str(dest)])
    if args.operation == "doctor":
        if args.profile != "android-arm64" or p.get("os") != "android":
            raise ValueError("Offline doctor supported only for android-arm64")
        helper = script_path(p, folder, "doctor_script")
        target = (args.target or default_target(args.profile)).resolve()
        return subprocess.call([sys.executable, str(helper), "--target", str(target),
                                "--ram", str(args.ram)])
    if args.operation == "smoke":
        if args.profile != "android-arm64" or p.get("os") != "android":
            raise ValueError("Experimental smoke is supported only for android-arm64")
        runner = script_path(p, folder, "smoke_script")
        target = (args.target or default_target(args.profile)).resolve()
        session = args.session.resolve()
        return subprocess.call([
            "bash", str(runner), "--kit", str(target), "--session", str(session),
            "--ram", str(args.ram)
        ])
    if args.operation == "build":
        shell = script_path(p, folder, "build_script")
        target = args.output_dir.resolve()
        target.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["OUTPUT_DIR"] = str(target)
        return subprocess.call(["bash", str(shell)], env=env, cwd=ROOT)
    if args.operation == "verify":
        target = (args.target or default_target(args.profile)).resolve()
        if p.get("os") == "android":
            helper = script_path(p, folder, "verify_script")
            return subprocess.call([sys.executable, str(helper),
                                    "--target", str(target)])
        if p.get("os") == "windows":
            runner = script_path(p, folder, "verify_script")
            return subprocess.call([sys.executable, str(runner), "verify",
                                    "--vm-dir", str(target)])
        if not (target / "DEBIAN_IMAGE_SHA512SUMS").is_file():
            raise ValueError(f"Missing VM base image at {target}")
        checks = [
            ["sha512sum", "-c", "DEBIAN_IMAGE_SHA512SUMS"],
            [str(target / "lib/ld-linux-x86-64.so.2"), "--library-path",
             str(target / "lib"), str(target / "bin/qemu-img"),
             "check", "-f", "qcow2", str(target / p.get("base_disk", "debian13.qcow2"))],
        ]
        for check in checks:
            rc = subprocess.call(check, cwd=target)
            if rc != 0:
                return rc
        return 0
    if args.operation == "run":
        if p.get("os") == "windows" and (args.command is not None or args.script is not None):
            raise ValueError("Windows GUI profiles do not support Bash --command or --script; use console instead")
        mode = args.mode
        if mode != "auto" and mode not in p.get("runtime", []):
            raise ValueError(f"{args.profile} does not support runtime {mode}")
        shell = script_path(p, folder, "run_script")
        target = (args.target or default_target(args.profile)).resolve()
        cmd = ["bash", str(shell), "--mode", mode, "--bundle", str(target),
               "--timeout", str(args.timeout)]
        if args.command is not None:
            cmd.extend(["--command", args.command])
        if args.script is not None:
            cmd.extend(["--script", str(args.script.resolve())])
        if args.log is not None:
            cmd.extend(["--log", str(args.log.resolve())])
        if args.output is not None:
            cmd.extend(["--output", str(args.output.resolve())])
        return subprocess.call(cmd)
    if args.operation == "session":
        if p.get("os") != "windows":
            raise ValueError("Session snapshot operations are only implemented for Tiny11")
        helper = script_path(p, folder, "session_script")
        target = (args.target or default_target(args.profile)).resolve()
        return subprocess.call([sys.executable, str(helper), args.action,
                                "--vm-dir", str(target),
                                "--snapshot-dir", str(args.snapshot_dir.resolve())])
    if args.operation == "console":
        if p.get("os") == "android":
            if args.action not in ("status", "screenshot", "sendkey", "powerdown", "click"):
                raise ValueError("Android ADB console supports status/screenshot/sendkey/click/powerdown only")
            helper = script_path(p, folder, "console_script")
            target = (args.target or default_target(args.profile)).resolve()
            action = "tap" if args.action == "click" else args.action
            cmd = [sys.executable, str(helper), action, "--bundle", str(target)]
            if args.output is not None:
                cmd.extend(["--output", str(args.output.resolve())])
            if args.keys is not None:
                cmd.extend(["--keys", args.keys])
            if action == "tap":
                cmd.extend(["--dx", str(args.dx), "--dy", str(args.dy)])
            return subprocess.call(cmd)
        if p.get("os") != "windows":
            raise ValueError("Console not supported for this VM profile")
        helper = script_path(p, folder, "console_script")
        target = (args.target or default_target(args.profile)).resolve()
        cmd = [sys.executable, str(helper), args.action, "--vm-dir", str(target)]
        if args.output is not None:
            cmd.extend(["--output", str(args.output.resolve())])
        if args.keys is not None:
            cmd.extend(["--keys", args.keys])
        if args.action in ("mousemove","mousedown","mouseup","click"):
            cmd.extend(["--dx",str(args.dx),"--dy",str(args.dy),"--button",args.button])
        return subprocess.call(cmd)
    raise ValueError(f"Unsupported operation: {args.operation}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list", help="List installed VM profiles and maturity")
    info = sub.add_parser("info", help="Show a profile JSON manifest")
    info.add_argument("profile")
    deploy = sub.add_parser("deploy", help="Verify/unpack an artifact in the current environment")
    deploy.add_argument("profile")
    deploy.add_argument("--archive", type=Path, required=True)
    deploy.add_argument("--target", type=Path)
    doctor = sub.add_parser("doctor", help="Read-only offline Android ARM64 preflight (no VM boot)")
    doctor.add_argument("profile")
    doctor.add_argument("--target", type=Path)
    doctor.add_argument("--ram", default="auto")
    smoke = sub.add_parser("smoke", help="Explicit offline experimental Android ARM64 single-boot test")
    smoke.add_argument("profile")
    smoke.add_argument("--target", type=Path)
    smoke.add_argument("--session", type=Path, required=True)
    smoke.add_argument("--ram", default="auto")
    build = sub.add_parser("build", help="Build an image from migrated sources (Docker on build host)")
    build.add_argument("profile")
    build.add_argument("--output-dir", type=Path, required=True)
    verify = sub.add_parser("verify", help="Validate the deployed base QCOW2")
    verify.add_argument("profile")
    verify.add_argument("--target", type=Path)
    run = sub.add_parser("run", help="Boot guest in ChatGPT/local or GitHub Actions")
    run.add_argument("profile")
    run.add_argument("--target", type=Path)
    run.add_argument("--mode", choices=["auto", "chat", "github"], default="auto")
    payload = run.add_mutually_exclusive_group()
    payload.add_argument("--command")
    payload.add_argument("--script", type=Path)
    run.add_argument("--log", type=Path)
    run.add_argument("--output", type=Path)
    run.add_argument("--timeout", type=int, default=240)
    session = sub.add_parser("session", help="Save/restore a STOPPED Tiny11 writable overlay and UEFI state")
    session.add_argument("profile")
    session.add_argument("action", choices=("save", "restore"))
    session.add_argument("--target", type=Path)
    session.add_argument("--snapshot-dir", type=Path, required=True)
    console = sub.add_parser("console", help="Control an offline Tiny11 QEMU GUI session")
    console.add_argument("profile")
    console.add_argument("--target", type=Path)
    console.add_argument("action", choices=("status", "screenshot", "wake", "powerdown", "sendkey", "mousemove", "mousedown", "mouseup", "click"))
    console.add_argument("--output", type=Path)
    console.add_argument("--keys")
    console.add_argument("--dx", type=int, default=0)
    console.add_argument("--dy", type=int, default=0)
    console.add_argument("--button", choices=("left","middle","right"), default="left")
    args = parser.parse_args()
    try:
        if args.operation == "list":
            for manifest in sorted(PROFILES.glob("*/profile.json")):
                data = json.loads(manifest.read_text(encoding="utf-8"))
                print(f"{data['id']:<14} {data['status']:<14} {data['name']}")
            return 0
        return launch(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"VM-Fabric: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
