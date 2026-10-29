#!/usr/bin/env bash
# Validate an unattended root console rather than just kernel boot messages.
set -Eeuo pipefail
[ "$#" -ge 1 ] || { echo "Usage: $0 /path/to/bundle [logfile]" >&2; exit 2; }
BUNDLE="$1"
if [ "$#" -ge 2 ]; then LOG="$2"; else LOG="$(mktemp)"; fi
python3 "$(dirname "$0")/console-smoke-test.py" "$BUNDLE" "$LOG"
[ -f "$BUNDLE/work.qcow2" ] || { echo "ERROR: writable QCOW2 overlay was not created" >&2; exit 1; }
"$BUNDLE/lib/ld-linux-x86-64.so.2" --library-path "$BUNDLE/lib" \
  "$BUNDLE/bin/qemu-img" check -f qcow2 "$BUNDLE/work.qcow2"
echo "PASS: automatic root console and writable overlay verified"
