#!/usr/bin/env bash
# Research-only extraction of the verified Xiaomi fastboot archive.
set -euo pipefail
shopt -s nullglob
mkdir -p reports work/partitions work/mounts

mapfile -d '' super_files < <(find work/unpacked -type f \( -name 'super.img' -o -name 'super.img.[0-9]*' \) -print0 | sort -zV)
if (( ${#super_files[@]} == 0 )); then
  echo "No super.img or super.img.N found in Xiaomi fastboot archive" >&2
  exit 1
fi
printf '%s\n' "${super_files[@]}" > reports/super-inputs.txt
head -c 4 "${super_files[0]}" | od -An -tx1 > reports/super-magic.txt

if [[ "$(head -c 4 "${super_files[0]}" | od -An -tx1 | tr -d ' \n')" == "3aff26ed" ]]; then
  echo "Converting Android sparse super image(s) to raw..."
  simg2img "${super_files[@]}" work/super.raw.img
  super=work/super.raw.img
elif (( ${#super_files[@]} == 1 )); then
  super="${super_files[0]}"
else
  echo "Concatenating split raw super image..."
  cat "${super_files[@]}" > work/super.raw.img
  super=work/super.raw.img
fi

echo "Extracting logical partitions; detailed metadata is logged in reports."
./work/lpunpack -v "$super" work/partitions 2>&1 | tee reports/super-metadata.txt
test -n "$(find work/partitions -maxdepth 1 -name '*.img' -print -quit)"
find work/partitions -maxdepth 1 -name '*.img' -printf '%f\t%s\n' | sort > reports/logical-partitions.tsv

# Keep physical boot/firmware images in the image inventory, but only mount
# recognized EROFS/ext4 filesystems. Device-private persist/modemst is excluded.
: > reports/mounted-partitions.tsv
: > reports/skipped-images.tsv
for image in work/partitions/*.img; do
  name="$(basename "$image" .img)"
  magic="$(dd if="$image" bs=1 skip=1024 count=4 status=none | od -An -tx1 | tr -d ' \n')"
  mnt="work/mounts/$name"
  mkdir -p "$mnt"
  if [[ "$magic" == "e2e1f5e0" ]]; then
    fs="erofs"
    sudo mount -t erofs -o ro,loop "$image" "$mnt"
  elif [[ "$magic" == "53ef" ]]; then
    fs="ext4"
    sudo mount -t ext4 -o ro,noload,loop "$image" "$mnt"
  else
    # ext4 magic is at 0x438 rather than 0x400; test it independently.
    extmagic="$(dd if="$image" bs=1 skip=1080 count=2 status=none | od -An -tx1 | tr -d ' \n')"
    if [[ "$extmagic" == "53ef" ]]; then
      fs="ext4"
      sudo mount -t ext4 -o ro,noload,loop "$image" "$mnt"
    else
      rmdir "$mnt"
      printf '%s\tunknown filesystem\n' "$name" >> reports/skipped-images.tsv
      continue
    fi
  fi
  printf '%s\t%s\n' "$name" "$fs" >> reports/mounted-partitions.tsv
  echo "Mounted $name ($fs)"
done

test -s reports/mounted-partitions.tsv
sudo python3 scripts/inventory_partitions.py work/mounts reports
echo "Inventory generated; preserving full library archive as an artifact."
