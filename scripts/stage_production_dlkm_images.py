#!/usr/bin/env python3
"""Stage exact published Mist DLKM PRODUCT_COPY_FILES into standalone image roots."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

START = "# BEGIN MIST_STOCK_DLKM_PRODUCT_COPY_FILES"
END = "# END MIST_STOCK_DLKM_PRODUCT_COPY_FILES"
DEST = {"TARGET_COPY_OUT_SYSTEM_DLKM":"system_dlkm","TARGET_COPY_OUT_VENDOR_DLKM":"vendor_dlkm"}
EXPECTED = {"system_dlkm":192,"vendor_dlkm":268}

def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as src:
        for chunk in iter(lambda:src.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--device",required=True,type=Path)
    p.add_argument("--prebuilts",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    text=(args.device/"device.mk").read_text()
    assert text.count(START)==text.count(END)==1,"Missing or duplicate DLKM block"
    block=text.split(START,1)[1].split(END,1)[0]
    entries=[]
    seen=set()
    for raw in block.splitlines():
        line=raw.strip().rstrip("\\").strip()
        if not line or line.startswith("#") or line.startswith("PRODUCT_COPY_FILES"):continue
        m=re.fullmatch(r"device/xiaomi/mist-kernel/(system_dlkm|vendor_dlkm)/([^:\s]+):\$\((TARGET_COPY_OUT_SYSTEM_DLKM|TARGET_COPY_OUT_VENDOR_DLKM)\)/([^:\s]+)",line)
        if not m:raise RuntimeError("Unexpected copy rule: "+line)
        source_partition,source_rel,var,dest_rel=m.groups()
        dest_partition=DEST[var]
        if source_partition!=dest_partition or source_rel!=dest_rel:raise RuntimeError("Unexpected partition/path mapping: "+line)
        relative=Path(source_rel)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] not in ("lib","flatten"):raise RuntimeError("Unsafe or unexpected module path: "+source_rel)
        key=(dest_partition,dest_rel)
        if key in seen:raise RuntimeError("Duplicate installed DLKM destination: "+repr(key))
        seen.add(key)
        source=args.prebuilts/source_partition/relative
        if not source.is_file() or source.is_symlink():raise RuntimeError("Missing/unsafe production source: "+str(source))
        dest=args.out/dest_partition/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,dest)
        entries.append({"partition":dest_partition,"path":dest_rel,"sha256":digest(source),"size":source.stat().st_size,"module":source.suffix==".ko"})
    summary={}
    for partition,expected in EXPECTED.items():
        found=[entry for entry in entries if entry["partition"]==partition]
        modules=[entry for entry in found if entry["module"]]
        if len(modules)!=expected:raise RuntimeError(f"{partition}: {len(modules)} .ko files, expected {expected}")
        loads=[entry["path"] for entry in found if Path(entry["path"]).name.startswith("modules.load")]
        if not loads:raise RuntimeError("No modules.load for "+partition)
        summary[partition]={"modules":len(modules),"total_files":len(found),"load_lists":loads}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"staging-manifest.json").write_text(json.dumps({"source":"production main at workflow checkout","summary":summary,"entries":entries},indent=2)+"\n")
    for name,item in summary.items():print(f"{name}: {item['modules']} modules, {item['total_files']} total files, loads={item['load_lists']}")
if __name__=="__main__":main()
