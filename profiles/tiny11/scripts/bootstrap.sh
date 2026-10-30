#!/usr/bin/env bash
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
[ "$#" = 2 ] || { echo "Usage: $0 READY_DIRECTORY_OR_SHARDS_DIRECTORY DEST" >&2; exit 2; }
python3 "$HERE/import-ready.py" "$1" "$2"
