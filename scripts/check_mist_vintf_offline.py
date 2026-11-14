#!/usr/bin/env python3
"""Mist targeted, offline VINTF source check. No Soong or Ninja invocation."""
import argparse
import json
import re
from pathlib import Path
from collections import defaultdict
import subprocess
from xml.etree import ElementTree as ET

def hal_instances(path):
    root=ET.parse(path).getroot()
    if root.tag != "manifest":
        raise ValueError("not a manifest")
    entries=[]
    for hal in root.findall("hal"):
        name=(hal.findtext("name") or "").strip()
        fmt=hal.attrib.get("format","hidl")
        versions=[x.text.strip() for x in hal.findall("version") if x.text]
        for f in hal.findall("fqname"):
            value=(f.text or "").strip()
            entries.append((name,fmt,value))
        for interface in hal.findall("interface"):
            iname=(interface.findtext("name") or "").strip()
            for inst in interface.findall("instance"):
                instance=(inst.text or "").strip()
                for version in (versions or ["unspecified"]):
                    entries.append((name,fmt,version+"::"+iname+"/"+instance))
    return entries

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path.home()/"android/lineage")
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    root=a.root.expanduser().resolve()
    vendor=root/"vendor/xiaomi/mist"
    device=root/"device/xiaomi/mist"
    mk=(vendor/"mist-vendor.mk").read_text()
    bp=(vendor/"Android.bp").read_text()
    selected=set(re.findall(r"\bmist_[A-Za-z0-9_]+\b",mk))
    declarations={}
    for match in re.finditer(r"(?m)^(?:prebuilt_etc|cc_prebuilt_binary|cc_prebuilt_library_shared|sh_binary)\s*\{(.*?)^\}",bp,re.S|re.M):
        body=match.group(1)
        n=re.search(r'\bname:\s*"([^"]+)"',body)
        s=re.search(r'\b(?:src|srcs):\s*\[?\s*"([^"]+)"',body)
        if n and s:
            declarations[n.group(1)]=s.group(1)
    sources=sorted({declarations[n] for n in selected if n in declarations and "/vintf/" in declarations[n] and declarations[n].endswith(".xml")})
    # Exactly one original ODM manifest is loaded at runtime based on
    # ro.boot.product.hardware.sku. Comparing all six alternatives together
    # fabricates duplicates in radio and NFC declarations.
    entries=defaultdict(list)
    sku_prefix="proprietary/odm/etc/vintf/manifest_"
    sku_sources=sorted(src for src in sources if src.startswith(sku_prefix))
    shared_sources=sorted(set(sources)-set(sku_sources))
    errors=[]
    def git_head(directory):
        run=subprocess.run(["git","-C",str(directory),"rev-parse","HEAD"],capture_output=True,text=True)
        return run.stdout.strip() if run.returncode==0 else None
    device_head=git_head(device)
    vendor_head=git_head(vendor)
    required_selected={
        "mist_hal_android_hardware_gatekeeper_service_qti_xml",
        "mist_hal_qseecom_1_0_service_vintf",
        "mist_stock_radio_config_vintf",
    }
    missing_selected=sorted(required_selected-selected)
    for name in missing_selected:
        errors.append("Missing required VINTF PRODUCT_PACKAGES entry: "+name)
    missing_declared=sorted(name for name in selected if name not in declarations)
    if missing_declared:
        errors.append("Selected modules missing parsed source declaration: "+", ".join(missing_declared))
    variants={}
    for sku_path in sku_sources:
        sku=Path(sku_path).stem.removeprefix("manifest_")
        per_variant=defaultdict(list)
        for src in shared_sources+[sku_path]:
            try:
                for ident in hal_instances(vendor/src):
                    per_variant["|".join(ident)].append(src)
            except (ET.ParseError,OSError,ValueError) as e:
                errors.append(f"{src}: {e}")
        duplicates={key:paths for key,paths in per_variant.items() if len(paths)>1}
        variants[sku]={"source":sku_path,
                       "hal_instance_count":len(per_variant),
                       "duplicate_instances":duplicates}
        for name,paths in per_variant.items():
            for src in paths:
                if src not in entries[name]:entries[name].append(src)
    if not sku_sources:
        errors.append("No ODM SKU VINTF manifest variants selected")
    duplicates={f"{sku}: {k}":v for sku,rec in variants.items()
                for k,v in rec["duplicate_instances"].items()}
    radio=[{"instance":k,"sources":v} for k,v in entries.items()
           if "radio" in k.lower()]
    # Capture local framework matrices as evidence of availability, not as a
    # fabricated full compatibility claim (merged device VINTF is not built).
    matrix_paths=sorted(str(p.relative_to(root)) for base in ("hardware/interfaces","device/xiaomi/mist","vendor/xiaomi/mist") if (root/base).exists() for p in (root/base).rglob("*compatibility_matrix*.xml") if p.is_file())
    result={
      "mode":"source_only_no_build",
      "device_tree_head":device_head,
      "vendor_tree_head":vendor_head,
      "required_selected_vintf_modules_missing":missing_selected,
      "device_tree_present":(device/"BoardConfig.mk").is_file(),
      "selected_vintf_fragments":sources,
      "selected_vintf_fragment_count":len(sources),
      "hal_instances":dict(entries),
      "duplicate_instances_within_selected_vendor_fragments":duplicates,
      "odm_sku_variants_checked_independently":variants,
      "sku_runtime_selection_verified":False,
      "radio_instances":radio,
      "odm_sku_variant_selected":any("/odm/" in src and "/manifest" in src for src in sources),
      "framework_matrix_candidates":matrix_paths[:60],
      "errors":errors,
      "not_verified":["complete merged framework/device compatibility","runtime HAL registration","SKU-specific ODM radio manifest","AVB/boot-chain"],
    }
    out=a.output or root/"mist-vintf-offline-report.json"
    out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:result[k] for k in ("mode","vendor_tree_head","required_selected_vintf_modules_missing","selected_vintf_fragment_count","duplicate_instances_within_selected_vendor_fragments","radio_instances","odm_sku_variant_selected","errors")},indent=2))
    print("Report:",out)
    if errors or duplicates:raise SystemExit(1)

if __name__=="__main__":
    main()
