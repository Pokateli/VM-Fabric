#!/usr/bin/env bash
# Offline deployment from a GitHub Actions artifact ZIP or bundle tar.gz.
set -Eeuo pipefail

usage() {
  echo "Usage: bash scripts/bootstrap.sh <debian13-arm64-vm.zip|debian13-arm64-qemu-bundle.tar.gz> [destination]"
  echo "Default destination: /mnt/data/debian13-arm64-vm"
}
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then usage; exit 0; fi
[ "$#" -ge 1 ] || { usage >&2; exit 2; }
for cmd in tar sha256sum sha512sum python3 realpath; do
  command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }
done
IN="$(realpath "$1")"
[ -f "$IN" ] || { echo "Missing archive: $IN" >&2; exit 1; }
DEST="${2:-/mnt/data/debian13-arm64-vm}"
[ ! -e "$DEST" ] || { echo "Destination exists, refusing to overwrite: $DEST" >&2; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if [[ "$IN" = *.zip ]]; then
  python3 - "$IN" "$TMP" <<'PYZIP'
from pathlib import Path
from zipfile import ZipFile
import sys
src,dest=Path(sys.argv[1]),Path(sys.argv[2])
with ZipFile(src) as z:
    for m in z.infolist():
        p=Path(m.filename)
        if p.is_absolute() or '..' in p.parts:
            raise SystemExit('Unsafe ZIP path: '+m.filename)
        if m.file_size > 8 * 1024**3:
            raise SystemExit('ZIP item too large: '+m.filename)
    z.extractall(dest)
PYZIP
  PACKAGE="$TMP/debian13-arm64-qemu-bundle.tar.gz"
  [ -f "$PACKAGE" ] || { echo "Artifact missing bundle tar.gz" >&2; exit 1; }
  if [ -f "$TMP/debian13-arm64-qemu-bundle.tar.gz.sha256" ]; then
    (cd "$TMP" && sha256sum -c debian13-arm64-qemu-bundle.tar.gz.sha256)
  else
    echo "WARNING: missing outer SHA256 checksum" >&2
  fi
else
  PACKAGE="$IN"
  if [ -f "$IN.sha256" ]; then
    (cd "$(dirname "$IN")" && sha256sum -c "$(basename "$IN").sha256")
  else
    echo "WARNING: no detached SHA256 file" >&2
  fi
fi

python3 - "$PACKAGE" <<'PYTAR'
import posixpath,sys,tarfile
root='debian13-arm64-qemu-bundle'
with tarfile.open(sys.argv[1],'r:gz') as tf:
    for m in tf:
        n=m.name
        if n.startswith('/') or '..' in n.split('/') or not (n==root or n.startswith(root+'/')):
            raise SystemExit('Unsafe TAR path: '+n)
        if m.issym() or m.islnk():
            t=m.linkname if m.islnk() else posixpath.join(posixpath.dirname(n),m.linkname)
            target=posixpath.normpath(t)
            if not (target==root or target.startswith(root+'/')):
                raise SystemExit('Unsafe TAR link: '+n+' -> '+m.linkname)
        elif not (m.isfile() or m.isdir()):
            raise SystemExit('Unsafe TAR entry: '+n)
PYTAR

mkdir -p "$(dirname "$DEST")"
STAGE="$(mktemp -d "$(dirname "$DEST")/.debian13-vm-stage.XXXXXX")"
trap 'rm -rf "$TMP" "$STAGE"' EXIT
tar -xzf "$PACKAGE" -C "$STAGE" --strip-components=1
[ -x "$STAGE/start.sh" ] || { echo "Incomplete bundle: missing start.sh" >&2; exit 1; }
(cd "$STAGE" && sha256sum -c SHA256SUMS && sha512sum -c DEBIAN_IMAGE_SHA512SUMS)
"$STAGE/lib/ld-linux-x86-64.so.2" --library-path "$STAGE/lib" "$STAGE/bin/qemu-system-aarch64" --version
"$STAGE/lib/ld-linux-x86-64.so.2" --library-path "$STAGE/lib" "$STAGE/bin/qemu-img" info "$STAGE/debian13-arm64.qcow2"
"$STAGE/lib/ld-linux-x86-64.so.2" --library-path "$STAGE/lib" "$STAGE/bin/qemu-img" check -f qcow2 "$STAGE/debian13-arm64.qcow2"
mv "$STAGE" "$DEST"
echo "READY: $DEST"
echo "Start with: $DEST/start.sh"
