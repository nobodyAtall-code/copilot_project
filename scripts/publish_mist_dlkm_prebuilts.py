#!/usr/bin/env python3
"""Restore verified stock DLKM binaries/metadata to the dedicated mist-kernel tree.

Never edits production device.mk and fails if any requested build source is absent.
"""
import argparse, hashlib, json, re, shutil
from pathlib import Path

PARTITIONS = {"vendor_dlkm_a": ("vendor_dlkm", 268), "system_dlkm_a": ("system_dlkm", 192)}
EXPECTED_FIRMWARE = "OS3.0.304.0.WPUMIXM"
EXPECTED_MD5 = "c4450c4e168052ca9de1211306d3beff"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    parser = argparse.ArgumentParser()
    for name in ("source", "manifest", "kernel-repo", "device-repo"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    if data.get("firmware") != EXPECTED_FIRMWARE or data.get("verified_source_md5") != EXPECTED_MD5:
        raise ValueError("Firmware provenance mismatch")
    if set(data["partitions"]) != set(PARTITIONS):
        raise ValueError("Unexpected partition set")
    staged = []
    for source_partition, (dest_partition, expected_count) in PARTITIONS.items():
        record = data["partitions"][source_partition]
        entries = record["files"]
        if record["module_count"] != expected_count or sum(e["type"] == "module" for e in entries) != expected_count:
            raise ValueError(f"{source_partition}: unexpected module count")
        if not record["load_lists"] or record.get("load_missing"):
            raise ValueError(f"{source_partition}: missing load metadata")
        seen = set()
        for entry in entries:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2:
                raise ValueError(f"Unsafe path: {relative}")
            if relative.as_posix() in seen:
                raise ValueError(f"Duplicate source: {relative}")
            seen.add(relative.as_posix())
            source = args.source / source_partition / relative
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"Missing/symlinked source: {source}")
            if source.stat().st_size != entry["size"] or digest(source) != entry["sha256"]:
                raise ValueError(f"SHA256 or size mismatch: {source}")
            destination = args.kernel_repo / dest_partition / relative
            if destination.exists() and (destination.is_symlink() or digest(destination) != entry["sha256"]):
                raise ValueError(f"Conflicting target: {destination}")
            staged.append((source, destination))
        if not set(record["load_lists"]).issubset(seen):
            raise ValueError(f"{source_partition}: missing modules.load references")
        print(f"{source_partition}: SHA256 checked {len(entries)} files, {expected_count} modules")
    # Only after all hashes and metadata pass, copy files to the dedicated prebuilt repo.
    for source, destination in staged:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
    device_makefile = (args.device_repo / "device.mk").read_text()
    references = set(re.findall(r'device/xiaomi/mist-kernel/(?:system_dlkm|vendor_dlkm)/[^\s:]+', device_makefile))
    if len(references) != 482:
        raise ValueError(f"Expected 482 existing device.mk references; found {len(references)}")
    missing = [p for p in sorted(references) if not (args.kernel_repo / p.removeprefix("device/xiaomi/mist-kernel/")).is_file()]
    if missing:
        for item in missing[:20]:
            print("MISSING:", item)
        raise ValueError(f"{len(missing)} device.mk source paths unresolved")
    print(f"SUCCESS: {len(references)} build paths satisfied; {len(staged)} stock files verified")

if __name__ == "__main__":
    main()
