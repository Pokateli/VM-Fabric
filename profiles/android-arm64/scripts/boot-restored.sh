#!/usr/bin/env bash
# Second-boot smoke test of a PRIVATE verified Android ARM64 bundle.
# Run only inside a dedicated Linux network namespace with loopback enabled.
# Preserve the kit's /data base via prepare-restore.py overlay.
set -Eeuo pipefail
(( $# == 2 )) || { echo "Usage: boot-restored.sh RESTORED_KIT SESSION" >&2; exit 2; }
KIT="$(realpath "$1")"
SESSION="$(realpath "$2")"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(readlink /proc/1/ns/net)" == "$(readlink /proc/self/ns/net)" ]]; then
  echo "Refuse to start Android guest outside a dedicated network namespace" >&2
  exit 2
fi
test -f "$SESSION/session.json"
test -s "$SESSION/build/userdata-arm64.qcow2"
test -L "$SESSION/build/ramdisk-wrap.img"
test -L "$SESSION/build/dex"
export SDK_ROOT="$KIT/sdk"
export BUILD_DIR="$SESSION/build"
export ANDROID_I_WANT_MY_TCG=yes
export CORES=1
export MEM="$(python3 "$HERE/host-memory-budget.py" --requested "${ANDROID_GUEST_RAM_MIB:-4096}")"
mkdir -p "$SESSION/second-boot-proof"
PROOF="$SESSION/second-boot-proof"
SOURCE="$KIT/upstream-src"
if [ "${ANDROID_SHORTCUT_TEST:-baseline}" = "cache-reset" ]; then
  SOURCE="$SESSION/upstream-src-cache-reset"
  cp -a "$KIT/upstream-src" "$SOURCE"
  python3 "$HERE/patch-shortcut-cache-experiment.py" "$SOURCE/scripts/40-bringup.sh"
elif [ "${ANDROID_SHORTCUT_TEST:-baseline}" = "safemode" ]; then
  # Never patch the verified SDK/source kit; modify only a per-session copy.
  SOURCE="$SESSION/upstream-src-safemode"
  cp -a "$KIT/upstream-src" "$SOURCE"
  python3 "$HERE/patch-safemode-experiment.py" "$SOURCE/scripts/40-bringup.sh"
elif [ "${ANDROID_SHORTCUT_TEST:-baseline}" != "baseline" ]; then
  echo "Unknown Android ShortcutService experiment" >&2
  exit 2
fi
cd "$SOURCE"
cleanup() {
  if [ -s "$BUILD_DIR/qemu.pid" ]; then
    pid=$(cat "$BUILD_DIR/qemu.pid")
    if [[ "$pid" =~ ^[0-9]+$ ]]; then
      kill -TERM "$pid" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT
timeout 90 sh scripts/30-launch.sh
bash "$HERE/boot-monitor.sh" "$PROOF" 45 &
watchdog_pid=$!
trap 'kill "$watchdog_pid" 2>/dev/null || true; cleanup' EXIT
bash "$HERE/boot-gate.sh" "$PWD" "$BUILD_DIR" "$PROOF"
if [ "${ANDROID_SHORTCUT_TEST:-baseline}" = "cache-reset" ]; then
  actual="$(timeout 35 "$SDK_ROOT/platform-tools/adb" -s emulator-5554 shell getprop ro.sys.safemode | tr -d '\r')"
  printf 'GUEST_SAFE_MODE=%s\n' "$actual" | tee "$PROOF/shortcut-experiment.txt"
  [ "$actual" != 1 ] || { echo "Cache reset ran in Safe Mode; reject ambiguous result" >&2; exit 88; }
  cache_result="$(timeout 35 "$SDK_ROOT/platform-tools/adb" -s emulator-5554 shell cat /data/local/tmp/vmfabric-shortcut-cache-result.txt | tr -d '\\r')"
  printf '%s\\n' "$cache_result" | tee -a "$PROOF/shortcut-experiment.txt"
  [ "$cache_result" = "SHORTCUT_CACHE_MOVED=1" ] || {
    echo "No confirmed ShortcutService cache move in disposable guest; reject experiment" >&2
    exit 89
  }
elif [ "${ANDROID_SHORTCUT_TEST:-baseline}" = "safemode" ]; then
  actual="$(timeout 35 "$SDK_ROOT/platform-tools/adb" -s emulator-5554 shell getprop ro.sys.safemode | tr -d '\r')"
  printf 'GUEST_SAFE_MODE=%s\n' "$actual" | tee "$PROOF/shortcut-experiment.txt"
  [ "$actual" = 1 ] || { echo "Safe mode was not enabled in Android WindowManagerService" >&2; exit 88; }
fi
python3 "$HERE/verify-stable-ready.py" --sdk-root "$SDK_ROOT" --proof-dir "$PROOF" --checks 5 --interval 20
timeout 300 python3 "$HERE/inspect-gui.py" --sdk-root "$SDK_ROOT" --proof-dir "$PROOF"
grep -Fxq 'PASS_STABLE_ANDROID_ARM64_PACKAGE_SERVICE' "$PROOF/STABILITY_RESULT.txt"
grep -Fxq 'LAUNCHER_HOME_EVIDENCE' "$PROOF/GUI_RESULT.txt"
echo PASS_SECOND_ANDROID_ARM64_LAUNCHER_BOOT | tee "$PROOF/RESULT.txt"
timeout 80 "$SDK_ROOT/platform-tools/adb" -s emulator-5554 reboot -p || true
sleep 10
cleanup
if [ -s "$BUILD_DIR/qemu.pid" ]; then
  pid=$(cat "$BUILD_DIR/qemu.pid")
  for i in $(seq 1 30); do
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    state=$(ps -p "$pid" -o stat= 2>/dev/null || true)
    if [[ "$state" == Z* ]]; then break; fi
    sleep 2
  done
  if kill -0 "$pid" 2>/dev/null; then
    state=$(ps -p "$pid" -o stat= 2>/dev/null || true)
    [[ "$state" == Z* ]] || { echo "QEMU still running; refusing QCOW2 inspection" >&2; exit 84; }
  fi
fi
qemu-img check -f qcow2 "$BUILD_DIR/userdata-arm64.qcow2" > "$PROOF/qcow2-check.txt"
echo PASS_SECOND_ANDROID_ARM64_QCOW2_CHECK | tee -a "$PROOF/RESULT.txt"
# Verify original, immutable /data base has not changed after guest poweroff.
python3 - "$SESSION/session.json" "$KIT/build/userdata-arm64.qcow2" <<'PY'
import hashlib,json,pathlib,sys
record=json.loads(pathlib.Path(sys.argv[1]).read_text())
base=pathlib.Path(sys.argv[2])
h=hashlib.sha256()
with base.open("rb") as inp:
    for chunk in iter(lambda:inp.read(4*1024*1024),b""):
        h.update(chunk)
if h.hexdigest()!=record["base_sha256"]:
    raise SystemExit("IMMUTABLE_BASE_QCOW2_HASH_CHANGED")
print("PASS_SECOND_ANDROID_ARM64_IMMUTABLE_BASE")
PY
echo PASS_SECOND_ANDROID_ARM64_IMMUTABLE_BASE | tee -a "$PROOF/RESULT.txt"
