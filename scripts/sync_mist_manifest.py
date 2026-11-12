#!/usr/bin/env python3
"""Synchronize mist device proprietary manifest with verified stock HAL batch.

Reads exact paths from source-staging allowlist; requires production vendor
copy of each file. Never invent paths, replace existing lines or add bloat.
"""
import argparse
import runpy
from pathlib import Path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--device", required=True, type=Path)
    p.add_argument("--vendor", required=True, type=Path)
    p.add_argument("--stager", default="scripts/stage_mist_hal_batch.py")
    args = p.parse_args()
    allow = runpy.run_path(args.stager)["FILES"]
    if len(allow) != 14:
        raise RuntimeError("HAL allowlist unexpectedly changed; review required")
    target = args.device / "proprietary-files.txt"
    existing = target.read_text()
    existing_names = {
        line.strip() for line in existing.splitlines()
        if line.strip() and not line.startswith("#")
    }
    rows = []
    for src in sorted(allow):
        assert src.startswith("vendor_a/")
        rel = src.removeprefix("vendor_a/")
        production_path = args.vendor / "proprietary" / "vendor" / rel
        if not production_path.is_file():
            raise RuntimeError(f"Production vendor blob missing: {production_path}")
        destination = "vendor/" + rel
        if destination not in existing_names:
            rows.append(destination)
    if not rows:
        print("Device proprietary manifest already includes all HAL paths")
        return
    with target.open("a") as f:
        f.write("\n# Curated stock HAL services, init and VINTF (verified vendor batch b5b802b)\n")
        f.write("\n".join(rows) + "\n")
    print("Added", len(rows), "verified file entries to device manifest")

if __name__ == "__main__":
    main()
