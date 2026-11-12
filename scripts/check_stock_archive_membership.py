#!/usr/bin/env python3
"""Read-only membership gate for Mist stock source archive.

Research-only: no binary extraction, no production manifest, no publishing.
Input: verified stock-vendor-source.tar.zst + generated configuration JSON.
Output: review reports and confirmed PATH candidates (not approved blobs).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import posixpath
import subprocess

PARTITION_MAP = {"/vendor/": "vendor_a/", "/odm/": "odm_a/"}
SENSITIVE = (
    "persist/", "modemst", "calibration/", "metadata/", "userdata/",
    ".pem", ".pk8", ".key", "id_rsa", "/secrets/",
)

def safe_name(raw: str) -> str | None:
    name = raw.removeprefix("./").rstrip("/")
    if not name or name.startswith("/") or "\x00" in name:
        return None
    if any(p in ("", ".", "..") for p in name.split("/")):
        return None
    if not name.startswith(("vendor_a/", "odm_a/", "vendor_dlkm_a/", "system_dlkm_a/")):
        return None
    if any(x in name.lower() for x in SENSITIVE):
        return None
    return name

def to_stock_path(path: str) -> str | None:
    if not path.startswith("/"):
        return None
    for mount, prefix in PARTITION_MAP.items():
        if path.startswith(mount):
            return safe_name(prefix + path[len(mount):])
    return None

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    doc = json.loads(args.config.read_text())
    proc = subprocess.run(
        ["tar", "--use-compress-program=zstd", "--list", "--file", str(args.archive)],
        capture_output=True, text=True, check=True,
    )
    names = set()
    rejected = 0
    for raw in proc.stdout.splitlines():
        cleaned = safe_name(raw)
        if cleaned:
            names.add(cleaned)
        else:
            rejected += 1
    if len(names) < 1000:
        raise SystemExit("Aborting: unexpectedly small safe stock archive inventory")
    if len(names) != doc["archive_members"] and abs(len(names) - doc["archive_members"]) > 15:
        raise SystemExit("Aborting: stock archive inventory diverges from verified audit")

    services = []
    for item in doc["init_files"]:
        for service in item["services"]:
            executable = service["binary"]
            path = to_stock_path(executable)
            if path is None:
                continue
            services.append({
                "name": service["name"], "rc": item["file"],
                "executable": executable, "archive_path": path,
                "present": path in names,
            })

    configs = []
    for item in doc["vintf_files"]:
        if not item["hals"]:
            continue
        path = safe_name(item["file"])
        configs.append({
            "path": item["file"], "present": path in names if path else False,
            "hals": sorted({h["name"] for h in item["hals"]}),
        })

    module_checks = []
    for item in doc["module_metadata_files"]:
        if not item["file"].endswith("/modules.load"):
            continue
        partition = item["file"].split("/", 1)[0]
        prefix = partition + "/lib/modules/"
        inventory = {
            posixpath.basename(x) for x in names
            if x.startswith(prefix) and x.endswith(".ko")
        }
        entries = item["entries"]
        # flattened system_dlkm/flatten/lib/modules/modules.load uses another
        # storage layout; do not conflate it with vendor_dlkm paths.
        if partition == "system_dlkm_a":
            inventory = {
                posixpath.basename(x) for x in names
                if x.startswith("system_dlkm_a/") and x.endswith(".ko")
            }
        missing = sorted({posixpath.basename(x) for x in entries} - inventory)
        module_checks.append({
            "load_file": item["file"], "entry_count": item["entry_count"],
            "available_archive_ko_basename_count": len(inventory),
            "missing_basename_count": len(missing), "missing_basenames": missing,
            "truncated_input": item["truncated"],
        })

    args.out.mkdir(parents=True, exist_ok=True)
    result = {
        "source_archive_sha256": doc["source_archive_sha256"],
        "safe_archive_members": len(names), "rejected_archive_names": rejected,
        "service_executables": services, "vintf_configs": configs,
        "module_checks": module_checks,
        "approval": "NOT APPROVED: no ELF closure, module ABI or boot validation",
    }
    (args.out / "archive-membership.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    present_services = [s for s in services if s["present"]]
    absent_services = [s for s in services if not s["present"]]
    lines = [
        "# Mist stock archive membership gate", "",
        "**Evidence only; no proprietary manifest is approved by this check.**", "",
        f"- Safe archive member paths: {len(names)}",
        f"- Rejected/unsafe member names: {rejected}",
        f"- Vendor/ODM init service references: {len(services)}",
        f"- Present executable paths: {len(present_services)}",
        f"- Missing executable paths: {len(absent_services)}",
        f"- VINTF documents with HAL declarations: {len(configs)}",
        f"- Present such VINTF paths: {sum(c['present'] for c in configs)}",
        "", "## Missing referenced executables (requires case-by-case review)",
    ]
    lines += [
        f"- \`{s['executable']}\` referenced by \`{s['rc']}\`"
        for s in absent_services[:120]
    ] or ["- None in this class."]
    lines += ["", "## Module load membership (basename only; NOT ABI validation)"]
    for m in module_checks:
        lines.append(
            f"- \`{m['load_file']}\`: {m['entry_count']} load lines; "
            f"{m['missing_basename_count']} absent .ko basenames; "
            f"metadata truncated={m['truncated_input']}"
        )
    lines += [
        "", "## Required follow-up gates",
        "- Review archive file types, symlink targets, permissions and SHA256.",
        "- Trace each candidate binary and recursive ELF DT_NEEDED library closure.",
        "- Validate VINTF instance selection, SELinux, init and vendor/ODM paths.",
        "- Inspect boot/vendor_boot ramdisks, exact kernel release and module ABI.",
        "- Obtain authoritative lpdump group sizes before BoardConfig changes.",
        "- Publish only a manually approved curated manifest, never this inventory.",
    ]
    (args.out / "archive-membership.md").write_text("\n".join(lines) + "\n")
    print(
        f"Checked {len(names)} stock archive paths; "
        f"{len(present_services)} referenced service paths found; "
        f"{len(module_checks)} module load lists checked."
    )

if __name__ == "__main__":
    main()
