#!/usr/bin/env python3
"""Read-only Mist stock boot modules and fstab comparison. No auto-installation."""
import argparse
import collections
import json
import subprocess
import tarfile
from pathlib import Path

ROOTS=("vendor_dlkm_a/","system_dlkm_a/","vendor_a/","odm_a/")
def parse_fstab(lines):
    entries={}
    for line in lines:
        parts=line.split()
        if len(parts)>=5:
            entries.setdefault(parts[1],[]).append({"source":parts[0],"fstype":parts[2],"flags":parts[4]})
    return entries

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ramdisk-audit",type=Path,required=True)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--device-fstab",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    src=json.loads(a.ramdisk_audit.read_text())
    if src.get("bootable_verified") is not False or not src.get("ramdisks"):
        raise SystemExit("Unexpected or missing stock ramdisk audit provenance")
    files={f["path"]:f for r in src["ramdisks"] for f in r["interesting_files"]}
    expected={"first_stage_ramdisk/fstab.default","first_stage_ramdisk/fstab.emmc",
              "lib/modules/modules.load","lib/modules/modules.load.recovery"}
    if not expected.issubset(files):
        raise SystemExit("Required stock ramdisk metadata absent")
    stock_entries={}
    for key in sorted(expected):
        if key.startswith("first_stage_ramdisk/"):
            stock_entries[key]=parse_fstab(files[key]["mount_entries"])
    device_entries=parse_fstab(line.strip() for line in a.device_fstab.read_text().splitlines()
                               if line.strip() and not line.lstrip().startswith("#"))
    stock_paths={key:sorted(set(x)) for key,x in stock_entries.items()}
    candidates={}
    for k in ("lib/modules/modules.load","lib/modules/modules.load.recovery"):
        listed=files[k]["module_load_order"]
        candidates[k]={"count":len(listed),"unique":len(set(listed)),
                       "duplicates":sorted(x for x,n in collections.Counter(listed).items() if n>1),
                       "order":listed}
    names=set(candidates["lib/modules/modules.load"]["order"])|set(candidates["lib/modules/modules.load.recovery"]["order"])
    if any("/" in n or n in ("",".","..") or not n.endswith(".ko") for n in names):
        raise SystemExit("Unexpected module name in stock modules.load")
    located=collections.defaultdict(list)
    proc=subprocess.Popen(["zstd","-dc","--",str(a.archive)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout,mode="r|") as tar:
            for mem in tar:
                path=mem.name.removeprefix("./")
                if not path.startswith(ROOTS) or not mem.isfile() or ".." in path.split("/"):
                    continue
                name=path.rsplit("/",1)[-1]
                if name in names:
                    located[name].append(path)
    finally:
        if proc.stdout: proc.stdout.close()
        rc=proc.wait()
    if rc: raise SystemExit("stock zstd stream failed")
    result={
        "source_run":43540094714,
        "source_boot_archive_run":43174896778,
        "stock_fstab_mountpoints":stock_paths,
        "device_staged_fstab_mountpoints":sorted(device_entries),
        "missing_from_device_staged_fstab":{
           k:sorted(set(entry)-set(device_entries)) for k,entry in stock_entries.items()},
        "extra_in_device_staged_fstab":{
           k:sorted(set(device_entries)-set(entry)) for k,entry in stock_entries.items()},
        "normal_module_count":candidates["lib/modules/modules.load"]["count"],
        "recovery_module_count":candidates["lib/modules/modules.load.recovery"]["count"],
        "normal_module_duplicates":candidates["lib/modules/modules.load"]["duplicates"],
        "recovery_module_duplicates":candidates["lib/modules/modules.load.recovery"]["duplicates"],
        "modules_unique_total":len(names),
        "modules_found_in_archived_stock_source":sum(name in located for name in names),
        "modules_missing_from_archived_stock_source":sorted(name for name in names if name not in located),
        "modules_with_multiple_locations":{n:paths for n,paths in sorted(located.items()) if len(paths)>1},
        "module_archive_paths":{n:sorted(paths) for n,paths in sorted(located.items())},
        "bootable_verified":False,
        "approved_for_production_wiring":False,
        "limitations":["Archive missing a module does not prove original vendor_boot lacks it.",
                       "Kernel compatibility, AVB, SELinux and init behavior require separate validation.",
                       "No proprietary module binaries are published by this audit."] }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("fstab source paths:",{k:len(v) for k,v in stock_paths.items()})
    print("normal module entries:",result["normal_module_count"],
          "recovery entries:",result["recovery_module_count"])
    print("unique module names:",len(names),"found in archive:",result["modules_found_in_archived_stock_source"],
          "not found in archive:",len(result["modules_missing_from_archived_stock_source"]))
    print("missing staged fstab mounts:",{k:len(v) for k,v in result["missing_from_device_staged_fstab"].items()})

if __name__=="__main__":
    main()
