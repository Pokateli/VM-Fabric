## Milestone — real Android 9 arm64-v8a Launcher3 + stable systemReady (October 30, 2026)

**Verified from real GitHub Actions artifact #13012470796, run #41127069219:**
- Booted API 28 ARM64 Google APIs guest on x86_64 host via 1-vCPU TCG.
- Guest `ro.product.cpu.abi=arm64-v8a`, ADB connected, `sys.boot_completed=1`.
- Android `system_server` PID **1671** remained unchanged across all **five** 20-second-interval ADB observations; `Service package: found` for every sample; `PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE`.
- ADB resolves HOME to **`com.android.launcher3/.Launcher`**, `SurfaceFlinger` and window services respond, `wm size` is `320x480`.
- ADB screenshot `android-screen-first.png` is **320x480 PNG, 69,340 bytes**; the image was opened and visually inspected and does show the Android home screen, Google search, Gmail, Photos, dialer, messages and status bar. Non-black pixel data alone was NOT used as visual proof.
- Guest `userdata-arm64.qcow2` passed `qemu-img check` after shutdown.

**Why this job nevertheless failed:** a *single* preliminary `package-service.txt` captured `Service package: not found` during early system_server startup, before the five later 100%-passing observations. The independent `portable-kit.py` packer incorrectly rejected this early diagnostic sample, despite stronger stable evidence. The initial sample is now accepted **only if** subsequent five same-PID samples and genuine Launcher3 framebuffer are fully verified. The old sample is retained for audit. Regression tests cover this exact real failure case and reject bogus initial text, PID changes, transient service or missing launcher.

- Follow-up GitHub run [#41129772918](https://github.com/Pokateli/VM-Fabric/actions/runs/41129772918) started with corrected packer and new `LAUNCHER_HOME_EVIDENCE` gate; pending result at last check.
- Main baseline remains experimental and unmodified by the selected OpenGL renderer; actual working candidate is isolated in this `android-arm64-legacy-hwui-lab-20261030` branch.
- Full `portability` and **second boot after restoring** the private kit remain UNVERIFIED. Never declare image `ready` before confirming restoration and repeat boot. Avoid publishing Google SDK binaries in public releases. Experimental guest still uses permissive SELinux and upstream binary patches.

---

## 2026-10-30 — system_server instability, exact stable-ready gate

The actual post-GUI test [#41122478374](https://github.com/Pokateli/VM-Fabric/actions/runs/41122478374) again reached `systemReady`, but the Android PackageManager service was **flapping**:
- 20:25:56 `READY: package service up`.
- 20:26:33 `Service package: not found`, directly after `ANDROID_ABI=arm64-v8a`.
- 20:27:02 boot monitor later observed `Service package: found`.
- 20:27:49 `ANDROID_GUI_STATUS=BLACK_FRAMEBUFFER`. Both 320x480 PNG captures had zero visible pixels. ADB `window` and `package` service commands also returned unavailable during GUI inspection.
- 20:28:37 the monitor reported ADB unavailable; stop/reboot of the test guest followed.

The prior workflow mistakenly used `grep -qi found` on `Service package: not found`, which falsely reported readiness, though subsequent pack step had a stricter exact check and refused publication. **The transport/publisher safely rejected the unstable image.**

Repaired pipeline:
- `verify-stable-ready.py`: five consecutive real ADB checks across >=80 seconds, all reporting `device`, `arm64-v8a`, `zygote=running`, and **exactly** `Service package: found`. It also requires the **same numeric system_server PID** across all five samples to detect rapid service restarts. Results: `STABILITY_RESULT.txt` and `stability-report.json`.
- Private portable-kit archive rejects missing, forged, transient or changed-PID stability samples; one transient `found` is no longer sufficient.
- Added synthetic regression coverage for `not found`, changing PIDs and stricter archive validation; 35/35 passed in [#41124939308](https://github.com/Pokateli/VM-Fabric/actions/runs/41124939308).
- A failed GitHub run [#41124688333](https://github.com/Pokateli/VM-Fabric/actions/runs/41124688333) was traced to a **single quote in a comment** inside the workflow's `bash -c '...'` nested network-namespace block. The shell tried `cd _` instead of launching QEMU. Fixed in commit `32eb342d`, with `tests/test_android_workflow.py` checking the nested script contains no unescaped apostrophes and passes `bash -n`.
- [Full TCG run #41125122042](https://github.com/Pokateli/VM-Fabric/actions/runs/41125122042) was downloading the pinned ARM64 SDK at last inspection.
- Experimental `patch-art-experiment.py` supports a **disabled-by-default** no-JIT switch before pinned zygote restart for a later controlled ART fault experiment. It has not been applied to production or baseline image, and it does not claim to repair `libart.so` SIGSEGV.

**Status remains experimental**. There is proven intermittent Android ARM64 `systemReady`, **not** stable PackageManager, working Launcher, or distributable portable image. The test image must remain isolated and avoid personal credentials.

---

## 2026-10-30 — CONFIRMED Android ARM64 systemReady on real TCG; GUI next

### Android Framework / graphics analysis from actual guest logs

The full `emulator-tail.log` in artifact #13008991563 contains ARM64 crash
backtraces after Android PackageManager startup:

- At guest uptime ~149s, `system_server` SIGSEGV in
  `/system/lib64/libart.so` `art::RememberForGcArgumentVisitor::Visit`,
  reached through ART quick resolution and `ActivityStarter.execute` /
  `ActivityManagerService.startHomeActivityLocked`. This strongly suggests
  the first HOME launch encounters an ART crash.
- At ~252-280s, `com.android.settings` `RenderThread` SIGSEGV in
  `/system/lib64/libhwui.so` (`GrGLProgramBuilder::CreateProgram`,
  `GrShaderVar::appendDecl`) on the Skia/OpenGL rendering path.
- `SurfaceFlinger`, `vendor.gralloc-2-0`, and
  `vendor.hwcomposer-2-1` all start; the remaining task is stabilizing
  UI processes and renderer on `-gpu swiftshader_indirect`.
- A controlled GPU-renderer comparison may be necessary. Do NOT claim a
  working Launcher based on `SurfaceFlinger` or `package` alone.
  `inspect-gui.py` captures bounded ADB crash logcat plus window/activity
  diagnostics and classifies an all-black PNG separately.



[GitHub Actions #41120493624](https://github.com/Pokateli/VM-Fabric/actions/runs/41120493624) is the **first successful real ARM64 Android PackageManager / systemReady run**. The workflow job ultimately failed **after** this milestone during kit packaging, so do not describe the entire job as successful.

Immutable evidence downloaded directly from Actions artifact #13008991563 (\`vm-fabric-android-arm64-tcg-proof\`):
- \`RESULT.txt\`: \`PASS_REAL_ANDROID_ARM64_TCG_BOOT\`
- \`android-properties.txt\`: \`ANDROID_ABI=arm64-v8a\`
- \`package-service.txt\`: \`Service package: found\`
- \`boot-gate-result.txt\`: \`ANDROID_BRINGUP_RETURNED_SUCCESS\`
- Runner log: \`READY: package service up (systemReady reached)\` and Android SDK API 28 on true QEMU TCG without KVM.
- ADB screencap \`android-screen.png\` exists and is 320x480 RGBA, 1662 bytes. **The actual framebuffer is entirely black** (all RGB values zero), so this is NOT proof of Launcher/desktop UI. The old code only checked the PNG header, hence incorrectly reported \`PASS real Android framebuffer PNG\`.

The post-boot pack step failed because the root-started emulator created a transient SDK file \`bootcompleted.ini\` that the unprivileged packer could not read (\`PermissionError\`). The portable-kit filter now excludes it and other emulator runtime lock files. A new \`inspect-gui.py\` runs local ADB wake/HOME/activity/SurfaceFlinger checks, captures framebuffer twice, decodes PNG filters via stdlib, and records \`BLACK_FRAMEBUFFER\` rather than claiming success on valid but empty PNG. A clean \`adb sync\` plus guest poweroff / QEMU stop is requested **before** backing up live \`userdata-arm64.qcow2\`; \`qemu-img check\` gates packing.

[Full follow-up workflow #41122478374](https://github.com/Pokateli/VM-Fabric/actions/runs/41122478374) was queued at last observation. Do NOT mark a portable private kit complete until that workflow actually uploads \`vm-fabric-android-arm64-private-kit\` and passes its SHA256 proof. Development profile is still experimental until Launcher UI proof and reproducible restore pass.

---
## 2026-10-30 evening — real Android ARM64 ADB connected; upstream timeout bug fixed

Real [GitHub boot #41064708650](https://github.com/Pokateli/VM-Fabric/actions/runs/41064708650) completed **failure** after fixing the earlier SELinux restorecon failure. This was **not another guest kernel failure**. Both primary job logs and the downloaded `vm-fabric-android-arm64-tcg-proof` artifact were inspected:

- `-selinux permissive` applied successfully to the pinned 37.3.3 Android Emulator.
- Guest kernel mounted the actual ARM64 system/vendor, Android first-stage init continued into second-stage init.
- Guest launched `surfaceflinger`, `adbd`, `bootanim`, and many other init services.
- `boot-monitor.log` recorded **`ADB_STATE=device`** at ~45s and **`ro.product.cpu.abi=arm64-v8a`** from the real running guest. **This is the first confirmed real ADB connection to Android ARM64 in VM-Fabric.**
- The upstream host bring-up script then exited code 127 at `timeout: failed to run command 'adbx': No such file or directory`. Exact cause: `adbx()` is a POSIX shell function in `scripts/lib/common.sh`, but GNU `timeout` can execute only external binaries. The two offending sites were `timeout 60 adbx root` and `timeout 300 adbx wait-for-device`. The first command swallowed exit 127 with `|| true`, the second aborted.
- **Fix:** new `profiles/android-arm64/scripts/patch-bringup-adb.py` verifies/replaces the two exact sites with `timeout ... "$ADB_BIN" -s "$SERIAL" ...`; the patch is idempotent and refuses unknown upstream changes. It is invoked immediately after cloning the exact pinned revision and before downloading the SDK.
- **Regression:** [GitHub #41120272947](https://github.com/Pokateli/VM-Fabric/actions/runs/41120272947) completed **success, 24/24 tests**, including an executable mock ADB verification.
- [Full TCG boot #41120204233](https://github.com/Pokateli/VM-Fabric/actions/runs/41120204233) was at SDK download on last inspection. The latest committed workflow also includes private streaming image packaging **only if** `PASS_REAL_ANDROID_ARM64_TCG_BOOT`, `ANDROID_ABI=arm64-v8a` and `Service package: found` all exist. A transient malformed YAML due to string replacement was corrected; [run #41120493624](https://github.com/Pokateli/VM-Fabric/actions/runs/41120493624) is the validated follow-up pipeline.
- **Still unconfirmed:** `service check package` after the Android zygote/media stub restart; Android Launcher GUI framebuffer; disk persistence; reduced-RAM operation inside ChatGPT. The profile remains `experimental` and disabled for regular run.

---
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
