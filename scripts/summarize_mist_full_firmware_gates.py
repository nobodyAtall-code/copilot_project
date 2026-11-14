#!/usr/bin/env python3
"""Summarize verifiable Mist full-firmware engineering gates without claiming boot readiness."""
import argparse
import json
from pathlib import Path

def read(path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--reports",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    root=args.reports
    avb=read(root/"mist-avb-stock-verification.json")
    ramdisk=read(root/"mist-vendor-ramdisk-review.json")
    super_layout=read(root/"lineage-super-layout.json")
    vintf=read(root/"mist-vintf-offline-report.json")
    inventory=read(root/"full-firmware-elf-ko-inventory.json")
    ramdisk_build=read(root/"MIST-VENDOR-BOOT-RESEARCH-REPORT.json")
    states={}
    states["stock_avb_signed_vbmeta"]={
        "status":"PASS" if avb and avb.get("original_vbmeta_rsa_signatures_verified") else "BLOCKED",
        "complete_descriptor_chain":avb.get("entire_stock_chain_verified") if avb else False,
        "top_level_verify_exit":avb.get("avbtool_results",{}).get("vbmeta.img",{}).get("verify_exit") if avb else None,
        "system_verify_exit":avb.get("avbtool_results",{}).get("vbmeta_system.img",{}).get("verify_exit") if avb else None,
    }
    states["stock_hashtree_complete"]={
        "status":"PASS" if avb and avb.get("entire_stock_chain_verified") else "BLOCKED",
        "scope":"Original stock images only; does not authenticate custom Lineage images",
    }
    states["review_ramdisk_fragment"]={
        "status":"PASS" if ramdisk and ramdisk.get("other_entries_metadata_content_order_identical") is True
                 and ramdisk.get("changed_cpio_paths")==["first_stage_ramdisk/fstab.default"] else "BLOCKED",
        "source_image_untouched": True,
        "safe_to_flash":False,
    }
    states["review_vendor_boot_v4_container"]={
        "status":"PASS" if ramdisk_build and all(ramdisk_build.get("checks",{}).values())
                 and not ramdisk_build.get("flash_permitted",True) else "BLOCKED",
        "avb_signed":False,
        "safe_to_flash":False,
    }
    states["lineage_source_super_geometry"]={
        "status":"PASS" if super_layout and super_layout.get("status")=="BOARD_LAYOUT_SOURCE_MATCH_ONLY" else "BLOCKED",
        "ota_payload_produced":False,"virtual_ab_snapshot_transition_verified":False,
    }
    states["hal_elf_inventory"]={
        "status":"PASS" if inventory and inventory.get("summary",{}).get("elfs",0)>=100 else "BLOCKED",
        "number_of_parsed_elfs":inventory.get("summary",{}).get("elfs",0) if inventory else 0,
        "all_runtime_dependencies_proven":False,
    }
    states["vintf_source_fragments"]={
        "status":"PASS" if vintf and not vintf.get("errors") and not vintf.get("duplicate_instances_within_selected_vendor_fragments") else "BLOCKED",
        "complete_merged_framework_device_manifest_proven":False,
        "sku_selected_on_device":False,
    }
    states["complete_merged_vintf"]={"status":"BLOCKED","why":"Requires produced target manifests and framework compatibility matrices with an actual check-vintf-all run; XML parse alone insufficient"}
    states["custom_avb_and_bootloader_trust"]={"status":"BLOCKED","why":"No proven bootloader trusted developer key, rollback state, custom image signing or physical boot"}
    states["virtual_ab_migration"]={"status":"BLOCKED","why":"No built target OTA payload, snapshots/COW/slot switch and on-device merge test"}
    result={
        "scope":"SHA-checked original stock firmware and production source trees",
        "gates":states,
        "all_release_gates_passed":all(x["status"]=="PASS" for x in states.values()),
        "flash_permitted":False,
        "full_rom_build_or_device_boot_proven":False,
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({n:r["status"] for n,r in states.items()},indent=2))
    print("Summary saved:",args.out)
if __name__=="__main__":
    main()
