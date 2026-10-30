## 2026-10-30 — Root-cause confirmed from actual two failed guest boots

**Real failure evidence, not a slow/blocked ADB alone:** both [#41042485490](https://github.com/Pokateli/VM-Fabric/actions/runs/41042485490) and [#41038844377](https://github.com/Pokateli/VM-Fabric/actions/runs/41038844377) exited with `failure` after ~57 minutes. Independently downloaded and inspected the attached `emulator-tail.log` and `boot-monitor.log`. Actual ARM64 Linux 4.4.302 kernel boots, mounts `vda1` as system and `vde` as vendor, Android first-stage init starts, loads precompiled vendor SELinux policy and switches to enforcing (`enforcing=1 old_enforcing=0`). Then:
```text
avc: denied { fowner } for pid=1 comm="init" capability=3 ... permissive=0
SELinux: Could not set context for /init: Operation not permitted
init: restorecon failed of /init failed: Operation not permitted
init: Reboot start, reason: reboot, rebootTarget: bootloader
Reboot failed -- System halted
```
QEMU stayed alive and used ~100% of one host vCPU, but Android was already halted; `ADB_STATE=unavailable` throughout. Therefore the previous timeout was a false sign of progress, and must not be repeated.

**Fix on branch:** new pinned/byte-checked `patch-guest-selinux.py` inserts documented Android Emulator option `-selinux permissive` in **guest** QEMU launcher before Android first-stage init (not on the host; development-only, not suitable for real devices or sensitive accounts). New `boot-gate.sh` aborts within five seconds of guest init reboot/kernel fatal and captures `guest-fatal.txt`, without letting the runner waste an hour waiting for nonexistent ADB. In workflow commit `5c69be7a`, both are wired into the boot pipeline.

The changed code passed **23/23 quick static/synthetic regression tests** in [#41064761233](https://github.com/Pokateli/VM-Fabric/actions/runs/41064761233), including idempotent early SELinux option injection and recognition of the actual reboot string. [New actual full TCG boot #41064708650](https://github.com/Pokateli/VM-Fabric/actions/runs/41064708650) was still installing the ARM64 cross-toolchain at last check. The untested workaround is **not yet proof of actual Android boot**.

---
## Update — current Android ARM64 bring-up and portable distribution

- [Live instrumented TCG boot #41042485490](https://github.com/Pokateli/VM-Fabric/actions/runs/41042485490): a real Linux GitHub runner, Android API28 `arm64-v8a` and pinned emulator; latest observation is **still in the boot/ADB step**. The live watchdog now writes `boot-monitor.log`, checking QEMU PID, ADB availability, `ro.product.cpu.abi`, zygote, `sys.boot_completed` and package service every 45s. A timeout or failure will attach a bounded `emulator-tail.log`. Do not infer guest readiness from an in-progress run.
- The workflow now attempts `adb exec-out screencap -p` after **actual** package service success, wakes the LCD first, and records `GUI_RESULT.txt`. GUI proof is separate from ADB/package-service proof.
- The **portable development-only private kit packer** `profiles/android-arm64/scripts/portable-kit.py` is implemented and has verified synthetic tar.gz/chunk roundtrip, SHA256 verification, refusal of wrong Android ABI, rejection of forged ADB/package-service marker and corruption detection. It streams compressed data into <=384 MiB parts, without a temporary multi-GB tar file. Packaging a real Google SDK image MUST wait until actual ADB package-service success; the packer checks `proof/RESULT.txt`, `proof/android-properties.txt` and `proof/package-service.txt`. Keep any such image private and respect the Android SDK license.
- [Portable kit + Android profile regression #41043161831](https://github.com/Pokateli/VM-Fabric/actions/runs/41043161831) completed **success**. The existing Tiny11/Debian profiles continue to pass in the same test suite.
- `vmfabric.py verify android-arm64` and the local ADB console now work on the experimental profile. Its `run` remains disabled until successful real guest boot; no false promotion to ready.
- Pending after successful GitHub proof: add a *guarded* pack/publish step in the Android workflow (not yet present), verify private artifact SHA256, then test QEMU ARM64 in the ChatGPT memory-limited container with a smaller guest-memory configuration.
- The existing upstream experiment involves experimental byte patches and relaxed guest security. Do not connect personal data or deploy its image to a public release.

---

# Android ARM64 — active TCG bring-up, 2026-10-30

## Verified on real GitHub Linux x86_64 runner

- Source code pinned to `lhns/android-arm-tcg@f9eecf6c0d2fcc1e255b5a6d7322b07cbe017ba9`, plus pinned emulator ZIP build `16489710` SHA-256 `a0da0fa20903a69ae52ab501f30fc5c768dcce31434cd2f55d52addc1a2c0495`.
- Google API28 system image actually downloaded and checked: source.properties says `AndroidVersion.ApiLevel=28`, `SystemImage.Abi=arm64-v8a`, `SystemImage.TagId=google_apis`.
- `kernel-ranchu` recognized as `Linux kernel ARM64 boot executable Image`.
- Emulator byte patches `soundhw-pci-abort`, `emu-keep-initramfs`, `heapsize-cap` succeeded with before/after verification.
- ARM64 kernel patch `kernel-keep-initramfs` and `fstab-dev-vde` patching succeeded.
- The guest vendor ext4 image was rebuilt and `vendor-forceencrypt` patch applied.
- First ARM64 cross-compile failure `bits/wordsize.h` traced to missing cross-architecture C library headers; fixed by adding `libc6-dev-arm64-cross` and a static AArch64 executable compile preflight before SDK download.
- GitHub workflow [#41038904545](https://github.com/Pokateli/VM-Fabric/actions/runs/41038904545) advanced to `Boot Android ARM64 under pure TCG without guest Internet`. At last checked, this step was **running**; there is **NO confirmed ADB package-service success or Android desktop** yet.
- A separate quick profile test [#41039313411](https://github.com/Pokateli/VM-Fabric/actions/runs/41039313411) completed **success** with 12 unit tests.
- Source branch: `android-arm64-tcg-20261030`, kept separate from `main` and existing ready Debian13 and Tiny11.
- This code uses special Google Android Emulator `qemu-system-aarch64-headless`, **not** generic upstream QEMU `virt` and not x86 Android.

## Caution

The upstream experiment modifies early Android boot, disables several test HAL services and guest SELinux enforcement, and strips user data `forceencrypt`: it is **NOT production-ready**. Experimental profile is intentionally disabled in `vmfabric.py run`. Do not use private accounts or sensitive data.

The guest reference configuration uses 4096 MiB guest RAM. ChatGPT x86_64 sandbox has an observed 4096 MiB total cgroup limit and no KVM. Running a 4096 MiB ARM64 guest in this chat is therefore not yet validated or recommended. First verify Android under GitHub TCG with more host RAM, then separately test reduced guest RAM without assuming ART will work.

## Remaining proof gates

1. Real QEMU TCG process still alive after Android boot.
2. ADB reports `ro.product.cpu.abi=arm64-v8a`.
3. Android `service check package` returns `found` (systemReady).
4. ADB PNG screenshot confirms launcher or explains UI failure.
5. Test controlled input, reboot, guest disk persistence and stop/restore.
6. Package guest and kernel, then verify ChatGPT sandbox resource limits.
7. Only after those proofs, change `profile.json` from `experimental` to `ready`.

Primary command entrypoints: `profiles/android-arm64/scripts/verify.py`,
`bootstrap.sh`, `run-vm.sh` (currently deliberate experimental gate),
`console.py` (ADB only), and `screenshot.py`.
