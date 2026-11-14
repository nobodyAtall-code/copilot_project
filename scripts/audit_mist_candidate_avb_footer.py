#!/usr/bin/env python3
"""Offline AVB footer and embedded vbmeta location audit for Mist vendor_boot.

This checks structural bytes only; DOES NOT authenticate signatures,
approve a boot, alter a file or make a modified image flashable.
"""
import argparse
import hashlib
import json
import pathlib
import struct

ORIGINAL_SHA = "f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb"
CANDIDATE_SHA = "4723a7e0d8be708cd637d77fc45d6a27b8d4bff1ff36b49e9ab001b544a96d82"
FOOTER_SIZE = 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


def parse_footer(blob):
    footer = blob[-FOOTER_SIZE:]
    if footer[:4] != b"AVBf":
        raise ValueError("Missing AVBf footer magic")
    major, minor, original_size, vbmeta_offset, vbmeta_size = struct.unpack_from(">IIQQQ", footer, 4)
    if major != 1 or vbmeta_size < 256:
        raise ValueError("Unexpected AVB footer version or vbmeta length")
    if original_size > vbmeta_offset or vbmeta_offset + vbmeta_size > len(blob) - FOOTER_SIZE:
        raise ValueError("Invalid AVB footer vbmeta region bounds")
    embedded = blob[vbmeta_offset:vbmeta_offset + vbmeta_size]
    if embedded[:4] != b"AVB0":
        raise ValueError("Embedded vbmeta magic not found at footer offset")
    return {
        "footer_version": [major, minor],
        "original_image_size": original_size,
        "vbmeta_offset": vbmeta_offset,
        "vbmeta_size": vbmeta_size,
        "footer_sha256": sha(footer),
        "embedded_vbmeta_sha256": sha(embedded),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stock", type=pathlib.Path, required=True)
    p.add_argument("--candidate", type=pathlib.Path, required=True)
    p.add_argument("--out", type=pathlib.Path, required=True)
    a = p.parse_args()
    stock = a.stock.read_bytes()
    candidate = a.candidate.read_bytes()
    if sha(stock) != ORIGINAL_SHA or sha(candidate) != CANDIDATE_SHA:
        raise SystemExit("Unexpected stock or candidate hash; refusing comparison")
    if len(stock) != len(candidate):
        raise SystemExit("Image lengths differ")
    source_footer = parse_footer(stock)
    candidate_footer = parse_footer(candidate)
    if source_footer != candidate_footer:
        raise SystemExit("Original and candidate AVB footer/vbmeta differ unexpectedly")
    report = {
        "status": "AVB_FOOTER_VBMETA_BYTES_PRESERVED_STRUCTURAL_ONLY",
        "stock_sha256": ORIGINAL_SHA,
        "candidate_sha256": CANDIDATE_SHA,
        "stock_footer": source_footer,
        "candidate_footer": candidate_footer,
        "footer_and_embedded_vbmeta_identical": True,
        "signatures_authenticate_modified_ramdisk": False,
        "signature_verification_executed": False,
        "flash_permitted": False,
        "next": "Use independent AOSP avbtool info_image and signing-chain validation; never rely on stale embedded stock signatures.",
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
