#!/usr/bin/env python3
"""Offline audit of Mist stock shared library install-rule collisions.

Reads generated Kati rules; does not build, delete or modify anything.
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--installs", type=Path, default=Path("out/soong/installs-lineage_mist.mk"))
    parser.add_argument("--bp", type=Path, default=Path("vendor/xiaomi/mist/Android.bp"))
    args=parser.parse_args()
    if not args.installs.is_file() or not args.bp.is_file():
        parser.error("run from LineageOS checkout after one generated Kati build")
    bp=args.bp.read_text()
    block_re=re.compile(r'cc_prebuilt_library_shared\s*\{(.*?)^\}', re.S|re.M)
    modules=[]
    for match in block_re.finditer(bp):
        block=match.group(1)
        def field(name):
            m=re.search(r'^\s*'+name+r':\s*"([^"]+)"',block,re.M)
            return m.group(1) if m else None
        module=field("name")
        stem=field("stem") or module
        rel=field("relative_install_path")
        if module is None or stem is None:
            continue
        base="out/target/product/mist/vendor/lib64/"
        dest=base+(rel+"/" if rel else "")+stem+".so"
        modules.append((module,dest))
    if not modules:
        parser.error("no cc_prebuilt_library_shared modules discovered")
    interesting={d for _,d in modules}
    rules=defaultdict(list)
    for lineno,line in enumerate(args.installs.open(),1):
        if not line.startswith("out/target/product/mist/vendor/lib64/"):
            continue
        path,sep,after=line.partition(":")
        if sep and path in interesting and not (" " in path or "\t" in path):
            rules[path].append((lineno,after.strip()[:360]))
    collisions=0
    missing=0
    for mod,dest in modules:
        entries=rules[dest]
        print("\n"+("COLLISION" if len(entries)>1 else "ONE_RULE" if entries else "NO_RULE"),
              mod, "=>",dest, f"({len(entries)} rules)")
        if len(entries)>1: collisions+=1
        if not entries: missing+=1
        for line_no,source in entries:
            print(f"  line {line_no}: {source}")
    print(f"\nSUMMARY inspected={len(modules)} collided={collisions} absent={missing}")
    print("NOTE: install-rule presence does not prove module selection, nor runtime ABI compatibility.")
    print("NOTE: do not remove KeyMint libraries simply because they share output paths with Android AIDL modules.")

if __name__=="__main__":
    main()
