#!/usr/bin/env python3
"""Classify actual Mist HAL ELF dependencies from verified stock data."""
import argparse
import json
from pathlib import Path
from collections import defaultdict

SEEDS = (
 "vendor_a/bin/hw/android.hardware.bluetooth@aidl-service-qti",
 "vendor_a/bin/hw/android.hardware.gatekeeper-service-qti",
 "vendor_a/bin/hw/android.hardware.gnss-aidl-service-qti",
 "vendor_a/bin/hw/android.hardware.health-service.qti",
 "vendor_a/bin/hw/android.hardware.thermal-service.qti",
)

def main():
 p = argparse.ArgumentParser()
 p.add_argument("--input", required=True, type=Path)
 p.add_argument("--output", required=True, type=Path)
 p.add_argument("--vendor-manifest", required=True, type=Path)
 args = p.parse_args()
 obj = json.loads(args.input.read_text())
 graph = {x["path"]: x for x in obj["dependency_graph"]}
 missing = [x for x in SEEDS if x not in graph or "dependencies" not in graph[x]]
 if missing:
  raise SystemExit("Missing / non-ELF stock HAL seeds: " + str(missing))
 installed = set(x.strip() for x in args.vendor_manifest.read_text().splitlines() if x.startswith("vendor/"))
 found = defaultdict(set)
 unresolved = defaultdict(set)
 for record in obj["dependency_graph"]:
  for dep in record.get("dependencies", []):
   if dep["status"] == "found_in_archived_vendor_odm" and dep["matched_path"]:
    found[dep["matched_path"]].add(record["path"])
   else:
    unresolved[dep["soname"]].add(record["path"])
 def runtime(path):
  return path.replace("vendor_a/", "vendor/", 1).replace("odm_a/", "odm/", 1)
 paths = [{"stock_path": path, "runtime_path": runtime(path),
           "already_in_manifest": runtime(path) in installed, "required_by": sorted(owners)}
          for path, owners in sorted(found.items())]
 doc = {
  "seeds": list(SEEDS), "parsed_graph_nodes": len(graph),
  "stock_resolved_dependencies": len(paths),
  "not_in_current_proprietary_manifest": sum(not p["already_in_manifest"] for p in paths),
  "stock_resolved_paths": paths,
  "unresolved_sonames_not_proven_missing": [
   {"soname": name, "required_by": sorted(parents)} for name, parents in sorted(unresolved.items())],
  "limitations": ["Stock-path matches do not confirm linker namespace or ABI",
                  "Unresolved libraries may come from LineageOS, Android or APEX",
                  "No automatic production blob approval; no build or boot validation"],
 }
 args.output.parent.mkdir(parents=True, exist_ok=True)
 args.output.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
 lines = ["# Mist five-HAL recursive ELF dependency results", "",
          "Research only; do not automatically publish every dependency.", "",
          "- Parsed stock HAL executable seeds: " + str(len(SEEDS)),
          "- Recursive ELF nodes: " + str(len(graph)),
          "- Stock vendor/ODM matched dependency paths: " + str(len(paths)),
          "- Matches not in device proprietary manifest: " + str(doc["not_in_current_proprietary_manifest"]),
          "- Unresolved SONAMEs (may be framework/APEX): " + str(len(unresolved)),
          "", "## Verified stock path candidates not in device manifest", ""]
 lines.extend("- " + x["runtime_path"] for x in paths if not x["already_in_manifest"])
 lines.extend(["", "## Unresolved names: check LineageOS sources before extracting", ""])
 lines.extend("- " + name for name in sorted(unresolved))
 lines.extend(["", "No vendor artifact or final ROM is approved by this report.", ""])
 args.output.with_suffix(".md").write_text("\n".join(lines))
 print("Five HAL ELFs parsed; stock dependency candidates:", len(paths))

if __name__ == "__main__":
 main()
