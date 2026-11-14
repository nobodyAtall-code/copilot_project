#!/usr/bin/env python3
"""Read-only, bounded Xiaomi Mist stock ramdisk and production tree inventory.

Does not repack images, copy private partition files, verify signatures, or flash.
"""
import argparse
import gzip
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

from inspect_mist_boot_chain import android_boot, vendor_boot

MAX_RAMDISK = 160 * 1024 * 1024
MAX_FILES = 30000
MAX_FILE = MAX_RAMDISK  # Members can be much larger than 4 MiB; still bounded by decoded archive.
WATCH = re.compile(r"(^|/)(fstab[^/]*|modules\.(load|options|blocklist)[^/]*|[^/]*\.rc|[^/]*\.avbpubkey)$")
SAFE_LINES = re.compile(r"(first_stage_mount|fileencryption|metadata_encryption|avb=|avb_keys=|slotselect|logical|overlay|mount_all|insmod|modprobe|modules\.load|vendor\.power|keymint|qsee|ueventd)", re.I)

def read_region(path, offset, size):
    if size < 0 or size > MAX_RAMDISK:
        raise ValueError("ramdisk too large")
    with path.open("rb") as f:
        f.seek(offset)
        block = f.read(size)
    if len(block) != size:
        raise ValueError("truncated ramdisk region")
    return block

def decode(data):
    if data.startswith(b"\x02\x21\x4c\x18") or data.startswith(b"\x04\x22\x4d\x18"):
        r = subprocess.run(["lz4","-dc"], input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=45)
        if r.returncode:
            raise ValueError("lz4 failed: " + r.stderr.decode(errors="replace")[-300:])
        result = r.stdout
    elif data.startswith(b"\x1f\x8b"):
        result = gzip.decompress(data)
    elif data.startswith(b"070701") or data.startswith(b"070702"):
        result = data
    else:
        raise ValueError("unknown ramdisk compression")
    if len(result) > MAX_RAMDISK:
        raise ValueError("unpacked ramdisk exceeds bounded limit")
    return result

def parse_cpio(data):
    off=0
    count=0
    while off+110 <= len(data):
        magic=data[off:off+6]
        if magic not in (b"070701",b"070702"):
            if data[off:].strip(b"\x00") == b"":
                return
            raise ValueError("unexpected CPIO magic at offset "+str(off))
        header=data[off+6:off+110]
        try:
            fields=[int(header[i:i+8],16) for i in range(0,104,8)]
        except ValueError as e:
            raise ValueError("invalid CPIO header") from e
        mode=fields[1]; size=fields[6]; namesize=fields[11]
        if namesize<1 or namesize>8192 or size>MAX_FILE:
            raise ValueError(f"CPIO member bounds exceeded: offset={off}, namesize={namesize}, filesize={size}, limit={MAX_FILE}")
        name_start=off+110
        name_end=name_start+namesize
        if name_end>len(data) or data[name_end-1]!=0:
            raise ValueError("truncated CPIO name")
        raw=data[name_start:name_end-1]
        name=raw.decode("utf-8",errors="replace")
        data_start=(name_end+3)&~3
        data_end=data_start+size
        if data_end>len(data):
            raise ValueError("truncated CPIO member")
        if name=="TRAILER!!!":
            return
        if name.startswith("/") or ".." in name.split("/"):
            raise ValueError("unsafe CPIO path")
        count+=1
        if count>MAX_FILES:
            raise ValueError("CPIO entry count exceeded")
        content=(data[data_start:data_end] if WATCH.search(name) and (mode & 0o170000)==0o100000 else b"")
        yield name,mode,content
        off=(data_end+3)&~3

def inventory(label, blob):
    extracted=decode(blob)
    items=list(parse_cpio(extracted))
    files=[]
    for name,mode,contents in items:
        if not WATCH.search(name):
            continue
        record={"path":name,"bytes":len(contents),
                "sha256":hashlib.sha256(contents).hexdigest(),
                "type":"regular" if (mode & 0o170000)==0o100000 else "other"}
        if name.rsplit("/",1)[-1].startswith("fstab") and contents:
            lines=contents.decode(errors="replace").splitlines()
            record["mount_entries"]=[line.strip()[:400] for line in lines
                if line.strip() and not line.lstrip().startswith("#")][:70]
        elif "modules.load" in name and contents:
            record["module_load_order"]=[line.strip() for line in
                contents.decode(errors="replace").splitlines()
                if line.strip() and not line.lstrip().startswith("#")][:500]
        elif name.endswith(".rc") and contents:
            record["relevant_init_lines"]=[line.strip()[:240] for line in
                contents.decode(errors="replace").splitlines()
                if SAFE_LINES.search(line)][:35]
        files.append(record)
    return {"fragment":label,"unpacked_bytes":len(extracted),
            "cpio_entry_count":len(items),"interesting_files":files}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--images-dir",required=True,type=Path)
    ap.add_argument("--device-dir",required=True,type=Path)
    ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args()
    stock_vendor=args.images_dir/"vendor_boot.img"
    init=args.images_dir/"init_boot.img"
    device=args.device_dir
    if not stock_vendor.is_file() or not init.is_file():
        ap.error("missing verified stock image")
    report={"purpose":"Offline stock-vs-production init/ramdisk inventory",
            "bootable_verified":False,"safe_to_flash":False,
            "ramdisks":[],"production":{},"warnings":[]}
    h=vendor_boot(stock_vendor,stock_vendor.stat().st_size)
    if h.get("header_version")!=4 or not h.get("ramdisk_table_entries"):
        raise SystemExit("unexpected vendor_boot layout or no ramdisk fragments")
    for frag in h["ramdisk_table_entries"]:
        chunk=read_region(stock_vendor,h["vendor_ramdisk_offset"]+frag["offset"],frag["size"])
        report["ramdisks"].append(inventory("vendor_boot:"+frag["name"],chunk))
    ih=android_boot(init,init.stat().st_size)
    if ih["ramdisk_size"]<=0:
        raise SystemExit("stock init_boot has no ramdisk")
    report["ramdisks"].append(inventory("init_boot",
        read_region(init,ih["ramdisk_offset"],ih["ramdisk_size"])))
    fstab=device/"rootdir/etc/fstab.mist"
    board=device/"BoardConfig.mk"
    mk=device/"device.mk"
    for src in [fstab,board,mk]:
        if not src.exists():
            raise SystemExit("missing production source "+str(src))
        report["production"][src.relative_to(device).as_posix()]={
            "sha256":hashlib.sha256(src.read_bytes()).hexdigest(),
            "bytes":src.stat().st_size}
    fstab_names=[x["path"] for r in report["ramdisks"] for x in r["interesting_files"]
                 if x["path"].rsplit("/",1)[-1].startswith("fstab")]
    report["stock_fstab_paths"]=sorted(set(fstab_names))
    report["production_fstab_staged_not_installed"]=(
        "PRODUCT_COPY_FILES" not in mk.read_text() or
        "rootdir/etc/fstab.mist" not in mk.read_text())
    report["warnings"]=[
        "Filesystem paths and module names are structural evidence only.",
        "Do not install fstab or module lists without validating AVB keys, first-stage mount, SELinux and kernel ABI.",
        "Runtime boot, AVB signature validity and recovery have not been tested."
    ]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("stock fragments:",len(report["ramdisks"]))
    for r in report["ramdisks"]:
        print(r["fragment"],"CPIO members",r["cpio_entry_count"],
              "config files",len(r["interesting_files"]))
    print("fstab paths:",report["stock_fstab_paths"])
    print("production fstab staged, not installed:",report["production_fstab_staged_not_installed"])

if __name__=="__main__":
    main()
