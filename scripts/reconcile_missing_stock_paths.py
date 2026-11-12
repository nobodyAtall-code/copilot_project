#!/usr/bin/env python3
"""Research-only reconciliation of missing stock service and VINTF paths.

Produces suggestions for human review, never a blob manifest or a runtime claim.
All inputs are retained in copilot_project.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from difflib import get_close_matches
import json
from pathlib import PurePosixPath, Path
import subprocess

PREFIXES = ("vendor_a/", "odm_a/", "system_dlkm_a/", "vendor_dlkm_a/")
SENSITIVE = ("persist/", "modemst", "calibration/", "metadata/", "userdata/",
             ".pem", ".pk8", ".key", "id_rsa", "/secrets/")
MAX_MATCHES = 12


def accepted(raw: str) -> str | None:
    raw = raw.removeprefix("./").rstrip("/")
    if not raw.startswith(PREFIXES) or raw.startswith("/"):
        return None
    if any(part in ("", ".", "..") for part in raw.split("/")):
        return None
    if any(term in raw.lower() for term in SENSITIVE):
        return None
    return raw


def tar_members(archive: Path) -> set[str]:
    proc = subprocess.run(
        ["tar", "--use-compress-program=zstd", "--list", "--file", str(archive)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
    )
    return {clean for raw in proc.stdout.splitlines()
            if (clean := accepted(raw))}


def alternatives(wanted: str, paths: set[str],
                 basename_index: dict[str, list[str]]) -> dict:
    basename = PurePosixPath(wanted).name
    exact_basename = sorted(x for x in basename_index.get(basename, [])
                            if x != wanted)
    wanted_dir = str(PurePosixPath(wanted).parent)
    siblings = sorted(x for x in paths
                      if str(PurePosixPath(x).parent) == wanted_dir)
    closest_names = get_close_matches(basename,
                                      [PurePosixPath(x).name for x in siblings],
                                      n=MAX_MATCHES, cutoff=0.46)
    # Listing filenames is deliberately not equivalent to ELF/ABI matching.
    fuzzy = sorted(x for x in siblings if PurePosixPath(x).name in closest_names
                   and x not in exact_basename and x != wanted)
    return {
        "requested_path": wanted,
        "exact_path_present": wanted in paths,
        "same_basename_elsewhere": exact_basename[:MAX_MATCHES],
        "nearby_names_same_directory": fuzzy[:MAX_MATCHES],
        "candidates_prove_compatibility": False,
    }


def main() -> None:
    arg = argparse.ArgumentParser()
    arg.add_argument("--archive", type=Path, required=True)
    arg.add_argument("--membership", type=Path, required=True)
    arg.add_argument("--out", type=Path, required=True)
    args = arg.parse_args()

    membership = json.loads(args.membership.read_text())
    paths = tar_members(args.archive)
    if len(paths) < 4000:
        raise SystemExit("Archive membership inventory unexpectedly small")

    index: dict[str, list[str]] = defaultdict(list)
    for name in sorted(paths):
        index[PurePosixPath(name).name].append(name)
    service_missing = [s for s in membership["service_executables"]
                       if not s["present"]]
    missing_unique = sorted({s["archive_path"] for s in service_missing})
    manifest_missing = [m for m in membership["vintf_configs"]
                        if not m["present"]]
    references = [
        {"kind": "init_executable", "path": path,
         "declared_by": sorted({s["rc"] for s in service_missing
                                if s["archive_path"] == path}),
         **alternatives(path, paths, index)}
        for path in missing_unique
    ]
    references += [
        {"kind": "vintf_manifest", "path": m["path"],
         "declares_hals": m["hals"],
         **alternatives(m["path"], paths, index)}
        for m in manifest_missing
    ]

    # Examine how much of the KeyMint service's surrounding configuration
    # is actually present. This is only an indexed path search.
    security_paths = sorted(x for x in paths
                            if any(token in x.lower()
                                   for token in ("keymint", "keymaster",
                                                 "secureclock", "sharedsecret")))
    rc_by_filename = sorted(x for x in paths if x.endswith(".rc")
                            and any(token in x.lower() for token in
                                    ("keymint", "keymaster")))
    findings = {
        "archive_members_in_scope": len(paths),
        "original_missing_service_references": len(service_missing),
        "missing_unique_executable_paths": len(missing_unique),
        "original_missing_vintf_paths": len(manifest_missing),
        "references": references,
        "security_related_archive_paths": security_paths,
        "security_related_rc_paths": rc_by_filename,
        "approval": "RESEARCH ONLY: path matches do not establish HAL registration, "
                    "boot readiness, ELF closure, or device SKU selection",
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "mist-missing-path-review.json").write_text(
        json.dumps(findings, indent=2, sort_keys=True) + "\n"
    )
    lines = [
        "# Mist missing service / KeyMint path review",
        "",
        "**Research only. No production blobs approved by filename matching.**",
        "",
        "- Source: successful stock archive membership gate run 43184532913",
        f"- Archived safe paths: {len(paths)}",
        f"- Absent init executable references: {len(service_missing)}",
        f"- Unique absent executable paths: {len(missing_unique)}",
        f"- Missing stock VINTF paths: {len(manifest_missing)}",
        f"- Security-related stock filenames: {len(security_paths)}",
        "",
        "## Missing references and stock-path alternatives",
        "",
    ]
    for rec in references:
        lines += [
            f"### {rec['kind']}: {rec['path']}",
            "- Exact path present: " + str(rec["exact_path_present"]),
            "- Same basename elsewhere: " + (
                ", ".join(rec["same_basename_elsewhere"]) or "none"),
            "- Similar file names in same directory: " + (
                ", ".join(rec["nearby_names_same_directory"]) or "none"),
        ]
        if rec["kind"] == "vintf_manifest":
            lines.append("- HAL declarations: " + ", ".join(rec["declares_hals"]))
        lines.append("")
    lines += ["## Stock KeyMint / Keymaster-related paths", ""]
    lines += ["- " + name for name in security_paths]
    lines += [
        "", "## Interpretation and next checks",
        "",
        "- A missing stock RC executable may be an optional upstream placeholder, "
        "a different partition path, or an actually absent binary; investigate.",
        "- Stock VINTF declarations can vary by device SKU or init-time "
        "manifest fragments. Confirm the active runtime manifest.",
        "- Inspect symlink types/targets, source file modes and sha256, "
        "then recursive DT_NEEDED dependency closure before a proprietary manifest.",
        "- Compare the KeyMint executable, its VINTF service registration, "
        "security policy and library dependencies. Missing one listed XML "
        "path does not prove the KeyMint HAL itself is absent.",
        "- Do not publish all stock binaries or unreviewed Qualcomm/Xiaomi services.",
        "",
        "Detailed records: mist-missing-path-review.json",
    ]
    (args.out / "mist-missing-path-review.md").write_text(
        "\n".join(lines) + "\n"
    )
    print(
        f"Reviewed {len(service_missing)} missing service references, "
        f"{len(missing_unique)} unique executable paths and "
        f"{len(manifest_missing)} VINTF paths"
    )


if __name__ == "__main__":
    main()
