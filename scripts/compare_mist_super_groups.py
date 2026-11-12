#!/usr/bin/env python3
"""Compare independently read Go liblp group descriptors with Python report.

Verifies group names, max bytes, allocations, partition membership. This is a
second implementation, NOT an official AOSP lpdump result or OTA layout proof.
"""
import argparse
import json
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python-report", type=Path, required=True)
    ap.add_argument("--go-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    original = json.loads(a.python_report.read_text())
    go_groups = json.loads(a.go_report.read_text())
    if not original.get("integrity_checks_passed"):
        raise SystemExit("Existing Python slot integrity failed")
    source = original["slots"][0]["primary"]["data"]["groups"]
    fields = ("maximum_size", "allocated_bytes", "partitions", "flags")
    def normalize(rec):
        return {k: sorted(rec[k]) if k == "partitions" else rec[k] for k in fields}
    expected = {g["name"]: normalize(g) for g in source}
    independent = {g["name"]: normalize(g) for g in go_groups}
    if len(expected) != len(source) or len(independent) != len(go_groups):
        raise SystemExit("Duplicate group name")
    missing = sorted(set(expected) - set(independent))
    extra = sorted(set(independent) - set(expected))
    differing = {k: {"python": expected[k], "go": independent[k]}
                 for k in sorted(set(expected) & set(independent))
                 if expected[k] != independent[k]}
    ok = not (missing or extra or differing)
    result = {"independent_tool": "Go group descriptor reader using pinned upstream super.go",
              "comparison": "group names, flags, maxima, allocated bytes, full membership",
              "groups_match": ok, "expected": expected, "independent": independent,
              "missing": missing, "unexpected": extra, "differing": differing,
              "official_aosp_lpdump_confirmed": False,
              "virtual_ab_ota_or_mi_ext_repackaging_validated": False,
              "production_boardconfig_validated": False}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"groups_match": ok, "expected_groups": len(expected),
                      "missing": missing, "unexpected": extra,
                      "differing": differing}, indent=2))
    if not ok:
        raise SystemExit("Go/Python LP group metadata differs")

if __name__ == "__main__":
    main()
