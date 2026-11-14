#!/usr/bin/env python3
"""Check Mist source-generated super layout against verified ORIGINAL stock liblp.

No firmware download, build, flashing, partition image generation or mutation.
"""
import argparse
import json
import pathlib
import re

EXPECTED = ("odm", "product", "system", "system_dlkm",
            "system_ext", "vendor", "vendor_dlkm")


def variable(data, key):
    pattern = r"(?m)^" + re.escape(key) + r"\\s*:?=\\s*(.*)$"
    match = re.search(pattern, data)
    if not match:
        raise ValueError("Missing " + key)
    return match.group(1).strip()


def make_logical_lines(text):
    return re.sub(r"\\\\\\n", " ", text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device-tree", type=pathlib.Path, required=True)
    ap.add_argument("--stock-super-report", type=pathlib.Path, required=True)
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()
    board = (args.device_tree / "BoardConfig.mk").read_text()
    config = make_logical_lines(board)
    stock = json.loads(args.stock_super_report.read_text())
    assert stock["integrity_checks_passed"], "stock metadata lacks integrity verification"
    first = stock["slots"][0]["primary"]["data"]
    groups = {x["name"]: x for x in first["groups"]}
    group = groups["qti_dynamic_partitions_a"]
    phys = next(x["size"] for x in first["block_devices"] if x["name"] == "super")
    group_name = variable(config, "BOARD_SUPER_PARTITION_GROUPS")
    size_name = "BOARD_QTI_DYNAMIC_PARTITIONS_SIZE"
    list_name = "BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST"
    names = variable(config, list_name).split()
    actual = {
        "stock_geometry_integrity": True,
        "stock_super_size": phys,
        "stock_active_group_maximum": group["maximum_size"],
        "stock_active_group_members": group["partitions"],
        "board_super_size": int(variable(config, "BOARD_SUPER_PARTITION_SIZE")),
        "board_group_name": group_name,
        "board_group_size": int(variable(config, size_name)),
        "board_partition_list": names,
        "mi_ext_generated": "mi_ext" in names,
    }
    assert actual["board_super_size"] == phys, actual
    assert group_name == "qti_dynamic_partitions", actual
    assert actual["board_group_size"] == group["maximum_size"], actual
    assert len(names) == len(EXPECTED) and set(names) == set(EXPECTED), actual
    assert "mi_ext" not in config.split("BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST :=", 1)[1].split("\n", 1)[0]
    fstab = args.device_tree / "boot/stock_snapshot/first_stage_ramdisk/fstab.default"
    original = fstab.read_text()
    mi_lines = [line for line in original.splitlines()
                if "mi_ext" in line and not line.startswith("#")]
    assert mi_lines, "Expected stock mi_ext references missing; review provenance"
    actual["stock_first_stage_mi_ext_fstab_references"] = len(mi_lines)
    actual["note"] = (
        "Source BoardConfig geometry passes; this does NOT validate generated "
        "target-slot OTA metadata, kernel/AVB bootchain, stock vendor_boot "
        "fstab behavior, COW snapshot, or runtime compatibility."
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(actual, indent=2, sort_keys=True) + "\n")
    print(json.dumps(actual, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
