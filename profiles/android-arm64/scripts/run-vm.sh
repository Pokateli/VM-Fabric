#!/usr/bin/env bash
# Android arm64 run path. This is experimental and will only be enabled in the
# VM-Fabric registry AFTER a real ARM64 Android ADB proof from GitHub Actions.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
MODE=auto
BUNDLE=/mnt/data/vm-fabric/android-arm64
TIMEOUT=2400
COMMAND=""
SCRIPT=""
LOG=""
while (( $# > 0 )); do
  case "$1" in
    --mode) MODE="$2";;
    --bundle) BUNDLE="$2";;
    --timeout) TIMEOUT="$2";;
    --command) COMMAND="$2";;
    --script) SCRIPT="$2";;
    --log) LOG="$2";;
    --output) : ;;
    *) echo "Unknown Android option $1" >&2; exit 2;;
  esac
  shift 2
done
[[ -z "$COMMAND" && -z "$SCRIPT" ]] || { echo "No host Bash commands accepted into Android guest" >&2; exit 2; }
[[ "$MODE" = chat || "$MODE" = github || "$MODE" = auto ]] || exit 2
python3 "$HERE/verify.py" --target "$BUNDLE"
echo "Android ARM64 experimental image is verified, but interactive runtime is disabled until first actual systemReady proof"
exit 3
