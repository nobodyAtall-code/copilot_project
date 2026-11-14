#!/usr/bin/env python3
"""Sign an isolated Mist developer vendor_boot for OFFLINE verification only.

WARNING: This does NOT update the OEM-signed top-level vbmeta hash descriptor.
A standalone developer key does not make an image flash-safe or OEM-trusted.
Never publish the signing key, stock candidate binaries, or this output as ROM.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
STOCK_SHA="f0d692792cacff3026876edbd68aed5d23be7e1acef3e6028ccd5fff21ae5acb"
STOCK_SIZE=100663296
def run(cmd):
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode:raise RuntimeError("avbtool failure: "+str(p.returncode)+"\n"+p.stderr[-1200:])
    return p.stdout+"\n"+p.stderr
def sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--avbtool",type=Path,required=True)
    ap.add_argument("--candidate",type=Path,required=True)
    ap.add_argument("--developer-rsa2048-key",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    a=ap.parse_args()
    for p in (a.avbtool,a.candidate,a.developer_rsa2048_key):
        if not p.is_file():ap.error("Missing input "+str(p))
    if a.output.name!="vendor_boot.img":ap.error("Verification requires output basename vendor_boot.img; use a separate dedicated directory")
    if a.output.exists():ap.error("Refusing overwrite")
    if a.candidate.stat().st_size!=STOCK_SIZE:ap.error("Unexpected v4 candidate container size")
    original_digest=sha(a.candidate)
    if original_digest==STOCK_SHA:ap.error("Original stock vendor_boot is not a custom candidate")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(a.candidate,a.output)
    tool=[sys.executable,str(a.avbtool)]
    try:
        # Original OEM footer becomes stale as soon as the ramdisk changes.
        # Strip its footer before creating a distinct RSA-signed developer
        # footer. The top-level OEM vbmeta remains unchanged and mismatched.
        run(tool+["erase_footer","--image",str(a.output)])
        run(tool+["add_hash_footer","--image",str(a.output),
             "--partition_name","vendor_boot","--partition_size",str(STOCK_SIZE),
             "--algorithm","SHA256_RSA2048",
             "--key",str(a.developer_rsa2048_key),"--rollback_index","0"])
        verified=run(tool+["verify_image","--image",str(a.output),
             "--key",str(a.developer_rsa2048_key)])
        info=run(tool+["info_image","--image",str(a.output)])
        if "SHA256_RSA2048" not in info:raise RuntimeError("Not RSA-signed")
        result={
          "status":"STANDALONE_DEV_KEY_RSA_SIGNATURE_VERIFIED_ONLY",
          "input_candidate_sha256":original_digest,
          "signed_output_sha256":sha(a.output),
          "standalone_footer_verified":True,
          "stock_top_level_vbmeta_updated":False,
          "stock_top_level_chain_accepts_output":False,
          "developer_key_trusted_by_bootloader":False,
          "rollback_index_policy_validated":False,
          "flash_permitted":False,
          "warning":"DO NOT FLASH. Requires complete device-trusted AVB chain, safe rollback and physical device validation.",
          "verify_tail":verified[-1000:]}
        a.report.parent.mkdir(parents=True,exist_ok=True)
        a.report.write_text(json.dumps(result,indent=2)+"\n")
        print(json.dumps(result,indent=2))
    except BaseException:
        a.output.unlink(missing_ok=True)
        raise
if __name__=="__main__":main()
