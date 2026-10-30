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
PID_FILE="$BUNDLE/chat-vm.pid"
if [ -e "$PID_FILE" ]; then
  old="$(cat "$PID_FILE")"
  if [[ "$old" =~ ^[0-9]+$ ]] && kill -0 "$old" 2>/dev/null; then
    echo "Existing process $old; inspect: python3 $HERE/vm-control.py status --vm-dir $BUNDLE"
    exit 0
  fi
  rm -f "$PID_FILE"
fi
nohup python3 "$HERE/dual-run.py" start --vm-dir "$BUNDLE" --headless --skip-hash >"$LOG" 2>&1 </dev/null &
pid=$!
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
