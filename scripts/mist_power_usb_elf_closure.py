#!/usr/bin/env python3
"""Fail-closed stock ELF dependency report for the published Mist Power/USB services."""
import argparse
import json
from collections import defaultdict, deque
from pathlib import Path

SEEDS = [
    "vendor_a/bin/hw/android.hardware.power-service",
    "vendor_a/bin/hw/android.hardware.usb-service.qti",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    a = parser.parse_args()
    data = json.loads(a.graph.read_text())
    nodes = {x["path"]: x for x in data["dependency_graph"]}
    results = []
    for seed in SEEDS:
        if seed not in nodes or "dependencies" not in nodes[seed]:
            raise SystemExit("Missing parseable seed ELF: "+seed)
        queue, visited = deque([seed]), set()
        resolved, unresolved = defaultdict(set), defaultdict(set)
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            node = nodes.get(current)
            if node is None or "dependencies" not in node:
                raise SystemExit("Incomplete recursive graph for "+current)
            for dep in node["dependencies"]:
                soname = dep["soname"]
                dest = dep.get("matched_path")
                if dest:
                    resolved[dest].add(current)
                    if dest not in visited:
                        queue.append(dest)
                else:
                    unresolved[soname].add(current)
        results.append({
            "seed": seed, "elf_graph_nodes": len(visited),
            "stock_resolved_dependencies": [
                {"path":path,"required_by":sorted(parents)}
                for path,parents in sorted(resolved.items())
            ],
            "unresolved_sonames": [
                {"soname":name,"required_by":sorted(parents)}
                for name,parents in sorted(unresolved.items())
            ]
        })
    report = {
        "firmware": "OS3.0.304.0.WPUMIXM",
        "vendor_main_commit": "3446338",
        "device_main_commit": "41666b8",
        "seeds": results,
        "approved_for_full_rom_build": False,
        "limitations": [
            "Archive-local DT_NEEDED closure is not Android 16 platform/APEX linker namespace validation",
            "Dynamic dlopen, VINTF/SELinux, Soong platform ownership and runtime ABI are not validated"
        ],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    for r in results:
        print(r["seed"],"nodes",r["elf_graph_nodes"],
              "stock deps",len(r["stock_resolved_dependencies"]),
              "unresolved sonames",len(r["unresolved_sonames"]))

if __name__ == "__main__":
    main()
