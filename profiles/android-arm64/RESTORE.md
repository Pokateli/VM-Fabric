# Android ARM64 (API 28) private kit — restore and second boot

This is the **experimental** Legacy OpenGL candidate, not the production-ready
VM-Fabric Android profile. Proven upstream run
[#41127069219](https://github.com/Pokateli/VM-Fabric/actions/runs/41127069219)
ran actual ARM64 Android Launcher3 and had five ADB PackageManager checks
with unchanged `system_server` PID 1671. The first attempt to archive it
failed due to over-strict validation of an earlier transient `not found`.
The fixed release workflow is
[#41129772918](https://github.com/Pokateli/VM-Fabric/actions/runs/41129772918).

## Private artifact (once published)

A complete portable kit must contain
`android-arm64-parts.json` and `part-000.bin` etc. Every 384 MiB shard is
checksummed. The archive is gzip-compressed and streams without a giant
intermediate TAR. Any Google SDK system image is to be kept private and used
under the applicable Android SDK license. Do not publish binaries to a public
GitHub release.

```bash
# In the VM-Fabric checkout:
python3 profiles/android-arm64/scripts/portable-kit.py unpack \
    /path/to/android-arm64-parts /mnt/data/android-arm64-restored
python3 vmfabric.py verify android-arm64 \
    --target /mnt/data/android-arm64-restored

# Keep restored base /data intact; make a separate session QCOW2 overlay:
python3 profiles/android-arm64/scripts/prepare-restore.py \
    --kit /mnt/data/android-arm64-restored \
    --session /mnt/data/android-arm64-session

# Must be root for unshare --net and opening the dedicated loopback namespace.
# The Android test VM has no Internet route; ADB uses localhost ports only.
sudo unshare --net -- bash -Eeuo pipefail -c '
  ip link set lo up
  exec bash "$1" "$2" "$3"
' _ "$PWD/profiles/android-arm64/scripts/boot-restored.sh" \
  /mnt/data/android-arm64-restored /mnt/data/android-arm64-session
```

**Note:** the above `boot-restored.sh` is a **new smoke-test path**; actual
second boot after restore must be demonstrated on an isolated GitHub runner
before Android can be tagged `ready`. It runs Android with 1 ARM64 TCG vCPU,
4096 MiB configured guest RAM, and demands both five stable PackageManager
observations and a real Launcher3 screenshot.

The working `userdata-arm64.qcow2` must remain compatible with the pinned
Google Android Emulator (older QEMU), so do not feed it a modern ZSTD-QCOW2
without proving emulator support. The *transport* compresses the image;
`prepare-restore.py` uses a new writable QCOW2 overlay and never mutates the
restored base. The source kit has permissive guest SELinux and experimental
patches; never use it with private credentials or sensitive user data.

## Acceptance gates for promoting the profile

1. Real Android ARM64 ADB `ro.product.cpu.abi=arm64-v8a`.
2. Same numeric `system_server` PID in five spaced checks, PackageManager
   `Service package: found` at each.
3. `sys.boot_completed=1`, SurfaceFlinger, Launcher3 HOME resolution,
   multi-color ADB PNG plus visually verified Android desktop.
4. Clean QEMU stop, `qemu-img check` on preserved `/data`.
5. Private chunk manifest/shards pass SHA-256 and genuine restore.
6. **Second boot** from the restored base via the session overlay passes
   gates 1–4 again.
7. Test constrained ChatGPT x86_64 guest memory budget separately; 4096 MiB
   guest RAM is not yet confirmed safe in the 4 GiB cgroup sandbox.
