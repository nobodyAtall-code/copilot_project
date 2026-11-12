#!/usr/bin/env python3
"""Generate a small Mist vendor prebuilt tree from the verified STOCK tar.

Publication is deliberately limited to hand-selected, observed stock 64-bit
KeyMint/Keymaster and secure clock libraries. No wildcard extraction.
The target repository receives only build declarations and source blobs.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

LIBS = (
    "android.hardware.security.secureclock-V1-ndk.so",
    "android.hardware.security.sharedsecret-V1-ndk.so",
    "android.hardware.security.sharedsecret-V2-ndk.so",
    "libkeymaster_messages.so",
    "libkeymasterdeviceutils.so",
    "libkeymasterprovision.so",
    "libkeymasterutils.so",
    "libqtikeymaster4.so",
    "libqtikeymint.so",
    "libspukeymint.so",
    "libspukeymintdeviceutils.so",
    "libspukeymintprovision.so",
    "libspukeymintutils.so",
)
MAX_BLOB_SIZE = 80 * 1024 * 1024
SOURCE_PREFIX = "vendor_a/lib64/"
PRODUCTION_PREFIX = "proprietary/vendor/lib64/"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--destination", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    expected = {SOURCE_PREFIX + name: name for name in LIBS}
    found = {}
    args.destination.mkdir(parents=True, exist_ok=True)
    output_dir = args.destination / PRODUCTION_PREFIX
    output_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        ["zstd", "-dc", "--", str(args.archive)],
        stdout=subprocess.PIPE,
    )
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                raw = member.name.removeprefix("./")
                if raw not in expected:
                    continue
                if raw in found:
                    raise RuntimeError(f"Repeated stock path {raw}")
                if not member.isfile() or member.size > MAX_BLOB_SIZE or member.size < 64:
                    raise RuntimeError(f"Bad type or size for {raw}")
                stream = tar.extractfile(member)
                if stream is None:
                    raise RuntimeError(f"Unreadable archive member: {raw}")
                data = stream.read(MAX_BLOB_SIZE + 1)
                if len(data) != member.size or data[:4] != bytes.fromhex("7f454c46"):
                    raise RuntimeError(f"Non-ELF or incomplete stock file {raw}")
                if data[4] != 2 or int.from_bytes(data[18:20], "little") != 183:
                    raise RuntimeError(f"Unexpected ELF class/machine in {raw}")
                name = expected[raw]
                (output_dir / name).write_bytes(data)
                found[raw] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    finally:
        if proc.stdout:
            proc.stdout.close()
        result = proc.wait()
    if result != 0:
        raise RuntimeError("zstd failed")
    missing = sorted(set(expected) - set(found))
    if missing:
        raise RuntimeError(f"Mandatory reviewed stock files missing: {missing}")
    blocks = [
        "// Mist stock firmware OS3.0.304.0.WPUMIXM",
        "// Initial KeyMint/Keymaster library batch; not a complete vendor bring-up.",
        "// Do not assume missing KeyMint VINTF XML means the HAL is present.",
        "",
    ]
    names = []
    for name in LIBS:
        module = "mist_stock_" + name.removesuffix(".so").replace("-", "_").replace(".", "_")
        names.append(module)
        blocks.extend([
            "cc_prebuilt_library_shared {",
            f'    name: "{module}",',
            f'    stem: "{name}",',
            f'    srcs: ["{PRODUCTION_PREFIX}{name}"],',
            '    vendor: true,',
            '    compile_multilib: "64",',
            '    strip: { none: true },',
            '    check_elf_files: false, // initial bootstrap; validate ABI before build',
            "}",
            "",
        ])
    (args.destination / "Android.bp").write_text("\n".join(blocks))
    (args.destination / "mist-vendor.mk").write_text(
        "# Mist initial verified-stock library batch\n"
        + "PRODUCT_PACKAGES += \\\n    "
        + " \\\n    ".join(names) + "\n"
    )
    (args.destination / "README.md").write_text(
        "# Mist vendor tree — initial stock library batch\n\n"
        "Source: Xiaomi Global OS3.0.304.0.WPUMIXM, MD5 "
        "c4450c4e168052ca9de1211306d3beff.\n\n"
        "Only the 13 explicitly reviewed archived lib64 paths listed in "
        "copilot_project/scripts/publish_mist_vendor_batch.py are included. "
        "This is an incremental bootstrap, not a complete vendor implementation. "
        "ELF architecture verified; library ABI, runtime service selection, "
        "namespace linking and LineageOS module duplication still need build validation.\n"
        "Do not add private partitions, factory calibration, secrets or stock applications.\n"
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({
        "firmware": "OS3.0.304.0.WPUMIXM",
        "scope": "13 explicitly selected lib64 libraries",
        "files": found,
        "status": "ELF architecture and source paths verified; ROM build not verified",
    }, indent=2, sort_keys=True) + "\n")
    print("Validated and packaged", len(found), "stock 64-bit shared libraries")

if __name__ == "__main__":
    main()
