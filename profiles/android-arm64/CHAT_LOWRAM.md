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
is configured for **2304 MiB** guest RAM, the same immutable private Android
Release kit, ADB `observe` normal mode and no Actions artifact upload. The
workflow must pass five same-PID PackageManager samples, Launcher3 real
framebuffer proof, clean QCOW2 stop and original base SHA-256.

The ChatGPT container currently has a **4096 MiB cgroup limit**. QEMU, the
emulator, Python, page cache and other processes share this limit. The memory
budget helper reserves at least 1024 MiB of headroom (in addition to memory
already in use). A 4096 MiB guest is rejected when it cannot fit. Running a
2304 MiB guest on GitHub does **not** by itself prove it works in ChatGPT's
4 GiB total host.

## Explicit offline ChatGPT smoke-test entrypoint (not an interactive console)

After the **private kit has already been downloaded and verified**, run:

```bash
# Requires root and installed local qemu-img, unshare, ip, python3.
# The session must NOT already exist; source /data image is immutable.
sudo bash profiles/android-arm64/scripts/run-chat-smoke.sh \
  --kit /mnt/data/android-arm64-restored \
  --session /mnt/data/android-arm64-chat-session \
  --ram auto
```

This launcher refuses missing local tools, missing kit, existing session,
non-root execution or an unavailable network namespace. It derives a
cgroup-safe RAM budget, checks the restored private kit, prepares a separate
writable QCOW2 overlay and performs an isolated, no-network normal-mode
smoke test. Its QEMU/ADB session is shut down after evidence collection,
not left running as an interactive desktop.

**No paid or remote storage:** the script does not download Android, use
third-party services or upload images or logs. The source SDK/emulator is
Google proprietary material under its applicable license and must remain
private. The guest uses experimental SELinux/HAL changes; do not use
personal logins or sensitive data.

The present ChatGPT sandbox may lack `qemu-img`, root network namespace
permissions and the private Android SDK itself. These missing prerequisites
prevent a live local boot until supplied; running the static tests is not a
substitute for a QEMU boot. In particular, never claim the ChatGPT-local
desktop is operational merely because GitHub's QEMU TCG test passes.
