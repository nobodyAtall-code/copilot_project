#!/usr/bin/env python3
"""Verify pinned MiCode mist-w-oss revisions without overwriting any checkout."""
import argparse
import json
import os
from pathlib import Path
import urllib.request

def fetch(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "mist-lineage-preflight"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    req = urllib.request.Request("https://api.github.com" + path, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text())
    if lock["upstream_branch"] != "mist-w-oss":
        raise RuntimeError("Unexpected branch")
    results = []
    for src in lock["sources"]:
        item = fetch("/repos/" + src["repo"] + "/commits/" + src["ref"])
        if item["sha"] != src["sha"] or item["commit"]["tree"]["sha"] != src["tree"]:
            raise RuntimeError("Pinned revision changed: " + src["repo"])
        results.append({"repo": src["repo"], "ref": src["ref"], "sha": src["sha"], "tree": src["tree"]})
    sources = {x["repo"]:x for x in results}
    if sources["nobodyAtall-code/kernel_build"]["tree"] != sources["MiCode/kernel_build"]["tree"]:
        raise RuntimeError("Owned kernel_build content diverges from MiCode")
    paths = [("MiCode/kernel_devicetree", "qcom/mist-common.dtsi", "mist-w-oss"),
             ("MiCode/kernel_devicetree", "qcom/mist-qrd-overlay.dts", "mist-w-oss"),
             ("nobodyAtall-code/android_kernel_xiaomi_mist", "build.config.msm.mist", "main"),
             ("nobodyAtall-code/android_kernel_xiaomi_mist", "mist.bzl", "main")]
    for repo, path, branch in paths:
        item = fetch("/repos/" + repo + "/contents/" + path + "?ref=" + branch)
        if item.get("type") != "file" or item.get("size", 0) < 100:
            raise RuntimeError("Missing or unexpectedly short source: " + repo + "/" + path)
    report = {"result": "PASS", "source_pins": results,
              "identical_kernel_build_tree": True,
              "required_paths": [dict(repo=r,path=p,ref=b) for r,p,b in paths],
              "limitations": "No compilation, ABI, DTBO equivalence or ROM boot was tested"}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    lines = ["# MiCode Mist kernel source preflight","",
             "PASS: " + str(len(results)) + " pinned upstream/owned revisions and required files verified.","",
             "Correct upstream branch: mist-w-oss, NOT mist-oss.","",
             "Owned kernel_build matches upstream tracked source tree; no reset/clone replacement required.","",
             "## Verified source pins",""]
    for src in results:
        lines.append("- " + src["repo"] + " (" + src["ref"] + "): " + src["sha"])
    lines += ["","## Still required","",
              "- Isolated Kleaf workspace with compiler, Bazel and all external kernel module directories",
              "- Full source build, generated DTB/DTBO comparison with verified stock firmware",
              "- Module ABI and boot validation before switching away from stock kernel prebuilt",
              "","This PASS is source provenance only, not a successful kernel build.",""]
    args.report.with_suffix(".md").write_text("\n".join(lines))
    print("Source preflight passed:", len(results), "pinned revisions", len(paths), "source paths")
if __name__ == "__main__":
    main()
