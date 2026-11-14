#!/usr/bin/env python3
"""One-shot Mist/LineageOS 23.2 offline readiness audit, NO build, modifications or flash.
Run: python3 scripts/audit_mist_offline_readiness.py ~/android/lineage
Writes one consolidated TXT to ~/mist-offline-readiness-<UTC>.txt.
"""
import collections
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "~/android/lineage").expanduser().resolve()
if not (root/"build/envsetup.sh").is_file():
    sys.exit("ERROR: LineageOS root missing: "+str(root))
output = pathlib.Path.home()/("mist-offline-readiness-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".txt")
checks = []
lines = []
def out(*args):
    lines.append(" ".join(str(x) for x in args))
def title(s):
    out("\n"+"="*70+"\n"+s+"\n"+"="*70)
def check(s,state,detail=""):
    checks.append((s,state))
    out("["+state+"]",s,detail)
def command(argv,timeout=12):
    try:
        p=subprocess.run(argv,cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         text=True,errors="replace",timeout=timeout)
        return p.returncode,(p.stdout+"\n"+p.stderr).strip()
    except Exception as e:
        return -1,str(e)
def rel(p):
    try:return str(p.relative_to(root))
    except ValueError:return str(p)
def sample(label,seq,maxn=15):
    seq=list(seq)
    out(label,"count:",len(seq))
    for x in seq[:maxn]:out("   ",str(x)[:240])
    if len(seq)>maxn:out("   ...",len(seq)-maxn,"more")
def scanfiles(folder,pattern):
    p=root/folder
    return [x for x in p.rglob(pattern) if x.is_file()] if p.is_dir() else []

out("MIST / LINEAGEOS 23.2 — ALL-IN-ONE OFFLINE READINESS REPORT")
out("UTC:",datetime.datetime.now(datetime.timezone.utc).isoformat())
out("Root:",root)
out("READ ONLY. NO SOURCE EDITS, NO FULL ROM BUILD, NO FLASH.")
out("PASS means observed local file/check; it is NOT device runtime validation.")

title("1. SOURCE CHECKOUT STATUS AND LOCAL CHANGES")
for label,path in (
    ("device","device/xiaomi/mist"),("vendor","vendor/xiaomi/mist"),
    ("kernel","kernel/xiaomi/mist"),("stock-kernel","device/xiaomi/mist-kernel"),
    ("MiCode-display-UAPI","vendor/qcom/opensource/mist-display-uapi"),
    ("CAF-common","hardware/qcom-caf/common")
):
    d=root/path
    if not d.is_dir():
        check(label,"FAIL",path+" missing")
        continue
    ec,sha=command(["git","-C",str(d),"rev-parse","--short","HEAD"])
    ec2,dirty=command(["git","-C",str(d),"status","--short","--untracked-files=no"])
    check(label,"WARN" if (ec or ec2 or dirty) else "PASS",
          path+" @ "+(sha[:25] if not ec else "not a git repo")+"; tracked changes "+str(len(dirty.splitlines()) if dirty else 0))
    if dirty:sample("  local modifications",dirty.splitlines(),8)

title("2. BOARD CONFIG, BOOT AND SUPER/OTA")
p=root/"device/xiaomi/mist/BoardConfig.mk"
if not p.is_file():check("BoardConfig.mk","FAIL","missing")
else:
    text=p.read_text(errors="replace")
    check("BoardConfig.mk","PASS",rel(p))
    for key in ("TARGET_BOARD_PLATFORM","TARGET_KERNEL_VERSION","TARGET_KERNEL_SOURCE",
                "TARGET_FORCE_PREBUILT_KERNEL","TARGET_PREBUILT_KERNEL",
                "BOARD_PREBUILT_VENDOR_BOOTIMAGE","BOARD_PREBUILT_DTBOIMAGE",
                "BOARD_SUPER_PARTITION_SIZE","BOARD_BOOTIMAGE_PARTITION_SIZE",
                "BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE","BOARD_INIT_BOOT_IMAGE_PARTITION_SIZE",
                "BOARD_DTBOIMG_PARTITION_SIZE"):
        m=re.findall(r"^\s*"+key+r"\s*[:?+]?=\s*([^#\n]*)",text,re.M)
        out("   ",key,"=",m[-1].strip() if m else "NOT SET")
    check("forced stock kernel with source UAPI","WARN" if re.search(
          r"^\s*TARGET_FORCE_PREBUILT_KERNEL\s*:?=\s*true",text,re.M) else "INFO",
          "kernel UAPI and stock kernel ABI may not match")
for path in ("device/xiaomi/mist-kernel/kernel","device/xiaomi/mist-kernel/vendor_boot.img",
             "device/xiaomi/mist-kernel/dtbo.img"):
    f=root/path
    check(path,"PASS" if f.is_file() else "FAIL",
          str(f.stat().st_size)+" bytes" if f.is_file() else "missing")
for path in ("out/target/product/mist/boot.img","out/target/product/mist/init_boot.img",
             "out/target/product/mist/super.img","out/target/product/mist/vendor_boot.img"):
    f=root/path
    out("   built image",path,"EXISTS" if f.is_file() else "not present")
check("LP partition groups / AVB chain / OTA layout","UNVERIFIED",
      "Exact verified stock group metadata & AVB descriptors must be compared, not inferred from sizes.")

title("3. DISPLAY GENERATOR AND STAGED HAL ARTIFACTS")
display=root/"out/soong/.intermediates/vendor/qcom/opensource/mist-display-uapi/qti_generate_display_kernel_headers/gen"
for name in ("display/drm/sde_drm.h","display/drm/msm_drm_pp.h",
             "display/media/mmm_color_fmt.h","display/media/msm_sde_rotator.h"):
    f=display/name
    check("display header "+name,"PASS" if f.is_file() and f.stat().st_size else "FAIL",rel(f))
vendor=root/"out/target/product/mist/vendor"
for name in ("bin/hw/vendor.qti.hardware.display.composer-service",
             "bin/hw/vendor.qti.camera.provider-service_64",
             "bin/hw/vendor.qti.hardware.lights.service",
             "etc/init/vendor.qti.hardware.display.composer-service.rc",
             "etc/vintf/manifest/vendor.qti.hardware.display.composer-service.xml"):
    f=vendor/name
    check("vendor artifact "+name,"PASS" if f.is_file() else "WARN",rel(f))
check("HAL device runtime", "UNVERIFIED","build output does not prove panel/camera/lights/radio/audio service works.")

title("4. VENDOR / IMAGE ELF DT_NEEDED CLOSURE (NAME-ONLY)")
bases=[root/p for p in ("out/target/product/mist/vendor","out/target/product/mist/odm",
                       "out/target/product/mist/product","out/target/product/mist/system_ext",
                       "out/target/product/mist/system","vendor/xiaomi/mist/proprietary")]
elfs=[]
available=set()
for base in bases:
    if not base.is_dir():continue
    for directory,subdirs,names in os.walk(base):
        subdirs[:]=[s for s in subdirs if s!=".git"]
        for n in names:
            p=pathlib.Path(directory)/n
            if n.endswith(".so") or ".so." in n:available.add(n)
            try:
                if p.is_file() and not p.is_symlink() and p.stat().st_size>63:
                    with p.open("rb") as f:magic=f.read(4)
                    if magic==b"\x7fELF":
                        elfs.append(p)
                        available.add(n)
            except OSError:pass
sample("ELFs discovered",[rel(p) for p in elfs],10)
readelf=shutil.which("readelf") or shutil.which("llvm-readelf")
if not readelf:check("ELF DT_NEEDED audit","UNVERIFIED","readelf or llvm-readelf missing")
else:
    unresolved=collections.defaultdict(list)
    failures=[]
    parsed=0
    for p in elfs:
        ec,raw=command([readelf,"-d",str(p)],timeout=8)
        if ec:
            if "There is no dynamic section" not in raw and len(failures)<12:
                failures.append(rel(p)+": "+raw[-160:])
            continue
        parsed+=1
        for need in re.findall(r"\(NEEDED\)\s+Shared library:\s+\[([^\]]+)\]",raw):
            if need not in available and len(unresolved[need])<5:
                unresolved[need].append(rel(p))
    out("ELFs parsed with dynamic readelf:",parsed,"/",len(elfs))
    out("Unique DT_NEEDED names not present in scanned roots:",len(unresolved))
    for name,users in sorted(unresolved.items())[:150]:
        out("    UNRESOLVED",name,"<--","; ".join(users[:3]))
    sample("ELF parser issues",failures,12)
    check("ELF filename dependency scan","WARN" if unresolved else "PASS",
          "Unresolved names may be legitimate APEX/VNDK libs or incomplete staging; NOT proof of broken runtime linker.")
out("ELF symbol versions, ABI, linker namespaces and stock proprietary SONAME differences are NOT verified.")

title("5. VINTF XML STRUCTURE (NOT HAL COMPATIBILITY)")
vfiles=[]
for path in ("device/xiaomi/mist","vendor/xiaomi/mist",
             "out/target/product/mist/vendor/etc/vintf","out/target/product/mist/odm/etc/vintf",
             "out/target/product/mist/system/etc/vintf",
             "out/target/product/mist/system_ext/etc/vintf"):
    d=root/path
    if d.is_dir():
        vfiles.extend(p for p in d.rglob("*.xml") if "vintf" in p.parts or
                      "manifest" in p.name or "compatibility_matrix" in p.name)
vfiles=list(dict.fromkeys(vfiles))
bad=[]
hal=collections.Counter()
for p in vfiles:
    try:
        e=ET.parse(p)
        for h in e.getroot().iter("hal"):
            n=h.findtext("name")
            if n:hal[n]+=1
    except ET.ParseError as err:bad.append(rel(p)+": "+str(err))
sample("VINTF file candidates",[rel(p) for p in vfiles],22)
sample("Malformed XML",bad)
sample("HAL declaration names",["%s (%s entries)"%(n,v) for n,v in hal.most_common()],40)
check("VINTF XML well-formedness","FAIL" if bad else ("PASS" if vfiles else "WARN"),
      str(len(vfiles))+" files, "+str(len(bad))+" XML parse errors")
check("checkvintf and shipping FCM compatibility","UNVERIFIED",
      "Need matching assembled vendor/system matrices, properties and checkvintf.")

title("6. SEPOLICY / INIT INVENTORY")
for path in ("device/xiaomi/mist/sepolicy","vendor/xiaomi/mist/sepolicy",
             "device/xiaomi/mist/rootdir","vendor/xiaomi/mist/proprietary/etc/init"):
    check(path,"PASS" if (root/path).is_dir() else "WARN","source path inventory")
ses=[]
for d in (root/"device/xiaomi/mist",root/"vendor/xiaomi/mist"):
    if d.is_dir():
        ses.extend(p for p in d.rglob("*") if p.is_file() and p.suffix in (".te",".cil"))
sample("Device/vendor sepolicy files",[rel(p) for p in ses],20)
sample("Staged vendor init rc",[rel(p) for p in
       (vendor/"etc/init").rglob("*.rc") if p.is_file()] if (vendor/"etc/init").is_dir() else [],20)
check("SELinux policy build/neverallow/label contexts","UNVERIFIED",
      "Needs actual policy compiler and assembled partition contents; listing files is insufficient.")
check("Init service runtime","UNVERIFIED","Requires generated services, property contexts and boot logs.")

title("7. KERNEL MODULE INVENTORY / ABI")
for path in ("device/xiaomi/mist-kernel","out/target/product/mist/vendor_dlkm",
             "out/target/product/mist/system_dlkm","out/target/product/mist/vendor/lib/modules"):
    sample(path+" *.ko",[rel(p) for p in scanfiles(path,"*.ko")],12)
modules=scanfiles("out/target/product/mist/vendor_dlkm","*.ko")
modinfo=shutil.which("modinfo")
if modinfo and modules:
    versions=collections.Counter()
    for p in modules[:500]:
        ec,raw=command([modinfo,"-F","vermagic",str(p)],timeout=4)
        versions[raw.strip() if ec==0 else "<unreadable>"]+=1
    sample("vendor_dlkm vermagic groups",[str(k)+" : "+str(v) for k,v in versions.items()],18)
else:out("Module vermagic scan unavailable (missing vendor_dlkm *.ko or modinfo).")
check("Kernel/module ABI, modversions, DTB and loading","UNVERIFIED",
      "Vermagic alone cannot establish ABI/symbol compatibility or boot-time module loading.")

title("8. COMPLETENESS AND REMAINING GATES")
for path in ("out/target/product/mist/module-info.json",
             "out/target/product/mist/installed-files-vendor.json",
             "out/target/product/mist/vendor/etc/vintf/manifest"):
    p=root/path
    out("Metadata:",path,"present" if p.exists() else "missing")
check("Source kernel build / complete ROM / first boot","UNVERIFIED",
      "Never infer from this report; no full build, flash, or runtime exercise.")

title("9. SUMMARY: ALL OBSERVATIONS")
for label,state in checks:out(state.ljust(11),label)
counter=collections.Counter(s for _,s in checks)
out("COUNTS:"," ".join(str(s)+"="+str(counter[s]) for s in ("PASS","FAIL","WARN","UNVERIFIED","INFO")))
out("PASS = localized inventory check; FAIL = check failed; WARN = incomplete or ambiguous;")
out("UNVERIFIED = requires more evidence. DO NOT FLASH based only on this report.")
output.write_text("\n".join(lines)+"\n",encoding="utf-8")
print("Audit complete. One report:",output)
print("Report size:",output.stat().st_size,"bytes")
print("Counts:",dict(counter))
