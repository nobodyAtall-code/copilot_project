#!/usr/bin/env python3
"""Publish only reviewed stock Mist USB/Power HAL triples to cloned production trees.

Run AFTER stage_mist_power_usb_review.py. Does not interact with GitHub by itself.
"""
import argparse
import hashlib
import json
from pathlib import Path

HALS = {
    "usb": ("android.hardware.usb-service.qti",
            "android.hardware.usb-service.qti.rc",
            "android.hardware.usb-service.qti.xml"),
    "power": ("android.hardware.power-service",
              "android.hardware.power-service.rc", "power.xml"),
}
MARKER = "// MIST_POWER_USB_HAL_BATCH_3"

def expected_modules():
    modules = []
    bp = [MARKER, "// Stock Mist OS3.0.304.0.WPUMIXM; runtime linker / SELinux unverified.", ""]
    for kind, (binary, rc, xml) in HALS.items():
        entries = [
            ("bin/hw/" + binary, f"mist_{kind}_stock_service", "binary", binary),
            ("etc/init/" + rc, f"mist_{kind}_stock_init", "init", rc),
            ("etc/vintf/manifest/" + xml, f"mist_{kind}_stock_vintf", "vintf/manifest", xml),
        ]
        for path, module, module_kind, basename in entries:
            modules.append((path, module))
            bp += [f"// stock vendor/{path}"]
            if module_kind == "binary":
                bp += ["cc_prebuilt_binary {", f'    name: "{module}",',
                       f'    srcs: ["proprietary/vendor/{path}"],',
                       f'    stem: "{basename}",', "    vendor: true,",
                       '    relative_install_path: "hw",',
                       '    compile_multilib: "64",',
                       "    strip: { none: true },",
                       "    check_elf_files: false, // dependency audit pending",
                       "}", ""]
            else:
                bp += ["prebuilt_etc {", f'    name: "{module}",',
                       f'    src: "proprietary/vendor/{path}",',
                       f'    filename: "{basename}",', "    vendor: true,",
                       f'    sub_dir: "{module_kind}",', "}", ""]
    return modules, "\n".join(bp).rstrip() + "\n"

def publish(staged, vendor, device, reviewed):
    report = json.loads((staged / "report.json").read_text())
    prior = json.loads(reviewed.read_text())
    actual = report.get("files", {})
    expected = prior.get("files", {})
    if report.get("status") != "review_only_no_publication" or report.get("firmware") != "OS3.0.304.0.WPUMIXM":
        raise RuntimeError("Unknown stage report provenance")
    if set(actual) != set(expected) or len(actual) != 6:
        raise RuntimeError("Staging members differ from successful reviewed batch")
    for name in actual:
        if actual[name] != expected[name]:
            raise RuntimeError("Stock report differs from approved prior run: " + name)
        if not name.startswith("vendor_a/"):
            raise RuntimeError("Unexpected stock partition")
        data = staged / "proprietary" / "vendor" / name.removeprefix("vendor_a/")
        if not data.is_file() or data.is_symlink():
            raise RuntimeError("Missing or unsafe source: " + str(data))
        if hashlib.sha256(data.read_bytes()).hexdigest() != actual[name]["sha256"] or data.stat().st_size != actual[name]["size"]:
            raise RuntimeError("Hash/size mismatch: " + name)
    modules, bp_block = expected_modules()
    paths = {path for path, _ in modules}
    expected_paths = {n.removeprefix("vendor_a/") for n in actual}
    if paths != expected_paths:
        raise RuntimeError("Hardcoded product modules do not match validated source files")
    bp_path, mk_path = vendor/"Android.bp", vendor/"mist-vendor.mk"
    man_path = device/"proprietary-files.txt"
    bp, mk, manifest = (p.read_text() for p in (bp_path, mk_path, man_path))
    if MARKER in bp or "MIST_POWER_USB_HAL_BATCH_3" in mk:
        raise RuntimeError("Already published this batch")
    for path, module in modules:
        if f'name: "{module}"' in bp or module in mk.split():
            raise RuntimeError("Module name already exists: " + module)
        dest = vendor/"proprietary/vendor"/path
        if dest.exists() or dest.is_symlink():
            raise RuntimeError("Vendor path already present: " + path)
        if "vendor/" + path in {ln.strip() for ln in manifest.splitlines()}:
            raise RuntimeError("Device extraction path already present: " + path)
    for path, _ in modules:
        source = staged/"proprietary/vendor"/path
        dest = vendor/"proprietary/vendor"/path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    bp_path.write_text(bp.rstrip()+"\n\n"+bp_block)
    mk_path.write_text(mk.rstrip()+"\n\n# MIST_POWER_USB_HAL_BATCH_3\nPRODUCT_PACKAGES += \\\n    "+" \\\n    ".join(m for _, m in modules)+"\n")
    man_path.write_text(manifest.rstrip()+"\n\n# Stock Mist Power/USB HALs (review run 43526702989)\n"+
                        "\n".join("vendor/"+p for p, _ in modules)+"\n")
    print("Wrote 6 hash-confirmed blobs, 6 vendor modules, and 6 device manifest entries")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--staged", type=Path, required=True)
    p.add_argument("--vendor", type=Path, required=True)
    p.add_argument("--device", type=Path, required=True)
    p.add_argument("--reviewed", type=Path, required=True)
    a=p.parse_args()
    publish(a.staged,a.vendor,a.device,a.reviewed)
