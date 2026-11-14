#!/usr/bin/env python3
"""Targeted Mist boot-critical integration gate, read-only and no ROM build.

Checks selected installed vendor output and service RC executable references.
Incomplete build output results in UNVERIFIED, not fictitious missing blobs.
"""
from __future__ import annotations

import datetime
import pathlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

root = pathlib.Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else pathlib.Path.home() / "android/lineage"
device = root / "device/xiaomi/mist"
vendor = root / "vendor/xiaomi/mist"
product = root / "out/target/product/mist"
staged = vendor / "proprietary"
results = []
details = []

def check(status, label, explanation):
    results.append((status, label, explanation))

def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""

def command(*args):
    try:
        p = subprocess.run(args, text=True, capture_output=True, timeout=20)
        return (p.returncode, (p.stdout + p.stderr).strip())
    except Exception as exc:
        return (-1, str(exc))

def output_file(absolute_vendor_path):
    if not absolute_vendor_path.startswith("/vendor/"):
        return None
    return product / absolute_vendor_path.lstrip("/")

def source_file(absolute_vendor_path):
    if not absolute_vendor_path.startswith("/vendor/"):
        return None
    return staged / absolute_vendor_path.lstrip("/")

def declared_modules():
    bp = read(vendor / "Android.bp")
    mk = re.sub(r"(?m)^\s*#.*$", "", read(vendor / "mist-vendor.mk"))
    named = set(re.findall(r'(?m)^\s*name:\s*"([^"]+)"', bp))
    requested = set(re.findall(r"\bmist_[A-Za-z0-9_]+\b", mk))
    return requested, named

requested, declared = declared_modules()
undefined = sorted(requested - declared)
check("FAIL" if undefined else "PASS", "Soong package declarations",
      "unresolved modules: " + ", ".join(undefined) if undefined else f"{len(requested)} Mist packages have declarations")

# Limit the review to init RC files that actually belong to selected prebuilt packages.
bp = read(vendor / "Android.bp")
selected_rc = []
for match in re.finditer(r'prebuilt_etc\s*\{(.*?)\n\}', bp, flags=re.S):
    block = match.group(1)
    name = re.search(r'\bname:\s*"([^"]+)"', block)
    src = re.search(r'\bsrc:\s*"([^"]+\.rc)"', block)
    if name and src and name.group(1) in requested:
        selected_rc.append((name.group(1), vendor / src.group(1)))
rc_executables = {}
missing_source = []
for module, path in selected_rc:
    if not path.is_file():
        missing_source.append(module + ": " + str(path))
        continue
    for line in read(path).splitlines():
        clean = line.strip()
        if clean.startswith("service "):
            cols = clean.split()
            if len(cols) >= 3 and cols[2].startswith("/vendor/"):
                rc_executables.setdefault(cols[2], set()).add(path.name + " service " + cols[1])
        elif clean.startswith("exec ") and " -- /vendor/" in clean:
            val = clean.partition(" -- ")[2].split()
            if val and val[0].startswith("/vendor/"):
                rc_executables.setdefault(val[0], set()).add(path.name + " exec")
check("FAIL" if missing_source else "PASS", "selected RC source presence",
      f"{len(selected_rc)} RC modules inspected; missing: " + ", ".join(missing_source[:10]))

# A missing source file is a candidate, not proof of absent runtime installation.
for binary, owners in sorted(rc_executables.items()):
    s, o = source_file(binary), output_file(binary)
    provenance = "staged-stock" if s and s.is_file() else ("output" if o and o.is_file() else "not in staged-source/output")
    details.append(binary + " <- " + ", ".join(sorted(owners)) + " [" + provenance + "]")
    if provenance == "not in staged-source/output":
        check("WARN", "unresolved vendor init reference " + binary,
              "no staged copy or existing output; may be supplied by platform or stock extraction")

# Camera perfopt invokes a script on property changes. Validate separately
# because an RC may be packaged by the platform instead of the staged vendor tree.
camera_rc = staged / "vendor/etc/init/vendor.qti.camera.provider-service_64.rc"
camera_text = read(camera_rc)
camera_script = "/vendor/bin/init.qti.cam.perfopt.sh"
if camera_script in camera_text:
    s, o = source_file(camera_script), output_file(camera_script)
    if (s and s.is_file()) or (o and o.is_file()):
        check("PASS", "camera perfopt helper staged", camera_script)
    else:
        check("WARN", "camera perfopt helper not staged",
              "camera RC references " + camera_script + "; source/installed output missing; need original stock archive and SELinux domain evidence")
else:
    check("UNVERIFIED", "camera perfopt helper", "no matching reference in current staged camera RC")

# Check exact stock-backup intent and ensure unverified fstab stays uninvolved.
board = read(device / "BoardConfig.mk")
device_mk = read(device / "device.mk")
if "BOARD_PREBUILT_VENDOR_BOOTIMAGE :=" in board and "PRODUCT_BUILD_VENDOR_BOOT_IMAGE := false" in device_mk:
    check("PASS", "vendor_boot prebuilt preservation", "stock prebuilt configured, custom vendor_boot build disabled")
else:
    check("WARN", "vendor_boot prebuilt preservation", "review board and product configuration")
if "rootdir/etc/fstab.mist" in (board + device_mk):
    check("WARN", "fstab staging", "staged fstab referenced in active boot configuration; validate first-stage provenance")
else:
    check("PASS", "fstab staging", "staged device fstab is not enabled by BoardConfig/device.mk")

# An actual checkvintf run needs Android build tools + a complete assembled mount tree.
vintf_files = sorted((staged / "vendor/etc/vintf").rglob("*.xml"))
bad_xml = []
for file in vintf_files:
    try:
        ET.parse(file)
    except (ET.ParseError, OSError) as exc:
        bad_xml.append(file.name + ": " + str(exc))
check("FAIL" if bad_xml else "PASS", "staged VINTF XML syntax",
      f"{len(vintf_files)} checked; " + "; ".join(bad_xml[:6]))
if (product / "vendor/etc/vintf/manifest.xml").exists() and shutil.which("checkvintf"):
    check("UNVERIFIED", "full framework VINTF compatibility",
          "installed manifest and host checker visible; mount map/framework matrices require a separately validated invocation")
else:
    check("UNVERIFIED", "full framework VINTF compatibility",
          "assembled vendor+system+product+odm VINTF and framework matrices not proven present")

sepolicy_files = list(device.rglob("*.te")) + list(device.rglob("file_contexts")) + list(device.rglob("service_contexts"))
if sepolicy_files:
    check("UNVERIFIED", "device SELinux source", f"{len(sepolicy_files)} policy files found; compiler/neverallow validation needed")
else:
    check("WARN", "device SELinux source", "no device .te or contexts found; do not fabricate rules without stock type/domain evidence")
check("UNVERIFIED", "kernel module ABI and AVB", "stock image presence alone is insufficient; no flash test")
check("UNVERIFIED", "ROM build and device boot", "not attempted")

timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
report = pathlib.Path.home() / ("mist-boot-critical-gates-" + timestamp + ".txt")
body = ["Mist focused boot-critical integration gates", "Source: " + str(root),
        "UTC: " + timestamp, "Read-only: no git mutations, build or flash", ""]
body.extend(f"[{status}] {name}: {why}" for status, name, why in results)
summary = " / ".join(f"{sum(s == status for s, _, _ in results)} {status}"
                     for status in ("PASS", "FAIL", "WARN", "UNVERIFIED"))
body += ["", "SUMMARY: " + summary, "", "Referenced service executables:", *details]
report.write_text("\n".join(body) + "\n", encoding="utf-8")
print("Report:", report)
print("SUMMARY:", summary)
sys.exit(1 if any(s == "FAIL" for s, _, _ in results) else 0)
