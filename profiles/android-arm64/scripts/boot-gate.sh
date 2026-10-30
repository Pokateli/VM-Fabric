#!/usr/bin/env bash
# Fail fast when Android ARM64 guest init reboots/halts before ADB is available.
# Execute in the same isolated network namespace as the emulator and ADB.
set -Eeuo pipefail
if [ "$#" -ne 3 ]; then
  echo "Usage: boot-gate.sh UPSTREAM_ROOT BUILD_DIR PROOF_DIR" >&2
  exit 2
fi
SOURCE_DIR="$1"
BUILD_DIR="$2"
PROOF_DIR="$3"
MAX_SECONDS="${ANDROID_BOOT_TIMEOUT_SEC:-2700}"
[[ "$MAX_SECONDS" =~ ^[0-9]+$ ]] && ((MAX_SECONDS>=120&&MAX_SECONDS<=3600)) || exit 2
mkdir -p "$PROOF_DIR"
EMU_LOG="$BUILD_DIR/emu.log"
[ -f "$SOURCE_DIR/scripts/40-bringup.sh" ] || { echo "Missing bring-up script" >&2; exit 2; }
FATAL_PATTERN='Reboot failed -- System halted|init: Reboot start|Kernel panic|init: restorecon failed of /init|reboot: Restarting system with command'
record() {
  printf '%s\n' "$1" > "$PROOF_DIR/boot-gate-result.txt"
  echo "$1"
}
timeout --signal=TERM --kill-after=15s "$MAX_SECONDS" sh "$SOURCE_DIR/scripts/40-bringup.sh" &
child=$!
cleanup() {
  if kill -0 "$child" 2>/dev/null; then
    kill "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
}
trap cleanup EXIT
while kill -0 "$child" 2>/dev/null; do
  if [ -f "$EMU_LOG" ] && grep -Eq "$FATAL_PATTERN" "$EMU_LOG"; then
    grep -E "$FATAL_PATTERN" "$EMU_LOG" | tail -15 > "$PROOF_DIR/guest-fatal.txt"
    record "GUEST_FATAL_EARLY_INIT_STOP"
    echo "Guest kernel/init halted; stopping ADB wait immediately" >&2
    exit 83
  fi
  sleep 5
done
if wait "$child"; then
  record "ANDROID_BRINGUP_RETURNED_SUCCESS"
else
  rc=$?
  record "ANDROID_BRINGUP_FAILED_EXIT_$rc"
  exit "$rc"
fi
