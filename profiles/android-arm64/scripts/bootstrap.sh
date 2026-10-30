#!/usr/bin/env bash
# Point VM-Fabric at a verified, locally downloaded Android ARM64 SDK cache.
# No 5+ GB copies and no implicit downloads from source repositories.
set -Eeuo pipefail
[ "$#" = 2 ] || { echo "Usage: bootstrap.sh BUNDLE_DIRECTORY DEST" >&2; exit 2; }
source="$(realpath "$1")"
target="$(realpath -m "$2")"
[ "$source" != "$target" ] || { echo 'Cannot deploy source onto itself' >&2; exit 2; }
test -f "$source/sdk/system-images/android-28/google_apis/arm64-v8a/source.properties"
test -f "$source/build/ramdisk-wrap.img"
mkdir -p "$target"
for part in sdk build; do
  if [ -L "$target/$part" ]; then
    [ "$(readlink -f "$target/$part")" = "$source/$part" ] || exit 2
  elif [ -e "$target/$part" ]; then
    echo "Refusing to overwrite existing $target/$part" >&2
    exit 2
  else
    ln -s "$source/$part" "$target/$part"
  fi
done
echo "Imported Android ARM64 SDK and ramdisk via symlinks, no duplication"
