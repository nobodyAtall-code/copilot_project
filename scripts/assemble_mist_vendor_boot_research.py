#!/usr/bin/env python3
"""Assemble a NON-FLASHABLE research-only Mist vendor_boot v4 candidate.

Exact original SHA and validated clean fragment report required.
Leaves original stock boot image unchanged. This is NOT AVB signed.
"""
import argparse
import hashlib
import json
import pathlib
import struct

from inspect_mist_boot_chain import align, vendor_boot

STOCK_SHA = "f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb"
STOCK_RAMDISK_SIZE = 10992661
STOCK_FRAGMENT_SHA = "cdd71cdf1100e0b1d3619cac557884ad5ecf1d2fc8d900d1a0d1a221212676f4"
STOCK_FSTAB_NEW_SHA = "a2d39870568abd03b0133d7f4a3f2197e7bf50079626b412f83079b66f09da38"
EXPECTED_FRAGMENT_SIZE = 10992947


def sha(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, msg):
    if not condition:
        raise ValueError(msg)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stock-vendor-boot", required=True, type=pathlib.Path)
    p.add_argument("--review-fragment", required=True, type=pathlib.Path)
    p.add_argument("--review-json", required=True, type=pathlib.Path)
    p.add_argument("--staged-fstab", required=True, type=pathlib.Path)
    p.add_argument("--output-dir", required=True, type=pathlib.Path)
    a = p.parse_args()
    need(not a.output_dir.exists() or not any(a.output_dir.iterdir()),
         "output-dir must not contain files")
    original = a.stock_vendor_boot.read_bytes()
    fragment = a.review_fragment.read_bytes()
    review = json.loads(a.review_json.read_text())
    need(sha(original) == STOCK_SHA, "Original vendor_boot SHA mismatch")
    need(sha(fragment) == STOCK_FRAGMENT_SHA, "Validated clean fragment SHA mismatch")
    need(sha(a.staged_fstab.read_bytes()) == STOCK_FSTAB_NEW_SHA,
         "Staged clean fstab changed since verified patch; regenerate first")
    need(review.get("status") == "FRAGMENT_ONLY_REVIEW_NOT_FLASHABLE" and
         review.get("stock_boot_sha256_verified") is True and
         review.get("source_fstab_sha256_verified") is True and
         review.get("other_entries_metadata_content_order_identical") is True and
         review.get("changed_cpio_paths") == ["first_stage_ramdisk/fstab.default"] and
         review.get("fragment_sha256") == STOCK_FRAGMENT_SHA and
         review.get("new_fstab_sha256") == STOCK_FSTAB_NEW_SHA,
         "Patch report mismatch")
    old = vendor_boot(a.stock_vendor_boot, len(original))
    need(old["header_version"] == 4, "Requires Android vendor boot header v4")
    need(len(old["ramdisk_table_entries"]) == 1, "Requires exactly one ramdisk fragment")
    one = old["ramdisk_table_entries"][0]
    need(one["offset"] == 0 and one["size"] == STOCK_RAMDISK_SIZE,
         "Unexpected original ramdisk fragment")
    need(one["format"] == "lz4-legacy" and
         len(fragment) == EXPECTED_FRAGMENT_SIZE and
         fragment.startswith(b"\x02\x21\x4c\x18"),
         "Unexpected new fragment length/format")
    page = old["page_size"]
    boot_ramdisk_offset = old["vendor_ramdisk_offset"]
    need(boot_ramdisk_offset == align(old["header_size"], page),
         "Unexpected original header alignment")
    old_dtb_start = old["dtb_offset"]
    old_dtb_end = old_dtb_start + old["dtb_size"]
    old_table_start = old_dtb_start + align(old["dtb_size"], page)
    old_table_end = old_table_start + old["ramdisk_table_bytes"]
    old_bootconfig_start = old["bootconfig_offset"]
    old_bootconfig_end = old_bootconfig_start + old["bootconfig_bytes"]
    need(old_table_end <= old_bootconfig_start and old_bootconfig_end <= len(original),
         "Malformed old image sections")
    # Refuse nonzero opaque tail, because we must not silently discard it.
    need(not any(original[old_bootconfig_end:]),
         "Nonzero bytes after original bootconfig; unsupported opaque trailer")
    need(old["ramdisk_table_bytes"] >= 108,
         "Insufficient ramdisk table")
    new_header = bytearray(original[:boot_ramdisk_offset])
    struct.pack_into("<I", new_header, 24, len(fragment))
    new_table = bytearray(original[old_table_start:old_table_end])
    struct.pack_into("<I", new_table, 0, len(fragment))
    dtb = original[old_dtb_start:old_dtb_end]
    original_bootconfig = original[old_bootconfig_start:old_bootconfig_end]
    parts = [
        bytes(new_header),
        fragment,
        b"\x00" * (align(len(fragment), page) - len(fragment)),
        dtb,
        original[old_dtb_end:old_table_start],  # original DTB padding
        bytes(new_table),
        original[old_table_end:old_bootconfig_start],  # original table padding
        original_bootconfig,
    ]
    candidate = b"".join(parts)
    need(len(candidate) <= len(original), "Candidate exceeds stock partition")
    candidate += b"\x00" * (len(original) - len(candidate))
    # Structural parser works on a path, so write to private research output
    # only after preflight checks. It is explicitly NOT an installer artifact.
    a.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_file = a.output_dir / "MIST-VENDOR-BOOT-RESEARCH-DO-NOT-FLASH.img"
    candidate_file.write_bytes(candidate)
    new = vendor_boot(candidate_file, len(candidate))
    checks = {
        "header_version": new["header_version"] == old["header_version"],
        "page_size": new["page_size"] == old["page_size"],
        "ramdisk_size": new["vendor_ramdisk_size"] == len(fragment),
        "ramdisk_fragment_size": new["ramdisk_table_entries"][0]["size"] == len(fragment),
        "ramdisk_fragment_offset": new["ramdisk_table_entries"][0]["offset"] == 0,
        "DTB_exact": candidate[new["dtb_offset"]:new["dtb_offset"] + new["dtb_size"]] == dtb,
        "bootconfig_exact": candidate[new["bootconfig_offset"]:new["bootconfig_offset"] + new["bootconfig_bytes"]] == original_bootconfig,
        "ramdisk_exact": candidate[new["vendor_ramdisk_offset"]:new["vendor_ramdisk_offset"] + len(fragment)] == fragment,
        "image_length": len(candidate) == len(original),
        "bootconfig_table_size": new["bootconfig_bytes"] == old["bootconfig_bytes"] and new["ramdisk_table_bytes"] == old["ramdisk_table_bytes"],
        "ramdisk_table_metadata": new["ramdisk_table_entries"][0]["name"] == one["name"] and new["ramdisk_table_entries"][0]["type"] == one["type"],
    }
    need(all(checks.values()), "Candidate structural invariants failed: " + repr(checks))
    result = {
        "status": "OFFLINE_V4_CONTAINER_STRUCTURE_PASS_NOT_FLASHABLE",
        "source_sha256": STOCK_SHA,
        "candidate_sha256": sha(candidate),
        "candidate_bytes": len(candidate),
        "checks": checks,
        "fragment_sha256": sha(fragment),
        "source_DTB_sha256": sha(dtb),
        "candidate_DTB_sha256": sha(candidate[new["dtb_offset"]:new["dtb_offset"] + new["dtb_size"]]),
        "source_bootconfig_sha256": sha(original_bootconfig),
        "candidate_bootconfig_sha256": sha(candidate[new["bootconfig_offset"]:new["bootconfig_offset"] + new["bootconfig_bytes"]]),
        "device_build_config_updated": False,
        "flash_permitted": False,
        "avb_signed_or_verified": False,
        "boot_verified": False,
        "remaining": [
            "AVB chain, signing and rollback index policy",
            "SELinux compilation and root/init contexts",
            "kernel module ABI/load and runtime recovery compatibility",
            "VINTF vendor HAL and OTA target partition metadata",
            "independent unpackbootimg/mkbootimg or avbtool validation",
        ],
    }
    (a.output_dir / "MIST-VENDOR-BOOT-RESEARCH-REPORT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
