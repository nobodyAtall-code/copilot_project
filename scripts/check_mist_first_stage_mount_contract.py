#!/usr/bin/env python3
"""Read-only Mist staged-fstab versus actual stock ramdisk boot contract.

Never replaces, edits, repacks or flashes the stock vendor_boot image.
"""
import argparse
import json
import pathlib

DYNAMIC={"system","system_ext","product","vendor","odm","vendor_dlkm","system_dlkm"}
def entries(lines):
    return [l.split() for l in lines if l.strip() and not l.lstrip().startswith("#") and len(l.split())>=5]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--device",type=pathlib.Path,required=True)
    p.add_argument("--stock-ramdisk-report",type=pathlib.Path,required=True)
    p.add_argument("--out",type=pathlib.Path,required=True)
    a=p.parse_args()
    report=json.loads(a.stock_ramdisk_report.read_text())
    stock={}
    for fragment in report["ramdisks"]:
        if fragment["fragment"].startswith("vendor_boot"):
            for f in fragment["interesting_files"]:
                if f["path"] in ("first_stage_ramdisk/fstab.default","first_stage_ramdisk/fstab.emmc"):
                    stock[f["path"]]=f["mount_entries"]
    assert len(stock)==2, "Both stock fstab alternatives required"
    staged_path=a.device/"rootdir/etc/fstab.mist"
    staged=entries(staged_path.read_text().splitlines())
    src=a.device/"device.mk"
    board=a.device/"BoardConfig.mk"
    device_text=src.read_text()
    board_text=board.read_text()
    staged_names={x[0] for x in staged if x[0] in DYNAMIC}
    assert staged_names==DYNAMIC, "Staged fstab missing a managed partition"
    assert all(x[0]!="mi_ext" and "/mi_ext" not in x[1] for x in staged), "Staged fstab still contains mi_ext"
    assert all(any(x[0]==part and x[2]=="erofs" for x in staged) for part in DYNAMIC), "Missing expected EROFS mounts"
    assert "PRODUCT_BUILD_VENDOR_BOOT_IMAGE := false" in device_text
    assert "BOARD_PREBUILT_VENDOR_BOOTIMAGE :=" in board_text
    output={"stock_fragments":{},"staged_fstab":{
        "path":"rootdir/etc/fstab.mist",
        "mount_entries":len(staged),
        "dynamic_mounts":sorted(staged_names),
        "mi_ext_mounts":0,
        "installed":False,
    },"boot_policy":{
        "uses_original_stock_vendor_boot":True,
        "custom_first_stage_fstab_installed":False,
        "stock_vendor_boot_with_mi_ext_references_remains_boot_input":True
    },"required_next_steps":[
        "Determine runtime fstab.default versus fstab.emmc selection from bootconfig/init",
        "Inspect original vendor/etc init references and bind/overlay behavior",
        "Construct and test custom first-stage ramdisk or preserve compatible stock mount plan",
        "Validate AVB, VINTF, SELinux, OTA metadata and slot switch before flash"
    ]}
    for name,lines in stock.items():
        all_entries=entries(lines)
        mi=[l for l in lines if "mi_ext" in l and not l.lstrip().startswith("#")]
        overlays=[l for l in lines if l.startswith("overlay ")]
        output["stock_fragments"][name]={
            "mount_entries":len(all_entries),
            "mi_ext_referencing_lines":len(mi),
            "overlay_entries":len(overlays),
            "dynamic_partition_mounts":sorted({e[0] for e in all_entries if e[0] in DYNAMIC})
        }
    assert output["stock_fragments"]["first_stage_ramdisk/fstab.default"]["mi_ext_referencing_lines"]>=20
    assert output["stock_fragments"]["first_stage_ramdisk/fstab.emmc"]["mi_ext_referencing_lines"]==0
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print(json.dumps(output,indent=2,sort_keys=True))
if __name__=="__main__":
    main()
