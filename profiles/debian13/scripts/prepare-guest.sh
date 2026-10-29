#!/usr/bin/env bash
# Offline customization on GitHub Actions runner only. Runtime remains unprivileged.
set -Eeuo pipefail
[ "$#" -eq 1 ] || { echo "Usage: $0 BUNDLE_DIR" >&2; exit 2; }
BASE="$(cd "$1" && pwd)"
LD="$BASE/lib/ld-linux-x86-64.so.2"
IMG="$BASE/bin/qemu-img"
DISK="$BASE/debian13.qcow2"
TMP="$(mktemp -d)"
RAW="$TMP/guest.raw"
NEW="$TMP/guest-ready.qcow2"
ROOT="$TMP/root"
LOOP=""
MOUNTED=0
cleanup() {
  if [ "$MOUNTED" -eq 1 ]; then sudo umount "$ROOT" || true; fi
  if [ -n "$LOOP" ]; then sudo losetup -d "$LOOP" || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT
for cmd in sudo losetup lsblk blkid mount umount sha512sum; do
  command -v "$cmd" >/dev/null || { echo "Missing build dependency: $cmd" >&2; exit 1; }
done
sudo -n true
[ -f "$DISK" ] || { echo "No input disk $DISK" >&2; exit 1; }
mkdir -p "$ROOT"
img() { "$LD" --library-path "$BASE/lib" "$IMG" "$@"; }
echo "[preseed] Converting compressed QCOW2 into temporary raw disk"
img convert -f qcow2 -O raw "$DISK" "$RAW"
LOOP="$(sudo losetup --find --partscan --show "$RAW")"
sudo udevadm settle 2>/dev/null || true
PART=""
while read -r part kind; do
  [ "$kind" = part ] || continue
  type="$(sudo blkid -s TYPE -o value "$part" 2>/dev/null || true)"
  if [ "$type" = ext4 ]; then PART="$part"; break; fi
done < <(lsblk -nrpo NAME,TYPE "$LOOP")
[ -n "$PART" ] || { echo "Cannot find Debian ext4 root on $LOOP" >&2; exit 1; }
echo "[preseed] Mounting $PART"
sudo mount -t ext4 -o rw,noatime "$PART" "$ROOT"
MOUNTED=1
sudo test -f "$ROOT/etc/passwd"
sudo install -d -m 755 "$ROOT/etc/systemd/system/serial-getty@ttyS0.service.d"
printf 'debian13-chatgpt-vm\n' > "$TMP/hostname"
printf 'LANG=C.UTF-8\n' > "$TMP/locale.conf"
printf 'KEYMAP=us\n' > "$TMP/vconsole.conf"
printf 'UTC\n' > "$TMP/timezone"
cat > "$TMP/autologin.conf" <<'GETTY'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear --keep-baud 115200,38400,9600 %I $TERM
GETTY
sudo install -m 644 "$TMP/hostname" "$ROOT/etc/hostname"
sudo install -m 644 "$TMP/locale.conf" "$ROOT/etc/locale.conf"
sudo install -m 644 "$TMP/vconsole.conf" "$ROOT/etc/vconsole.conf"
sudo install -m 644 "$TMP/timezone" "$ROOT/etc/timezone"
sudo install -m 644 "$TMP/autologin.conf" "$ROOT/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf"
sudo ln -sfn /usr/share/zoneinfo/UTC "$ROOT/etc/localtime"
# Empty machine-id means NOT first boot; unique ID is created on first guest boot.
sudo rm -f "$ROOT/etc/machine-id"
sudo install -m 644 /dev/null "$ROOT/etc/machine-id"
# Prevent interactive firstboot wizard even if upstream defaults change.
sudo ln -sfn /dev/null "$ROOT/etc/systemd/system/systemd-firstboot.service"
sudo umount "$ROOT"
MOUNTED=0
sudo losetup -d "$LOOP"
LOOP=""
echo "[preseed] Compressing initialized QCOW2 with zlib"
img convert -f raw -O qcow2 -c -o compat=1.1,compression_type=zlib "$RAW" "$NEW"
img check -f qcow2 "$NEW"
mv "$NEW" "$DISK"
(cd "$BASE" && sha512sum debian13.qcow2 > DEBIAN_IMAGE_SHA512SUMS)
img info "$DISK"
echo "PRESEED_OK: unattended guest root console configured"
