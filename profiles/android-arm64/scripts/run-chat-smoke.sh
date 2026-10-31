#!/usr/bin/env bash
# Explicit offline smoke-test entrypoint; NOT a ready/interactive VM profile.
# Requires a locally restored PRIVATE verified Android ARM64 kit.
set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
KIT=""
SESSION=""
RAM="auto"
usage() {
  echo "Usage: sudo bash $0 --kit RESTORED_PRIVATE_KIT --session NEW_DIRECTORY [--ram auto|MIB]" >&2
  exit 2
}
while (( $# > 0 )); do
  case "$1" in
    --kit) (( $# >= 2 )) || usage; KIT="$2"; shift 2;;
    --session) (( $# >= 2 )) || usage; SESSION="$2"; shift 2;;
    --ram) (( $# >= 2 )) || usage; RAM="$2"; shift 2;;
    *) usage;;
  esac
done
[[ -n "$KIT" && -n "$SESSION" ]] || usage
(( EUID == 0 )) || { echo "Root required for isolated network namespace (sudo bash ...)" >&2; exit 3; }

for tool in qemu-img unshare ip realpath python3 timeout; do
  command -v "$tool" >/dev/null || { echo "Missing local tool: $tool" >&2; exit 3; }
done
KIT="$(realpath -e -- "$KIT")"
SESSION="$(realpath -m -- "$SESSION")"
[[ -d "$KIT" ]] || { echo "Verified private kit directory is missing" >&2; exit 3; }
[[ ! -e "$SESSION" && ! -L "$SESSION" ]] || {
  echo "Session already exists: refuse overwrite or resume" >&2; exit 3;
}
# Fail before creating overlays if this sandbox denies network namespaces.
unshare --net -- bash -c 'ip link set lo up' || {
  echo "Host disallows isolated network namespace. Guest not launched." >&2
  exit 3
}
# On ChatGPT's finite 4 GiB cgroup choose a conservative guest size automatically.
# On an unbounded host an explicit size is required.
MEM="$(python3 "$HERE/host-memory-budget.py" --requested "$RAM")"
[[ "$MEM" =~ ^[0-9]+$ ]] || exit 3
# Auto sizing may choose 2560 MiB on an almost-empty 4 GiB cgroup.
# Cap automatic selection at the dedicated 2304 MiB experimental target
# until more memory sizes are proven on an actual restricted chat host.
if [[ "$RAM" == auto ]] && (( MEM > 2304 )); then
  MEM=2304
fi
export ANDROID_GUEST_RAM_MIB="$MEM"
export ANDROID_SHORTCUT_TEST=observe

python3 "$HERE/verify.py" --target "$KIT"
python3 "$HERE/prepare-restore.py" --kit "$KIT" --session "$SESSION"

echo "ANDROID_CHAT_EXPERIMENT=offline ram_mib=$MEM"
echo "IMMUTABLE_KIT=$KIT"
echo "THROWAWAY_SESSION=$SESSION"
# ADB stays on loopback in a dedicated host network namespace with no internet.
unshare --net -- bash -Eeuo pipefail -c '
  ip link set lo up
  exec bash "$1" "$2" "$3"
' _ "$HERE/boot-restored.sh" "$KIT" "$SESSION"
echo "ANDROID_CHAT_EXPERIMENT=PASS_RESTORED_NORMAL_MODE_SMOKE"
