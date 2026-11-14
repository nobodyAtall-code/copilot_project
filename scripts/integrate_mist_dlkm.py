#!/usr/bin/env python3
"""Install verified Mist stock DLKM files and exact PRODUCT_COPY_FILES mappings."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

PARTITIONS={"vendor_dlkm_a":("vendor_dlkm",268),"system_dlkm_a":("system_dlkm",192)}
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(4194304),b""):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    for name in ("source","manifest","kernel-repo","device-repo"):ap.add_argument("--"+name,required=True,type=Path)
    a=ap.parse_args()
    data=json.loads(a.manifest.read_text())
    if data.get("firmware")!="OS3.0.304.0.WPUMIXM" or data.get("verified_source_md5")!="c4450c4e168052ca9de1211306d3beff":raise ValueError("Wrong stock firmware")
    if set(data["partitions"])!=set(PARTITIONS):raise ValueError("Wrong DLKM partitions")
    mappings=[]
    for part,(destname,n) in PARTITIONS.items():
        p=data["partitions"][part]
        if p["module_count"]!=n or sum(x["type"]=="module" for x in p["files"])!=n:raise ValueError("Bad module count for "+part)
        if not p["load_lists"] or p.get("load_missing"):raise ValueError("Bad modules.load")
        paths=set()
        for entry in p["files"]:
            rel=Path(entry["path"])
            if rel.is_absolute() or ".." in rel.parts or len(rel.parts)<2 or rel.as_posix() in paths:raise ValueError("Unsafe module path "+str(rel))
            paths.add(rel.as_posix())
            source=a.source/part/rel
            if not source.is_file() or source.is_symlink():raise ValueError("Missing or symlinked stock file "+str(source))
            if source.stat().st_size!=entry["size"] or sha(source)!=entry["sha256"]:raise ValueError("Stock hash mismatch "+str(source))
            dest=a.kernel_repo/destname/rel
            if dest.exists():
                if dest.is_symlink() or sha(dest)!=entry["sha256"]:raise ValueError("Conflicting production file "+str(dest))
            else:
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source,dest)
            mappings.append((destname,rel.as_posix(),f"    device/xiaomi/mist-kernel/{destname}/{rel.as_posix()}:$(TARGET_COPY_OUT_{destname.upper()})/{rel.as_posix()}"))
        for load in p["load_lists"]:
            if load not in paths:raise ValueError("Missing load metadata "+load)
        print(f"{part}: verified {n} modules and {len(paths)} source files",flush=True)
    mk=a.device_repo/"device.mk"
    original=mk.read_text()
    marker="# BEGIN MIST_STOCK_DLKM_PRODUCT_COPY_FILES"
    if marker in original:raise ValueError("DLKM block already present; refusing automatic overwrite")
    mappings.sort()
    lines=[marker,"# Exact stock module payloads; runtime compatibility is not yet proven.","PRODUCT_COPY_FILES += \\"]
    only=[item[2] for item in mappings]
    lines.extend(line+(" \\" if i<len(only)-1 else "") for i,line in enumerate(only))
    lines.append("# END MIST_STOCK_DLKM_PRODUCT_COPY_FILES")
    mk.write_text(original.rstrip()+"\n\n"+"\n".join(lines)+"\n")
    print(f"Added {len(only)} original stock module and metadata install rules",flush=True)

if __name__=="__main__":main()
