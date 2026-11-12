#!/usr/bin/env python3
"""Curated mist HAL prebuilt batch; stock path allowlist, never bulk copy.

Output is a staging directory plus Soong/product makefile additions. The GitHub
Actions workflow owns publication, using an authenticated existing main branch.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

# These filenames were checked against archived mist init/VINTF inventory.
FILES = {
    "vendor_a/bin/hw/android.hardware.bluetooth@aidl-service-qti": "binary",
    "vendor_a/bin/hw/android.hardware.gatekeeper-service-qti": "binary",
    "vendor_a/bin/hw/android.hardware.gnss-aidl-service-qti": "binary",
    "vendor_a/bin/hw/android.hardware.health-service.qti": "binary",
    "vendor_a/bin/hw/android.hardware.thermal-service.qti": "binary",
    "vendor_a/etc/init/android.hardware.bluetooth@aidl-service-qti.rc": "init",
    "vendor_a/etc/init/android.hardware.gatekeeper-service-qti.rc": "init",
    "vendor_a/etc/init/android.hardware.gnss-aidl-service-qti.rc": "init",
    "vendor_a/etc/init/android.hardware.health-service.qti.rc": "init",
    "vendor_a/etc/init/android.hardware.thermal-service.qti.rc": "init",
    "vendor_a/etc/vintf/manifest/bluetooth_hci.xml": "vintf",
    "vendor_a/etc/vintf/manifest/android.hardware.gnss-aidl-service-qti.xml": "vintf",
    "vendor_a/etc/vintf/manifest/android.hardware.health-service.qti.xml": "vintf",
    "vendor_a/etc/vintf/manifest/android.hardware.thermal-service.qti.xml": "vintf",
}
MAX_SIZE = 32 * 1024 * 1024
MARKER = "// MIST_CURATED_HAL_BATCH_1"

def make_module(path, kind):
    rel = path.removeprefix("vendor_a/")
    basename = rel.rsplit("/", 1)[-1]
    module = "mist_hal_" + basename.replace(".", "_").replace("-", "_").replace("@", "_")
    lines = [f"// stock: {path}"]
    if kind == "binary":
        lines += ["cc_prebuilt_binary {", f'    name: "{module}",',
                  f'    srcs: ["proprietary/vendor/{rel}"],',
                  f'    stem: "{basename}",', '    vendor: true,',
                  '    relative_install_path: "hw",',
                  '    compile_multilib: "64",',
                  '    strip: { none: true },',
                  '    check_elf_files: false, // pending dynamic linker / APEX audit',
                  '}']
    else:
        lines += ["prebuilt_etc {", f'    name: "{module}",',
                  f'    src: "proprietary/vendor/{rel}",',
                  f'    filename: "{basename}",',
                  '    vendor: true,',
                  f'    sub_dir: "{("init" if kind == "init" else "vintf/manifest")}",',
                  '}']
    return module, "\n".join(lines)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    files = {}
    proc = subprocess.Popen(["zstd", "-dc", "--", str(args.archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            for member in tf:
                name = member.name.removeprefix("./")
                if name not in FILES:
                    continue
                if name in files:
                    raise RuntimeError(f"Duplicate tar path: {name}")
                if not member.isfile() or not (0 < member.size < MAX_SIZE):
                    raise RuntimeError(f"Unexpected source type/size: {name}")
                stream = tf.extractfile(member)
                if stream is None:
                    raise RuntimeError(f"Cannot extract: {name}")
                data = stream.read(MAX_SIZE + 1)
                if len(data) != member.size:
                    raise RuntimeError(f"Truncated archive member: {name}")
                kind = FILES[name]
                if kind == "binary":
                    if data[:4] != b"\x7fELF" or data[4] != 2 or int.from_bytes(data[18:20], "little") != 183:
                        raise RuntimeError(f"Expected AArch64 ELF64: {name}")
                elif kind == "init" and not data.lstrip().startswith((b"#", b"service", b"on ")):
                    raise RuntimeError(f"Unrecognized init rc contents: {name}")
                elif kind == "vintf" and b"<manifest" not in data:
                    raise RuntimeError(f"Expected VINTF manifest: {name}")
                relative = name.removeprefix("vendor_a/")
                destination = args.out / "proprietary" / "vendor" / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                files[name] = {"kind": kind, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    finally:
        if proc.stdout:
            proc.stdout.close()
        status = proc.wait()
    if status != 0:
        raise RuntimeError("zstd decompression failed")
    missing = sorted(set(FILES) - set(files))
    if missing:
        raise RuntimeError(f"Required stock HAL source paths missing: {missing}")
    modules = [make_module(x, FILES[x]) for x in FILES]
    (args.out / "batch.bp.txt").write_text(
        MARKER + "\n" + "\n\n".join(defn for _, defn in modules) + "\n"
    )
    (args.out / "batch.mk.txt").write_text(
        "# MIST_CURATED_HAL_BATCH_1\nPRODUCT_PACKAGES += \\\n    "
        + " \\\n    ".join(name for name, _ in modules) + "\n"
    )
    (args.out / "batch-report.json").write_text(
        json.dumps({"firmware": "OS3.0.304.0.WPUMIXM", "count": len(files),
                    "files": files, "approval": "stock paths and formats only; no ROM boot validation"},
                   indent=2, sort_keys=True) + "\n"
    )
    print(f"Curated {len(files)} HAL files; output includes {len(modules)} Soong modules")

if __name__ == "__main__":
    main()
