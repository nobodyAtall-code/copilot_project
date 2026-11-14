#!/usr/bin/env python3
"""Resolve exact stock Mist KeyMint hashes and camera/TEE SELinux labels.

Read-only. Uses the original checksum-verified vendor/odm archive, never
publishes binary policy, original scripts or unrelated stock contents.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import tarfile

NEEDED = {
    "vendor_a/etc/vintf/manifest/android.hardware.security.keymint-service-qti.xml": "keymint_vintf",
    "vendor_a/etc/init/android.hardware.security.keymint-service-qti.rc": "keymint_rc",
    "vendor_a/etc/selinux/vendor_file_contexts": "file_contexts",
    "vendor_a/etc/selinux/vendor_service_contexts": "service_contexts",
    "vendor_a/etc/selinux/vendor_hwservice_contexts": "hwservice_contexts",
    "vendor_a/etc/selinux/vendor_sepolicy.cil": "vendor_cil",
    "odm_a/etc/selinux/odm_file_contexts": "odm_file_contexts",
    "odm_a/etc/selinux/odm_sepolicy.cil": "odm_cil",
}
MATCH = re.compile(r"(?i)camera|perfopt|keymint|keymaster|qsee|drmrpc|vendor_qti_init_shell|keystore")
MAX_MATCH = 90

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--archive", required=True, type=pathlib.Path)
    a.add_argument("--sha256", required=True, type=pathlib.Path)
    a.add_argument("--vendor-tree", required=True, type=pathlib.Path)
    a.add_argument("--out", required=True, type=pathlib.Path)
    args = a.parse_args()
    verify = subprocess.run(["sha256sum", "-c", args.sha256.name],
                            cwd=args.archive.parent, capture_output=True, text=True)
    if verify.returncode or args.archive.name + ": OK" not in verify.stdout:
        raise SystemExit("Original archive checksum failed: " + verify.stdout + verify.stderr)
    found = {}
    child = subprocess.Popen(["zstd", "-dc", "--", str(args.archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=child.stdout, mode="r|") as tar:
            for member in tar:
                path = member.name.removeprefix("./")
                if path not in NEEDED:
                    continue
                if not member.isfile() or member.size > 4 * 1024 * 1024:
                    raise SystemExit("Unexpected stock file type or size " + path)
                data = tar.extractfile(member).read()
                info = {"path": path, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()}
                if path.endswith("contexts"):
                    rows = []
                    for line in data.decode("utf-8", "replace").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and MATCH.search(line):
                            rows.append(line[:350])
                    info["matching_context_lines"] = rows[:MAX_MATCH]
                    info["total_matching_context_lines"] = len(rows)
                found[path] = info
    finally:
        if child.stdout:
            child.stdout.close()
        code = child.wait()
        if code:
            raise SystemExit("Archive extraction failed " + str(code))
    if len(found) != len(NEEDED):
        raise SystemExit("Stock selection incomplete: " + repr(sorted(set(NEEDED) - set(found))))
    checks = []
    for path in list(NEEDED)[:2]:
        relative = pathlib.Path("proprietary") / pathlib.Path(path.replace("vendor_a/", "vendor/"))
        source = args.vendor_tree / relative
        original = found[path]
        if not source.is_file():
            checks.append({"source": str(relative), "status": "MISSING_VENDOR_SOURCE"})
        else:
            b = source.read_bytes()
            digest = hashlib.sha256(b).hexdigest()
            checks.append({"source": str(relative),
                           "status": "EXACT_MATCH" if digest == original["sha256"] else "MISMATCH",
                           "vendor_sha256": digest, "stock_sha256": original["sha256"]})
    report = {"firmware": "OS3.0.304.0.WPUMIXM",
              "source_sha256_verified": True,
              "stock_files": [found[p] for p in NEEDED],
              "keymint_vendor_source_comparison": checks,
              "limitations": ["Stock policy context lines are reference evidence, not Lineage policy rules",
                              "No checkvintf, SELinux compile/neverallow, runtime service test or flash",
                              "CIL file SHA256 metadata only; compiled vendor CIL is not source policy"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    for row in checks:
        print(row["source"] + ": " + row["status"])
    for p in NEEDED:
        n = found[p].get("total_matching_context_lines")
        if n is not None:
            print(p, "matching relevant context lines:", n)

if __name__ == "__main__":
    main()
