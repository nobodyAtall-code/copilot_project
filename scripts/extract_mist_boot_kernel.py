#!/usr/bin/env python3
"""Extract and validate the exact Android boot v3/v4 kernel payload for mist.

No repacking, patching, flashing, or device-specific identifier extraction.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

PAGE_SIZE = 4096
ARM64_MAGIC = b"ARM\x64"
KERNEL_FORMATS = {
    b"\x1f\x8b": "gzip",
    b"\x04\x22\x4d\x18": "lz4-frame",
    b"\x02\x21\x4c\x18": "lz4-legacy",
    b"\xfd7zXZ\x00": "xz",
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def align(size: int, block: int) -> int:
    return (size + block - 1) // block * block

def detect(data: bytes) -> str:
    if len(data) > 0x3c and data[0x38:0x3c] == ARM64_MAGIC:
        return "arm64-Image"
    for magic, label in KERNEL_FORMATS.items():
        if data.startswith(magic):
            return label
    return "unknown"

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--boot", type=Path, required=True)
    p.add_argument("--verified-hashes", type=Path, required=True,
                   help="sha256sum-format report accompanying stock boot files")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    # Require stock image hash to match the trusted image digest report.
    expected = {}
    for line in args.verified_hashes.read_text().splitlines():
        chunks = line.split()
        if len(chunks) >= 2:
            expected[Path(chunks[-1].lstrip("*")).name] = chunks[0]
    if "boot.img" not in expected:
        raise SystemExit("Missing boot.img digest from stock archive report")
    data = args.boot.read_bytes()
    if sha256(data) != expected["boot.img"].lower():
        raise SystemExit("Stock boot.img SHA256 mismatch")
    if len(data) < 4096 or data[:8] != b"ANDROID!":
        raise SystemExit("Not an Android boot image")
    kernel_size, ramdisk_size, os_version, header_size = struct.unpack_from("<IIII", data, 8)
    header_version = struct.unpack_from("<I", data, 40)[0]
    if header_version not in (3, 4):
        raise SystemExit(f"Unsupported Android boot header v{header_version}")
    if not (1500 <= header_size <= PAGE_SIZE):
        raise SystemExit(f"Invalid Android v3/v4 header size {header_size}")
    if not (8 * 1024 * 1024 <= kernel_size <= 100 * 1024 * 1024):
        raise SystemExit(f"Unexpected kernel payload size {kernel_size}")
    start = align(header_size, PAGE_SIZE)
    end = start + kernel_size
    if end > len(data):
        raise SystemExit("Kernel data extends beyond verified boot image")
    payload = data[start:end]
    fmt = detect(payload)
    if fmt == "unknown":
        raise SystemExit("Unrecognized kernel payload format; refusing to publish")
    args.out.mkdir(parents=True, exist_ok=True)
    kernel_file = args.out / "kernel"
    kernel_file.write_bytes(payload)
    manifest = {
        "source": "Xiaomi Global OS3.0.304.0.WPUMIXM",
        "firmware_md5": "c4450c4e168052ca9de1211306d3beff",
        "boot_img_sha256": sha256(data),
        "boot_img_length": len(data),
        "header_version": header_version,
        "header_size": header_size,
        "kernel_offset": start,
        "kernel_size": kernel_size,
        "kernel_sha256": sha256(payload),
        "kernel_format": fmt,
        "ramdisk_size_in_boot": ramdisk_size,
        "os_version_raw": os_version,
        "warning": "Kernel payload only, no DTBO or vendor_boot and no LineageOS build/boot validation",
    }
    (args.out / "kernel-source.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (args.out / "README.md").write_text(
        "# Mist stock-compatible kernel payload\n\n"
        "Extracted **unchanged** from the MD5-verified Xiaomi Global "
        "OS3.0.304.0.WPUMIXM Android boot.img.\n\n"
        "See kernel-source.json for payload format, offsets and SHA256. "
        "This is a temporary stock-compatible boot bring-up prebuilt; "
        "it is NOT a source-built Lineage kernel, a complete boot chain, "
        "or evidence of ROM build/boot success.\n"
        "Do not replace init_boot/vendor_boot/dtbo/recovery without separate validation.\n"
    )
    print(f"Validated Android boot header v{header_version}; {fmt} kernel payload {kernel_size} bytes; sha256={sha256(payload)}")

if __name__ == "__main__":
    main()
