#!/usr/bin/env python3
"""Mist read-only metadata/ELF inventory. Research only; never publish blobs."""
import argparse
import hashlib
import io
import json
import posixpath
import subprocess
import tarfile
from collections import deque
from pathlib import Path
from elftools.elf.elffile import ELFFile

ROOTS = ("vendor_a/", "odm_a/")
PARTITIONS = ("vendor_a/", "odm_a/", "vendor_dlkm_a/", "system_dlkm_a/")
SENSITIVE = ("persist/", "modemst", "calibration/", "userdata/", ".pem", ".pk8", ".key", "id_rsa", "/secrets/")
MAX_FILE = 80 * 1024 * 1024
SEEDS = (
    "vendor_a/bin/hw/qcrilNrd",
    "vendor_a/bin/imsdaemon",
    "vendor_a/bin/ims_rtp_daemon",
    "vendor_a/lib64/libqtikeymint.so",
    "vendor_a/lib64/libspukeymint.so",
)

def accepted(name):
    name = name.removeprefix("./").rstrip("/")
    if not name.startswith(PARTITIONS) or any(p in ("", ".", "..") for p in name.split("/")):
        return None
    if any(term in name.lower() for term in SENSITIVE):
        return None
    return name

def elf_details(data):
    if data[:4] != b"\x7fELF":
        return None
    elf = ELFFile(io.BytesIO(data))
    dynamic = elf.get_section_by_name(".dynamic")
    needed = []
    soname = None
    runpath = []
    if dynamic:
        for tag in dynamic.iter_tags():
            if tag.entry.d_tag == "DT_NEEDED":
                needed.append(tag.needed)
            elif tag.entry.d_tag == "DT_SONAME":
                soname = tag.soname
            elif tag.entry.d_tag in ("DT_RUNPATH", "DT_RPATH"):
                runpath.append(getattr(tag, "runpath", getattr(tag, "rpath", "")))
    return {"bits": elf.elfclass, "machine": elf.header.e_machine,
            "needed": needed, "soname": soname, "runpath": runpath}

def symlink_destination(name, link):
    if link.startswith("/"):
        prefix_map = {"/vendor/": "vendor_a/", "/odm/": "odm_a/"}
        for prefix, archive_prefix in prefix_map.items():
            if link.startswith(prefix):
                return accepted(archive_prefix + link[len(prefix):])
        return None
    return accepted(posixpath.normpath(posixpath.join(posixpath.dirname(name), link)))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", action="append", default=[])
    args = p.parse_args()
    if not args.archive.is_file():
        p.error("source archive missing")
    requested = set(SEEDS) | set(args.seed)
    if any(accepted(x) != x for x in requested):
        p.error("unsafe seed path")
    members = {}
    elfs = {}
    command = subprocess.Popen(["zstd", "-dc", "--", str(args.archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=command.stdout, mode="r|") as tar:
            for member in tar:
                name = accepted(member.name)
                if not name or name in members:
                    continue
                kind = "file" if member.isfile() else "symlink" if member.issym() else "hardlink" if member.islnk() else "directory" if member.isdir() else "other"
                entry = {"type": kind, "mode": oct(member.mode), "uid": member.uid, "gid": member.gid, "size": member.size}
                if kind in ("symlink", "hardlink"):
                    entry["link_target"] = member.linkname
                    entry["resolved_target"] = symlink_destination(name, member.linkname) if kind == "symlink" else accepted(member.linkname)
                if kind == "file" and member.size <= MAX_FILE:
                    f = tar.extractfile(member)
                    if f:
                        data = f.read(MAX_FILE + 1)
                        if len(data) <= MAX_FILE:
                            entry["sha256"] = hashlib.sha256(data).hexdigest()
                            if data.startswith(b"\x7fELF"):
                                try:
                                    elfs[name] = elf_details(data)
                                except Exception as exc:
                                    entry["elf_error"] = type(exc).__name__
                elif kind == "file":
                    entry["hash_skipped"] = "over 80 MiB bound"
                members[name] = entry
    finally:
        if command.stdout:
            command.stdout.close()
        status = command.wait()
    if status != 0:
        raise SystemExit("zstd decompression failed")
    if len(members) < 4000:
        raise SystemExit("unexpectedly small archive inventory")
    def deref(path):
        seen = set()
        while path in members and members[path]["type"] in ("symlink", "hardlink"):
            if path in seen:
                return None
            seen.add(path)
            path = members[path].get("resolved_target")
            if not path:
                return None
        return path if path in members else None
    def resolve(origin, dep, bits):
        folder = posixpath.dirname(origin)
        partition = origin.split("/", 1)[0]
        libdir = "lib64" if bits == 64 else "lib"
        candidates = [f"{partition}/{libdir}/{dep}", f"vendor_a/{libdir}/{dep}", f"odm_a/{libdir}/{dep}",
                      f"{partition}/{libdir}/hw/{dep}", f"vendor_a/{libdir}/hw/{dep}",
                      posixpath.join(folder, dep)]
        for candidate in dict.fromkeys(candidates):
            target = deref(candidate)
            if target in elfs and elfs[target]["bits"] == bits:
                return candidate, target
        return None, None
    queue = deque(sorted(requested))
    visited = set()
    graph = []
    while queue:
        path = queue.popleft()
        target = deref(path)
        if path in visited:
            continue
        visited.add(path)
        if not target or target not in elfs:
            graph.append({"path": path, "status": "not_present_or_not_parsed_elf"})
            continue
        info = elfs[target]
        dependencies = []
        for dep in info["needed"]:
            match, physical = resolve(target, dep, info["bits"])
            dependencies.append({"soname": dep, "matched_path": match, "elf_path": physical,
                                 "status": "found_in_archived_vendor_odm" if physical else "unresolved_in_archive_may_be_system"})
            if match and match not in visited:
                queue.append(match)
        graph.append({"path": path, "resolved_elf": target, "bits": info["bits"], "machine": info["machine"],
                      "runpath_not_evaluated": info["runpath"], "dependencies": dependencies})
    tracked = set(visited)
    tracked.update(x.get("elf_path") for item in graph for x in item.get("dependencies", []) if x.get("elf_path"))
    tracked = {x for x in tracked if x in members}
    report = {"archive": args.archive.name, "archive_members_accepted": len(members),
              "elf_files_parsed": len(elfs), "seeds": sorted(requested),
              "metadata": {p: members[p] for p in sorted(tracked)}, "dependency_graph": graph,
              "limitations": ["Research only; no blob approval or runtime validation",
                              "Unresolved DT_NEEDED may belong to system/APEX or other partitions",
                              "RUNPATH, namespace restrictions, ABI and dlopen dependencies are not verified",
                              "SHA256 records file contents, not kernel/module compatibility"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"accepted={len(members)} elf={len(elfs)} tracked={len(tracked)} unresolved={sum(d['matched_path'] is None for r in graph for d in r.get('dependencies', []))}")

if __name__ == "__main__":
    main()
