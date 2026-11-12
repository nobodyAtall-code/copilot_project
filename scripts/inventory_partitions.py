#!/usr/bin/env python3
"""Read-only inventory of mounted logical partitions. Research output only."""
import csv
import hashlib
import os
import pathlib
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve()
reports = pathlib.Path(sys.argv[2]).resolve()
reports.mkdir(parents=True, exist_ok=True)
libs_list = reports / "libraries.paths0"
count = 0
lib_count = 0
with (
    (reports / "all-files.tsv").open("w") as all_file,
    (reports / "libraries.tsv").open("w") as lib_file,
    libs_list.open("wb") as tar_inputs,
):
    file_csv = csv.writer(all_file, delimiter="\t", lineterminator="\n")
    lib_csv = csv.writer(lib_file, delimiter="\t", lineterminator="\n")
    file_csv.writerow(["partition", "path", "size", "kind"])
    lib_csv.writerow(["partition", "path", "size", "sha256"])
    for mount in sorted(root.iterdir()):
        if not mount.is_dir() or not os.path.ismount(mount):
            continue
        for base, dirs, files in os.walk(mount, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
            dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(base, d)))
            for filename in sorted(files):
                full = pathlib.Path(base) / filename
                rel = full.relative_to(root)
                if "\t" in str(rel) or "\n" in str(rel):
                    raise ValueError(f"Unexpected whitespace in filename: {rel!r}")
                if full.is_symlink():
                    kind = "symlink"
                    size = 0
                elif full.is_file():
                    kind = "file"
                    size = full.stat().st_size
                else:
                    kind = "other"
                    size = 0
                file_csv.writerow([mount.name, full.relative_to(mount), size, kind])
                count += 1
                if filename.endswith(".so") or ".so." in filename:
                    if kind == "other":
                        continue
                    digest = ""
                    if kind == "file":
                        sha = hashlib.sha256()
                        with full.open("rb") as stream:
                            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                                sha.update(chunk)
                        digest = sha.hexdigest()
                    lib_csv.writerow([mount.name, full.relative_to(mount), size, digest])
                    tar_inputs.write(os.fsencode(str(rel)) + b"\0")
                    lib_count += 1

if lib_count == 0:
    raise RuntimeError("No .so libraries discovered; refusing empty artifact")

archive = reports / "all-shared-libraries.tar.zst"
subprocess.run(
    ["tar", "--create", "--file", str(archive), "--use-compress-program=zstd",
     "--directory", str(root), "--null", "--files-from", str(libs_list)],
    check=True,
)
libs_list.unlink()
(reports / "summary.txt").write_text(
    f"indexed_files={count}\nshared_libraries_and_symlinks={lib_count}\n"
)
print(f"Indexed {count} files and {lib_count} shared libraries/symlinks", flush=True)
print(f"Compressed shared library archive: {archive.stat().st_size} bytes", flush=True)
