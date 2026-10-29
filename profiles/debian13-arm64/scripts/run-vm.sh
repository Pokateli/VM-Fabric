#!/usr/bin/env bash
# Shared runner for the identical Debian VM in ChatGPT or GitHub Actions.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
MODE=auto
BUNDLE="$(printenv VM_BUNDLE 2>/dev/null || true)"
[ -n "$BUNDLE" ] || BUNDLE="/mnt/data/vm-fabric/debian13-arm64"
COMMAND=""
SCRIPT=""
LOG="$(printenv VM_LOG 2>/dev/null || true)"
OUTPUT="$(printenv VM_OUTPUT 2>/dev/null || true)"
[ -n "$LOG" ] || LOG="guest-console.log"
[ -n "$OUTPUT" ] || OUTPUT="guest-output.txt"
TIMEOUT=600
usage() {
  cat <<'HELP'
Usage: bash scripts/run-vm.sh [--mode auto|chat|github] [--bundle DIR]
  [--command BASH | --script FILE] [--log LOG] [--output FILE]
  [--timeout SECONDS]
auto: GitHub Actions -> batch; ChatGPT/local -> interactive.
chat: interactive unless --command/--script is specified.
github: batch with logs. Guest networking disabled.
HELP
}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode|--bundle|--command|--script|--log|--output|--timeout)
      [ "$#" -ge 2 ] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --mode) MODE="$2";;
        --bundle) BUNDLE="$2";;
        --command) COMMAND="$2";;
        --script) SCRIPT="$2";;
        --log) LOG="$2";;
        --output) OUTPUT="$2";;
        --timeout) TIMEOUT="$2";;
      esac
      shift 2;;
    --help|-h) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2;;
  esac
done
case "$MODE" in
  auto) if [ "$(printenv GITHUB_ACTIONS 2>/dev/null || :)" = true ]; then MODE=github; else MODE=chat; fi;;
  chat|github) ;;
  *) echo "Unsupported mode: $MODE" >&2; exit 2;;
esac
[ -x "$BUNDLE/start.sh" ] || { echo "Missing VM: $BUNDLE/start.sh" >&2; exit 1; }
[ -z "$COMMAND" ] || [ -z "$SCRIPT" ] || { echo "Choose --command OR --script" >&2; exit 2; }
if [ "$MODE" = chat ] && [ -z "$COMMAND" ] && [ -z "$SCRIPT" ]; then
  echo "VM_MODE=chat interactive: $BUNDLE"
  exec "$BUNDLE/start.sh"
fi
if [ -z "$COMMAND" ] && [ -z "$SCRIPT" ]; then
  COMMAND=$'id -u\nuname -r\ncat /etc/os-release'
fi
echo "VM_MODE=$MODE batch: $BUNDLE"
args=(--bundle "$BUNDLE" --log "$LOG" --output "$OUTPUT" --timeout "$TIMEOUT")
if [ -n "$SCRIPT" ]; then
  args+=(--script "$SCRIPT")
else
  args+=(--command "$COMMAND")
fi
python3 "$HERE/guest-exec.py" "${args[@]}"
