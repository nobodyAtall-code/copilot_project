#!/usr/bin/env python3
"""Summarize mist stock configuration from the verified staged-audit artifact.

Research only. Outputs a bounded Markdown report and JSON inventory; does not
generate a proprietary-files.txt, modify device repos, or assert bootability.
"""
from __future__ import annotations
import collections
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path("input/staged-audit")
CONFIG = ROOT / "selected-stock-config"
OUTPUT = Path("research/generated")
OUTPUT.mkdir(parents=True, exist_ok=True)
MAX_FILE = 2_000_000

def read_stock_file(path: Path) -> str | None:
    if path.is_symlink() or not path.is_file():
        return None
    if path.stat().st_size > MAX_FILE:
        return None
    return path.read_text(encoding="utf-8", errors="replace")

def text_in(elem: ET.Element, name: str) -> str:
    found = elem.find(name)
    return (found.text or "").strip() if found is not None else ""

def review_xml(source: str, rel: str) -> dict:
    result = {"file": rel, "kind": "other", "hals": [], "error": None}
    try:
        root = ET.fromstring(source)
    except ET.ParseError as e:
        result["error"] = str(e)
        return result
    result["kind"] = root.tag
    if root.tag == "manifest":
        for hal in root.findall("hal"):
            name = text_in(hal, "name")
            if not name:
                continue
            record = {
                "name": name, "format": hal.get("format", ""),
                "versions": sorted(set(v.text.strip() for v in hal.findall("version") if v.text)),
                "fqnames": sorted(set(v.text.strip() for v in hal.findall("fqname") if v.text)),
                "instances": [],
            }
            for interface in hal.findall("interface"):
                iface = text_in(interface, "name")
                for instance in interface.findall("instance"):
                    if instance.text:
                        record["instances"].append(iface + "/" + instance.text.strip())
            result["hals"].append(record)
    return result

def iter_lines(contents: str):
    for raw in contents.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            yield line

def summarize_fstab(contents: str):
    entries = []
    for line in iter_lines(contents):
        parts = line.split()
        if len(parts) >= 4 and (parts[1].startswith("/") or parts[0].startswith("/")):
            entries.append({"device": parts[0], "mountpoint": parts[1],
                            "fs": parts[2], "mount_flags": parts[3],
                            "fs_mgr_flags": parts[4] if len(parts) > 4 else ""})
    return entries

def summarize_rc(contents: str):
    services = []
    imports = []
    for line in iter_lines(contents):
        if line.startswith("service "):
            parts = line.split()
            if len(parts) >= 3:
                services.append({"name": parts[1], "binary": parts[2]})
        elif line.startswith("import "):
            imports.append(line[7:].strip())
    return services, imports

audit_file = ROOT / "audit.json"
if not audit_file.is_file() or not CONFIG.is_dir():
    sys.exit("Missing audit.json or selected-stock-config; download artifact from run 43178657329")
audit = json.loads(audit_file.read_text())
if audit.get("members", 0) < 1000 or audit.get("selected_config_count", 0) < 50:
    sys.exit("Unexpected staged stock audit counts")

xml_records, fstab_records, rc_records, module_records = [], [], [], []
skipped = []
for p in sorted(CONFIG.rglob("*")):
    if not (p.is_file() or p.is_symlink()):
        continue
    rel = p.relative_to(CONFIG).as_posix()
    if p.is_symlink():
        skipped.append({"path": rel, "reason": "symlink"})
        continue
    content = read_stock_file(p)
    if content is None:
        skipped.append({"path": rel, "reason": "unreadable or oversized"})
        continue
    filename = p.name
    if filename.endswith(".xml") and "/vintf/" in ("/" + rel):
        xml_records.append(review_xml(content, rel))
    elif "fstab" in filename.lower():
        fstab_records.append({"file": rel, "entries": summarize_fstab(content)})
    elif filename.endswith(".rc") and "/init/" in ("/" + rel):
        services, imports = summarize_rc(content)
        rc_records.append({"file": rel, "services": services, "imports": imports})
    elif filename.startswith(("modules.load", "modules.dep", "modules.blocklist",
                               "modules.alias", "modules.softdep")):
        lines = list(iter_lines(content))
        module_records.append({"file": rel, "entry_count": len(lines),
                               "entries": lines[:500],
                               "truncated": len(lines) > 500})

hals = sorted(set(h["name"] for x in xml_records for h in x["hals"]))
services = sorted(set(s["name"] for x in rc_records for s in x["services"]))
all_mounts = sorted(set(e["mountpoint"] for x in fstab_records for e in x["entries"]))
report = {
    "source_run": 43178657329, "parent_firmware_run": 43174896778,
    "source_archive_sha256": audit.get("source_sha256"),
    "archive_members": audit.get("members"),
    "top_level_counts": audit.get("top_level_counts", {}),
    "boot_images": audit.get("boot_images", []),
    "selected_config_count": audit.get("selected_config_count"),
    "vintf_files": xml_records, "fstab_files": fstab_records,
    "init_files": rc_records, "module_metadata_files": module_records,
    "skipped": skipped,
}
(OUTPUT / "mist-stock-config.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
lines = [
    "# Mist stock VINTF / fstab / init / module audit",
    "",
    "**Research evidence only. Not a LineageOS device-tree validation or approved proprietary manifest.**",
    "",
    "- Source run: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43178657329",
    "- Firmware staging run: https://github.com/nobodyAtall-code/copilot_project/actions/runs/43174896778",
    f"- Stock source SHA256: `{audit.get('source_sha256', 'unknown')}`",
    f"- Archive members: {audit.get('members')}; selected config entries: {audit.get('selected_config_count')}",
    f"- Parsed VINTF XML: {len(xml_records)}; HAL names: {len(hals)}",
    f"- Fstab files: {len(fstab_records)}; mountpoints: {len(all_mounts)}",
    f"- Init .rc files: {len(rc_records)}; service names: {len(services)}",
    f"- Kernel module metadata files: {len(module_records)}",
    f"- Skipped symlinks/oversized config: {len(skipped)}",
    "",
    "## VINTF HAL names (stock declarations, not compatibility proof)",
    *[f"- `{n}`" for n in hals],
    "",
    "## Fstab mountpoints and filesystem types",
]
for rec in fstab_records:
    lines += [f"### `{rec['file']}`"]
    if not rec["entries"]:
        lines += ["No conventional fstab entries parsed."]
    else:
        for ent in rec["entries"]:
            lines.append(f"- `{ent['mountpoint']}` : `{ent['fs']}` ; `{ent['fs_mgr_flags']}`")
lines += ["", "## Stock init services (name and file only)"]
for rec in rc_records:
    if rec["services"]:
        lines.append(f"- `{rec['file']}`: " + ", ".join(s["name"] for s in rec["services"]))
lines += ["", "## Kernel module metadata files"]
for rec in module_records:
    lines.append(f"- `{rec['file']}`: {rec['entry_count']} non-comment lines")
lines += [
    "", "## Review gates",
    "- Compare stock HAL declarations against LineageOS 23.2 framework expectations.",
    "- Inspect and validate full fstab flags and AVB chains before any BoardConfig changes.",
    "- Match module loads, dependencies, and kernel release against the actual stock boot ramdisk.",
    "- Determine which proprietary binaries are truly needed; avoid copying stock packages wholesale.",
    "- No conclusions about successful boot, SELinux, radio, camera, NFC or fingerprint are made here.",
    "",
    "Detailed structured records: `mist-stock-config.json`.",
]
(OUTPUT / "mist-stock-config.md").write_text("\n".join(lines).replace("\`", "`") + "\n")
print(f"Report ready: {len(hals)} HAL names; {len(fstab_records)} fstab files; "
      f"{len(services)} services; {len(module_records)} module metadata files")
