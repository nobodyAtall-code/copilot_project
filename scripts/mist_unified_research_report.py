#!/usr/bin/env python3
"""Combine already-validated mist stock artifacts and current tree preflight.

This is an evidence inventory, not an Android build, lpdump, or OTA simulator.
All inputs are explicit; missing/stale evidence is reported, never assumed.
"""
import argparse
import json
from pathlib import Path

def load(path):
    if not path or not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return None

def main():
    p=argparse.ArgumentParser()
    for field in ("super","groups","sizes","boot","preflight"):
        p.add_argument("--"+field,type=Path,required=True)
    p.add_argument("--boot-deep",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--markdown",type=Path,required=True)
    a=p.parse_args()
    super_data,groups,sizes,boot,preflight=[load(getattr(a,k)) for k in ("super","groups","sizes","boot","preflight")]
    deep=load(a.boot_deep)
    gates={}
    gates["stock_lp_primary_backup_checksum"]=bool(super_data and super_data.get("integrity_checks_passed"))
    gates["go_python_group_parity"]=bool(groups and groups.get("groups_match"))
    gates["go_python_partition_size_parity"]=bool(sizes and sizes.get("partition_sizes_match"))
    gates["stock_boot_structural_report_present"]=boot is not None
    gates["stock_avb_dtbo_fdt_metadata_structure"]=bool(deep and deep.get("stock_metadata_structures_valid"))
    gates["production_preflight_report_present"]=preflight is not None
    # These require separate authoritative/build/device evidence and are
    # deliberately never inferred from the third-party Go reader.
    for name in ("official_aosp_lpdump","ota_virtual_ab_snapshot_safe",
                 "mi_ext_ota_handling","avb_signature_chain_rollback_verified",
                 "vintf_sepolicy_runtime_compatible","elf_dependency_closure",
                 "lineage_23_2_full_build","physical_boot_and_hardware"):
        gates[name]=False
    slots=super_data.get("slots",[]) if super_data else []
    source=(slots[0].get("primary",{}).get("data",{}) if slots else {})
    groups_list=source.get("groups",[])
    partitions=source.get("partitions",[])
    relevant=["default","qti_dynamic_partitions_a","qti_dynamic_partitions_b"]
    group_info=[dict(name=g.get("name"),maximum_size=g.get("maximum_size"),
                     allocated_bytes=g.get("allocated_bytes"),partitions=g.get("partitions"))
                for g in groups_list]
    report={
      "scope":"offline read-only cross-artifact research, not flashing or ROM build",
      "stock_super_source_run":43268799416,
      "stock_boot_source_run":43266837030,
      "deeper_stock_boot_metadata": deep,
      "gates":gates,
      "stock_metadata_slot_count":len(slots),
      "groups":group_info,
      "populated_partitions":[dict(name=x.get("name"),size=x.get("size"),group=x.get("group"))
                              for x in partitions if x.get("size",0)>0],
      "verified_stock_group_name_set":sorted(g.get("name") for g in groups_list),
      "expected_known_group_names":relevant,
      "mi_ext_in_stock":any(x.get("name","").startswith("mi_ext") for x in partitions),
      "unresolved":[
       "Official Android 16 AOSP lpdump comparison is not present in evidence",
       "Stock group maxima are per A/B group and must not be summed as physical super size",
       "Virtual A/B snapshot budget and mi_ext OTA inclusion cannot be deduced from LP group tables",
       "Actual AVB descriptors/chains/signatures and device-side rollback state unverified",
       "Stock DTB/DTBO applicability, kernel module load order and vendor ramdisk semantics unverified",
       "HAL/ELF/VINTF/SELinux closure and Android 16 bring-up are unverified",
       "No LineageOS full build, flash, boot or hardware test"
      ],
      "raw_source_reports_available":{k:v is not None for k,v in
         (("super",super_data),("groups",groups),("sizes",sizes),
          ("boot",boot),("deep_boot",deep),("preflight",preflight))}
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    lines=["# Redmi Note 17 5G (mist) — unified offline ROM research",
           "","> Read-only evidence summary. This is **not** a successful ROM build, OTA test or flashability claim.",
           "","## Gates"]
    for k,v in gates.items():
        lines.append(f"- {'PASS' if v else 'UNVERIFIED'} — `{k}`")
    lines+=["","## Verified stock LP groups","",
            "| Group | Maximum bytes | Allocated bytes | Partition members |",
            "|---|---:|---:|---|"]
    for g in group_info:
        lines.append(f"| `{g['name']}` | {g['maximum_size']} | {g['allocated_bytes']} | {', '.join(g['partitions'] or [])} |")
    lines+=["","## Research still required"]
    lines.extend("- "+v for v in report["unresolved"])
    lines+=["","## Original evidence",
            "- [Independent LP metadata run 43268799416](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43268799416)",
            "- [Boot-chain structural run 43266837030](https://github.com/nobodyAtall-code/copilot_project/actions/runs/43266837030)",
            "","All output is bounded JSON/text; no stock binary images are uploaded."]
    a.markdown.parent.mkdir(parents=True,exist_ok=True)
    a.markdown.write_text("\n".join(lines)+"\n")
    print(json.dumps({"verified_offline_gates":sum(gates.values()),
                      "total_gates":len(gates),"stock_groups":group_info},indent=2))
    required=("stock_avb_dtbo_fdt_metadata_structure","stock_lp_primary_backup_checksum","go_python_group_parity",
              "go_python_partition_size_parity","production_preflight_report_present")
    if not all(gates[k] for k in required):
        raise SystemExit("Required previously verified evidence or current preflight report missing")

if __name__=="__main__":
    main()
