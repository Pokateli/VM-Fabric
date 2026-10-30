#!/usr/bin/env bash
# Tiny11: detached ChatGPT TCG GUI or GitHub KVM readiness probe; guest network off.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
MODE=auto
BUNDLE=/mnt/data/vm-fabric/tiny11
TIMEOUT=600
LOG=""
COMMAND=""
SCRIPT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2";;
    --bundle) BUNDLE="$2";;
    --timeout) TIMEOUT="$2";;
    --log) LOG="$2";;
    --output) : ;;
    --command) COMMAND="$2";;
    --script) SCRIPT="$2";;
    *) echo "Unknown option: $1" >&2; exit 2;;
  esac
  shift 2
done
[ -z "$COMMAND" ] && [ -z "$SCRIPT" ] || { echo "Windows GUI profile does not accept Bash guest commands" >&2; exit 2; }
if [ "$MODE" = auto ]; then
  if [ "${GITHUB_ACTIONS:-}" = true ]; then MODE=github; else MODE=chat; fi
fi
[[ "$MODE" = chat || "$MODE" = github ]] || exit 2
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || exit 2
mkdir -p "$BUNDLE"
if [ -z "${QEMU_HOME:-}" ]; then
  for path in "$BUNDLE/qemu-runtime" /mnt/data/tiny11-qemu-vga-fixed/tiny11-qemu-runtime-linux-amd64 /mnt/data/tiny11-qemu-runtime-linux-amd64; do
    if [ -x "$path/bin/qemu-img" ]; then export QEMU_HOME="$path"; break; fi
  done
fi
python3 "$HERE/dual-run.py" verify --vm-dir "$BUNDLE" --skip-hash
if [ "$MODE" = github ]; then
  python3 "$HERE/dual-run.py" probe --vm-dir "$BUNDLE" --accelerator kvm --headless --seconds "$TIMEOUT" --skip-hash
  exit "$?"
fi
LOG="${LOG:-$BUNDLE/chat-vm.log}"
# This sandbox often has a 4GiB cgroup limit. 2560MiB guest RAM plus
# QEMU/host buffers can trigger OOM-kill with no QEMU error in its own log.
# Keep a 1792MiB safe default for TCG; user can opt in to larger RAM.
RAM="${TINY11_RAM_MIB:-1792}"
[[ "$RAM" =~ ^[0-9]+$ ]] && (( RAM >= 1024 && RAM <= 8192 )) || {
  echo "Invalid TINY11_RAM_MIB (expected 1024..8192)" >&2; exit 2;
}
PID_FILE="$BUNDLE/chat-vm.pid"
if [ -e "$PID_FILE" ]; then
  old="$(cat "$PID_FILE")"
  if [[ "$old" =~ ^[0-9]+$ ]] && kill -0 "$old" 2>/dev/null; then
    echo "Existing process $old; inspect: python3 $HERE/vm-control.py status --vm-dir $BUNDLE"
    exit 0
  fi
  rm -f "$PID_FILE"
fi
# A child of a temporary chat shell may be killed when that shell's
# process group is reaped. Start a completely detached OS session instead.
pid="$(python3 - "$HERE/dual-run.py" "$BUNDLE" "$LOG" "$RAM" <<'PY'
import subprocess,sys
script,bundle,log,ram=sys.argv[1:]
with open(log,'ab',buffering=0) as output:
    child=subprocess.Popen([sys.executable,script,'start','--vm-dir',bundle,
                            '--headless','--skip-hash','--ram',ram],
                           stdin=subprocess.DEVNULL,stdout=output,
                           stderr=subprocess.STDOUT,start_new_session=True)
print(child.pid)
PY
)"
printf '%s\n' "$pid" >"$PID_FILE"
for i in $(seq 1 30); do
  if [ -S "$BUNDLE/qemu-monitor.sock" ]; then
    echo "VM STARTED pid=$pid; log=$LOG; monitor=$BUNDLE/qemu-monitor.sock"
    exit 0
  fi
  if ! kill -0 "$pid" 2>/dev/null; then
    tail -40 "$LOG" >&2 || :
    exit 1
  fi
  sleep 1
done
echo "QEMU monitor did not become ready" >&2
exit 1
