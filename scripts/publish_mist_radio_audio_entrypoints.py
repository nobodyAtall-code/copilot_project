#!/usr/bin/env python3
"""Prepare six SHA256-proven stock RIL/audio entrypoints in device/vendor repos.

Fingerprint stays excluded: stock RC and VINTF disagree on service instance.
This does not prove Android runtime linker, SELinux or boot compatibility.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ENTRIES = [
    ("mist_stock_radio", "vendor/bin/hw/qcrilNrd", "binary"),
    ("mist_stock_radio_script", "vendor/bin/init.qcrild.sh", "script"),
    ("mist_stock_radio_rc", "vendor/etc/init/qcrilNrd.rc", "rc"),
    ("mist_stock_audio", "vendor/bin/hw/audiohalservice.qti", "binary"),
    ("mist_stock_audio_rc", "vendor/etc/init/audiohalservice_qti.rc", "rc"),
    ("mist_stock_audio_vintf", "vendor/etc/vintf/manifest/manifest_audiocorehal_default.xml", "vintf"),
]
MARKER = "MIST_STOCK_RADIO_AUDIO_BATCH_1"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--staged",type=Path,required=True)
    ap.add_argument("--device",type=Path,required=True)
    ap.add_argument("--vendor",type=Path,required=True)
    a=ap.parse_args()
    hashes=json.loads((a.staged/"checksums.json").read_text())["files"]
    bp_path=a.vendor/"Android.bp"
    mk_path=a.vendor/"mist-vendor.mk"
    manifest_path=a.device/"proprietary-files.txt"
    bp,mk,manifest=(x.read_text() for x in (bp_path,mk_path,manifest_path))
    if MARKER in bp or MARKER in mk:
        raise SystemExit("Already integrated; refusing duplicate publish")
    existing={x.strip().split(";")[0] for x in manifest.splitlines() if x.startswith("vendor/")}
    if len({name for name,_,_ in ENTRIES})!=6:
        raise SystemExit("Duplicate module name")
    for name,rel,kind in ENTRIES:
        src=a.staged/"proprietary"/rel
        dst=a.vendor/"proprietary"/rel
        record=hashes.get(rel.replace("vendor/","vendor_a/",1))
        if not record or not src.is_file() or dst.exists() or rel in existing:
            raise SystemExit("Unsafe or existing file: "+rel)
        if hashlib.sha256(src.read_bytes()).hexdigest()!=record["sha256"]:
            raise SystemExit("Stock hash mismatch: "+rel)
    blocks=["// "+MARKER,
        "// Original OS3.0.304.0.WPUMIXM; runtime dependency closure NOT established",""]
    for name,rel,kind in ENTRIES:
        filename=rel.rsplit("/",1)[-1]
        if kind=="binary":
            blocks += ["cc_prebuilt_binary {",f'    name: "{name}",',
                       f'    srcs: ["proprietary/{rel}"],',f'    stem: "{filename}",',
                       "    vendor: true,", '    relative_install_path: "hw",',
                       '    compile_multilib: "64",',"    strip: { none: true },",
                       "    check_elf_files: false,","}",""]
        elif kind=="script":
            blocks += ["sh_binary {",f'    name: "{name}",',
                       f'    src: "proprietary/{rel}",',f'    filename: "{filename}",',
                       "    vendor: true,","}",""]
        else:
            sub="init" if kind=="rc" else "vintf/manifest"
            blocks += ["prebuilt_etc {",f'    name: "{name}",',
                       f'    src: "proprietary/{rel}",',f'    filename: "{filename}",',
                       "    vendor: true,",f'    sub_dir: "{sub}",',"}",""]
    pkg=["# "+MARKER,
         "# Fingerprint excluded: original RC/VINTF service-instance mismatch.",
         "# Source bring-up only; not boot or linker verified.",
         "PRODUCT_PACKAGES += \\"]
    pkg.extend("    "+name+(" \\" if i<5 else "") for i,(name,_,_) in enumerate(ENTRIES))
    for name,rel,kind in ENTRIES:
        src=a.staged/"proprietary"/rel
        target=a.vendor/"proprietary"/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,target)
    bp_path.write_text(bp.rstrip()+"\n\n"+"\n".join(blocks)+"\n")
    mk_path.write_text(mk.rstrip()+"\n\n"+"\n".join(pkg)+"\n")
    manifest_path.write_text(manifest.rstrip()+"\n\n"+
        "# Stock Mist RIL/audio bring-up from artifact 14095953800\n"+
        "\n".join(rel for _,rel,_ in ENTRIES)+"\n")
    print("Prepared 6 verified OEM files, 6 modules, 6 manifest entries")
if __name__=="__main__": main()
