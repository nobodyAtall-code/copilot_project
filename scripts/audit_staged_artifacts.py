#!/usr/bin/env python3
"""Audit an already staged mist vendor/boot archive without publishing blobs.

Input files are downloaded by a research-only workflow in copilot_project.
No output in this tool is a production proprietary-files manifest.
"""
import collections
import hashlib
import json
import pathlib
import subprocess
import sys

SOURCE = pathlib.Path("input/vendor/stock-vendor-source.tar.zst")
BOOT = pathlib.Path("input/boot")
OUT = pathlib.Path("reports/staging-audit")
OUT.mkdir(parents=True, exist_ok=True)

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def list_tar(archive):
    p = subprocess.run(["tar", "-I", "zstd", "-tf", str(archive)],
                       check=True, text=True, stdout=subprocess.PIPE)
    return [line.rstrip("/") for line in p.stdout.splitlines() if line.rstrip("/")]

if not SOURCE.is_file():
    sys.exit(f"Missing vendor source archive: {SOURCE}")
paths = list_tar(SOURCE)
if len(paths) < 1000 or not any(p.startswith("vendor_a/") for p in paths):
    sys.exit("Unexpected vendor archive layout/count")

counts = collections.Counter()
extensions = collections.Counter()
interesting = []
prefixes = (
    "vendor_a/etc/vintf/", "odm_a/etc/vintf/",
    "vendor_a/etc/init/", "odm_a/etc/init/",
    "vendor_a/etc/permissions/", "odm_a/etc/permissions/",
)
for path in paths:
    if path.startswith("/") or ".." in pathlib.PurePosixPath(path).parts:
        sys.exit(f"Unsafe archive member: {path!r}")
    part = path.split("/", 1)[0]
    counts[part] += 1
    extensions[pathlib.PurePosixPath(path).suffix.lower()] += 1
    basename = pathlib.PurePosixPath(path).name
    if (path.startswith(prefixes) or "fstab" in basename.lower()
            or basename.startswith(("modules.load", "modules.dep", "modules.blocklist",
                                     "modules.alias", "modules.softdep"))):
        interesting.append(path)

# Selected configuration only: no bulk copying firmware, services or binaries.
# tar glob matches are constrained to paths that already passed validation.
selected = [p for p in interesting if p.endswith((".xml", ".rc"))
            or "fstab" in pathlib.PurePosixPath(p).name
            or pathlib.PurePosixPath(p).name.startswith(
                ("modules.load", "modules.dep", "modules.blocklist",
                 "modules.alias", "modules.softdep"))]
selected = sorted(set(selected))
config_dir = OUT / "selected-stock-config"
config_dir.mkdir(exist_ok=True)
if selected:
    # --verbatim-files-from prevents tar from interpreting a member as an option.
    members = OUT / "config-members.txt"
    members.write_text("\n".join(selected) + "\n")
    subprocess.run(["tar", "-I", "zstd", "-xf", str(SOURCE), "-C", str(config_dir),
                    "--verbatim-files-from", "-T", str(members)],
                   check=True)
    # Do not follow links out of the extraction area during subsequent analysis.

boot_rows = []
for p in sorted(BOOT.rglob("*.img")):
    with p.open("rb") as f:
        magic = f.read(8)
    boot_rows.append(dict(file=str(p.relative_to(BOOT)), bytes=p.stat().st_size,
                          sha256=digest(p), magic_hex=magic.hex(),
                          recognized_header=("ANDROID!" if magic == b"ANDROID!"
                                             else "VNDRBOOT" if magic == b"VNDRBOOT"
                                             else "other (vbmeta/dtbo/etc)")))
if not boot_rows:
    sys.exit("Missing staged boot images")

data = dict(source_sha256=digest(SOURCE), members=len(paths),
            top_level_counts=dict(sorted(counts.items())),
            extensions=dict(extensions.most_common(25)), boot_images=boot_rows,
            selected_config_count=len(selected))
(OUT / "audit.json").write_text(json.dumps(data, indent=2) + "\n")
(OUT / "interesting-paths.txt").write_text("\n".join(sorted(set(interesting))) + "\n")
md = [
    "# Mist staged archive inspection (research only)",
    "",
    "This is an inventory, **not** an approved proprietary manifest or bootable kernel tree.",
    f"Source archive SHA256: \`{data['source_sha256']}\`",
    f"Archive members: {len(paths)}; selected config entries: {len(selected)}",
    "",
    "## Members by partition",
    *[f"- {k}: {v}" for k, v in sorted(counts.items())],
    "",
    "## Stock boot images",
    "| Image | Size (bytes) | Magic | SHA256 |",
    "| --- | ---: | --- | --- |",
    *[f"| {r['file']} | {r['bytes']} | {r['recognized_header']} | \`{r['sha256']}\` |"
      for r in boot_rows],
    "",
    "Inspect selected-stock-config/ for actual fstab, VINTF, init and module metadata.",
    "Review paths, symlinks, ELF dependencies, ABI, permissions and SELinux labels",
    "before building or committing any proprietary vendor makefile.",
]
(OUT / "README.md").write_text("\n".join(md) + "\n")
print(f"Inspected {len(paths)} archive entries and {len(boot_rows)} boot images")
