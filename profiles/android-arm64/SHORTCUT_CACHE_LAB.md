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
- Quick CI: [run #41250694709](https://github.com/Pokateli/VM-Fabric/actions/runs/41250694709) passed **55/55** tests, including executing the patched guest shell in a disposable local directory.
- The first obsolete restored-boot workflow [run #41250041676](https://github.com/Pokateli/VM-Fabric/actions/runs/41250041676) unexpectedly started on an intermediate workflow commit (before the archive fix). Its result is not evidence for this experiment.
- The corrected one-time restored-boot [run #41250738934](https://github.com/Pokateli/VM-Fabric/actions/runs/41250738934) was queued with `push` trigger scoped to this workflow file. Branch concurrency is configured to cancel obsolete runs.
- The Android kit was archived in a **private GitHub Release** (`actions-artifacts-archive-2026-10`) and deleted from temporary Actions artifacts. The new workflow downloads that exact private Release ZIP, validates its SHA256 sidecar, unpacks only the trusted kit, and uploads **no new Actions artifacts**. Only bounded job logs are retained.
- Local fast unit tests: `python3 -m unittest discover -s tests -p 'test_android_shortcut_cache.py' -v`.
- Static check: `python3 -m py_compile profiles/android-arm64/scripts/patch-shortcut-cache-experiment.py` and `bash -n profiles/android-arm64/scripts/boot-restored.sh`.
- Heavy test: the branch's `push` trigger runs only on updates to `.github/workflows/test-android-arm64-restored.yml`; it was enabled to run a single corrected proof. Do not change that workflow file without intending another heavy run. GitHub manual dispatch additionally requires the workflow to exist on the default branch; this development branch alone does not make that UI available.
- `boot-restored.sh` supports `ANDROID_GUEST_RAM_MIB` in the range 1536–4096 (defaults to the previous 4096). Reduced guest RAM has **not** been proven; the ChatGPT container has a 4096 MiB memory cgroup cap.

## Follow-up
Compare with Safe Mode control and original normal-boot failure. If a successful cache-reset run repeats with normal mode, replace the experiment with a narrow first-boot cache regeneration or investigate the installed package triggering ShortcutService. Do not promote profile to ready until a normal-mode cold/warm boot and constrained 4 GiB host tests pass.
