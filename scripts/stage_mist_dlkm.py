#!/usr/bin/env python3
"""Verify and stage stock Mist DLKM module payloads without modifying production trees."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path("work/mounts")
REPORTS = Path("reports")
OUT = Path("output/mist-stock-dlkm")
REPORTS.mkdir(exist_ok=True, parents=True)
OUT.mkdir(exist_ok=True, parents=True)
SUMMARY = {}
for partition in ("vendor_dlkm_a", "system_dlkm_a"):
    source = ROOT / partition
    if not source.is_mount():
        raise RuntimeError(f"Not mounted: {source}")
    dest = OUT / partition
    dest.mkdir(parents=True, exist_ok=True)
    modules = sorted(p for p in source.rglob("*.ko") if p.is_file())
    if not modules:
        raise RuntimeError(f"No .ko modules in {partition}")
    metadata = sorted(p for p in source.rglob("*") if p.is_file() and (p.name.startswith("modules.") or p.name in ("modules.load", "modules.blocklist", "modules.options")))
    loads = [p for p in metadata if p.name == "modules.load" or p.name.startswith("modules.load.")]
    if not loads:
        raise RuntimeError(f"No modules.load file for {partition}")
    entries = []
    for p in sorted(set(modules + metadata)):
        rel = p.relative_to(source)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if p.is_symlink():
            # Preserve symlinks only when their resolved target is inside the source partition.
            resolved = p.resolve(strict=True)
            if not resolved.is_relative_to(source.resolve()):
                raise RuntimeError(f"Escaping symlink: {p}")
            target.symlink_to(os.readlink(p))
        else:
            shutil.copy2(p, target)
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        entries.append({"path":str(rel),"size":p.stat().st_size,"sha256":sha,"type":"module" if p.suffix==".ko" else "metadata"})
    basenames = {p.name for p in modules}
    missing = []
    for p in loads:
        for raw in p.read_text(errors="replace").splitlines():
            line = raw.strip().split("#",1)[0].strip()
            if not line: continue
            module = line.split()[0].rsplit("/",1)[-1]
            if module not in basenames:
                missing.append({"list":str(p.relative_to(source)),"module":line})
    if missing:
        raise RuntimeError(f"{partition} modules.load references missing modules: {missing[:20]}")
    SUMMARY[partition]={"module_count":len(modules),"load_lists":[str(p.relative_to(source)) for p in loads],"metadata_count":len(metadata),"files":entries,"load_missing":[]}
    print(f"{partition}: {len(modules)} modules, {len(loads)} load lists, {len(metadata)} metadata files",flush=True)
(REPORTS/"mist-dlkm-manifest.json").write_text(json.dumps({"firmware":"OS3.0.304.0.WPUMIXM","verified_source_md5":"c4450c4e168052ca9de1211306d3beff","partitions":SUMMARY,"runtime_abi_verified":False,"production_merged":False},indent=2)+"\n")
archive = REPORTS/"mist-stock-dlkm.tar.zst"
subprocess.run(["tar","-C",str(OUT),"--create","--use-compress-program=zstd -T0","--file",str(archive),"vendor_dlkm_a","system_dlkm_a"],check=True)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
(REPORTS/"mist-stock-dlkm.sha256").write_text(f"{digest}  {archive.name}\n")
print(f"Staged archive {archive} ({archive.stat().st_size} bytes), sha256 {digest}",flush=True)
