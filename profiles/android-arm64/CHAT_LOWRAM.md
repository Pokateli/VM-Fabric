# Android ARM64 ChatGPT low-memory test (experimental, offline)

The existing Android 9 ARM64 ADB + Launcher3 guest is **not** promoted to the
`ready` profile. A normal-mode restored second boot at **4096 MiB** completed
with 5/5 stable `system_server` checks in
[run #41251519179](https://github.com/Pokateli/VM-Fabric/actions/runs/41251519179).
Another earlier normal boot crashed in ART / `ShortcutParser`; stability is not
yet reproducible enough to treat this as a general-purpose VM.

## 2304 MiB test

The single GitHub QEMU TCG run
[#41252841437](https://github.com/Pokateli/VM-Fabric/actions/runs/41252841437)
**PASSED** with **2304 MiB** guest RAM, the same immutable private Android
Release kit, ADB `observe` normal mode and no Actions artifact upload.
The complete live proof includes all five same-PID PackageManager checks,
Launcher3 GUI framebuffer, clean QCOW2 validation and original base SHA-256.
The same test at 4096 MiB also passed independently.

The ChatGPT container currently has a **4096 MiB cgroup limit**. QEMU, the
emulator, Python, page cache and other processes share this limit. The memory
budget helper reserves at least 1024 MiB of headroom (in addition to memory
already in use). A 4096 MiB guest is rejected when it cannot fit. Running a
2304 MiB guest on GitHub does **not** by itself prove it works in ChatGPT's
4 GiB total host.

## Offline private Release restore and host doctor (2026-11-01)

The private GitHub Release asset `run-41129772918-artifact-13012994299-vm-fabric-android-arm64-private-kit.zip` was archived under tag `actions-artifacts-archive-2026-10`, along with its matching `.zip.sha256` sidecar. To avoid Actions storage, use the existing Release: first obtain both files through an authenticated GitHub client **outside** the sandbox, then provide them locally. This command does not access GitHub, download SDK binaries, or use external storage.

```bash
python3 vmfabric.py restore android-arm64 \
  --archive /mnt/data/run-41129772918-artifact-13012994299-vm-fabric-android-arm64-private-kit.zip \
  --sha256 /mnt/data/run-41129772918-artifact-13012994299-vm-fabric-android-arm64-private-kit.zip.sha256 \
  --target /mnt/data/android-arm64-restored

python3 vmfabric.py doctor android-arm64 \
  --target /mnt/data/android-arm64-restored --ram auto

# Only if doctor reports local_smoke_prerequisites_met=true:
python3 vmfabric.py smoke android-arm64 \
  --target /mnt/data/android-arm64-restored \
  --session /mnt/data/android-arm64-chat-session \
  --ram auto
```

The `restore` command verifies the whole Release ZIP SHA-256, restricts members to the exact shard manifest and numbered parts, calls the pinned private-kit internal SHA-256 verification and checks Android ARM64 SDK provenance. It uses a temporary local directory and publishes the restored target only after every check succeeds. A pre-existing destination is rejected. Restoration requires free local disk space but **does not require QEMU**.

The `doctor` command checks host cgroup RAM, namespace isolation, SDK/ABI evidence and the availability of `qemu-img`, without writing any image. If there is no system `qemu-img`, the smoke launcher can use the SDK's own `sdk/emulator/qemu-img` **only if it exists and is executable after kit verification**; its `--version` command must also succeed. Android SDK installations can include such a binary, but it has not been inspected in this chat sandbox. No assumptions are made that it is always bundled.

Both commands preserve `status=experimental` and the normal `run` gate. Keep Google's Android SDK/private system images out of public GitHub releases and chat-visible raw logs. Neither restores the kit currently absent from this sandbox nor proves that Android launches within its 4 GiB total memory limit.

---

## Explicit offline ChatGPT smoke-test entrypoint (not an interactive console)

After the **private kit has already been downloaded and verified**, run:

```bash
# Requires root and installed local qemu-img, unshare, ip, python3.
# The session must NOT already exist; source /data image is immutable.
python3 vmfabric.py smoke android-arm64 \
  --target /mnt/data/android-arm64-restored \
  --session /mnt/data/android-arm64-chat-session \
  --ram auto

# Equivalent explicit entrypoint:
sudo bash profiles/android-arm64/scripts/run-chat-smoke.sh \
  --kit /mnt/data/android-arm64-restored \
  --session /mnt/data/android-arm64-chat-session \
  --ram auto
```

This launcher refuses missing local tools, missing kit, existing session,
non-root execution or an unavailable network namespace. It first tries a
privileged host network namespace; if CAP_SYS_ADMIN is missing, it tries
`unshare --user --map-root-user --net` with loopback only. Both methods
fail closed rather than running with unrestricted host networking. It derives a
cgroup-safe RAM budget and caps automatic guest RAM at **2304 MiB**,
checks the restored private kit, prepares a separate writable QCOW2 overlay
and performs an isolated, no-network normal-mode smoke test. Its QEMU/ADB
session is shut down after evidence collection, not left running as an
interactive desktop.

**No paid or remote storage:** the script does not download Android, use
third-party services or upload images or logs. The source SDK/emulator is
Google proprietary material under its applicable license and must remain
private. The guest uses experimental SELinux/HAL changes; do not use
personal logins or sensitive data.

**Observed inside the present ChatGPT sandbox:** `unshare --net` fails with
`Operation not permitted`, but `unshare --user --map-root-user --net`
succeeds and `ip link set lo up` succeeds inside it. The new launcher
supports this working fallback. The sandbox currently still lacks
`qemu-img` and the private Google Android SDK kit. Those prerequisites
prevent an actual local ARM64 guest boot today; static tests and GitHub's
QEMU TCG successes are not substitutes for real ChatGPT-local proof.

## Verification / safety status (2026-11-01)

- GitHub low-RAM test [#41252841437](https://github.com/Pokateli/VM-Fabric/actions/runs/41252841437): **success**, 2304 MiB, 5/5 stable PackageManager checks, real Launcher3 and immutable QCOW2.
- Fast CI [#41255615499](https://github.com/Pokateli/VM-Fabric/actions/runs/41255615499): **77/77 tests**.
- `minimum_guest_ram_mib` is now 2304 based on observed GitHub ARM64 TCG evidence; `status` remains `experimental` and `runtime=[]`. The normal `vmfabric.py run` stays disabled for Android.
- `vmfabric.py smoke android-arm64` explicitly runs the offline smoke path instead. It requires an already verified private SDK kit and host QEMU dependencies; it does not download files or change the saved base.
- `verify.py --live` now requires exact `Service package: found` instead of the substring `found` (which also appears in `not found`).
- Chat sandbox: user+network namespace with loopback is confirmed; `qemu-img` is missing and local `apt-get update` could not complete in a bounded network test. The private Android kit is not present under `/mnt/data`. Actual ChatGPT-local boot is not yet established.
