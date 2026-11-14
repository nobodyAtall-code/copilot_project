#!/usr/bin/env python3
"""Stage stock Mist RIL/audio/fingerprint entrypoints from verified firmware.

Emits exact proprietary sources, Soong fragments and extraction paths.
This does NOT provide full linker closure or boot readiness.
"""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path
from xml.etree import ElementTree

# type, module, archive-relative filename, expected vendor install path
ENTRIES = [
 ("binary","mist_stock_radio","bin/hw/qcrilNrd","bin/hw/qcrilNrd"),
 ("script","mist_stock_radio_script","bin/init.qcrild.sh","bin/init.qcrild.sh"),
 ("rc","mist_stock_radio_rc","etc/init/qcrilNrd.rc","etc/init/qcrilNrd.rc"),
 ("binary","mist_stock_audio","bin/hw/audiohalservice.qti","bin/hw/audiohalservice.qti"),
 ("rc","mist_stock_audio_rc","etc/init/audiohalservice_qti.rc","etc/init/audiohalservice_qti.rc"),
 ("vintf","mist_stock_audio_vintf","etc/vintf/manifest/manifest_audiocorehal_default.xml","etc/vintf/manifest/manifest_audiocorehal_default.xml"),
 ("binary","mist_stock_fingerprint","bin/hw/android.hardware.biometrics.fingerprint-service.odm","bin/hw/android.hardware.biometrics.fingerprint-service.odm"),
 ("rc","mist_stock_fingerprint_rc","etc/init/fingerprint-odm.rc","etc/init/fingerprint-odm.rc"),
 ("vintf","mist_stock_fingerprint_vintf","etc/vintf/manifest/fingerprint-odm.xml","etc/vintf/manifest/fingerprint-odm.xml"),
]
MAX_BYTES=50*1024*1024
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    chosen={"vendor_a/"+path:(kind,module,path,install) for kind,module,path,install in ENTRIES}
    if len(chosen)!=len(ENTRIES): raise ValueError("duplicate archive paths")
    observed={}
    process=subprocess.Popen(["zstd","-dc","--",str(args.archive)],stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout,mode="r|") as archive:
            for member in archive:
                key=member.name.removeprefix("./")
                if key not in chosen: continue
                kind,module,path,install=chosen[key]
                if key in observed or not member.isfile() or not 0<member.size<=MAX_BYTES:
                    raise RuntimeError("Repeated/invalid source: "+key)
                handle=archive.extractfile(member)
                if handle is None: raise RuntimeError("Unreadable source "+key)
                data=handle.read(MAX_BYTES+1)
                if len(data)!=member.size: raise RuntimeError("Truncated source "+key)
                if kind=="binary":
                    if data[:4]!=b"\x7fELF" or data[4]!=2 or int.from_bytes(data[18:20],"little")!=183:
                        raise RuntimeError("Not an ARM64 ELF binary "+key)
                elif kind=="vintf":
                    if ElementTree.fromstring(data).tag!="manifest": raise RuntimeError("Bad VINTF manifest "+key)
                elif kind=="rc":
                    if b"service " not in data: raise RuntimeError("Missing init service "+key)
                dest=args.output/"proprietary"/"vendor"/path
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(data)
                observed[key]={"sha256":hashlib.sha256(data).hexdigest(),"size":member.size,
                               "module":module,"destination":"vendor/"+install}
    finally:
        if process.stdout: process.stdout.close()
        result=process.wait()
    if result!=0 or len(observed)!=len(chosen):
        raise RuntimeError("zstd error or missing exact stock entries: "+str(sorted(chosen.keys()-observed.keys())))
    bp=["// MIST_RADIO_AUDIO_FP_ENTRYPOINT_BATCH_1",
        "// Stock OS3.0.304.0.WPUMIXM. Runtime dependencies and sepolicy NOT YET CLOSED.",""]
    names=[]
    for kind,name,path,install in ENTRIES:
        names.append(name)
        basename=install.split("/")[-1]
        if kind=="binary":
            bp.extend(["cc_prebuilt_binary {",f'    name: "{name}",',
                f'    srcs: ["proprietary/vendor/{path}"],',f'    stem: "{basename}",',
                "    vendor: true,", '    relative_install_path: "hw",',
                '    compile_multilib: "64",',"    strip: { none: true },",
                "    check_elf_files: false,","}",""])
        elif kind=="script":
            bp.extend(["sh_binary {",f'    name: "{name}",',
                f'    src: "proprietary/vendor/{path}",',f'    filename: "{basename}",',
                "    vendor: true,","}",""])
        else:
            sub="init" if kind=="rc" else "vintf/manifest"
            bp.extend(["prebuilt_etc {",f'    name: "{name}",',
                f'    src: "proprietary/vendor/{path}",',f'    filename: "{basename}",',
                "    vendor: true,",f'    sub_dir: "{sub}",',"}",""])
    args.output.joinpath("batch.bp").write_text("\n".join(bp)+"\n")
    mk=["# MIST_RADIO_AUDIO_FP_ENTRYPOINT_BATCH_1",
        "# Original Mist service entrypoints; full runtime dependency closure pending.",
        "PRODUCT_PACKAGES += \\"]
    mk.extend("    "+n+(" \\" if i<len(names)-1 else "") for i,n in enumerate(names))
    args.output.joinpath("batch.mk").write_text("\n".join(mk)+"\n")
    args.output.joinpath("manifest-additions.txt").write_text(
        "# Mist stock RIL/audio/fingerprint service entrypoints\n"+
        "\n".join("vendor/"+path for _,_,path,_ in ENTRIES)+"\n")
    args.output.joinpath("checksums.json").write_text(json.dumps({
        "firmware":"OS3.0.304.0.WPUMIXM","status":"source-verified entrypoints only; NOT runtime complete",
        "files":observed},indent=2,sort_keys=True)+"\n")
    print("Validated and staged",len(observed),"stock files",len(names),"Soong modules")
if __name__=="__main__": main()
