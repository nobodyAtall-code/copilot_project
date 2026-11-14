#!/usr/bin/env python3
"""Produce a REVIEW-ONLY replacement Mist vendor ramdisk fragment.

Verified STOCK vendor_boot.img -> legacy-LZ4 fragment -> newc archive.
Replace only first_stage_ramdisk/fstab.default with the staged clean fstab;
preserve every other CPIO entry byte-for-byte, metadata and order.
Output is NOT a vendor_boot.img and MUST NEVER be flashed.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import struct
import subprocess
import tempfile

from inspect_mist_boot_chain import vendor_boot

STOCK_BOOT_HASH = "f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb"
STOCK_FSTAB_HASH = "cfc3c5b837d6b1491126667eff591efcc23f888548bdcd5839216f630b942516"
TARGET = "first_stage_ramdisk/fstab.default"
MAX_DECODED = 160 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def align4(n):
    return (n + 3) & ~3


def decode_cpio(blob):
    """Yield (original complete header+name+payload record bytes, name, file data, mode)."""
    pos = 0
    found_trailer = False
    count = 0
    while pos + 110 <= len(blob):
        start = pos
        magic = blob[pos:pos + 6]
        if magic not in (b"070701", b"070702"):
            raise ValueError("Invalid newc magic at " + str(pos))
        fields = [int(blob[pos + 6 + j:pos + 14 + j], 16) for j in range(0, 104, 8)]
        mode, size, namesize = fields[1], fields[6], fields[11]
        if namesize < 1 or namesize > 8192 or size < 0 or size > MAX_DECODED:
            raise ValueError("CPIO bounds exceeded")
        name_begin = pos + 110
        name_end = name_begin + namesize
        if name_end > len(blob) or blob[name_end - 1] != 0:
            raise ValueError("Truncated or unterminated CPIO name")
        name = blob[name_begin:name_end - 1].decode("utf-8")
        if name.startswith("/") or ".." in name.split("/"):
            raise ValueError("Unsafe CPIO entry " + name)
        data_begin = align4(name_end)
        data_end = data_begin + size
        if data_end > len(blob):
            raise ValueError("Truncated CPIO data " + name)
        end = align4(data_end)
        if end > len(blob):
            raise ValueError("Invalid CPIO padding")
        yield blob[start:end], name, blob[data_begin:data_end], mode, blob[start:start + 110], blob[start + 110:data_begin], blob[data_end:end]
        pos = end
        count += 1
        if count > 30000:
            raise ValueError("CPIO entry count exceeded")
        if name == "TRAILER!!!":
            found_trailer = True
            break
    if not found_trailer:
        raise ValueError("Missing newc TRAILER!!!")
    if blob[pos:].strip(b"\x00"):
        raise ValueError("Unexpected bytes after CPIO trailer")
    return blob[pos:]


def replace_record(record, new_data):
    full, name, old_data, mode, header, namepart, padding = record
    if (mode & 0o170000) != 0o100000:
        raise ValueError("Target must be a regular file")
    raw = bytearray(header)
    raw[54:62] = f"{len(new_data):08x}".encode("ascii")  # c_filesize, hex newc header
    # original may be CRC '070702'; reject because checksum must be computed
    if raw[:6] != b"070701":
        raise ValueError("Unsupported CRC cpio format")
    payload_padding = b"\x00" * (align4(len(new_data)) - len(new_data))
    return bytes(raw) + namepart + new_data + payload_padding


def execute(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--vendor-boot", required=True, type=pathlib.Path)
    p.add_argument("--fstab", required=True, type=pathlib.Path)
    p.add_argument("--output-dir", required=True, type=pathlib.Path)
    args = p.parse_args(argv)
    if not shutil.which("lz4"):
        raise SystemExit("lz4 CLI is required (sudo apt install lz4)")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise SystemExit("Output directory must be new or empty; refusing overwrite")
    h = hashlib.sha256()
    with args.vendor_boot.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != STOCK_BOOT_HASH:
        raise SystemExit("Wrong vendor_boot.img SHA256; refusing patch")
    v = vendor_boot(args.vendor_boot, args.vendor_boot.stat().st_size)
    fragments = v.get("ramdisk_table_entries", [])
    if v.get("header_version") != 4 or len(fragments) != 1:
        raise SystemExit("Expected single stock v4 vendor ramdisk fragment")
    frag = fragments[0]
    if frag["format"] != "lz4-legacy":
        raise SystemExit("Expected original legacy LZ4 compression")
    with args.vendor_boot.open("rb") as src:
        src.seek(v["vendor_ramdisk_offset"] + frag["offset"])
        compressed = src.read(frag["size"])
    with tempfile.TemporaryDirectory() as scratch:
        # CLI decompression does not write any partition/device, only temp.
        r = subprocess.run(["lz4", "-d", "-c"], input=compressed, capture_output=True, timeout=60)
        if r.returncode:
            raise SystemExit("LZ4 decode failed: " + r.stderr.decode(errors="replace")[-250:])
        raw = r.stdout
        if len(raw) > MAX_DECODED:
            raise SystemExit("Decompressed ramdisk exceeds limit")
        clean_fstab = args.fstab.read_bytes()
        clean_rows = [x.split() for x in clean_fstab.splitlines() if x.strip() and not x.lstrip().startswith(b"#")]
        if any(b"mi_ext" in x for x in clean_rows):
            raise SystemExit("Clean fstab unexpectedly includes mi_ext")
        managed = {b"system", b"system_ext", b"product", b"vendor", b"odm",
                   b"vendor_dlkm", b"system_dlkm"}
        if {r[0] for r in clean_rows if r[0] in managed} != managed:
            raise SystemExit("Clean fstab missing a required logical partition")
        records = list(decode_cpio(raw))
        hits = [x for x in records if x[1] == TARGET]
        if len(hits) != 1:
            raise SystemExit("Expected one original first-stage fstab.default; found " + str(len(hits)))
        if sha(hits[0][2]) != STOCK_FSTAB_HASH:
            raise SystemExit("Original first-stage fstab.default SHA mismatch; aborting")
        produced = b"".join(
            replace_record(rec, clean_fstab) if rec[1] == TARGET else rec[0]
            for rec in records
        )
        produced += b"\x00" * ((4 - len(produced) % 4) % 4)
        # Ensure all non-target entries preserve bytes/metadata/order, and
        # that the target new record is parsable with exactly the expected data.
        rebuilt = list(decode_cpio(produced))
        if len(rebuilt) != len(records):
            raise SystemExit("Entry count drift")
        for old, new in zip(records, rebuilt):
            if old[1] != new[1]:
                raise SystemExit("Member path/order changed")
            if old[1] == TARGET:
                if new[2] != clean_fstab or new[3] != old[3]:
                    raise SystemExit("Replacement did not roundtrip")
            elif old[0] != new[0]:
                raise SystemExit("Unexpected change to " + old[1])
        # LZ4 -l explicitly creates a legacy stream; output is not vendor_boot.
        r = subprocess.run(["lz4", "-l", "-12", "-c"], input=produced, capture_output=True, timeout=90)
        if r.returncode or not r.stdout.startswith(b"\x02\x21\x4c\x18"):
            raise SystemExit("Legacy LZ4 compression failed")
        check = subprocess.run(["lz4", "-d", "-c"], input=r.stdout, capture_output=True, timeout=60)
        if check.returncode or check.stdout != produced:
            raise SystemExit("Compressed fragment failed roundtrip")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        fragment_path = args.output_dir / "mist-vendor-ramdisk-REVIEW-ONLY.cpio.lz4"
        fragment_path.write_bytes(r.stdout)
        report = {
            "status": "FRAGMENT_ONLY_REVIEW_NOT_FLASHABLE",
            "stock_boot_sha256_verified": True,
            "source_boot_sha256": STOCK_BOOT_HASH,
            "source_fstab_sha256_verified": True,
            "old_fstab_sha256": STOCK_FSTAB_HASH,
            "new_fstab_sha256": sha(clean_fstab),
            "old_cpio_entries": len(records) - 1,
            "new_cpio_entries": len(rebuilt) - 1,
            "changed_cpio_paths": [TARGET],
            "other_entries_metadata_content_order_identical": True,
            "stock_fragment_bytes": len(compressed),
            "new_fragment_bytes": len(r.stdout),
            "fragment_sha256": sha(r.stdout),
            "bootconfig_and_dtbs_untouched_in_source": True,
            "vendor_boot_repacked": False,
            "avb_signatures_verified": False,
            "safe_to_flash": False,
            "warnings": [
                "No boot image generated; only a replacement ramdisk fragment for review.",
                "Original stock vendor_boot still installed in current Lineage device tree.",
                "Modules are preserved in the CPIO but kernel ABI/runtime loading not validated.",
                "Do not flash until full boot image/recovery and AVB/SELinux/OTA validation.",
            ],
        }
        (args.output_dir / "mist-vendor-ramdisk-review.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


def main():
    execute(None)


if __name__ == "__main__":
    main()
