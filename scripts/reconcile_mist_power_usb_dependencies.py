#!/usr/bin/env python3
"""Reconcile audited Mist Power/USB stock ELF dependencies with production trees.

No automatic copying: stock archive presence is not a runtime linker or platform ABI guarantee.
"""
import argparse
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--vendor-bp",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    report=json.loads(a.report.read_text())
    if report.get("approved_for_full_rom_build") is not False:
        raise SystemExit("unexpected report approval state")
    seeds=report.get("seeds",[])
    expected={"vendor_a/bin/hw/android.hardware.power-service","vendor_a/bin/hw/android.hardware.usb-service.qti"}
    if {s.get("seed") for s in seeds}!=expected:
        raise SystemExit("wrong ELF report seeds")
    installed={s.strip().split(":",1)[0] for s in a.manifest.read_text().splitlines()
               if s.strip().startswith(("vendor/","odm/"))}
    bp=a.vendor_bp.read_text()
    merged={}
    unresolved={}
    for seed in seeds:
        for record in seed.get("stock_resolved_dependencies",[]):
            path=record["path"]
            if not path.startswith(("vendor_a/","odm_a/")) or ".." in path.split("/"):
                raise SystemExit("unsafe dependency path: "+path)
            dest=path.replace("vendor_a/","vendor/",1).replace("odm_a/","odm/",1)
            item=merged.setdefault(dest,{"stock_paths":[],"parents":set()})
            item["stock_paths"].append(path)
            item["parents"].update(record["required_by"])
        for entry in seed.get("unresolved_sonames",[]):
            n=entry["soname"]
            unresolved.setdefault(n,set()).update(entry["required_by"])
    rows=[]
    for path,item in sorted(merged.items()):
        rows.append({"runtime_path":path,"source_paths":sorted(set(item["stock_paths"])),
                     "already_in_proprietary_files":path in installed,
                     "referenced_in_vendor_android_bp":('proprietary/'+path) in bp,
                     "required_by":sorted(item["parents"]),
                     "classification":"existing_vendor_file" if path in installed else "review_for_platform_conflict_and_ABI"})
    output={
        "source":"Actions run 43527718972 stock Power/USB closure report",
        "vendor_dependency_paths":len(rows),
        "already_listed":sum(x["already_in_proprietary_files"] for x in rows),
        "not_yet_listed":sum(not x["already_in_proprietary_files"] for x in rows),
        "review_candidates":rows,
        "unresolved_sonames":[{"soname":k,"required_by":sorted(v)} for k,v in sorted(unresolved.items())],
        "automatic_installation_approved":False,
        "reason":"Need platform/APEX namespace and Soong duplicate-install checks, plus dlopen/SELinux review"
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print("Stock resolved paths:",len(rows),
          "already in device manifest:",output["already_listed"],
          "review candidates:",output["not_yet_listed"],
          "unresolved distinct SONAMEs:",len(unresolved))

if __name__=="__main__":
    main()
