#!/usr/bin/env python3
"""Stage exactly two mist stock HAL service triples for review; never publish blindly."""
import argparse
import hashlib
import json
import subprocess
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

SERVICES = {
    "usb": {
        "binary": "vendor_a/bin/hw/android.hardware.usb-service.qti",
        "rc": "vendor_a/etc/init/android.hardware.usb-service.qti.rc",
        "xml": "vendor_a/etc/vintf/manifest/android.hardware.usb-service.qti.xml",
        "hal": "android.hardware.usb",
    },
    "power": {
        "binary": "vendor_a/bin/hw/android.hardware.power-service",
        "rc": "vendor_a/etc/init/android.hardware.power-service.rc",
        "xml": "vendor_a/etc/vintf/manifest/power.xml",
        "hal": "android.hardware.power",
    },
}
LIMIT = 32 * 1024 * 1024

def run(archive, stock_config, membership, dest):
    config = json.loads(stock_config.read_text())
    archive_evidence = json.loads(membership.read_text())
    known = {(entry["file"], service["binary"]): service
             for entry in config["init_files"]
             for service in entry["services"]}
    membership_paths = {(e["archive_path"], e["rc"]): e for e in archive_evidence["service_executables"]}
    xml_hals = {x["file"]: {h["name"] for h in x["hals"]} for x in config["vintf_files"]}
    allowed = {}
    for subsystem, v in SERVICES.items():
        binary = "/"+v["binary"].replace("vendor_a/", "vendor/", 1)
        if (v["rc"], binary) not in known:
            raise ValueError(f"{subsystem}: RC executable not in audit")
        if not membership_paths.get((v["binary"], v["rc"]), {}).get("present", False):
            raise ValueError(f"{subsystem}: executable missing from stock archive evidence")
        if v["hal"] not in xml_hals.get(v["xml"], set()):
            raise ValueError(f"{subsystem}: VINTF declaration mismatch")
        for kind in ("binary","rc","xml"):
            path = v[kind]
            if path in allowed:
                raise ValueError("duplicate allowlisted path: " + path)
            allowed[path] = (subsystem, kind)
    seen = {}
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(["zstd","-dc","--",str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for item in tar:
                name = item.name.removeprefix("./")
                if name not in allowed:
                    continue
                if name in seen or not item.isfile() or not 0 < item.size <= LIMIT:
                    raise ValueError("duplicate, oversized or invalid archive entry: "+name)
                data = tar.extractfile(item).read(LIMIT+1)
                if len(data) != item.size:
                    raise ValueError("truncated archive entry: "+name)
                subsystem, kind = allowed[name]
                if kind == "binary":
                    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1 or int.from_bytes(data[18:20],"little") != 183:
                        raise ValueError("not ELF64 AArch64: "+name)
                elif kind == "rc":
                    expected = SERVICES[subsystem]["binary"].replace("vendor_a/","/vendor/",1)
                    if not any(line.strip().startswith("service ") and expected in line.split() for line in data.decode().splitlines()):
                        raise ValueError("RC does not reference selected binary: "+name)
                elif kind == "xml":
                    root = ET.fromstring(data)
                    if root.tag != "manifest" or SERVICES[subsystem]["hal"] not in [(h.findtext("name") or "").strip() for h in root.findall("hal")]:
                        raise ValueError("XML does not declare selected HAL: "+name)
                target = dest/"proprietary"/"vendor"/name.removeprefix("vendor_a/")
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
                seen[name] = {"sha256":hashlib.sha256(data).hexdigest(),"size":len(data),"type":kind}
    finally:
        proc.stdout.close()
        exit_code=proc.wait()
    if exit_code:
        raise RuntimeError("zstd decompression failed")
    if set(seen) != set(allowed):
        raise RuntimeError("missing stock files: "+str(sorted(set(allowed)-set(seen))))
    report={"firmware":"OS3.0.304.0.WPUMIXM","files":seen,"status":"review_only_no_publication","limitations":"ELF DT_NEEDED, Lineage module collisions, SEPolicy, VINTF runtime and boot unverified"}
    (dest/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("Verified and staged",len(seen),"stock files from",len(SERVICES),"services; NO PRODUCTION PUSH")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--stock-config",type=Path,required=True)
    p.add_argument("--membership",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    run(a.archive,a.stock_config,a.membership,a.out)
