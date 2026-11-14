#!/usr/bin/env python3
"""Audit stock SELinux context coverage against actual HAL/init executable paths.

Consumes existing verified stock policy evidence and current mounted stock
partitions; never exports policy binaries or invents allow rules.
"""
import argparse, json, pathlib, re, collections

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--evidence", type=pathlib.Path, required=True)
    p.add_argument("--mounts", type=pathlib.Path, required=True)
    p.add_argument("--vendor-tree", type=pathlib.Path, required=True)
    p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args()
    data=json.loads(a.evidence.read_text())
    files={pathlib.PurePosixPath(x["path"]).name:x for x in data["stock_files"]}
    filectx=files["vendor_file_contexts"]["matching_context_lines"]
    servicectx=files["vendor_service_contexts"]["matching_context_lines"]
    hwctx=files["vendor_hwservice_contexts"]["matching_context_lines"]
    names={
      "camera_perfopt":"/vendor/bin/init.qti.cam.perfopt.sh",
      "camera_provider":"/vendor/bin/hw/vendor.qti.camera.provider-service_64",
      "keymint":"/vendor/bin/hw/android.hardware.security.keymint-service-qti",
      "qseecomd":"/vendor/bin/qseecomd",
      "qsee_service":"/vendor/bin/hw/vendor.qti.hardware.qseecom@1.0-service"
    }
    contexts=[]
    for line in filectx:
        parts=line.split()
        if len(parts)<2: continue
        try:pat=re.compile(parts[0])
        except re.error:continue
        contexts.append((parts[0],parts[1],pat))
    resolution={}
    for key, path in names.items():
        matches=[{"pattern":pat,"context":label} for pat,label,rx in contexts if rx.fullmatch(path)]
        stockpath=a.mounts/"vendor_a"/path.removeprefix("/vendor/")
        curated=a.vendor_tree/"proprietary/vendor"/path.removeprefix("/vendor/")
        resolution[key]={"path":path,"stock_file_present":stockpath.exists(),
                         "curated_file_present":curated.exists(),
                         "matching_stock_rules":matches,
                         "status":"MATCH" if len({x["context"] for x in matches})==1 and matches else
                                  "CONFLICT" if len({x["context"] for x in matches})>1 else "NO_MATCH_IN_FILTERED_EVIDENCE"}
    report={
      "source":"existing SHA256-verified mist-keymint-selinux-stock-evidence.json",
      "service_file_labels":resolution,
      "relevant_binder_services":servicectx,
      "relevant_hwbinder_services":hwctx,
      "policy_files":{
        "vendor_cil_in_stock":(a.mounts/"vendor_a/etc/selinux/vendor_sepolicy.cil").is_file(),
        "odm_cil_in_stock":(a.mounts/"odm_a/etc/selinux/odm_sepolicy.cil").is_file(),
        "stock_vendor_file_contexts":(a.mounts/"vendor_a/etc/selinux/vendor_file_contexts").is_file(),
      },
      "limitations":[
        "Only firmware-proven filtered contexts are compared: other valid file-context patterns can exist",
        "No assumption that original stock CIL can be reused as Lineage policy",
        "No platform/Qualcomm .te source policy compiled; neverallow and on-device enforcement unverified",
        "Service names not listed in filtered evidence are not automatically missing"]
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("Mist stock SELinux contexts vs source paths:")
    for key,x in resolution.items():
        print(key, x["status"],x["stock_file_present"],x["curated_file_present"],
              [t["context"] for t in x["matching_stock_rules"]])
if __name__=="__main__":main()
