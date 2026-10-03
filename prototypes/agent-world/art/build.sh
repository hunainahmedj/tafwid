#!/usr/bin/env bash
# Builds an environment package with headless Blender on work-station.
# Usage: art/build.sh <placeholder|cafe-kit|cafe-baked> [blender args, e.g. --samples 768 --texels 20]
set -euo pipefail

target="${1:?usage: art/build.sh <placeholder|cafe-kit|cafe-baked> [blender args]}"
shift
extra="$*"
case "$target" in
  placeholder) env=placeholder variant=kit ;;
  cafe-kit) env=cafe variant=kit ;;
  cafe-baked) env=cafe variant=baked ;;
  *) echo "unknown target: $target" >&2; exit 2 ;;
esac

here="$(cd "$(dirname "$0")" && pwd)"
app="$(dirname "$here")"
host="${TAFWID_BLENDER_HOST:-work-station}"
remote_root="/mnt/c/tafwid-art"
win_root='C:\tafwid-art'
blender="/mnt/c/Program Files/Blender Foundation/Blender 5.1/blender.exe"

mkdir -p "$app/art/previews/$target" "$app/public/environments/$env/$variant"
rsync -a --delete --exclude previews --exclude __pycache__ "$here/" "$host:$remote_root/src/"
ssh "$host" "rm -rf '$remote_root/out/$target' && cd '$remote_root' && '$blender' -b --factory-startup \
  --python '$win_root\\src\\$target\\build.py' -- --out '$win_root\\out\\$target' $extra" \
  > "$app/art/previews/$target.log" 2>&1 || { tail -40 "$app/art/previews/$target.log"; exit 1; }
grep -E "^(TAFWID|Error|Traceback)" "$app/art/previews/$target.log" || true

rsync -a --delete "$host:$remote_root/out/$target/package/" "$app/public/environments/$env/$variant/"
rsync -a --delete "$host:$remote_root/out/$target/previews/" "$app/art/previews/$target/"
rsync -a "$host:$remote_root/out/$target/lightmaps/" "$app/art/previews/$target/lightmaps/" 2>/dev/null || true
echo "Built $env/$variant"
