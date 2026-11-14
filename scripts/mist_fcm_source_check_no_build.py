#!/usr/bin/env python3
"""Try existing framework FCM source files against each Mist VINTF SKU, no build.

Uses installed assemble_vintf -c check path; check outcome is a focused source
diagnostic, NOT full target-generated VINTF or runtime certification.
"""
import argparse,json,os,subprocess,tempfile,xml.etree.ElementTree as ET
from pathlib import Path

def run(argv,env=None):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=40,env=env)
        return {"exit":p.returncode,"stderr":p.stderr[-1500:],"stdout":p.stdout[-500:]}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {"exit":-1,"stderr":str(e),"stdout":""}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    a=ap.parse_args()
    root=a.root.resolve()
    assembler=root/"out/host/linux-x86/bin/assemble_vintf"
    vendor=root/"vendor/xiaomi/mist/proprietary"
    if not assembler.is_file():ap.error("No installed assemble_vintf: cannot run no-build tests")
    xmlroot=root/"hardware/interfaces/compatibility_matrices"
    if not xmlroot.is_dir():ap.error("No hardware/interfaces framework matrices in source checkout")
    fm=[]
    for p in sorted(xmlroot.glob("*.xml")):
        try:
            r=ET.parse(p).getroot()
            if r.tag=="compatibility-matrix" and r.get("type")=="framework":fm.append(p)
        except ET.ParseError:pass
    if not fm:ap.error("No valid source framework FCM XML found")
    common=sorted((vendor/"vendor/etc/vintf/manifest").glob("*.xml"))
    # These are all stock fragments. They may include disabled platform-owned
    # services, so do not turn this diagnostic into a 'production merged pass'.
    skus=sorted((vendor/"odm/etc/vintf").glob("manifest_*.xml"))
    results={}
    with tempfile.TemporaryDirectory(prefix="mist-fcm-check-") as temp:
        for sku in skus:
            merged=Path(temp)/(sku.stem+".xml")
            assembly=run([str(assembler),"-i",":".join(map(str,common+[sku])),"-o",str(merged)])
            checks={}
            if assembly["exit"]==0:
                for matrix in fm:
                    env=dict(os.environ,PRODUCT_ENFORCE_VINTF_MANIFEST="true")
                    # -c performs a host-libvintf compatibility comparison.
                    # Android FCM files can contain build-time expressions;
                    # error output is preserved verbatim as evidence.
                    checks[matrix.name]=run([str(assembler),"-i",str(matrix),
                        "-o",str(Path(temp)/(sku.stem+"-"+matrix.name)),
                        "-c",str(merged)],env=env)
            results[sku.stem]={"assemble":assembly,"framework_matrix_checks":checks}
    success_count=sum(1 for x in results.values() for r in x["framework_matrix_checks"].values() if r["exit"]==0)
    report={"mode":"SOURCE_FCM_CANDIDATE_COMPATIBILITY_NO_BUILD",
        "framework_matrix_candidates":[str(p.relative_to(root)) for p in fm],
        "sku_variants":results,"successful_compatibility_checks":success_count,
        "source_only":True,"complete_merged_target_vintf_compatible":False,
        "warning":"Uses stock unselected fragments and individual source framework FCMs, not generated target framework matrices/manifests. A PASS here is only diagnostic."}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("Source FCM candidates:",len(fm),"SKU cases:",len(results),"check exit zero:",success_count)
    print("Report:",a.out)
if __name__=="__main__":main()
