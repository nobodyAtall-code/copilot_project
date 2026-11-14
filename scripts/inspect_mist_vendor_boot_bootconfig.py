#!/usr/bin/env python3
"""Read-only Xiaomi Mist v4 vendor_boot bootconfig and first-stage fstab hints.

Requires the existing stock vendor_boot.img. Does not unpack/repack/flash it.
Use with the verified OS3.0.304.0.WPUMIXM image SHA256 by default.
"""
import argparse
import hashlib
import json
import pathlib
import re

from inspect_mist_boot_chain import vendor_boot

STOCK_SHA256 = "f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb"
MAX_BOOTCONFIG = 128 * 1024
KEYWORDS = ("fstab", "boot_devices", "hardware", "slot_suffix", "bootdevice", "androidboot")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vendor-boot", type=pathlib.Path, required=True)
    ap.add_argument("--output", type=pathlib.Path, required=True)
    ap.add_argument("--allow-other-sha256", action="store_true",
                    help="For explicit development images; stock exact-hash check otherwise required")
    args = ap.parse_args()
    h = hashlib.sha256()
    with args.vendor_boot.open("rb") as f:
        for block in iter(lambda: f.read(4 << 20), b""):
            h.update(block)
    actual_hash = h.hexdigest()
    if actual_hash != STOCK_SHA256 and not args.allow_other_sha256:
        raise SystemExit("Refusing unverified vendor_boot SHA256: " + actual_hash)
    meta = vendor_boot(args.vendor_boot, args.vendor_boot.stat().st_size)
    if meta.get("header_version") != 4:
        raise SystemExit("Expected stock vendor_boot v4")
    n = meta.get("bootconfig_bytes", 0)
    start = meta.get("bootconfig_offset", 0)
    if n < 1 or n > MAX_BOOTCONFIG:
        raise SystemExit("Invalid bootconfig length: " + str(n))
    with args.vendor_boot.open("rb") as f:
        f.seek(start)
        raw = f.read(n)
    if len(raw) != n:
        raise SystemExit("Short vendor_boot bootconfig read")
    # Some OEMs add a trailer or NUL padding. Retain a readable escaped
    # representation while reporting only recognized selection hints.
    printable = raw.decode("utf-8", errors="replace").replace("\x00", "\n")
    hints = []
    for line in printable.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if any(k in clean.lower() for k in KEYWORDS):
            hints.append(clean[:512])
    suffix = [x for x in hints if re.search(r"(?:androidboot\.)?fstab_suffix\s*=", x)]
    report = {
        "stock_sha256_exact": actual_hash == STOCK_SHA256,
        "vendor_boot_sha256": actual_hash,
        "header_version": meta["header_version"],
        "ramdisk_fragments": meta["ramdisk_table_entries"],
        "bootconfig_bytes": n,
        "bootconfig_offset": start,
        "bootconfig_selection_hints": hints,
        "explicit_fstab_suffix": suffix,
        "fstab_selected_confirmed": False,
        "warning": (
            "Absence of fstab_suffix in vendor_boot bootconfig is NOT proof of "
            "fstab.default or fstab.emmc selection; kernel cmdline, bootloader "
            "properties, and init/fs_mgr fallback may decide. Stock first-stage "
            "fstab is still embedded in vendor_boot ramdisk."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
