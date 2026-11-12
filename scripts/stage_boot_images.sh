#!/usr/bin/env bash
# Stage only publicly distributed stock boot-chain images from official ROM.
set -euo pipefail
mkdir -p reports/boot-images
mapfile -d '' image_dirs < <(find work/unpacked -type d -name images -print0)
if (( ${#image_dirs[@]} != 1 )); then
  echo "Expected exactly one fastboot images directory" >&2
  exit 1
fi
src="${image_dirs[0]}"
for name in boot.img init_boot.img vendor_boot.img dtbo.img recovery.img vbmeta.img vbmeta_system.img; do
  test -s "$src/$name" || { echo "Missing stock image: $name" >&2; exit 1; }
  cp "$src/$name" "reports/boot-images/$name"
done
(cd reports/boot-images && sha256sum *.img > ../boot-images.sha256)
