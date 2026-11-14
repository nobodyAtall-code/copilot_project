#!/usr/bin/env python3
"""Mist LineageOS 23.2 tree integration audit: read-only, one TXT report.
Run: python3 /tmp/audit_mist_tree_integration.py ~/android/lineage
Requires only Python 3. Produces one TXT in $HOME.
No builds, no repo sync, no flashing, no source edits.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import re
import subprocess
import shutil
import sys
import xml.etree.ElementTree as ET

root = Path(sys.argv[1] if len(sys.argv) > 1 else "~/android/lineage").expanduser().resolve()
if not (root/"build/envsetup.sh").is_file():
    sys.exit("ERROR: supply your LineageOS checkout root")
outfile = Path.home()/("mist-tree-integration-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".txt")
rows, results = [], []
def emit(*msg):
    rows.append(" ".join(str(x) for x in msg))
def section(s):
    emit("\n"+"="*76+"\n"+s+"\n"+"="*76)
def result(name,kind,detail):
    results.append((name,kind))
    emit("["+kind+"]",name,":",detail)
def text(path):
    p=root/path
    return p.read_text(errors="replace") if p.is_file() else ""
def sample(label,values,limit=25):
    values=list(values)
    emit(label,"("+str(len(values))+")")
    for v in values[:limit]:emit(" ",str(v)[:300])
    if len(values)>limit:emit(" ... plus",len(values)-limit)
def run(args,timeout=15):
    try:
        p=subprocess.run(args,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         encoding="utf-8",errors="replace",timeout=timeout)
        return p.returncode,(p.stdout+"\n"+p.stderr).strip()
    except Exception as e:return -1,str(e)
def glob(rootrel,pat):
    d=root/rootrel
    return sorted(d.rglob(pat)) if d.is_dir() else []

emit("MIST / ANDROID 16 — TREE INTEGRATION AND BOOT BLOCKER AUDIT")
emit("Date:",datetime.now(timezone.utc).isoformat())
emit("Root:",root)
emit("READ-ONLY: no build, flashing, file modifications or network.")
emit("WARN = risk or evidence gap; FAIL = specific local broken reference.")
device="device/xiaomi/mist"
vendor="vendor/xiaomi/mist"
board=text(device+"/BoardConfig.mk")
devmk=text(device+"/device.mk")
product=text(device+"/lineage_mist.mk")
vbp=text(vendor+"/Android.bp")
vmk=text(vendor+"/mist-vendor.mk")
manifest=text(device+"/proprietary-files.txt")

section("1. SOURCE REVISIONS AND CHANGED FILES")
for name,p in [("device",device),("vendor",vendor),("kernel","kernel/xiaomi/mist"),
               ("stock prebuilts","device/xiaomi/mist-kernel"),
               ("MiCode display UAPI","vendor/qcom/opensource/mist-display-uapi"),
               ("CAF common","hardware/qcom-caf/common")]:
    d=root/p
    if not d.is_dir():
        result(name,"FAIL","directory missing: "+p);continue
    _,revision=run(["git","-C",str(d),"rev-parse","--short","HEAD"])
    _,dirty=run(["git","-C",str(d),"status","--short","--untracked-files=no"])
    result(name,"WARN" if dirty else "PASS",p+" @ "+revision.splitlines()[0]+"; changed: "+str(len(dirty.splitlines())))
    if dirty:sample(" Modified tracked files",dirty.splitlines(),12)

section("2. DEVICE CONFIG / BOOT / SECURITY WIRING")
for p in ("AndroidProducts.mk","BoardConfig.mk","device.mk","lineage_mist.mk",
          "proprietary-files.txt","extract-files.py","setup-makefiles.py"):
    result("device/"+p,"PASS" if (root/device/p).is_file() else "FAIL","file presence")
for path,patt in [("device sepolicy",device+"/sepolicy"),
                  ("rootdir",device+"/rootdir"),
                  ("recovery",device+"/recovery"),
                  ("configs",device+"/configs")]:
    result(path,"PASS" if (root/patt).is_dir() else "WARN",patt)
configfiles=[(p,root/device/p) for p in ("BoardConfig.mk","device.mk","lineage_mist.mk")]
combined="\n".join(text(device+"/"+p) for p,_ in configfiles)
security_vars=["BOARD_VENDOR_SEPOLICY_DIRS","BOARD_SEPOLICY_DIRS","SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS",
               "SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS","PRODUCT_PRIVATE_SEPOLICY_DIRS",
               "PRODUCT_PUBLIC_SEPOLICY_DIRS"]
settings=[v for v in security_vars if re.search(r"^\s*"+v+r"\s*[:+?]?=",combined,re.M)]
sample("Device SELinux settings",settings)
policyfiles=glob(device,"*.te")+glob(device,"*.cil")+glob(vendor,"*.te")+glob(vendor,"*.cil")
sample("Device/vendor SELinux source files",[p.relative_to(root) for p in policyfiles])
result("Device-specific SEPolicy integration","WARN" if not settings or not policyfiles else "PASS",
       "No clear policy build wiring" if not settings or not policyfiles else "files and settings present; not compiled")
for k in ("TARGET_BOARD_PLATFORM","TARGET_KERNEL_SOURCE","TARGET_FORCE_PREBUILT_KERNEL",
          "TARGET_PREBUILT_KERNEL","BOARD_PREBUILT_VENDOR_BOOTIMAGE",
          "BOARD_PREBUILT_DTBOIMAGE","BOARD_SUPER_PARTITION_SIZE"):
    m=re.findall(r"^\s*"+k+r"\s*[:+?]?=\s*([^#\n]+)",board,re.M)
    emit(" ",k,":",m[-1].strip() if m else "<NOT SET>")
for fname in ("kernel","vendor_boot.img","dtbo.img"):
    p=root/"device/xiaomi/mist-kernel"/fname
    hashfile=p.with_name(fname+".sha256")
    if not p.is_file():
        result("stock "+fname,"FAIL","missing");continue
    if hashfile.is_file():
        words=hashfile.read_text().split()
        expected=words[0] if words else ""
        actual=hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
        result("stock "+fname+" SHA256","PASS" if actual==expected else "FAIL",
               "matches provenance lock" if actual==expected else "MISMATCH")
    else:result("stock "+fname,"WARN","exists but no *.sha256 lock")
for key in ("BOARD_AVB_ENABLE","BOARD_AVB_ALGORITHM","BOARD_AVB_KEY_PATH",
            "BOARD_SUPER_PARTITION_GROUPS","BOARD_QTI_DYNAMIC_PARTITIONS_SIZE",
            "BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST",
            "TARGET_RECOVERY_FSTAB","BOARD_INCLUDE_DTB_IN_BOOTIMG"):
    emit(" ",key,":","present" if re.search(r"^\s*"+key+r"\s*[:+?]?=",combined,re.M) else "not in three primary config files")
result("Complete dynamic groups and AVB integration","UNVERIFIED",
       "Must cross-check stock super metadata, vbmeta and OTA packaging; not inferred from source grep.")
for fn in ("device/xiaomi/mist/boot/stock_snapshot/lib/modules/modules.load",
           "device/xiaomi/mist/boot/stock_snapshot/first_stage_ramdisk/fstab.default"):
    result("stock boot snapshot "+Path(fn).name,"PASS" if (root/fn).is_file() else "WARN",fn)

section("3. VENDOR MANIFEST COVERAGE, SOONG MODULES AND PACKAGE SELECTION")
declared=[]
for raw in manifest.splitlines():
    val=raw.strip().split("#",1)[0].strip()
    if val:
        declared.append(val.split("|",1)[0].lstrip("-"))
sample("proprietary-files.txt entries",declared,35)
missing=[p for p in declared if not (root/vendor/"proprietary"/p).exists()]
sample("Manifest paths absent from vendor checkout",missing,80)
result("Proprietary manifest membership","FAIL" if missing else ("PASS" if declared else "WARN"),
       str(len(missing))+" entries missing out of "+str(len(declared)))
presentfiles=[p for p in glob(vendor+"/proprietary","*") if p.is_file()]
emit("Vendor proprietary source files:",len(presentfiles))
sample("Present blobs not included in extraction manifest",
       [str(p.relative_to(root/vendor/"proprietary")) for p in presentfiles
        if str(p.relative_to(root/vendor/"proprietary")) not in declared],25)
# Capture Soong blocks one block per top-level declaration; this tree uses standard stanza syntax.
blocks=re.findall(r"(?ms)^(cc_prebuilt_library_shared|cc_prebuilt_binary|prebuilt_etc)\s*\{(.*?)^\}",vbp)
modules={}
sources=[]
for typ,body in blocks:
    match=re.search(r'\bname:\s*"([^"]+)"',body)
    if not match:continue
    name=match.group(1)
    sources_match=re.search(r'\bsrcs?:\s*(?:\[\s*)?"([^"]+)"',body)
    src=sources_match.group(1) if sources_match else None
    stem=re.search(r'\b(?:stem|filename):\s*"([^"]+)"',body)
    modules[name]=(typ,src,stem.group(1) if stem else None,body)
    if src:sources.append(src)
packages=re.findall(r"\bmist_[A-Za-z0-9_]+\b",vmk)
sample("Unselected Soong modules",[n for n in modules if n not in packages],60)
sample("PRODUCT_PACKAGES without corresponding vendor module",[n for n in packages if n not in modules],60)
sample("Soong source blobs missing",[s for s in sources if not (root/vendor/s).is_file()],60)
sample("prebuilt modules with check_elf_files: false",
       [n for n,(typ,src,stem,body) in modules.items() if "check_elf_files: false" in body],50)
emit("Soong prebuilt modules:",len(modules),"PRODUCT_PACKAGES refs:",len(packages),
     "proprietary files:",len(presentfiles))
result("Vendor modules vs package selection",
       "WARN" if (set(modules)!=set(packages) or len(packages)!=len(set(packages))) else "PASS",
       "Presence/selection only; not installation verification.")
result("Vendor ELF strict check disabled",
       "WARN" if any("check_elf_files: false" in b[-1] for b in modules.values()) else "PASS",
       "Disabled checks require actual linker/SONAME ABI evidence before production.")
result("Vendor tree completeness","UNVERIFIED",
       "Curated blobs only; requires verified stock archive membership/diffs and service dependency closure.")

section("4. STAGED FILES VS SELECTED STOCK SERVICES")
vout=root/"out/target/product/mist/vendor"
vendor_services=[p for p in glob(vendor+"/proprietary/vendor/bin/hw","*") if p.is_file()]
installed=[]
missing_services=[]
for s in vendor_services:
    dest=vout/"bin/hw"/s.name
    if dest.is_file():installed.append(s.name)
    else:missing_services.append(s.name)
sample("Vendor stock services currently staged",[n for n in installed],70)
sample("Vendor stock services not staged (may be platform-owned, intentionally)",missing_services,70)
if vout.is_dir():
    sample("Staged vendor init", [p.name for p in glob("out/target/product/mist/vendor/etc/init","*.rc")],60)
    sample("Staged vendor VINTF fragments",
           [p.name for p in glob("out/target/product/mist/vendor/etc/vintf","*.xml")],70)
else:result("Vendor staging","WARN","out/target/product/mist/vendor missing")
result("Init/VINTF system integration","UNVERIFIED",
       "Listing files cannot establish service registration, SELinux labels, FCM or runtime start.")

section("5. ELF LIBRARIES: FOCUSED STAGED VS SOURCE DEPENDENCIES")
readelf="readelf"
if not shutil.which(readelf):
    result("ELF needed scan","WARN","readelf unavailable")
else:
    paths=[]
    for base in (vout,root/"vendor/xiaomi/mist/proprietary",root/"out/target/product/mist/system",
                 root/"out/target/product/mist/product",root/"out/target/product/mist/system_ext"):
        if not base.is_dir():continue
        for p in base.rglob("*"):
            if not p.is_file() or p.is_symlink():continue
            try:
                with p.open("rb") as f:magic=f.read(4)
                if magic==bytes((127,69,76,70)):paths.append(p)
            except OSError:pass
    provided={p.name for p in paths}
    needed=defaultdict(set)
    for p in paths:
        rc,raw=run([readelf,"-d",str(p)],timeout=8)
        if rc:continue
        for n in re.findall(r'\(NEEDED\)\s+Shared library:\s+\[([^\]]+)\]',raw):
            if n not in provided:needed[n].add(p.name)
    emit("ELF binaries discovered:",len(paths))
    emit("Unique DT_NEEDED names missing in sampled source/staged roots:",len(needed))
    sample("Unresolved candidates (including common Android system/APEX libs)",
           [k+" <- "+", ".join(sorted(v)[:5]) for k,v in sorted(needed.items())],100)
    result("ELF complete runtime closure","UNVERIFIED",
           "Filename scan over partial output is not SONAME, VNDK/APEX or linker namespace verification.")

section("6. KERNEL MODULE AND VENDOR_BOOT EVIDENCE")
for loc in ("device/xiaomi/mist-kernel","out/target/product/mist/vendor_dlkm",
            "out/target/product/mist/system_dlkm"):
    sample(loc+" .ko", [p.relative_to(root) for p in glob(loc,"*.ko")],10)
for f in ("device/xiaomi/mist/boot/stock_snapshot/lib/modules/modules.load",
          "device/xiaomi/mist/boot/stock_snapshot/lib/modules/modules.load.recovery"):
    txt=text(f)
    entries=[s.strip() for s in txt.splitlines() if s.strip() and not s.startswith("#")]
    sample(f+" entries",entries,20)
result("Vendor_boot module and DTB runtime ABI","UNVERIFIED",
       "Stock vendor_boot.img is present; parsing 291 embedded modules or matching .ko symbol ABI requires extracted stock evidence.")
result("Rebuilt kernel/DTBO integration","UNVERIFIED",
       "Still using forced stock kernel; no source-built compatible image or device boot verified.")

section("7. FINAL ACTIONABLE SUMMARY")
counts=Counter(k for _,k in results)
emit("Counts:"," ".join(k+"="+str(counts[k]) for k in ("PASS","FAIL","WARN","UNVERIFIED")))
for name,status in results:emit(status.ljust(11),name)
emit("\nNEXT GATES: (1) resolve actual absent device integration files,")
emit("(2) validate boot module inventory / stock partition evidence,")
emit("(3) complete vendor extraction and ELF SONAME/linker namespaces,")
emit("(4) run real checkvintf and compiled SELinux policy validation,")
emit("(5) only after evidence, consider expensive ROM compilation.")
emit("NO boot/flash readiness assertion.")
outfile.write_text("\n".join(rows)+"\n",encoding="utf-8")
print("Report:",outfile)
print("Bytes:",outfile.stat().st_size)
print("Counts:",dict(counts))
