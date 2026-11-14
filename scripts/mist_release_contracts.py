#!/usr/bin/env python3
"""Mist source-only VINTF, AVB and virtual A/B contract audit. Never declares OTA safe."""
import argparse,json,re,xml.etree.ElementTree as ET
from pathlib import Path
PARTS={"system","system_ext","product","vendor","odm","vendor_dlkm","system_dlkm"}
def var(text,name):
    text=re.sub(r"\\\s*\n"," ",text)
    m=re.search(r"(?m)^\s*"+re.escape(name)+r"\s*:?=\s*([^\n]*)",text)
    return m.group(1).strip() if m else None
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    root=a.root.resolve(); device=root/"device/xiaomi/mist"
    board=(device/"BoardConfig.mk").read_text()
    product=(device/"device.mk").read_text()
    parts=set((var(board,"BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST") or "").split())
    ota={
       "physical_super_size_matches_stock":var(board,"BOARD_SUPER_PARTITION_SIZE")=="10200547328",
       "group_size_matches_stock":var(board,"BOARD_QTI_DYNAMIC_PARTITIONS_SIZE")=="10190061568",
       "lineage_seven_partitions_match":parts==PARTS,
       "stock_mi_ext_omitted_in_target": "mi_ext" not in parts,
       "virtual_ab_vendor_ramdisk_product_inherited":"virtual_ab_ota/launch_with_vendor_ramdisk.mk" in product,
       "stock_vendor_boot_prebuilt":bool(var(board,"BOARD_PREBUILT_VENDOR_BOOTIMAGE")),
       "vendor_boot_rebuild_disabled":var(product,"PRODUCT_BUILD_VENDOR_BOOT_IMAGE")=="false",
       "mi_ext_first_stage_and_overlay_runtime_migrated":False,
       "real_target_ota_payload_and_postinstall_tested":False,
       "virtual_ab_snapshots_cow_and_slot_merge_tested":False,
       "ota_migration_safe":False,
    }
    matrices=[];parse_errors=[]
    for base in (root/"hardware/interfaces/compatibility_matrices",root/"system/libvintf",device):
        if not base.is_dir():continue
        for path in sorted(base.rglob("*compatibility_matrix*.xml")):
            try:
                e=ET.parse(path).getroot()
                matrices.append({"path":str(path.relative_to(root)),"tag":e.tag,"type":e.get("type"),"level":e.get("level")})
            except ET.ParseError as exc:parse_errors.append({"path":str(path.relative_to(root)),"error":str(exc)})
    framework=[x for x in matrices if x["tag"]=="compatibility-matrix" and x["type"]=="framework"]
    vintf={
        "framework_matrix_source_candidates":framework,
        "xml_parsing_errors":parse_errors,
        "source_only":True,
        "target_generated_framework_and_device_manifest_tested":False,
        "fcms_checked_by_libvintf":False,
        "complete_merged_framework_device_vintf_compatible":False,
    }
    avb={
        "original_stock_chain_verified_prior_run":True,
        "stock_vendor_boot_prebuilt_used":ota["stock_vendor_boot_prebuilt"],
        "custom_vendor_boot_standalone_signature_is_top_level_chain":False,
        "trusted_custom_root_vbmeta_and_rollback_verified":False,
        "custom_vendor_boot_flash_permitted":False,
    }
    result={"scope":"SOURCE_GEOMETRY_AND_FCM_DISCOVERY_NOT_FULL_RELEASE",
        "vintf":vintf,"avb":avb,"virtual_ab":ota,
        "boot_verified":False,"flash_permitted":False}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"framework_fcm_source_candidates":len(framework),
        "source_matrix_xml_parse_errors":len(parse_errors),
        "lineage_super_geometry_source_matches":ota["physical_super_size_matches_stock"] and ota["group_size_matches_stock"] and ota["lineage_seven_partitions_match"],
        "custom_avb_flash_permitted":False,"virtual_ab_ota_migration_safe":False},indent=2))
    print("Report:",a.out)
if __name__=="__main__":main()
