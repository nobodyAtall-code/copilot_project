#!/usr/bin/env python3
"""Reconcile stock vendor_boot embedded kernel modules against archive closure JSON."""
import argparse
import collections
import json
from pathlib import Path
from inspect_mist_boot_chain import vendor_boot
from audit_mist_stock_ramdisks import read_region,decode,parse_cpio

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--vendor-boot",type=Path,required=True)
    ap.add_argument("--closure",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    closure=json.loads(a.closure.read_text())
    missing=set(closure["modules_missing_from_archived_stock_source"])
    archive=set(closure["module_archive_paths"])
    if len(missing)!=106 or not closure.get("bootable_verified") is False:
        raise SystemExit("unexpected prior closure provenance/counts")
    h=vendor_boot(a.vendor_boot,a.vendor_boot.stat().st_size)
    if h["header_version"]!=4:
        raise SystemExit("vendor_boot v4 expected")
    present=collections.defaultdict(list)
    fragments=[]
    for f in h["ramdisk_table_entries"]:
        data=read_region(a.vendor_boot,h["vendor_ramdisk_offset"]+f["offset"],f["size"])
        items=list(parse_cpio(decode(data)))
        found=0
        for name,mode,_ in items:
            if name.endswith(".ko"):
                present[Path(name).name].append({"fragment":f["name"],"path":name})
                found+=1
        fragments.append({"fragment":f["name"],"embedded_ko_paths":found})
    resolved=sorted(missing & set(present))
    unresolved=sorted(missing-set(present))
    both=sorted(archive & set(present))
    result={"source_closure_run":43540343960,"source_boot_image_run":43174896778,
            "vendor_boot_fragments":fragments,
            "archive_missing_names":len(missing),
            "resolved_by_vendor_boot":len(resolved),
            "resolved_module_names":resolved,
            "still_unresolved_names":unresolved,
            "also_in_vendor_archive":both,
            "embedded_module_paths":dict(sorted(present.items())),
            "bootable_verified":False,
            "approved_for_production_wiring":False,
            "limitations":["Module name presence alone does not verify vermagic, signature, dependencies, load order or firmware compatibility.",
                           "Never copy/repack stock vendor_boot until AVB and ramdisk table semantics are validated."]}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("vendor_boot fragments:",fragments)
    print("106 archive-unmatched modules resolved inside vendor_boot:",len(resolved))
    print("Still unresolved:",len(unresolved))
    print("Also in vendor archive:",len(both))
if __name__=="__main__":
    main()
