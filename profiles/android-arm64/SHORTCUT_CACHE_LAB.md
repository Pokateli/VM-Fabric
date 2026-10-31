# Android ARM64 second boot — ShortcutService cache isolation (2026-11-01)

## Grounded baseline
- Original restored Legacy OpenGL image: run 41132811947 failed stability gate on sample 5/5 (prior 4 passed).
- Isolated Safe Mode restoration: run 41134334742 passed 5/5 stable system_server PID, Launcher3, QCOW2 check, immutable base check.
- Safe Mode is diagnostic only. It prevents some ShortcutService package-change processing and is not a standard Android startup fix.

## Next experiment
This branch adds `ANDROID_SHORTCUT_TEST=cache-reset`, never enabled by default.
In a *disposable overlay* session, at the pinned zygote restart point it:
1. Stops zygote.
2. If present, moves `/data/system_ce/0/shortcut_service` to `/data/local/tmp/vmfabric-shortcut-cache-backup`. Refuses a pre-existing backup, a dangling backup symlink, or a missing source directory (no false-positive cache reset).
3. Explicitly disables persistent Safe Mode and restarts zygote.
4. Reads the real guest result marker and requires `SHORTCUT_CACHE_MOVED=1`, Safe Mode to be off, 5/5 stable package-service observations, genuine GUI evidence, clean QCOW2 check and immutable source-disk SHA256.

**Limitations:** A pass would implicate persisted ShortcutService state, not prove a precise ART root cause. A failure would suggest non-cache paths (package rescan, ART/JIT, framework or timing). Only the overlay gets modified; move is not a substitute for a recovery process in production. The prior image/SDK has relaxed guest security settings; do not use personal credentials.

## CI/storage
- Latest quick CI: [run #41250866246](https://github.com/Pokateli/VM-Fabric/actions/runs/41250866246) passed **60/60** tests, including executing the patched guest shell in a disposable local directory and checking host cgroup RAM decisions.
- The first obsolete restored-boot workflow [run #41250041676](https://github.com/Pokateli/VM-Fabric/actions/runs/41250041676) unexpectedly started on an intermediate workflow commit (before the archive fix). Its result is not evidence for this experiment.
- The corrected one-time restored-boot [run #41250738934](https://github.com/Pokateli/VM-Fabric/actions/runs/41250738934) was queued with `push` trigger scoped to this workflow file. Branch concurrency is configured to cancel obsolete runs.
- The Android kit was archived in a **private GitHub Release** (`actions-artifacts-archive-2026-10`) and deleted from temporary Actions artifacts. The new workflow downloads that exact private Release ZIP, validates its SHA256 sidecar, unpacks only the trusted kit, and uploads **no new Actions artifacts**. Only bounded job logs are retained.
- Local fast unit tests: `python3 -m unittest discover -s tests -p 'test_android_shortcut_cache.py' -v`.
- Static check: `python3 -m py_compile profiles/android-arm64/scripts/patch-shortcut-cache-experiment.py` and `bash -n profiles/android-arm64/scripts/boot-restored.sh`.
- Heavy test: the branch's `push` trigger runs only on updates to `.github/workflows/test-android-arm64-restored.yml`; it was enabled to run a single corrected proof. Do not change that workflow file without intending another heavy run. GitHub manual dispatch additionally requires the workflow to exist on the default branch; this development branch alone does not make that UI available.
- `boot-restored.sh` supports `ANDROID_GUEST_RAM_MIB=auto` or an explicit integer 1536–4096. `auto` derives the largest 256 MiB increment fitting the finite cgroup limit, current usage, and a **1024 MiB host reserve**. On the observed 4096 MiB cgroup with ~570 MiB in use it chooses **2304 MiB**; an explicit 4096 MiB guest fails closed. Without a finite cgroup limit, choose an explicit number (default 4096).
- For the documented `sudo unshare --net` invocation, preserve the opt-in RAM override using `ANDROID_GUEST_RAM_MIB=auto sudo --preserve-env=ANDROID_GUEST_RAM_MIB unshare ...`. If already root, export `ANDROID_GUEST_RAM_MIB=auto` before executing the script. Reduced-RAM Android guest startup is **not yet proven**; this guards against host OOM, not Android compatibility.
- Latest live boot [#41250738934](https://github.com/Pokateli/VM-Fabric/actions/runs/41250738934): archive restored from private Release with SHA256 verification. Guest test outcome must be checked separately; never infer success from archive restore.

## Follow-up
Compare with Safe Mode control and original normal-boot failure. If a successful cache-reset run repeats with normal mode, replace the experiment with a narrow first-boot cache regeneration or investigate the installed package triggering ShortcutService. Do not promote profile to ready until a normal-mode cold/warm boot and constrained 4 GiB host tests pass.

## 2026-11-01 — result of the destructive-cache hypothesis and next experiment

Real [cache-reset run #41250738934](https://github.com/Pokateli/VM-Fabric/actions/runs/41250738934) **failed by design with exit 96**. ADB connected and verified restored QEMU boot reached the pinned `40-bringup.sh` script. At the zygote restart, the exact directory `/data/system_ce/0/shortcut_service` did **not** exist. The cache-reset script wrote `SHORTCUT_CACHE_SOURCE_MISSING`, and refused to label an unmodified system as a repaired cache. This does not implicate a corrupt persisted shortcut cache.

The Android 9 AOSP `ShortcutService.checkPackageChanges()` code uses `injectIsSafeModeEnabled()` to skip `rescanUpdatedPackagesLocked()`; the same routine loops through installed packages and calls `rescanPackageIfNeeded`. Reference: https://android.googlesource.com/platform/frameworks/base/+/android-9.0.0_r30/services/core/java/com/android/server/pm/ShortcutService.java . The previous archived native tombstone shows `ShortcutParser.createShortcutFromManifest` / ART quick resolution crash in that path. Source and evidence support narrowing to shortcut manifest scan, but not yet an exact code or binary patch.

A new **read-only normal-mode** `ANDROID_SHORTCUT_TEST=observe` run is configured in [#41251519179](https://github.com/Pokateli/VM-Fabric/actions/runs/41251519179). It makes no state changes and fails closed if Safe Mode is active. On failure, before QEMU stops, `capture-crash.py` collects bounded ADB guest state, crash and main logcats, and the newest native tombstone. The current branch subsequently adds the Android system logcat buffer as well; that addition belongs to the *next* run, not to #41251519179's pinned commit. Only short matching crash lines go to the job console; the private archived SDK is not uploaded again. Tests for the collector and branch regression are checked in CI.

Do not claim this second run passed until the exact same-PID five-sample, real Launcher3, and QCOW2 assertions pass. If normal mode fails, inspect native fault and AOSP API 28 `services.odex` before designing a narrowly targeted, byte-verified experimental patch. Leave original private kit immutable.
