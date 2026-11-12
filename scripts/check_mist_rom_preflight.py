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
    # Verified from the SHA256-checked stock boot-chain structure artifact
    # (run 43266837030); these are structural, not image-build checks.
    check("init_boot header version", "BOARD_INIT_BOOT_HEADER_VERSION := 4" in board,
          "verified stock init_boot header is v4")
    check("init_boot mkbootimg args", "BOARD_MKBOOTIMG_INIT_ARGS += --header_version $(BOARD_INIT_BOOT_HEADER_VERSION)" in board,
          "init_boot packaging must request its observed header version")
    check("stock LZ4 ramdisk format", "BOARD_RAMDISK_USE_LZ4 := true" in board,
          "stock init_boot, vendor_boot and recovery ramdisks use LZ4")
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
    # Structural-only Soong audit: verify every currently published vendor
    # module is requested by product makefiles and installs where its source
    # path indicates. This is NOT a substitute for actual Soong compilation.
    module_blocks = re.findall(
        r"(?ms)^(cc_prebuilt_library_shared|cc_prebuilt_binary|prebuilt_etc)\s*\{(.*?)^\}",
        bp,
    )
    parsed = []
    for kind, body in module_blocks:
        n = re.search(r'\bname:\s*"([^"]+)"', body)
        src = re.search(r'\bsrcs?:\s*(?:\[\s*)?"([^"]+)"', body)
        stem = re.search(r'\b(?:stem|filename):\s*"([^"]+)"', body)
        if not n or not src or not stem:
            problems.append("Unparseable vendor Soong module (missing name/src/stem)")
            continue
        name, source, filename = n.group(1), src.group(1), stem.group(1)
        source_present = (vendor / source).is_file()
        if not source_present:
            problems.append("Vendor Soong source missing: " + source)
        if kind == "cc_prebuilt_binary":
            folder = "vendor/bin"
            prop = re.search(r'\brelative_install_path:\s*"([^"]+)"', body)
            if prop:
                folder += "/" + prop.group(1)
        elif kind == "cc_prebuilt_library_shared":
            folder = "vendor/lib64"
            prop = re.search(r'\brelative_install_path:\s*"([^"]+)"', body)
            if prop:
                folder += "/" + prop.group(1)
            if not re.search(r'\bcompile_multilib:\s*"64"', body):
                problems.append("Stock AArch64 library lacks explicit 64-bit install: " + name)
        else:
            folder = "vendor/etc"
            prop = re.search(r'\bsub_dir:\s*"([^"]+)"', body)
            if prop:
                folder += "/" + prop.group(1)
        target = folder + "/" + filename
        stock_path = source.removeprefix("proprietary/")
        if target != stock_path:
            problems.append("Soong destination differs from stock source: " + name +
                            " (" + target + " != " + stock_path + ")")
        parsed.append(name)
    pack = re.findall(r'\bmist_[A-Za-z0-9_]+\b', vendor_mk)
    check("vendor Soong modules parsed", len(parsed) == len(module_blocks) and bool(parsed),
          "all currently supported Soong prebuilt blocks must parse")
    check("vendor Soong unique names", len(parsed) == len(set(parsed)),
          "no duplicate Soong module names")
    check("vendor product packages unique", len(pack) == len(set(pack)),
          "no duplicate PRODUCT_PACKAGES module references")
    missing_pack = sorted(set(parsed) - set(pack))
    dangling_pack = sorted(set(pack) - set(parsed))
    check("vendor Soong/product package parity", not missing_pack and not dangling_pack,
          "Soong not packaged: " + repr(missing_pack) +
          "; product package with no Soong module: " + repr(dangling_pack))
    checks["vendor_parsed_module_count"] = len(parsed)
    checks["vendor_product_package_count"] = len(pack)
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
