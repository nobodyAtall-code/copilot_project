#!/usr/bin/env python3
"""Offline check of Mist BoardConfig against SHA-checked original super geometry.

Only source/geometry checks: does not prove OTA, AVB, COW, ramdisk or boot.
"""
import argparse
import json
import pathlib
import re

EXPECTED = {"odm", "product", "system", "system_dlkm",
            "system_ext", "vendor", "vendor_dlkm"}


def variable(data, key):
    pattern = r"(?m)^" + re.escape(key) + r"\s*:?=\s*(.*)$"
    found = re.search(pattern, data)
    if found is None:
        raise ValueError("Missing variable: " + key)
    return found.group(1).strip()


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--device-tree", type=pathlib.Path, required=True)
    a.add_argument("--stock-super-report", type=pathlib.Path, required=True)
    a.add_argument("--out", type=pathlib.Path)
    args = a.parse_args()
    config = (args.device_tree / "BoardConfig.mk").read_text()
    # Convert actual Make backslash-newline continuations to spaces.
    logical = re.sub(r"\\\r?\n[ \t]*", " ", config)
    stock = json.loads(args.stock_super_report.read_text())
    assert stock["integrity_checks_passed"], "Original metadata validation failed"
    data = stock["slots"][0]["primary"]["data"]
    groups = {g["name"]: g for g in data["groups"]}
    group = groups["qti_dynamic_partitions_a"]
    physical = next(d["size"] for d in data["block_devices"] if d["name"] == "super")
    partitions = variable(logical, "BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST").split()
    reported = {
        "stock_super_size": physical,
        "stock_group_size": group["maximum_size"],
        "board_super_size": int(variable(logical, "BOARD_SUPER_PARTITION_SIZE")),
        "board_group_size": int(variable(logical, "BOARD_QTI_DYNAMIC_PARTITIONS_SIZE")),
        "board_group_name": variable(logical, "BOARD_SUPER_PARTITION_GROUPS"),
        "board_partitions": partitions,
        "stock_metadata_valid": True,
    }
    assert reported["board_super_size"] == physical, reported
    assert reported["board_group_size"] == group["maximum_size"], reported
    assert reported["board_group_name"] == "qti_dynamic_partitions", reported
    assert len(partitions) == 7 and set(partitions) == EXPECTED, reported
    assert "mi_ext" not in partitions, reported
    stock_fstab = (args.device_tree /
                   "boot/stock_snapshot/first_stage_ramdisk/fstab.default").read_text()
    mi_ext_lines = [line for line in stock_fstab.splitlines()
                    if line.strip() and not line.lstrip().startswith("#") and
                    "mi_ext" in line]
    assert mi_ext_lines, "Unexpected missing stock mi_ext fstab reference"
    reported["original_stock_vendor_boot_mi_ext_lines"] = len(mi_ext_lines)
    reported["status"] = "BOARD_LAYOUT_SOURCE_MATCH_ONLY"
    reported["remaining"] = [
        "Lineage target-slot metadata and full OTA payload validation",
        "Stock vendor_boot mi_ext overlay and init dependencies",
        "AVB signing and first-stage mount",
        "VAB snapshot/COW and real boot",
    ]
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(reported, indent=2, sort_keys=True) + "\n")
    print(json.dumps(reported, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
