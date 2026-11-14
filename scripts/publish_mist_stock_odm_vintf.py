#!/usr/bin/env python3
"""Publish exact original Mist stock ODM SKU VINTF XMLs; never synthesize content."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

VARIANTS=(
    "hcesim_dsds",
    "hcesim_ssss",
    "hcesimese_dsds",
    "hcesimese_ssss",
    "nonfc_dsds",
    "nonfc_ssss",
)
def fail(m): raise SystemExit(m)
def hal_signature(source):
    root=ET.fromstring(source)
    if root.tag!="manifest" or root.attrib.get("type")!="device":fail("invalid device VINTF manifest")
    result=[]
    for h in root.findall("hal"):
        name=(h.findtext("name") or "").strip()
        fqs=sorted((fq.text or "").strip() for fq in h.findall("fqname"))
        vers=sorted((v.text or "").strip() for v in h.findall("version"))
        result.append((name,fqs,vers))
    return sorted(result)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stock-config",type=Path,required=True)
    ap.add_argument("--inventory",type=Path,required=True)
    ap.add_argument("--device",type=Path,required=True)
    ap.add_argument("--vendor",type=Path,required=True)
    a=ap.parse_args()
    stock=json.loads(a.inventory.read_text())
    records={p["file"]:p for p in stock["vintf_files"]}
    source_root=a.stock_config.resolve()
    source_files=[]
    digests={}
    for variant in VARIANTS:
        rel=f"odm_a/etc/vintf/manifest_{variant}.xml"
        source=source_root/rel
        if not source.is_file() or source.is_symlink():fail("Missing or symlink source: "+rel)
        data=source.read_bytes()
        if not (50<len(data)<1048576):fail("Invalid size "+rel)
        if rel not in records or records[rel].get("error"):fail("Inventory lacks "+rel)
        old=sorted((h["name"],sorted(h.get("fqnames",[])),sorted(h.get("versions",[]))) for h in records[rel]["hals"])
        new=hal_signature(data)
        if old!=new:fail("Stock inventory and exact XML mismatch: "+rel)
        radio=[fq for name,fqs,_ in new if name=="android.hardware.radio.data" for fq in fqs]
        expect=2 if variant.endswith("dsds") else 1
        if len(radio)!=expect or "IRadioData/slot1" not in radio:fail("Unexpected SIM slot set: "+rel)
        nfc=any(name=="android.hardware.nfc" for name,_,_ in new)
        if nfc == variant.startswith("nonfc"):fail("NFC variant mismatch: "+rel)
        sha=hashlib.sha256(data).hexdigest()
        dest=a.vendor/"proprietary/odm/etc/vintf"/source.name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=data:fail("Refusing overwrite mismatched production "+str(dest))
        dest.write_bytes(data)
        source_files.append((variant,source.name))
        digests[source.name]=sha
    bp=a.vendor/"Android.bp"
    mk=a.vendor/"mist-vendor.mk"
    manifest=a.device/"proprietary-files.txt"
    marker="// MIST_STOCK_ODM_SKU_VINTF_BATCH"
    b=bp.read_text()
    if marker not in b:
        lines=["",marker,"// Exact stock XML variants. libvintf selects by ro.boot.product.hardware.sku.","// device_specific installs to /odm/etc/vintf. No default/forced SKU.",""]
        for variant,filename in source_files:
            lines += ["prebuilt_etc {",f'    name: "mist_odm_vintf_{variant}",',f'    src: "proprietary/odm/etc/vintf/{filename}",',f'    filename: "{filename}",',"    device_specific: true,",'    sub_dir: "vintf",',"}",""]
        bp.write_text(b.rstrip()+"\n"+"\n".join(lines)+"\n")
    elif not all(f'mist_odm_vintf_{v}' in b for v in VARIANTS):fail("Partial existing ODM Soong section")
    make=mk.read_text()
    if "MIST_STOCK_ODM_SKU_VINTF_BATCH" not in make:
        mk.write_text(make.rstrip()+"\n\n# MIST_STOCK_ODM_SKU_VINTF_BATCH\n# All alternatives shipped; libvintf selects ONLY matching boot hardware SKU.\nPRODUCT_PACKAGES += \\\n"+ "".join("    mist_odm_vintf_"+v+(" \\\n" if i<5 else "\n") for i,v in enumerate(VARIANTS)))
    elif not all("mist_odm_vintf_"+v in make for v in VARIANTS):fail("Partial existing ODM PRODUCT_PACKAGES")
    m=manifest.read_text()
    if "# MIST_STOCK_ODM_SKU_VINTF_BATCH" not in m:
        manifest.write_text(m.rstrip()+"\n\n# MIST_STOCK_ODM_SKU_VINTF_BATCH — original SKU selector manifests, do not flatten to manifest.xml\n"+"".join("odm/etc/vintf/"+filename+"\n" for _,filename in source_files))
    elif not all("odm/etc/vintf/"+filename in m for _,filename in source_files):fail("Partial existing ODM extraction manifest")
    print(json.dumps({"status":"verified_original_stock_variants_staged","files":digests,"selection":"ro.boot.product.hardware.sku","runtime_sku_confirmed":False},indent=2))

if __name__=="__main__":main()
