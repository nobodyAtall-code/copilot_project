#!/usr/bin/env python3
"""Read-only Mist boot/ODM packaging preflight, WITHOUT any Android build or flash."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

EXPECTED={
 "vendor_boot.img":("f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb",100663296,b"VNDRBOOT"),
 "dtbo.img":("2030334cc0a778389732cc1e7d05d4cdf5d8c2c0ce6b281331128f2cfc847703",25165824,bytes.fromhex("d7b7ab1e")),
}
SKUS=("hcesim_dsds","hcesim_ssss","hcesimese_dsds","hcesimese_ssss","nonfc_dsds","nonfc_ssss")
def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for b in iter(lambda:stream.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def prop(name):
    try:
        p=subprocess.run(["adb","shell","getprop",name],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=7,text=True,check=True)
        v=p.stdout.strip()
        if len(v)<100 and re.fullmatch(r"[A-Za-z0-9_.-]*",v):return v
    except (FileNotFoundError,subprocess.CalledProcessError,subprocess.TimeoutExpired):pass
    return None
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path.home()/"android/lineage")
    ap.add_argument("--stock-adb",action="store_true",help="Read only non-identifying stock SKU property from authorized connected device")
    a=ap.parse_args()
    root=a.root.expanduser().resolve()
    d=root/"device/xiaomi/mist"
    v=root/"vendor/xiaomi/mist"
    prebuilt=root/"device/xiaomi/mist-kernel"
    board=(d/"BoardConfig.mk").read_text()
    product=(d/"device.mk").read_text()
    mk=(v/"mist-vendor.mk").read_text()
    checks={}
    errors=[]
    for file,(sha,size,magic) in EXPECTED.items():
        path=prebuilt/file
        if not path.is_file():checks[file]={"status":"MISSING"};errors.append("missing "+str(path));continue
        with path.open("rb") as stream:header=stream.read(len(magic))
        observed=digest(path)
        checks[file]={"bytes":path.stat().st_size,"sha256":observed,"matches_original_stock":observed==sha and path.stat().st_size==size and header==magic}
        if not checks[file]["matches_original_stock"]:errors.append("stock image SHA256/size/magic mismatch: "+file)
    board_vendor=re.search(r"(?m)^BOARD_PREBUILT_VENDOR_BOOTIMAGE\s*:=\s*device/xiaomi/mist-kernel/vendor_boot.img\s*$",board)
    board_dtbo=re.search(r"(?m)^BOARD_PREBUILT_DTBOIMAGE\s*:=\s*device/xiaomi/mist-kernel/dtbo.img\s*$",board)
    checks["stock_vendor_boot_selected"]=bool(board_vendor) and "PRODUCT_BUILD_VENDOR_BOOT_IMAGE := false" in product
    checks["stock_dtbo_selected"]=bool(board_dtbo)
    checks["unverified_stock_kernel_forced"]="TARGET_FORCE_PREBUILT_KERNEL := true" in board
    checks["all_six_sku_modules_selected"]=all("mist_odm_vintf_"+sku in mk for sku in SKUS)
    checks["all_six_stock_odm_files_exist"]=all((v/"proprietary/odm/etc/vintf"/("manifest_"+sku+".xml")).is_file() for sku in SKUS)
    for key in ("stock_vendor_boot_selected","stock_dtbo_selected","all_six_sku_modules_selected","all_six_stock_odm_files_exist"):
        if not checks[key]:errors.append("production source precondition failed: "+key)
    sku=prop("ro.boot.product.hardware.sku") if a.stock_adb else None
    report={
        "stock_image_checks":checks,
        "boot_hardware_sku":sku,
        "stock_adb_requested":a.stock_adb,
        "sku_matches_stock_manifest":sku in SKUS if sku else None,
        "sku_manifest_path":"/odm/etc/vintf/manifest_"+sku+".xml" if sku in SKUS else None,
        "source_errors":errors,
        "critical_open_blockers":[
            "Modified init_boot and dynamic partitions require a verified AVB signing/rollback plan and firmware-compatible image hashes.",
            "Original stock vendor_boot fstab references Xiaomi mi_ext; transition to seven-partition Lineage super and OTA is not verified.",
            "Full merged VINTF compatibility and actual enforcing device boot are unverified.",
        ],
        "safe_to_flash":False,
        "full_rom_build_required_for_this_preflight":False,
    }
    out=root/"mist-bootchain-preflight.json"
    out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,indent=2))
    print("Saved:",out)
    raise SystemExit(1 if errors or (a.stock_adb and sku not in SKUS) else 0)
if __name__=="__main__":main()
