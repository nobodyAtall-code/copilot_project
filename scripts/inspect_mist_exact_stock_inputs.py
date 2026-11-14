#!/usr/bin/env python3
"""Inspect selected exact stock firmware paths without exporting proprietary bytes."""
import argparse
import hashlib
import json
import pathlib
import subprocess
import tarfile

WATCH = {
    "camera_helper": ["vendor_a/bin/init.qti.cam.perfopt.sh",
                      "vendor_a/etc/init.qti.cam.perfopt.sh",
                      "odm_a/bin/init.qti.cam.perfopt.sh"],
    "camera_rc": ["vendor_a/etc/init/vendor.qti.camera.provider-service_64.rc"],
    "camera_vintf": ["vendor_a/etc/vintf/manifest/vendor.qti.camera.provider.xml",
                     "vendor_a/etc/vintf/manifest/vendor.qti.camera.postproc-impl.xml"],
    "keymint_vintf": ["vendor_a/etc/vintf/manifest/android.hardware.security.keymint-service-qti.xml"],
    "keymint_rc": ["vendor_a/etc/init/android.hardware.security.keymint-service-qti.rc"],
    "selinux": ["vendor_a/etc/selinux/vendor_file_contexts",
               "vendor_a/etc/selinux/vendor_service_contexts",
               "vendor_a/etc/selinux/vendor_hwservice_contexts",
               "vendor_a/etc/selinux/vendor_sepolicy.cil",
               "vendor_a/etc/selinux/precompiled_sepolicy",
               "odm_a/etc/selinux/odm_file_contexts",
               "odm_a/etc/selinux/odm_sepolicy.cil"],
    "camera_module": ["vendor_dlkm_a/lib/modules/camera.ko",
                      "vendor_dlkm_a/lib/modules/modules.dep",
                      "vendor_dlkm_a/lib/modules/modules.load"],
}
LOOKUP = {p: group for group, paths in WATCH.items() for p in paths}
MAX_HASH = 40 * 1024 * 1024

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", type=pathlib.Path, required=True)
    ap.add_argument("--sha256", type=pathlib.Path, required=True)
    ap.add_argument("--json", type=pathlib.Path, required=True)
    ap.add_argument("--markdown", type=pathlib.Path, required=True)
    a = ap.parse_args()
    a.json.parent.mkdir(parents=True, exist_ok=True)
    a.markdown.parent.mkdir(parents=True, exist_ok=True)
    c = subprocess.run(["sha256sum", "-c", a.sha256.name], cwd=a.archive.parent,
                       capture_output=True, text=True)
    if c.returncode or a.archive.name + ": OK" not in c.stdout:
        raise SystemExit("Verified source SHA256 FAILED: " + c.stdout + c.stderr)
    found = {}
    basename_matches = []
    rc_ref = []
    child = subprocess.Popen(["zstd", "-dc", "--", str(a.archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=child.stdout, mode="r|") as archive:
            for member in archive:
                name = member.name.removeprefix("./").rstrip("/")
                if not name.startswith(("vendor_a/", "odm_a/", "vendor_dlkm_a/", "system_dlkm_a/")):
                    continue
                if any(part in ("", ".", "..") for part in name.split("/")):
                    continue
                if name.endswith("init.qti.cam.perfopt.sh") or name.endswith("/camera.ko"):
                    basename_matches.append(name)
                if name not in LOOKUP:
                    continue
                row = {"group": LOOKUP[name], "path": name, "size": member.size,
                       "type": "file" if member.isfile() else "symlink" if member.issym() else "other",
                       "mode": oct(member.mode)}
                if member.issym():
                    row["link_target"] = member.linkname
                if member.isfile() and member.size <= MAX_HASH:
                    fh = archive.extractfile(member)
                    if fh:
                        data = fh.read(MAX_HASH + 1)
                        if len(data) <= MAX_HASH:
                            row["sha256"] = hashlib.sha256(data).hexdigest()
                            if name.endswith("vendor.qti.camera.provider-service_64.rc"):
                                rc_ref = [line.strip()[:250] for line in data.decode("utf-8", "replace").splitlines()
                                          if "init.qti.cam.perfopt.sh" in line or "vendor_qti_init_shell" in line][:10]
                            if name.endswith("/modules.load"):
                                row["camera_ko_in_load"] = any(
                                    pathlib.PurePosixPath(x.strip()).name == "camera.ko"
                                    for x in data.decode("utf-8", "replace").splitlines())
                            if name.endswith("/modules.dep"):
                                row["camera_dep_line"] = [line[:600] for line in data.decode("utf-8", "replace").splitlines()
                                                          if line.startswith(("camera.ko:", "/vendor/lib/modules/camera.ko:"))][:4]
                found[name] = row
    finally:
        if child.stdout:
            child.stdout.close()
        status = child.wait()
    if status:
        raise SystemExit("zstd failed " + str(status))
    if len(found) < 5:
        raise SystemExit("Unexpectedly few stock entries; wrong input layout?")
    entries = [found.get(path, {"path": path, "group": group, "status": "ABSENT_FROM_VERIFIED_ARCHIVE"})
               for group, paths in WATCH.items() for path in paths]
    output = {"firmware": "OS3.0.304.0.WPUMIXM", "sha256_verification": "PASS",
              "records": entries, "camera_basename_matches": sorted(set(basename_matches)),
              "camera_rc_references": rc_ref,
              "notes": ["Exact archive membership, not final Lineage install selection",
                        "Missing archive path may still be provided by platform/system",
                        "No proprietary file bytes, policy contents, or personal data exported"]}
    a.json.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    lines = ["# Mist exact stock firmware provenance", "",
             "Source: SHA256-verified OS3.0.304.0.WPUMIXM stock vendor archive", "",
             "| Group | Stock path | Present | Bytes | SHA256 prefix |",
             "|---|---|---|---:|---|"]
    for row in entries:
        lines.append("| " + row["group"] + " | `" + row["path"] + "` | " +
                     ("yes" if "status" not in row else "NO") + " | " + str(row.get("size", "-")) +
                     " | " + row.get("sha256", "-")[:16] + " |")
    lines += ["", "## Camera helper and module matches", "",
              "\n".join("- `" + p + "`" for p in sorted(set(basename_matches))) or "None",
              "", "## Camera RC references", "",
              "\n".join("- `" + line.replace("|", "/") + "`" for line in rc_ref) or "None",
              "", "**No binary or SELinux policy content has been published.**",
              "No runtime, overlay selection or ABI compatibility is implied.", ""]
    a.markdown.write_text("\n".join(lines))
    print("Stock SHA256 PASS; selected entries:", len(found), "of", len(LOOKUP))
    print("Camera/helper basename matches:", sorted(set(basename_matches)))

if __name__ == "__main__":
    main()
