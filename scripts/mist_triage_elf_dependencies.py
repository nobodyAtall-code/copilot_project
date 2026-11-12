#!/usr/bin/env python3
"""Triage repeated DT_NEEDED edges without claiming system/APEX runtime closure."""
import argparse
import collections
import json
from pathlib import Path

# Candidates below are hints only. Actual namespace/APEX availability needs
# matching Android 16 partition and dynamic linker evidence.
FRAMEWORK_HINTS={"libc.so","libm.so","libdl.so","liblog.so","libc++.so",
 "libbase.so","libutils.so","libbinder.so","libbinder_ndk.so",
 "libhardware.so","libz.so","libcrypto.so","libssl.so",
 "libnativewindow.so","libsync.so","libcutils.so"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True,type=Path)
    p.add_argument("--json",required=True,type=Path)
    p.add_argument("--markdown",required=True,type=Path)
    a=p.parse_args()
    d=json.loads(a.input.read_text())
    edges=collections.defaultdict(set)
    misses=collections.defaultdict(set)
    present=collections.defaultdict(set)
    for node in d.get("dependency_graph",[]):
        origin=node.get("path")
        for dep in node.get("dependencies",[]):
            soname=dep.get("soname")
            if not origin or not soname:continue
            edges[soname].add(origin)
            (misses if dep.get("matched_path") is None else present)[soname].add(origin)
    rows=[]
    for name in sorted(misses):
        rows.append({"soname":name,"unresolved_origin_count":len(misses[name]),
          "archive_resolved_origin_count":len(present.get(name,set())),
          "classification":"system_or_apex_candidate_unverified" if name in FRAMEWORK_HINTS
              else "needs_partition_namespace_investigation",
          "sample_origins":sorted(misses[name])[:5]})
    rows.sort(key=lambda x:(-x["unresolved_origin_count"],x["soname"]))
    output={"scope":"deduplicated static stock archive DT_NEEDED inventory",
      "total_dependency_edges_from_graph":sum(len(node.get("dependencies",[])) for node in d.get("dependency_graph",[])),
      "unresolved_edges_from_graph":sum(1 for node in d.get("dependency_graph",[]) for dep in node.get("dependencies",[]) if dep.get("matched_path") is None),
      "unique_unresolved_sonames":len(rows),
      "unique_candidate_system_apex_sonames":sum(r["classification"]=="system_or_apex_candidate_unverified" for r in rows),
      "unresolved_sonames":rows,
      "runtime_linker_namespace_verified":False,"system_apex_availability_verified":False,
      "warning":"An edge may repeat across ELF files; unresolved in stock archive does not imply missing at runtime."}
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(output,indent=2)+"\n")
    lines=["# Mist stock ELF dependency triage","",
      "This is static analysis; candidates for system/APEX are **not** confirmed runtime libraries.","",
      f"Unresolved graph edges: **{output['unresolved_edges_from_graph']}**",
      f"Distinct unresolved SONAMEs: **{len(rows)}**","",
      "| SONAME | Unresolved source ELF count | Triage |","|---|---:|---|"]
    for row in rows:
        lines.append(f"| `{row['soname']}` | {row['unresolved_origin_count']} | {row['classification']} |")
    a.markdown.parent.mkdir(parents=True,exist_ok=True)
    a.markdown.write_text("\n".join(lines)+"\n")
    print(json.dumps({k:output[k] for k in ("unresolved_edges_from_graph","unique_unresolved_sonames","unique_candidate_system_apex_sonames")},indent=2))
if __name__=="__main__":
    main()
