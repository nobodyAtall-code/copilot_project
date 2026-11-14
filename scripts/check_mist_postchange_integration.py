#!/usr/bin/env python3
"""Mist read-only post-change integration check. Never builds or flashes."""
import datetime
import hashlib
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

root = pathlib.Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else pathlib.Path.home() / "android/lineage"
device = root / "device/xiaomi/mist"
vendor = root / "vendor/xiaomi/mist"
prebuilt = root / "device/xiaomi/mist-kernel"
checks = []
details = []

def record(name, status, note):
    checks.append((name, status, note))

def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

def run(args, cwd=None):
    try:
        p = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
        return p.returncode, p.stdout.strip()
    except Exception as exc:
        return -1, str(exc)

def required_file(path):
    present = path.is_file()
    record(str(path.relative_to(root)), "PASS" if present else "FAIL", "exists" if present else "missing")
    return present

for p in [device / "BoardConfig.mk", device / "device.mk", device / "lineage_mist.mk",
          vendor / "Android.bp", vendor / "mist-vendor.mk",
          prebuilt / "kernel", prebuilt / "vendor_boot.img", prebuilt / "dtbo.img"]:
    required_file(p)

lineage = read(device / "lineage_mist.mk") or ""
required_vendor = "$(call inherit-product, vendor/xiaomi/mist/mist-vendor.mk)"
optional_vendor = "$(call inherit-product-if-exists, vendor/xiaomi/mist/mist-vendor.mk)"
if required_vendor in lineage:
    inheritance_status, inheritance_note = "PASS", "required dependency enabled"
elif optional_vendor in lineage:
    inheritance_status, inheritance_note = "FAIL", "local checkout still uses optional vendor inheritance; sync device tree main"
else:
    inheritance_status, inheritance_note = "FAIL", "required vendor inheritance line not found"
record("required vendor inheritance", inheritance_status, inheritance_note)
details.append("Local vendor inheritance lines: " + repr([line.strip() for line in lineage.splitlines() if "mist-vendor.mk" in line]))
board = read(device / "BoardConfig.mk") or ""
record("stock kernel fallback", "PASS" if re.search(r"(?m)^TARGET_FORCE_PREBUILT_KERNEL\s*:=\s*true\s*$", board) else "WARN",
       "stock prebuilt retained" if "TARGET_FORCE_PREBUILT_KERNEL := true" in board else "not confirmed")
record("stock vendor_boot", "PASS" if "BOARD_PREBUILT_VENDOR_BOOTIMAGE :=" in board else "WARN", "configuration presence only")
record("stock dtbo", "PASS" if "BOARD_PREBUILT_DTBOIMAGE :=" in board else "WARN", "configuration presence only")

bp = read(vendor / "Android.bp") or ""
mk = read(vendor / "mist-vendor.mk") or ""
defined = set(re.findall(r'(?m)^\s*name:\s*"([^"]+)"', bp))
requested = set(re.findall(r'\bmist_[A-Za-z0-9_]+\b', re.sub(r'(?m)^\s*#.*$', '', mk)))
undefined = sorted(requested - defined)
record("vendor PRODUCT_PACKAGES declarations", "FAIL" if undefined else "PASS",
       "undefined: " + ", ".join(undefined) if undefined else str(len(requested)) + " Mist modules defined in Android.bp")
details.append("Requested Mist modules: " + ", ".join(sorted(requested)))

xml_root = vendor / "proprietary/vendor/etc/vintf"
xmls = sorted(xml_root.rglob("*.xml")) if xml_root.is_dir() else []
parse_fail = []
for path in xmls:
    try:
        ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        parse_fail.append(str(path.relative_to(vendor)) + ": " + str(exc))
record("staged VINTF XML parsing", "FAIL" if parse_fail else ("PASS" if xmls else "WARN"),
       str(len(xmls)) + " parsed; " + "; ".join(parse_fail[:8]))
record("device SELinux integration", "WARN", "requires evidence-backed rules and local sepolicy compiler; no assumed success")
record("on-device HAL/VINTF compatibility", "UNVERIFIED", "static source checks cannot prove service registration or boot")
record("full ROM and flash readiness", "UNVERIFIED", "not attempted by this script")

for repo in [device, vendor, root / "kernel/xiaomi/mist"]:
    if (repo / ".git").exists() or (repo / ".git").is_file():
        head_rc, head = run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo)
        branch_rc, branch = run(["git", "branch", "--show-current"], cwd=repo)
        details.append("git revision " + str(repo) + ": branch=" + (branch if branch_rc == 0 else "unknown")
                       + " HEAD=" + (head if head_rc == 0 else "unknown"))
        rc, output = run(["git", "status", "--short"], cwd=repo)
        details.append("git status " + str(repo) + " (exit=" + str(rc) + "):\n" + (output or "(clean)"))
    else:
        details.append("git checkout unavailable: " + str(repo))

timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
target = pathlib.Path.home() / ("mist-postchange-integration-" + timestamp + ".txt")
lines = ["Mist post-change read-only validation", "Root: " + str(root),
         "UTC: " + timestamp, "No ROM build or flashing performed", ""]
for name, status, note in checks:
    lines.append("[" + status + "] " + name + ": " + note)
lines.extend(["", "SUMMARY: " + " / ".join(str(sum(x[1] == status for x in checks)) + " " + status
              for status in ("PASS", "FAIL", "WARN", "UNVERIFIED")), "", *details])
target.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("Report:", target)
print(lines[-len(details)-2])
sys.exit(1 if any(x[1] == "FAIL" for x in checks) else 0)
