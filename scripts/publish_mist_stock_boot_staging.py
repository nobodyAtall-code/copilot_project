#!/usr/bin/env python3
"""Stage audit-normalized stock boot configuration in production device tree."""
import argparse,json,hashlib
from pathlib import Path

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--audit",type=Path,required=True)
 p.add_argument("--output-root",type=Path,required=True)
 a=p.parse_args()
 d=json.loads(a.audit.read_text())
 if d.get("safe_to_flash") is not False or d.get("bootable_verified") is not False:
  raise SystemExit("Unexpected audit safety flags")
 files={f["path"]:f for group in d["ramdisks"] for f in group["interesting_files"]}
 expected={"first_stage_ramdisk/fstab.default":54,"first_stage_ramdisk/fstab.emmc":23,
           "lib/modules/modules.load":110,"lib/modules/modules.load.recovery":294}
 root=a.output_root/"boot"/"stock_snapshot"
 provenance={}
 for name,count in expected.items():
  f=files[name]
  lines=f["mount_entries"] if "fstab." in name else f["module_load_order"]
  if len(lines)!=count or any("\r" in line or "\n" in line for line in lines):
   raise SystemExit("Invalid count or line for "+name)
  if "modules.load" in name and any(not line.endswith(".ko") for line in lines):
   raise SystemExit("Invalid module name")
  dst=root/name
  dst.parent.mkdir(parents=True,exist_ok=True)
  dst.write_text("# Audit-normalized Xiaomi stock boot config; NOT installed.\n"+
    "# Original SHA256 and provenance in source-manifest.json.\n"+"\n".join(lines)+"\n")
  provenance[name]={"entry_count":count,"original_stock_sha256":f["sha256"],
                    "normalized_sha256":hashlib.sha256(dst.read_bytes()).hexdigest()}
 (root/"README.md").write_text(
 "# Mist OS3.0.304.0.WPUMIXM stock boot configuration snapshot\n\n"
 "Generated from SHA256-verified stock vendor_boot ramdisk in copilot_project "
 "GitHub Actions run 43540094714, and reconciled module inventory in run "
 "43540630241. This directory is NOT included in the device build.\n\n"
 "Warning: These are audit-normalized copies, NOT byte-identical original "
 "ramdisk files; blank lines and comments are omitted. Original checksums are "
 "tracked in source-manifest.json. The module-load files preserve order and "
 "duplicate names. The actual stock kernel .ko payloads, AVB keys, device-tree "
 "blobs and recovery logic are not included here. Never activate these paths "
 "without completing ramdisk packaging, kernel ABI, AVB, fstab, init and "
 "SELinux checks. This snapshot is not a bootable vendor_boot image.\n")
 (root/"source-manifest.json").write_text(json.dumps({
  "source_firmware":"OS3.0.304.0.WPUMIXM",
  "source_stock_images_run":43174896778,
  "source_ramdisk_audit_run":43540094714,
  "source_module_reconcile_run":43540630241,
  "byte_identical_to_stock":False,"installed_in_build":False,
  "safe_to_flash":False,"files":provenance},indent=2,sort_keys=True)+"\n")
 print("Materialized source snapshots:",len(provenance))
if __name__=="__main__":
 main()
