#!/usr/bin/env python3
"""Inspect actual target-files/OTA ZIP metadata for Mist virtual A/B migration.

Reads metadata only. No installation, lpunpack, payload extraction or flashing.
Metadata conformity is NOT a successful OTA or COW/snapshot merge test.
"""
import argparse,json,zipfile
from pathlib import Path
EXPECTED={"system","system_ext","product","vendor","odm","vendor_dlkm","system_dlkm"}
def properties(txt):
    result={}
    for line in txt.splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line:continue
        k,v=line.split("=",1);result[k.strip()]=v.strip()
    return result
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--zip",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    with zipfile.ZipFile(a.zip) as z:
        names=set(z.namelist())
        def read(name):
            if name not in names:return None
            return z.read(name).decode("utf-8","replace")
        misc=properties(read("META/misc_info.txt") or "")
        dyn=properties(read("META/dynamic_partitions_info.txt") or "")
        ab=read("META/ab_partitions.txt")
        abparts=set(ab.split()) if ab is not None else None
        payload="payload.bin" in names
        payload_magic=None
        if payload:
            with z.open("payload.bin") as f:payload_magic=f.read(4).hex()
    group=dyn.get("super_partition_groups")
    groups=set(group.split()) if group else set()
    partlist=set(dyn.get("dynamic_partition_list","").split())
    if not partlist:
        partlist=set(dyn.get("super_qti_dynamic_partitions_partition_list","").split())
    output={
      "archive":a.zip.name,
      "archive_type":"OTA" if payload else "TARGET_FILES_OR_OTHER",
      "virtual_ab_configuration":{k:v for k,v in misc.items() if "virtual_ab" in k.lower() or "ab_update" in k.lower()},
      "ab_partitions":sorted(abparts) if abparts is not None else None,
      "dynamic_partitions":sorted(partlist),
      "dynamic_groups":sorted(groups),
      "target_seven_logical_partitions_match":partlist==EXPECTED,
      "mi_ext_in_update_partition_list":bool(abparts and "mi_ext" in abparts),
      "mi_ext_in_new_dynamic_partition_list":"mi_ext" in partlist,
      "payload_present":payload,
      "payload_header_magic":payload_magic,
      "payload_header_valid_if_present":payload_magic=="43724155" if payload else None,
      "metadata_present":bool(misc) and bool(dyn) and abparts is not None,
      "source_slot_mi_ext_retention_covered":False,
      "on_device_virtual_ab_cow_snapshot_merge_verified":False,
      "on_device_boot_and_rollback_verified":False,
      "ota_migration_safe":False,
    }
    output["metadata_layout_consistent"]=bool(output["metadata_present"] and output["target_seven_logical_partitions_match"] and
        not output["mi_ext_in_update_partition_list"] and not output["mi_ext_in_new_dynamic_partition_list"] and
        (not payload or output["payload_header_valid_if_present"]))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"metadata_layout_consistent":output["metadata_layout_consistent"],
      "payload_present":payload,"device_snapshot_merge_verified":False},indent=2))
    print("Report:",a.out)
    if not output["metadata_layout_consistent"]:raise SystemExit(1)
if __name__=="__main__":main()
