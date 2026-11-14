#!/usr/bin/env python3
"""Read-only stock Mist AVB checks with the actual AOSP avbtool; no signing or flashing."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HASHES={
    "boot.img":"45ba1fec1fbacb06c182f546d63b5a4b2bf54627094745bff5e208eb72b1b579",
    "init_boot.img":"0ee70e2a65598028e2de2b89b9b4af39422ffce40ac8283787435e91cb570989",
    "vendor_boot.img":"f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb",
    "dtbo.img":"2030334cc0a778389732cc1e7d05d4cdf5d8c2c0ce6b281331128f2cfc847703",
    "vbmeta.img":"813358d77d8d57b4e40e07b489df47282d11f5a0afd1d6dc7adb68db20d9ab76",
    "vbmeta_system.img":"1cf465b814024e2bd1df43455a51587fe6cf9f0b5535e8e13ee961b28c259377",
}
def digest(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path.home()/"android/lineage")
    p.add_argument("--images-dir",type=Path,required=True,help="Directory of original verified stock boot-chain images, including vbmeta.img and vbmeta_system.img")
    p.add_argument("--out",type=Path)
    args=p.parse_args()
    root=args.root.expanduser().resolve()
    avb=root/"external/avb/avbtool.py"
    files=args.images_dir.expanduser().resolve()
    if not avb.is_file():p.error("missing AOSP external/avb/avbtool.py")
    if not files.is_dir():p.error("missing stock images directory")
    checked={}
    for name,sha in HASHES.items():
        candidate=files/name
        if not candidate.is_file():
            checked[name]={"status":"MISSING"};continue
        actual=digest(candidate)
        checked[name]={"status":"STOCK_MATCH" if actual==sha else "HASH_MISMATCH",
                       "bytes":candidate.stat().st_size,"sha256":actual}
    if any(v["status"]=="HASH_MISMATCH" for v in checked.values()):
        raise SystemExit("Image SHA mismatch: cannot run AVB verification on non-stock bytes")
    if checked["vbmeta.img"]["status"]=="MISSING" or checked["vbmeta_system.img"]["status"]=="MISSING":
        raise SystemExit("Original vbmeta.img and vbmeta_system.img are required; do not substitute modified/generated images")
    # avbtool reads stock vbmeta descriptors and attempts actual signature/hash
    # verification. A missing referenced image is an incomplete input, not
    # automatically a crypto failure.
    executions={}
    for name in ("vbmeta.img","vbmeta_system.img","vendor_boot.img","dtbo.img"):
        if checked[name]["status"]!="STOCK_MATCH":continue
        cmd=[sys.executable,str(avb),"info_image","--image",str(files/name)]
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
        executions[name]={"info_exit":cp.returncode,"info":(cp.stdout+cp.stderr)[-12000:]}
    for name in ("vbmeta.img","vbmeta_system.img","vendor_boot.img"):
        if checked[name]["status"]!="STOCK_MATCH":continue
        cmd=[sys.executable,str(avb),"verify_image","--image",str(files/name)]
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        executions.setdefault(name,{})["verify_exit"]=cp.returncode
        executions[name]["verify_output"]=(cp.stdout+cp.stderr)[-12000:]
    result={"mode":"READ_ONLY_STOCK_AVBTOOL_VERIFICATION","stock_images":checked,
            "avbtool_results":executions,
            "caveats":["Stock AVB verify_image is not proof that a LineageOS init_boot, custom super, or modified vendor_boot is signed/accepted by bootloader.",
                       "Missing images for chained descriptors may prevent whole-chain verification.",
                       "Bootloader state, trusted public keys and rollback counters cannot be verified from image files alone."],
            "custom_rom_flash_safe":False}
    out=args.out or root/"mist-avb-stock-verification.json"
    out.write_text(json.dumps(result,indent=2)+"\n")
    print("Saved:",out)
    for name,entry in executions.items():
        print(name, "info=",entry.get("info_exit"),"verify=",entry.get("verify_exit","not run"))
    print("Only original stock images checked; no custom ROM signing/boot readiness claim.")
if __name__=="__main__":main()
