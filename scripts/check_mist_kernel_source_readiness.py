#!/usr/bin/env python3
"""Read-only, fail-closed preflight for production mist kernel source integration.

Run against a *separate kernel build workspace* (NOT a Lineage source checkout):
  python3 scripts/check_mist_kernel_source_readiness.py --root /path/to/kernel/workspace

This deliberately does not modify Kconfig, fabricate Xiaomi MIHW sources,
compile anything, or mark a kernel boot-compatible.
"""
import argparse
import json
from pathlib import Path

def check(root):
    kernel = root / "msm-kernel"
    mihw_link = kernel / "drivers/mihw"
    # Resolve the *actual* upstream relative symlink; do not assume an\n    # arbitrary workspace root depth.\n    source = mihw_link.resolve() if mihw_link.is_symlink() else root / "vendor/xiaomi/proprietary/mihw"
    perf = kernel / "arch/arm64/configs/vendor/mist_perf.config"
    required = {
        "mist Bazel definition": kernel / "mist.bzl",
        "mist build config": kernel / "build.config.msm.mist",
        "mist perf fragment": perf,
        "Kleaf build rules": root / "build/kernel/kleaf/kernel.bzl",
        "Qualcomm platform map": kernel / "arch/arm64/boot/dts/vendor/qcom/platform_map.bzl",
        "Xiaomi MIHW Kconfig": source / "Kconfig",
        "Xiaomi MIHW Makefile": source / "Makefile",
    }
    checks = {label: path.is_file() for label, path in required.items()}
    config = perf.read_text() if perf.is_file() else ""
    enabled = {s: any(line.strip() == s + "=y" or line.strip() == s + "=m"
                      for line in config.splitlines())
               for s in ("CONFIG_MIHW", "CONFIG_MI_SCHED", "CONFIG_METIS",
                         "CONFIG_METIS_WALT", "CONFIG_MIGT", "CONFIG_MIGT_WALT")}
    link_target = str(mihw_link.readlink()) if mihw_link.is_symlink() else None
    checks["MIHW symlink points at expected tree"] = (
        mihw_link.is_symlink() and source.as_posix().endswith("/vendor/xiaomi/proprietary/mihw")
    )
    checks["MIHW vendor source available through kernel symlink"] = (
        (mihw_link / "Kconfig").is_file() and (mihw_link / "Makefile").is_file()
    )
    result = {
        "status": "SOURCE_LAYOUT_READY" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "mist_perf_enabled_options": enabled,
        "mihw_link": link_target,
        "limitations": ("Source layout only. Passing does not prove source provenance, "
                        "compilation, kernel/module ABI, DTBO compatibility, AVB or boot."),
    }
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True,
                        help="root containing msm-kernel, build/kernel, vendor/xiaomi")
    parser.add_argument("--json", type=Path, default=None,
                        help="optional local JSON output path")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error("workspace root does not exist: " + str(root))
    result = check(root)
    print(json.dumps(result, indent=2))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2) + "\n")
    if result["status"] != "SOURCE_LAYOUT_READY":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
