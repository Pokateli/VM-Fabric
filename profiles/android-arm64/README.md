# Android ARM64 (experimental) in VM-Fabric

## Purpose

A **real** `arm64-v8a` Android guest on an `x86_64` ChatGPT or GitHub host,
using Google's special Android Emulator QEMU AArch64/ranchu engine and software
TCG. This is **not Android-x86** and is not a generic Linux/QEMU `virt`
disk image.

**Baseline:** Android 9 (API 28), Google APIs ARM64.
**Status:** experimental until a GitHub Actions run produces true ADB evidence
`getprop ro.product.cpu.abi == arm64-v8a` and
`service check package == ... found`. A live screenshot of the launcher is a
separate, stronger gate; reaching `systemReady` does not prove Android GUI.

## Source and build

- First-boot reference: https://github.com/lhns/android-arm-tcg
- Exact source revision:
  `f9eecf6c0d2fcc1e255b5a6d7322b07cbe017ba9` (MIT).
- Google SDK source:
  `system-images;android-28;google_apis;arm64-v8a`.
- Emulator pinned to build `16489710` with verified downloaded SHA-256
  `a0da0fa20903a69ae52ab501f30fc5c768dcce31434cd2f55d52addc1a2c0495`.
- Windows/Tiny11 or Debian profiles are **not** modified by this candidate.
- Test workflow:
  [Android ARM64 first TCG boot](https://github.com/Pokateli/VM-Fabric/actions/workflows/build-android-arm64.yml)
  on branch `android-arm64-tcg-20261030`.

The upstream toolkit is **not** an official Google VM image builder. It
patches specific Android/emulator binary bytes, rebuilds an ARM64 ramdisk,
removes several crash-looping HAL registrations, and disables encryption of
the disposable test `/data` volume. The in-guest bring-up disables SELinux
enforcement. Treat this profile as a **disposable development-only guest**,
with no personal accounts, secrets, or sensitive APKs.

The workflow downloads official Google SDK files, checks the pinned emulator
ZIP SHA-256, verifies ARM64 SDK metadata, cross-compiles an AArch64 init
wrapper and runs the patched guest with `ANDROID_I_WANT_MY_TCG=yes` and
`-accel off`. It uses a Linux network namespace with only loopback for local
ADB: no guest Internet is needed for these tests.

## Run / control after a successful build

The current VM-Fabric profile is intentionally **not yet enabled**; a
successfully deployed bundle is still needed. When the real guest boot is
validated, the runtime can be enabled. Source-only skeleton:

```bash
python3 vmfabric.py info android-arm64
# After installing the SDK and ARM64 ramdisk:
python3 profiles/android-arm64/scripts/verify.py --target /mnt/data/vm-fabric/android-arm64
# On a live emulator (private local ADB):
python3 vmfabric.py console android-arm64 status
python3 vmfabric.py console android-arm64 screenshot --output /mnt/data/android-arm64.png
python3 vmfabric.py console android-arm64 sendkey --keys KEYCODE_HOME
python3 vmfabric.py console android-arm64 click --dx 320 --dy 520
```

GitHub's x86_64 KVM cannot accelerate an ARM64 guest. Emulation is
slow and the reference toolkit was designed for 4GiB *guest* RAM.
The ChatGPT sandbox may have a 4GiB **total** memory cgroup: launching
that 4GiB guest there is expected to run out of RAM. Reducing guest
RAM to 2–3GiB requires another **real** Android boot/ART stability
validation; it cannot be assumed safe. For now, prefer first boot on
the GitHub runner with more host memory.

## Next quality gates

1. Pass image provenance/ABI/emulator checks on GitHub.
2. Boot Android first-stage kernel and init wrapper.
3. Require `arm64-v8a` from real ADB and package service.
4. Obtain real GUI screenshot using `adb exec-out screencap -p`, test input.
5. Check reboot, persistence, resource limits and safe delivery to ChatGPT.
6. Only then mark VM-Fabric profile `ready`.
