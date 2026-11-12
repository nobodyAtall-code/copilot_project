#!/usr/bin/env python3
"""Read-only structural preflight for mist LineageOS device/vendor/kernel trees.

Usage: python3 scripts/check_mist_rom_preflight.py DEVICE_TREE VENDOR_TREE KERNEL_PREBUILT_TREE
Inputs are local disposable checkouts; this never downloads, patches or publishes binaries.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

def main():
    p = argparse.ArgumentParser()
    p.add_argument("device", type=pathlib.Path)
    p.add_argument("vendor", type=pathlib.Path)
    p.add_argument("kernel", type=pathlib.Path)
    p.add_argument("--report", type=pathlib.Path)
    args = p.parse_args()
    device, vendor, kernel = args.device, args.vendor, args.kernel
    problems, warnings, checks = [], [], {}
    def check(name, condition, detail):
        checks[name] = {"passed": bool(condition), "detail": detail}
        if not condition:
            problems.append(name + ": " + detail)
    for path in ("BoardConfig.mk", "device.mk", "lineage_mist.mk", "AndroidProducts.mk", "proprietary-files.txt", "extract-files.py", "setup-makefiles.py"):
        check("device/" + path, (device / path).is_file(), "required device configuration file")
    for path in ("Android.bp", "mist-vendor.mk"):
        check("vendor/" + path, (vendor / path).is_file(), "required vendor build definition")
    board = (device / "BoardConfig.mk").read_text() if (device / "BoardConfig.mk").is_file() else ""
    product = (device / "lineage_mist.mk").read_text() if (device / "lineage_mist.mk").is_file() else ""
    check("kernel prebuilt wiring", "TARGET_PREBUILT_KERNEL := device/xiaomi/mist-kernel/kernel" in board, "BoardConfig must reference checked-in verified stock kernel")
    check("vendor product inheritance", "vendor/xiaomi/mist/mist-vendor.mk" in product, "product makefile must include vendor package definitions")
    k = kernel / "kernel"
    check("kernel payload present", k.is_file() and k.stat().st_size > 1024 * 1024, "stock Image must be committed to kernel prebuilt tree")
    if k.is_file():
        with k.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        checks["kernel_sha256"] = digest
        lock = kernel / "kernel-source.json"
        if lock.is_file():
            stock_meta = json.loads(lock.read_text())
            check("kernel stock SHA256", digest == stock_meta.get("kernel_sha256"), "kernel Image must match the locked stock boot-image extraction")
            check("kernel stock source", stock_meta.get("source") == "Xiaomi Global OS3.0.304.0.WPUMIXM", "expected exact stock firmware provenance")
        else:
            problems.append("Missing kernel-source.json provenance lock")
    manifest = device / "proprietary-files.txt"
    paths = []
    if manifest.is_file():
        for line in manifest.read_text().splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#"):
                continue
            # Extract-utils modifiers and renaming are unsupported in this initial manifest.
            if not re.fullmatch(r"(?:vendor|odm|system_ext|product|system)/[A-Za-z0-9_./@+-]+", entry) or ".." in pathlib.PurePosixPath(entry).parts:
                problems.append("Unsupported manifest entry (must be reviewed): " + entry)
                continue
            paths.append(entry)
    check("no duplicate manifest entries", len(paths) == len(set(paths)), "duplicate proprietary manifest paths")
    check("manifest nonempty", bool(paths), "at least one reviewed vendor file expected")
    absent = [x for x in paths if not (vendor / "proprietary" / x).is_file()]
    # Some vendor files may be symlinks. Keep their safety assessment separate.
    check("manifest files published", not absent, "missing paths in vendor tree: " + ", ".join(absent[:30]))
    for x in paths:
        pth = vendor / "proprietary" / x
        if pth.is_symlink():
            warnings.append("symlink needs target review: " + x)
    vendor_mk = (vendor / "mist-vendor.mk").read_text() if (vendor / "mist-vendor.mk").is_file() else ""
    bp = (vendor / "Android.bp").read_text() if (vendor / "Android.bp").is_file() else ""
    checks["vendor_makefile_bytes"] = len(vendor_mk.encode())
    checks["vendor_soong_bytes"] = len(bp.encode())
    checks["manifest_file_count"] = len(paths)
    # Explicit unsatisfied gates. No inference from physical super size.
    gates = {
        "authoritative dynamic partition group metadata": False,
        "validated vendor_boot ramdisk and dtbo integration": False,
        "SELinux / VINTF / encryption integration": False,
        "full vendor ELF dependency closure": False,
        "LineageOS 23.2 lunch/build": False,
        "on-device boot and hardware validation": False,
    }
    warnings.extend(["UNVERIFIED gate: " + gate for gate in gates])
    result = {
        "scope": "read-only integration preflight, not ROM compilation",
        "device": "mist",
        "checks": checks,
        "errors": problems,
        "warnings": warnings,
        "unverified_gates": list(gates),
        "ready_for_rom_build_claim": False,
        "flashable": False,
    }
    output = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output)
    print(output)
    sys.exit(1 if problems else 0)

if __name__ == "__main__":
    main()
