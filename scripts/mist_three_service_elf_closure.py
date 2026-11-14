#!/usr/bin/env python3
"""One-pass archive-local ELF closure for Mist RIL, audio and fingerprint.

Consumes a precomputed graph from inspect_stock_elf_metadata.py and compares
the actual staged stock fingerprint RC/VINTF interface declarations.
No linker namespace, Soong build, or device boot claim is made.
"""
import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path
from xml.etree import ElementTree as ET

SEEDS = {
    "radio": "vendor_a/bin/hw/qcrilNrd",
    "audio": "vendor_a/bin/hw/audiohalservice.qti",
    "fingerprint": "vendor_a/bin/hw/android.hardware.biometrics.fingerprint-service.odm",
}
PLATFORM_CANDIDATES = {
    "libc.so", "libdl.so", "libm.so", "liblog.so", "libbinder_ndk.so",
    "libbase.so", "libc++.so", "libutils.so", "libcutils.so",
    "libvndksupport.so", "libapexsupport.so",
}

def closure(seed, nodes):
    if seed not in nodes or "dependencies" not in nodes[seed]:
        raise RuntimeError("Seed missing from static ELF graph: " + seed)
    queue = deque([seed])
    visited = set()
    stock_paths = defaultdict(set)
    unresolved = defaultdict(set)
    while queue:
        path = queue.popleft()
        if path in visited:
            continue
        visited.add(path)
        node = nodes.get(path)
        if not node or "dependencies" not in node:
            raise RuntimeError("Incomplete ELF dependency graph at " + path)
        for dep in node["dependencies"]:
            soname = dep["soname"]
            match = dep.get("matched_path")
            if match:
                stock_paths[match].add(path)
                if match not in visited:
                    queue.append(match)
            else:
                unresolved[soname].add(path)
    return {
        "seed": seed,
        "recursive_elf_nodes": len(visited),
        "archive_resolved_dependency_paths": [
            {"path": k, "required_by": sorted(v)} for k, v in sorted(stock_paths.items())
        ],
        "unresolved_archive_sonames": [
            {"soname": k, "candidate_platform_apex": k in PLATFORM_CANDIDATES,
             "required_by": sorted(v)} for k, v in sorted(unresolved.items())
        ],
        "archive_local_elf_graph_complete": True,
    }

def check_fingerprint(staged):
    rc = (staged / "proprietary/vendor/etc/init/fingerprint-odm.rc").read_text()
    xml = ET.parse(staged / "proprietary/vendor/etc/vintf/manifest/fingerprint-odm.xml")
    names = set()
    for hal in xml.findall("hal"):
        if hal.findtext("name") != "android.hardware.biometrics.fingerprint":
            continue
        for fq in hal.findall("fqname"):
            names.add(fq.text or "")
    rc_interfaces = set(re.findall(
        r"^\s*interface\s+aidl\s+android\.hardware\.biometrics\.fingerprint\.(\S+)",
        rc, re.M
    ))
    expected = {f"android.hardware.biometrics.fingerprint.{n}" for n in names}
    return {
        "declared_rc_interfaces": sorted(rc_interfaces),
        "declared_vintf_instances": sorted(names),
        "registration_consistent": bool(rc_interfaces) and rc_interfaces == expected,
        "blocks_publication": rc_interfaces != expected or not rc_interfaces,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--graph", required=True, type=Path)
    p.add_argument("--staged", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    source = json.loads(args.graph.read_text())
    nodes = {x["path"]: x for x in source["dependency_graph"]}
    results = {kind: closure(seed, nodes) for kind, seed in SEEDS.items()}
    fingerprint = check_fingerprint(args.staged)
    report = {
        "firmware": "OS3.0.304.0.WPUMIXM",
        "results": results,
        "fingerprint_registration": fingerprint,
        "publishable_as_complete_vendor_hal": False,
        "caveats": [
            "Stock-only static dependency traversal; framework/APEX modules not verified",
            "No linker namespace / dynamic dlopen / ABI / SELinux / device boot validation",
            "Stock-resolved file is not necessarily required as a stock copy when platform owns path",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for kind, row in results.items():
        print(kind, "ELFs", row["recursive_elf_nodes"],
              "stock paths", len(row["archive_resolved_dependency_paths"]),
              "unresolved SONAMEs", len(row["unresolved_archive_sonames"]))
    print("Fingerprint RC/VINTF consistent:", fingerprint["registration_consistent"])
    if fingerprint["blocks_publication"]:
        print("BLOCKED: Fingerprint stock init RC and VINTF have different service instances.")
    print("Report:", args.out)

if __name__ == "__main__":
    main()
