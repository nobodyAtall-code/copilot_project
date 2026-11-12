#!/usr/bin/env python3
"""Research-only inventory, candidate list and source archive for stock mist blobs."""
import csv
import hashlib
import os
import pathlib
import subprocess

ROOT = pathlib.Path("work/mounts")
REPORTS = pathlib.Path("reports")
REPORTS.mkdir(exist_ok=True)
PARTITIONS = {
    "vendor_a": "vendor",
    "odm_a": "odm",
    "vendor_dlkm_a": "vendor_dlkm",
    "system_dlkm_a": "system_dlkm",
}
# These are deliberately not automatic production dependencies.
SKIP_PREFIXES = (
    "app/", "priv-app/", "overlay/", "apex/",
    "etc/selinux/precompiled_sepolicy",
)
SKIP_EXACT = {
    "build.prop", "etc/build.prop", "etc/NOTICE.xml.gz", "etc/NOTICE_GPL.html.gz",
}
SKIP_SUFFIXES = (".apk", ".odex", ".vdex", ".art", ".oat", ".pem", ".pk8", ".key")
SOURCE_DIRS = ("vendor_a", "odm_a", "vendor_dlkm_a", "system_dlkm_a")
for name in SOURCE_DIRS:
    if not (ROOT / name).is_mount():
        raise RuntimeError(f"Required stock partition not mounted: {name}")
entries = []
excluded = []
all_rows = []
with (REPORTS / "all-files.tsv").open(newline="") as inp:
    all_rows = list(csv.DictReader(inp, delimiter="\t"))
for row in all_rows:
    part = row["partition"]
    if part not in PARTITIONS:
        continue
    p = row["path"]
    if p.startswith("/") or any(x in (".", "..") for x in pathlib.PurePosixPath(p).parts):
        raise RuntimeError(f"Unsafe path: {p!r}")
    if part in ("vendor_dlkm_a", "system_dlkm_a"):
        # Kernel modules will be handled with kernel prebuilt packaging.
        continue
    reason = None
    if row["kind"] not in ("file", "symlink"):
        reason = "unsupported file type"
    elif p in SKIP_EXACT:
        reason = "stock metadata"
    elif p.startswith(SKIP_PREFIXES):
        reason = "hyperos application/overlay or precompiled policy"
    elif p.endswith(SKIP_SUFFIXES):
        reason = "package, generated binary or key-like file"
    if reason:
        excluded.append((PARTITIONS[part], p, reason))
    else:
        entries.append((PARTITIONS[part], p, row["kind"]))
if not entries or len(entries) < 1000:
    raise RuntimeError(f"Unexpected candidate count: {len(entries)}")
with (REPORTS / "proprietary-candidates.txt").open("w") as out:
    out.write("# Mist Global OS3.0.304.0.WPUMIXM — review candidates, NOT yet production-approved\n")
    out.write("# Generated from mounted EROFS stock images. Review for LineageOS 23.2.\n")
    out.write("# Kernel modules are staged separately, not duplicated here.\n")
    for partition in ("vendor", "odm"):
        out.write(f"\n# {partition.upper()} — stock candidates\n")
        for part, p, kind in sorted(entries):
            if part == partition:
                out.write(f"{part}/{p}\n")
with (REPORTS / "candidate-exclusions.tsv").open("w") as out:
    out.write("partition\tpath\treason\n")
    for part, p, reason in sorted(excluded):
        out.write(f"{part}\t{p}\t{reason}\n")
(REPORTS / "candidate-summary.txt").write_text(
    "firmware=OS3.0.304.0.WPUMIXM\n"
    f"vendor_odm_candidates={len(entries)}\n"
    f"candidate_exclusions={len(excluded)}\n"
    "source_archive_partitions=vendor_a,odm_a,vendor_dlkm_a,system_dlkm_a\n"
)

archive = REPORTS / "stock-vendor-source.tar.zst"
subprocess.run(
    ["tar", "-C", str(ROOT), "--create", "--use-compress-program=zstd",
     "--file", str(archive), *SOURCE_DIRS],
    check=True,
)
digest = hashlib.sha256()
with archive.open("rb") as stream:
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
        digest.update(chunk)
(REPORTS / "stock-vendor-source.sha256").write_text(
    f"{digest.hexdigest()}  {archive.name}\n"
)
print(f"Review candidates: {len(entries)}; exclusions: {len(excluded)}", flush=True)
print(f"Stock source archive: {archive.stat().st_size / 1048576:.1f} MiB", flush=True)
