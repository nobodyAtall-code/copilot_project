#!/usr/bin/env python3
"""Validate an isolated Xiaomi mist Kleaf source layout (never modify owner repos).

Expected GitHub Actions workspace:
  build/kernel/   -> owned kernel_build at pinned revision
  msm-kernel/     -> owned Xiaomi kernel at pinned revision
  msm-kernel/arch/arm64/boot/dts/vendor/ -> MiCode kernel_devicetree
"""
import argparse
import json
from pathlib import Path

REQUIRED = {
 "build/kernel/BUILD.bazel":"Owned kernel_build/Kleaf implementation",
 "build/kernel/kleaf/kernel.bzl":"Kleaf build rules",
 "msm-kernel/BUILD.bazel":"Owned Mist kernel Bazel targets",
 "msm-kernel/build.config.msm.mist":"Xiaomi mist build configuration",
 "msm-kernel/mist.bzl":"Mist Kleaf definitions",
 "msm-kernel/msm_kernel_extensions.bzl":"DTS wiring and platform map",
 "msm-kernel/arch/arm64/boot/dts/vendor/BUILD.bazel":"MiCode kernel_dtstree Bazel package",
 "msm-kernel/arch/arm64/boot/dts/vendor/qcom/platform_map.bzl":"MiCode Qualcomm DTB/DTBO selection",
 "msm-kernel/arch/arm64/boot/dts/vendor/qcom/mist-common.dtsi":"Mist hardware DTS",
 "msm-kernel/arch/arm64/boot/dts/vendor/qcom/mist-qrd-overlay.dts":"Mist hardware overlay",
}
EXTERNAL_MARKERS = {
 "build/bazel_common_rules/dist/dist.bzl":"Kernel Bazel common distribution rules",
 "common/BUILD.bazel":"Android Common Kernel target",
 "prebuilts/clang/host/linux-x86":"Pinned Clang toolchain",
 "prebuilts/kernel-build-tools":"Kernel image and dist tools",
 "prebuilts/build-tools":"Bazel build utilities",
 "tools/mkbootimg":"Boot image packaging tools",
 "external/dtc":"Device tree compiler",
 "build/build-tools":"Build tools (separate from build/kernel)",
 "build/bazel_common_rules":"Bazel shared rules",
}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--root",type=Path,required=True)
 p.add_argument("--out",type=Path,required=True)
 args=p.parse_args()
 root=args.root.resolve()
 resolved={}
 for name,comment in REQUIRED.items():
  path=root/name
  resolved[name]={"present":path.is_file(), "role":comment}
 missing=[k for k,v in resolved.items() if not v["present"]]
 external={k:{"present":(root/k).exists(),"purpose":v} for k,v in EXTERNAL_MARKERS.items()}
 extensions=(root/"msm-kernel/msm_kernel_extensions.bzl").read_text() if not missing else ""
 if extensions and "arch/arm64/boot/dts/vendor:qcom/platform_map.bzl" not in extensions:
  # The canonical label starts //msm-kernel/.../vendor:qcom/platform_map.bzl
  if "platform_map.bzl" not in extensions:
   raise RuntimeError("Mist kernel no longer references expected Qualcomm platform map")
 variant=(root/"msm-kernel/mist.bzl").read_text() if not missing else ""
 if variant and "def define_mist():" not in variant:
  raise RuntimeError("Mist Bazel target registration missing")
 if variant and "define_msm_la(" not in variant:
  raise RuntimeError("Mist kernel build macro missing")
 result={"required":resolved,"required_missing":missing,"external":external,
         "external_missing":[k for k,v in external.items() if not v["present"]],
         "assembled_source_layout_valid":not missing,
         "kernel_compiled":False,
         "limitations":"Bazel evaluation, external dependencies, compilation, module ABI, DTBO match and boot all untested"}
 args.out.parent.mkdir(parents=True,exist_ok=True)
 args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 md=["# Mist isolated kernel source layout gate","","**Assembled core Kleaf layout:** "+("PASS" if not missing else "FAIL"),"",
     "Core source paths checked: "+str(len(REQUIRED)),"",
     "## Missing source paths", ""]
 md.extend("- "+x for x in missing)
 md+=["","## External projects not yet staged",""]
 md.extend("- "+name+" — "+val["purpose"] for name,val in external.items() if not val["present"])
 md+=["","This is **not** a successful Bazel query or kernel build.",""]
 args.out.with_suffix(".md").write_text("\n".join(md))
 print("Source path checks:",len(REQUIRED)-len(missing),"/",len(REQUIRED),
       "; external prerequisites absent:",len(result["external_missing"]))
 if missing:
  raise SystemExit("Missing essential Mist source paths: "+", ".join(missing))

if __name__=="__main__":
 main()
