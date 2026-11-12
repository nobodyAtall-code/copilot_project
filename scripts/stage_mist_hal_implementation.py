#!/usr/bin/env python3
"""Package four verified stock HAL implementation libraries, no wildcards."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

BLOBS = [
 "vendor_a/lib64/hw/android.hardware.bluetooth@aidl-impl-qti.so",
 "vendor_a/lib64/hw/android.hardware.gnss-aidl-impl-qti.so",
 "vendor_a/lib64/hw/libqtigatekeeper.so",
 "vendor_a/lib64/libQSEEComAPI.so",
]
MARKER = "// MIST_HAL_IMPL_BATCH_2"
MAX_SIZE = 40 * 1024 * 1024

def main():
 ap = argparse.ArgumentParser()
 ap.add_argument("--archive", type=Path, required=True)
 ap.add_argument("--report", type=Path, required=True)
 ap.add_argument("--out", type=Path, required=True)
 args = ap.parse_args()
 document = json.loads(args.report.read_text())
 candidates = {x["stock_path"]: x for x in document["stock_resolved_paths"]}
 if any(path not in candidates for path in BLOBS):
  raise SystemExit("Requested HAL implementation not supported by actual ELF graph")
 for path in BLOBS:
  if not candidates[path]["required_by"]:
   raise SystemExit("Selected library has no actual ELF dependency edge")
 args.out.mkdir(parents=True, exist_ok=True)
 hashes = {}
 process = subprocess.Popen(["zstd", "-dc", "--", str(args.archive)], stdout=subprocess.PIPE)
 try:
  with tarfile.open(fileobj=process.stdout, mode="r|") as tf:
   for member in tf:
    name = member.name.removeprefix("./")
    if name not in BLOBS:
     continue
    if name in hashes or not member.isfile() or not (128 < member.size < MAX_SIZE):
     raise RuntimeError("Duplicate or invalid selected stock archive entry: "+name)
    data = tf.extractfile(member).read(MAX_SIZE + 1)
    if len(data) != member.size or data[:4] != bytes.fromhex("7f454c46") or data[4] != 2 or int.from_bytes(data[18:20], "little") != 183:
     raise RuntimeError("Wrong ELF format or truncated: "+name)
    rel = name.removeprefix("vendor_a/")
    dest = args.out / "proprietary/vendor" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    hashes[name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "parents": candidates[name]["required_by"]}
 finally:
  if process.stdout:
   process.stdout.close()
  status = process.wait()
 if status:
  raise RuntimeError("zstd decompression failure")
 if set(hashes) != set(BLOBS):
  raise RuntimeError("Missing source entries: "+str(set(BLOBS)-set(hashes)))
 bp = [MARKER, "// Stock OS3.0.304.0.WPUMIXM; linker ABI still needs actual build", ""]
 modules = []
 for name in BLOBS:
  rel = name.removeprefix("vendor_a/")
  stem = rel.rsplit("/",1)[-1]
  module = "mist_impl_" + stem.removesuffix(".so").replace(".", "_").replace("-", "_").replace("@","_")
  modules.append(module)
  bp += ["cc_prebuilt_library_shared {", '    name: "'+module+'",',
         '    stem: "'+stem+'",', '    srcs: ["proprietary/vendor/'+rel+'"],',
         '    vendor: true,', '    compile_multilib: "64",',
         '    relative_install_path: "hw",' if "/hw/" in rel else '    // Standard vendor lib64 location',
         '    strip: { none: true },',
         '    check_elf_files: false, // unresolved platform/namespace imports',
         "}", ""]
 (args.out/"batch.bp.txt").write_text("\n".join(bp))
 (args.out/"batch.mk.txt").write_text("# MIST_HAL_IMPL_BATCH_2\nPRODUCT_PACKAGES += \\\n    " + " \\\n    ".join(modules) + "\n")
 (args.out/"batch-report.json").write_text(json.dumps({"paths":hashes, "status":"four direct-graph stock libs; install path and ABI not build verified"}, indent=2,sort_keys=True)+"\n")
 print("Validated",len(hashes),"directly referenced stock HAL implementation libraries")

if __name__ == "__main__":
 main()
