#!/usr/bin/env bash
# Android ARM64 boot monitor. Run INSIDE the SAME network namespace as the
# emulator, so localhost-only ADB works without making the guest Internet-facing.
# Writes diagnostic logs even if early init/zygote never reaches systemReady.
set -Eeuo pipefail
OUT="${1:?Usage: boot-monitor.sh PROOF_DIR [PERIOD_SECONDS]}"
PERIOD="${2:-45}"
[[ "$PERIOD" =~ ^[0-9]+$ ]] && (( PERIOD >= 5 && PERIOD <= 180 )) || exit 2
: "${SDK_ROOT:?SDK_ROOT required}"
: "${BUILD_DIR:?BUILD_DIR required}"
ADB="$SDK_ROOT/platform-tools/adb"
test -x "$ADB" || { echo "Missing adb: $ADB" >&2; exit 2; }
mkdir -p "$OUT"
LOG="$OUT/boot-monitor.log"
t=0
while :; do
  {
    echo "===== $(date -u +%FT%TZ) elapsed_seconds=$t ====="
    if [ -f "$BUILD_DIR/qemu.pid" ]; then
      read -r pid < "$BUILD_DIR/qemu.pid"
      if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
        echo "QEMU_PROCESS=alive pid=$pid"
        ps -p "$pid" -o pid,etime,%cpu,%mem,rss,stat,comm --no-headers 2>/dev/null || :
      else
        echo "QEMU_PROCESS=not_alive"
        echo "Early termination: inspect emulator-tail.log"
        exit 1
      fi
    else
      echo "QEMU_PROCESS=not_started"
    fi
    state="$(timeout 12 "$ADB" -s emulator-5554 get-state 2>/dev/null || :)"
    echo "ADB_STATE=${state:-unavailable}"
    if [[ "$state" == device ]]; then
      for prop in ro.product.cpu.abi ro.build.version.sdk sys.boot_completed init.svc.zygote; do
        value="$(timeout 12 "$ADB" -s emulator-5554 shell getprop "$prop" 2>/dev/null || :)"
        printf '%s=%s\n' "$prop" "${value//$'\r'/}"
      done
      pkg="$(timeout 15 "$ADB" -s emulator-5554 shell service check package 2>/dev/null || :)"
      echo "PACKAGE_SERVICE=${pkg//$'\r'/}"
    fi
    df -h "$BUILD_DIR" | tail -1
  } >> "$LOG" 2>&1
  if (( t % 180 == 0 )); then
    tail -15 "$LOG" || :
  fi
  sleep "$PERIOD"
  t=$(( t + PERIOD ))
done
