#!/usr/bin/env python3
"""Run installed libvintf assembler on source-selected Mist vendor + each ODM SKU.

No Soong/Kati/Ninja and no firmware download or device writes. This checks
syntax/merge semantics, NOT framework FCM compatibility or device runtime.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path.home()/"android/lineage")
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--assembler",type=Path)
    args=ap.parse_args()
    root=args.root.expanduser().resolve()
    assembler=args.assembler or root/"out/host/linux-x86/bin/assemble_vintf"
    vendor=root/"vendor/xiaomi/mist"
    script=Path(__file__).resolve().parent/"check_mist_vintf_offline.py"
    if not assembler.is_file() or not vendor.is_dir() or not script.is_file():
        raise SystemExit("Missing assembler, vendor source or existing VINTF source audit")
    with tempfile.TemporaryDirectory(prefix="mist-vintf-") as temp:
        temp=Path(temp)
        audit=temp/"source.json"
        cmd=[sys.executable,str(script),"--root",str(root),"--output",str(audit)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
        if not audit.is_file():
            raise SystemExit("Source audit did not produce JSON: "+p.stderr[-900:])
        src=json.loads(audit.read_text())
        paths=src.get("selected_vintf_fragments",[])
        skus=sorted(x for x in paths if x.startswith("proprietary/odm/etc/vintf/manifest_"))
        common=sorted(set(paths)-set(skus))
        results={}
        for name in skus:
            sku=Path(name).stem.removeprefix("manifest_")
            # Keep ODM in a separate input to model one selected boot SKU.
            selected=common+[name]
            inputs=[vendor/x for x in selected]
            missing=[str(p) for p in inputs if not p.is_file()]
            if missing:
                results[sku]={"status":"BLOCKED","missing_inputs":missing}
                continue
            output=temp/(sku+".xml")
            argv=[str(assembler),"-i",":".join(map(str,inputs)),"-o",str(output)]
            q=subprocess.run(argv,capture_output=True,text=True,timeout=120,env=None)
            results[sku]={
              "status":"PASS" if q.returncode==0 and output.is_file() and output.stat().st_size>0 else "FAILED",
              "assembler_exit":q.returncode,
              "inputs":selected,
              "merged_output_bytes":output.stat().st_size if output.is_file() else 0,
              "stderr_tail":q.stderr[-2400:],
              "stdout_tail":q.stdout[-800:],
            }
        result={
         "mode":"LOCAL_LIBVINTF_ASSEMBLY_NO_BUILD",
         "source_audit_exit":p.returncode,
         "source_audit_errors":src.get("errors",[]),
         "sku_count":len(skus),
         "results":results,
         "all_skus_assembled":len(skus)==6 and not src.get("errors") and
                                p.returncode==0 and all(v["status"]=="PASS" for v in results.values()),
         "full_merged_framework_device_vintf_compatible":False,
         "on_device_runtime_verified":False,
         "notes":"Assembles selected stock vendor HAL fragments and each ODM SKU independently; framework matrices, generated platform manifests, FCM and runtime are not supplied."
        }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"all_skus_assembled":result["all_skus_assembled"],"sku_results":{k:v["status"] for k,v in results.items()}},indent=2))
    print("Report:",args.out)
    if not result["all_skus_assembled"]:
        raise SystemExit(1)

if __name__=="__main__":
    main()
