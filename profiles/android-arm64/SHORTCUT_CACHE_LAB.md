# Android ARM64 second boot — ShortcutService cache isolation (2026-11-01)

## Grounded baseline
- Original restored Legacy OpenGL image: run 41132811947 failed stability gate on sample 5/5 (prior 4 passed).
- Isolated Safe Mode restoration: run 41134334742 passed 5/5 stable system_server PID, Launcher3, QCOW2 check, immutable base check.
- Safe Mode is diagnostic only. It prevents some ShortcutService package-change processing and is not a standard Android startup fix.

## Next experiment
This branch adds `ANDROID_SHORTCUT_TEST=cache-reset`, never enabled by default.
In a *disposable overlay* session, at the pinned zygote restart point it:
1. Stops zygote.
2. If present, moves `/data/system_ce/0/shortcut_service` to `/data/local/tmp/vmfabric-shortcut-cache-backup`. Refuses a pre-existing backup.
3. Explicitly disables persistent Safe Mode and restarts zygote.
4. Requires Safe Mode to be off, 5/5 stable package-service observations, genuine GUI evidence, clean QCOW2 check and immutable source-disk SHA256.

**Limitations:** A pass would implicate persisted ShortcutService state, not prove a precise ART root cause. A failure would suggest non-cache paths (package rescan, ART/JIT, framework or timing). Only the overlay gets modified; move is not a substitute for a recovery process in production. The prior image/SDK has relaxed guest security settings; do not use personal credentials.

## CI/storage
- Restored Android 4 GiB boot workflow is **manual dispatch only** on this branch to avoid unapproved Actions minutes and artifact storage. No heavy workflow has been triggered by this change.
- Local fast unit tests: `python3 -m unittest discover -s tests -p 'test_android_shortcut_cache.py' -v`.
- Static check: `python3 -m py_compile profiles/android-arm64/scripts/patch-shortcut-cache-experiment.py` and `bash -n profiles/android-arm64/scripts/boot-restored.sh`.
- Triggering manually: select branch `android-arm64-shortcut-cache-lab-20261101` in Actions under "Android ARM64 restored private kit second boot (TCG)" and use Run workflow. Keep proof bounded; private full Google SDK must not become a public artifact.

## Follow-up
Compare with Safe Mode control and original normal-boot failure. If a successful cache-reset run repeats with normal mode, replace the experiment with a narrow first-boot cache regeneration or investigate the installed package triggering ShortcutService. Do not promote profile to ready until a normal-mode cold/warm boot and constrained 4 GiB host tests pass.
