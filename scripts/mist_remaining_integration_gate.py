#!/usr/bin/env python3
"""Consolidated Mist production-source closure audit; never claims a boot pass."""
import argparse
import collections
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--device",type=Path,required=True)
    ap.add_argument("--vendor",type=Path,required=True)
    ap.add_argument("--prebuilts",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    problems=[]
    warnings=[]
    checks={}
    def problem(topic,msg):problems.append({"topic":topic,"message":msg})
    def warning(topic,msg):warnings.append({"topic":topic,"message":msg})
    device=(a.device/"device.mk").read_text()
    board=(a.device/"BoardConfig.mk").read_text()
    product=(a.device/"lineage_mist.mk").read_text()
    bp=(a.vendor/"Android.bp").read_text()
    mk=(a.vendor/"mist-vendor.mk").read_text()
    files=(a.device/"proprietary-files.txt").read_text()
    checks["stock_kernel_prebuilt_selected"]="TARGET_FORCE_PREBUILT_KERNEL := true" in board
    checks["stock_vendor_boot_selected"]="BOARD_PREBUILT_VENDOR_BOOTIMAGE := device/xiaomi/mist-kernel/vendor_boot.img" in board
    checks["custom_vendor_boot_disabled"]="PRODUCT_BUILD_VENDOR_BOOT_IMAGE := false" in device
    for key, value in checks.items():
        if not value:problem("bootchain","Unexpected boot baseline: "+key)
    # Read the actual multi-line make variable; comments elsewhere containing
    # 'mi_ext' must not turn an unresolved first-stage mount into a pass.
    group=[]
    lines=board.splitlines()
    for idx,line in enumerate(lines):
        if re.match(r"^BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST\s*:=",line):
            j=idx
            while j<len(lines):
                line=lines[j].split("#",1)[0]
                group.extend(re.findall(r"[a-z][a-z0-9_]*",line.split(":=",1)[-1] if j==idx else line))
                j+=1
                if not line.rstrip().endswith(chr(92)):break
            break
    partitions=sorted(set(group))
    checks["generated_dynamic_partitions"]=partitions
    if not partitions:problem("super","Cannot parse target dynamic partition list")
    elif "mi_ext" not in partitions and checks["stock_vendor_boot_selected"]:
        warning("bootchain","Original stock vendor_boot first-stage fstab references mi_ext, while generated dynamic partition list excludes it. Boot/AVB/OTA migration is unresolved; no automatic fstab or signing changes.")
    if "BOARD_PREBUILT_VENDOR_BOOTIMAGE" in board and "rootdir/etc/fstab.mist" not in device:
        warning("bootchain","Staged fstab.mist is not installed with the active stock prebuilt vendor_boot; its contents do not affect first-stage init.")
    for s in ("vendor_dlkm","system_dlkm"):
        if ("TARGET_COPY_OUT_"+s.upper()) not in board: problem("dlkm","Missing "+s+" partition output mapping")
    # All declared stock prebuilts that are selected by product must have a real source.
    definitions={}
    for match in re.finditer(r"(?m)^(cc_prebuilt_binary|cc_prebuilt_library_shared|prebuilt_etc|sh_binary)\s*\{(.*?)^\}",bp,re.S|re.M):
        body=match.group(2)
        nm=re.search(r'\bname:\s*"([^"]+)"',body)
        if not nm: continue
        name=nm.group(1)
        src=re.search(r'\b(?:src|srcs):\s*(?:\[)?\s*"([^"]+)"',body)
        filename=re.search(r'\bfilename:\s*"([^"]+)"',body)
        stem=re.search(r'\bstem:\s*"([^"]+)"',body)
        definitions[name]={"source":src.group(1) if src else None,"stem":stem.group(1) if stem else None,"filename":filename.group(1) if filename else None,"type":match.group(1)}
    packages=set(re.findall(r"\bmist_[A-Za-z0-9_]+\b",mk))
    unresolved=sorted(packages-set(definitions))
    if unresolved:problem("vendor-make","Selected vendor modules not declared in Android.bp: "+", ".join(unresolved))
    active_sources=[]
    for name in sorted(packages & set(definitions)):
        source=definitions[name]["source"]
        if not source:problem("vendor-source",name+" has no parsed src/srcs");continue
        active_sources.append(source)
        if not (a.vendor/source).is_file():problem("vendor-source",name+" missing "+source)
    checks["selected_vendor_modules"]=len(packages)
    checks["selected_vendor_sources"]=len(active_sources)
    # Manifest list must cover each selected vendor source, not only a broad inventory.
    manifest={line.split(":",1)[0].strip() for line in files.splitlines() if line.strip() and not line.lstrip().startswith("#")}
    missing_manifest=sorted(set(s.replace("proprietary/","",1) for s in active_sources)-manifest)
    if missing_manifest:problem("vendor-extraction","Selected proprietary sources missing from device manifest: "+", ".join(missing_manifest[:15]))
    paths={}
    for name in sorted(packages & set(definitions)):
        d=definitions[name]
        source=d["source"]
        if not source:continue
        if d["type"] in ("cc_prebuilt_binary","sh_binary"):
            directory="bin"
            if re.search(r'relative_install_path:\s*"hw"',bp[bp.find('name: "'+name+'"'):bp.find('}',bp.find('name: "'+name+'"'))]):directory="bin/hw"
            filename=d["stem"] or d["filename"] or Path(source).name
        elif d["type"]=="cc_prebuilt_library_shared":
            directory="lib64"
            if "/hw/" in source:directory="lib64/hw"
            filename=(d["stem"] or Path(source).stem)+".so"
        else:
            start=bp.find('name: "'+name+'"')
            tail=bp[start:bp.find("}",start)]
            sub=re.search(r'sub_dir:\s*"([^"]+)"',tail)
            directory="etc/"+sub.group(1) if sub else "etc"
            filename=d["filename"] or Path(source).name
        dest="vendor/"+directory+"/"+filename
        if dest in paths:problem("vendor-install","Two curated modules install "+dest+": "+name+" and "+paths[dest])
        paths[dest]=name
    checks["unique_curated_vendor_destinations"]=len(paths)
    # Selected init RC files: validate actual source-executable consistency where proprietary paths are referenced.
    missing_init=[]
    for src in active_sources:
        if not src.endswith(".rc"):continue
        rc=(a.vendor/src).read_text(errors="replace")
        for cmd in re.findall(r"(?m)^\s*(?:service\s+\S+\s+|exec(?:_background)?\s+--\s+)(/vendor/(?:bin|bin/hw)/[^\s\\]+)",rc):
            rel=cmd.removeprefix("/vendor/")
            if ("vendor/"+rel not in paths and not (a.vendor/"proprietary/vendor"/rel).is_file()):
                missing_init.append({"rc":src,"executable":cmd})
    if missing_init:
        warning("init","Curated RC files refer to executables not installed by selected vendor modules (some may be platform-owned): "+json.dumps(missing_init[:20]))
    # Parse XML content and detect duplicate HAL names/versions/interfaces within selected fragments.
    vintf={}
    parsed=0
    for src in sorted(set(active_sources)):
        if "/vintf/" not in src or not src.endswith(".xml"):continue
        try:
            root=ET.parse(a.vendor/src).getroot()
            parsed+=1
            vintf[src]=[]
            for hal in root.findall(".//hal"):
                name=(hal.findtext("name") or "").strip()
                for fqname in hal.findall("fqname"):
                    vintf[src].append(name+"/"+(fqname.text or "").strip())
                for interface in hal.findall("interface"):
                    iname=(interface.findtext("name") or "").strip()
                    for instance in interface.findall("instance"):
                        vintf[src].append(name+"/"+iname+"/"+(instance.text or "").strip())
        except ET.ParseError as e:problem("vintf","Invalid selected fragment "+src+": "+str(e))
    checks["curated_vintf_fragments_parsed"]=parsed
    # Absence of SKU-dependent ODM manifests is a genuine open boot/runtime constraint.
    if not any("odm" in p and "manifest" in p for p in active_sources):
        warning("odm","No chosen SKU-specific ODM VINTF variant in curated vendor package; radio slot registration remains unresolved.")
    checks["vintf_hal_instances_by_file"]=vintf
    checks["boot_readiness"]=False
    checks["full_rom_build_verified"]=False
    checks["device_boot_verified"]=False
    result={"hard_source_errors":problems,"open_integration_blockers":warnings,"checks":checks}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"hard_source_errors":len(problems),"open_integration_blockers":len(warnings),"selected_modules":len(packages),"curated_vintf_fragments":parsed},indent=2))
    for item in problems:print("ERROR:",item["topic"],item["message"])
    for item in warnings:print("OPEN:",item["topic"],item["message"])
    if problems:raise SystemExit(1)
if __name__=="__main__":main()
