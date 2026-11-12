#!/usr/bin/env python3
"""Read-only inspection of SHA-verified Xiaomi mist stock boot-chain images.

Reports structure and bounded offsets; never extracts or republishes payloads.
A parsed header does NOT verify AVB signatures, DTBO compatibility, ramdisk
contents, module ordering, SELinux, or LineageOS bootability.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

NAMES = ("boot.img", "init_boot.img", "vendor_boot.img", "recovery.img",
         "dtbo.img", "vbmeta.img", "vbmeta_system.img")
MAX_HEADER = 4096

def align(n, block):
    if block < 1 or (block & (block - 1)):
        raise ValueError("Invalid image page alignment")
    return (n + block - 1) // block * block

def u32(data, off, endian="<"):
    return struct.unpack_from(endian + "I", data, off)[0]

def u64(data, off, endian="<"):
    return struct.unpack_from(endian + "Q", data, off)[0]

def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def peek(path, offset, length=MAX_HEADER):
    with path.open("rb") as stream:
        stream.seek(offset)
        return stream.read(length)

def compressed_magic(buf):
    if buf.startswith(b"\x1f\x8b"): return "gzip"
    if buf.startswith(b"\x04\x22\x4d\x18"): return "lz4-frame"
    if buf.startswith(b"\x02\x21\x4c\x18"): return "lz4-legacy"
    if buf.startswith(b"\x28\xb5\x2f\xfd"): return "zstd"
    if buf.startswith(b"070701"): return "cpio-newc"
    return "unidentified"

def android_boot(path, size):
    h = peek(path, 0)
    if h[:8] != b"ANDROID!":
        raise ValueError("Not Android boot image magic; header not decoded")
    kernel, ramdisk, os_version, header_size = struct.unpack_from("<IIII", h, 8)
    version = u32(h, 40)
    if version not in (3, 4) or not 1580 <= header_size <= MAX_HEADER:
        raise ValueError("Unsupported Android boot v3/v4 header")
    kernel_at = align(header_size, 4096)
    ramdisk_at = kernel_at + align(kernel, 4096)
    if ramdisk_at + ramdisk > size:
        raise ValueError("boot kernel/ramdisk sizes extend outside image")
    return {"kind": "android_boot", "header_version": version,
            "header_size": header_size, "kernel_size": kernel,
            "ramdisk_size": ramdisk, "kernel_offset": kernel_at,
            "ramdisk_offset": ramdisk_at if ramdisk else None,
            "ramdisk_format": compressed_magic(peek(path, ramdisk_at, 8)) if ramdisk else None,
            "os_version_raw": os_version,
            "signature_size_from_v4_header": u32(h, 1580) if version == 4 else None}

def vendor_boot(path, size):
    h = peek(path, 0)
    if h[:8] != b"VNDRBOOT":
        raise ValueError("Not vendor boot image magic")
    version, page = struct.unpack_from("<II", h, 8)
    if version not in (3, 4) or page < 512 or page > 65536:
        raise ValueError("Unsupported vendor boot header version/page")
    ramdisk = u32(h, 24)
    header_size = u32(h, 2096)
    dtb = u32(h, 2100)
    if not 2112 <= header_size <= MAX_HEADER:
        raise ValueError("Unexpected vendor boot header size")
    ramdisk_at = align(header_size, page)
    dtb_at = ramdisk_at + align(ramdisk, page)
    after_dtb = dtb_at + align(dtb, page)
    if after_dtb > size:
        raise ValueError("Vendor boot ramdisk/DTB exceeds image")
    result = {"kind": "vendor_boot", "header_version": version,
              "header_size": header_size, "page_size": page,
              "vendor_ramdisk_size": ramdisk, "vendor_ramdisk_offset": ramdisk_at,
              "ramdisk_format": compressed_magic(peek(path, ramdisk_at, 8)),
              "dtb_size": dtb, "dtb_offset": dtb_at}
    if version == 4:
        table_bytes, entries, stride, bootconfig_bytes = struct.unpack_from("<IIII", h, 2112)
        if entries > 1024 or (entries and stride < 108) or entries * stride > table_bytes:
            raise ValueError("Invalid vendor ramdisk table dimensions")
        bootconfig_at = after_dtb + align(table_bytes, page)
        if bootconfig_at + bootconfig_bytes > size:
            raise ValueError("Vendor ramdisk table/bootconfig exceeds image")
        fragments = []
        table = peek(path, after_dtb, table_bytes)
        if len(table) != table_bytes:
            raise ValueError("Truncated vendor ramdisk table")
        for index in range(entries):
            item = table[index * stride:(index + 1) * stride]
            frag_size, frag_offset, frag_type = struct.unpack_from("<III", item, 0)
            if frag_offset + frag_size > ramdisk:
                raise ValueError("Vendor ramdisk fragment outside ramdisk")
            name = item[12:44].split(b"\0", 1)[0].decode("ascii", "replace")
            fragments.append({"index": index, "name": name, "type": frag_type,
                              "size": frag_size, "offset": frag_offset,
                              "format": compressed_magic(peek(path, ramdisk_at + frag_offset, 8))})
        result.update({"ramdisk_table_bytes": table_bytes, "ramdisk_table_entries": fragments,
                       "bootconfig_bytes": bootconfig_bytes,
                       "bootconfig_offset": bootconfig_at})
    return result

def dtbo(path, size):
    h = peek(path, 0)
    if u32(h, 0, ">") != 0xd7b7ab1e:
        raise ValueError("No Android DTBO table magic")
    total, header, stride, count, offset, page, version = struct.unpack_from(">7I", h, 4)
    if total > size or header < 32 or count > 10000 or stride < 32 or offset + count * stride > total:
        raise ValueError("Invalid Android DTBO table bounds")
    return {"kind": "dtbo_table", "dtbo_total_bytes": total,
            "header_size": header, "entry_size": stride,
            "entry_count": count, "entries_offset": offset,
            "page_size": page, "version": version,
            "note": "DTBO images/board IDs not decoded or matched to stock DTB"}

def vbmeta(path, size):
    h = peek(path, 0)
    if h[:4] != b"AVB0":
        raise ValueError("No AVB0 vbmeta header magic")
    major, minor = struct.unpack_from(">II", h, 4)
    auth, aux = struct.unpack_from(">QQ", h, 12)
    if 256 + auth + aux > size:
        raise ValueError("vbmeta auth and auxiliary blocks exceed image")
    return {"kind": "avb_vbmeta", "libavb_required_major": major,
            "libavb_required_minor": minor, "auth_block_size": auth,
            "aux_block_size": aux,
            "note": "Signature validity, descriptors, rollback indices and chain partition keys NOT verified"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--images-dir", type=Path, required=True)
    p.add_argument("--sha256-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    expected = {}
    for line in a.sha256_file.read_text().splitlines():
        chunks = line.split()
        if len(chunks) == 2:
            expected[Path(chunks[1].lstrip("*")).name] = chunks[0].lower()
    missing = sorted(set(NAMES) - set(expected))
    if missing:
        raise SystemExit("Missing required manifest hashes: " + ", ".join(missing))
    report = {"source": "SHA256-verified OS3.0.304.0.WPUMIXM boot-image artifact",
              "source_run": 43174896778, "images": {}, "errors": [],
              "boot_chain_integration_verified": False, "safe_to_flash": False}
    for name in NAMES:
        path = a.images_dir / name
        if not path.is_file():
            raise SystemExit("Missing boot image: " + name)
        actual = checksum(path)
        if actual != expected[name]:
            raise SystemExit("Stock image SHA256 mismatch: " + name)
        size = path.stat().st_size
        rec = {"bytes": size, "sha256": actual, "sha256_verified": True}
        try:
            if name == "vendor_boot.img":
                rec.update(vendor_boot(path, size))
            elif name == "dtbo.img":
                rec.update(dtbo(path, size))
            elif name.startswith("vbmeta"):
                rec.update(vbmeta(path, size))
            else:
                rec.update(android_boot(path, size))
        except (ValueError, struct.error) as ex:
            rec["structure_error"] = str(ex)
            report["errors"].append(name + ": " + str(ex))
        report["images"][name] = rec
        print(name, "sha256 verified", actual, "size", size,
              "header", rec.get("kind", "UNVERIFIED"))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if report["errors"]:
        raise SystemExit("Boot chain structure review incomplete; see JSON errors")

if __name__ == "__main__":
    main()
