#!/usr/bin/env python3
"""Inspect extracted stock Mist DLKM modules; no production-tree writes."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path("work/stock-dlkm")
EXPECTED = {
    "vendor_dlkm_a": 268,
    "system_dlkm_a": 192,
}
summary = {}
for partition, count in EXPECTED.items():
    root = ROOT / partition
    modules = sorted(root.rglob("*.ko"))
    if len(modules) != count:
        raise RuntimeError(f"{partition}: expected {count} modules, got {len(modules)}")
    byname = collections.defaultdict(list)
    releases = collections.Counter()
    missing_modinfo = []
    invalid_elf = []
    for f in modules:
        byname[f.name].append(str(f.relative_to(root)))
        with f.open("rb") as fd:
            if fd.read(4) != b"\x7fELF":
                invalid_elf.append(str(f.relative_to(root)))
                continue
        proc = subprocess.run(["modinfo", "-F", "vermagic", str(f)], text=True, capture_output=True)
        if proc.returncode:
            missing_modinfo.append({"file":str(f.relative_to(root)),"error":proc.stderr.strip()[:200]})
        else:
            releases[proc.stdout.strip()] += 1
    dependency_missing = []
    dep_lines = 0
    for depfile in sorted(root.rglob("modules.dep")):
        for line in depfile.read_text(errors="replace").splitlines():
            if ":" not in line: continue
            dep_lines += 1
            left, right = line.split(":",1)
            for item in (left.split()+right.split()):
                if item.rsplit("/",1)[-1] not in byname:
                    dependency_missing.append({"source":str(depfile.relative_to(root)),"entry":item})
    duplicate_names = {k:v for k,v in byname.items() if len(v)>1}
    summary[partition] = {
        "module_count":len(modules),
        "vermagic_counts":dict(releases),
        "invalid_elf":invalid_elf,
        "modinfo_failures":missing_modinfo,
        "dependency_records":dep_lines,
        "missing_dep_basenames":dependency_missing,
        "duplicate_basenames":duplicate_names,
        "module_load_files":[str(p.relative_to(root)) for p in sorted(root.rglob("modules.load*"))],
        "metadata_files":[str(p.relative_to(root)) for p in sorted(root.rglob("modules.*"))],
    }
    print(partition, json.dumps({k:v for k,v in summary[partition].items() if k in ("module_count","vermagic_counts","dependency_records","missing_dep_basenames","invalid_elf")},indent=2),flush=True)
Path("reports").mkdir(exist_ok=True)
Path("reports/mist-stock-dlkm-abi-audit.json").write_text(json.dumps({"firmware":"OS3.0.304.0.WPUMIXM","source_run":43587815827,"partitions":summary,"boot_runtime_verified":False,"production_integrated":False},indent=2)+"\n")
if any(v["invalid_elf"] or v["modinfo_failures"] or v["missing_dep_basenames"] for v in summary.values()):
    raise SystemExit("Stock module integrity/dependency validation reported errors; inspect JSON artifact")
