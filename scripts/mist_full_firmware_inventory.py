#!/usr/bin/env python3
"""Read-only whole-partition ELF, KO, VINTF and image research; never export blobs."""
import argparse, collections, hashlib, json, os, pathlib, subprocess
from elftools.elf.elffile import ELFFile

PARTS={"vendor_a","odm_a","vendor_dlkm_a","system_dlkm_a","system_a","system_ext_a","product_a","mi_ext_a"}
PRIVATE=("persist","modemst","userdata","secdata","keystore","calibration","keybox")
def digest(p):
    d=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(4<<20),b""):d.update(chunk)
    return d.hexdigest()
def modinfo(p,k):
    try:
        x=subprocess.run(["modinfo","-F",k,str(p)],capture_output=True,text=True,timeout=8)
        return x.stdout.strip()[:800] if x.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):return None
def elfinfo(p):
    with p.open("rb") as f:
        e=ELFFile(f)
        dyn=e.get_section_by_name(".dynamic")
        needed=[]; soname=None; runpath=[]
        if dyn:
            for t in dyn.iter_tags():
                if t.entry.d_tag=="DT_NEEDED":needed.append(t.needed)
                if t.entry.d_tag=="DT_SONAME":soname=t.soname
                if t.entry.d_tag in ("DT_RPATH","DT_RUNPATH"):
                    runpath.append(getattr(t,"runpath",getattr(t,"rpath","")))
        return {"bits":e.elfclass,"machine":str(e.header.e_machine),
                "soname":soname,"needed":needed,"runpath":runpath[:8]}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mounts",type=pathlib.Path,required=True)
    ap.add_argument("--images",type=pathlib.Path,required=True)
    ap.add_argument("--json",type=pathlib.Path,required=True)
    ap.add_argument("--markdown",type=pathlib.Path,required=True)
    a=ap.parse_args()
    out={"firmware":"OS3.0.304.0.WPUMIXM","partitions":[],"elfs":[],"modules":[],
         "vintf":[],"init":[],"images":[],"errors":[]}
    max_records=25000
    for root in sorted(a.mounts.iterdir()):
        if not root.is_dir() or root.name not in PARTS or not os.path.ismount(root):continue
        record={"partition":root.name,"files":0,"symlinks":0,"so":0,"ko":0,"vintf":0,"init":0}
        for base,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[x for x in dirs if not pathlib.Path(base,x).is_symlink()]
            for name in files:
                full=pathlib.Path(base,name)
                relative=full.relative_to(root).as_posix()
                if any(t in relative.lower().split("/") for t in PRIVATE):continue
                if full.is_symlink():record["symlinks"]+=1;continue
                if not full.is_file():continue
                record["files"]+=1
                size=full.stat().st_size
                if "/etc/vintf/" in "/"+relative and name.endswith(".xml"):
                    record["vintf"]+=1
                    if len(out["vintf"])<max_records:out["vintf"].append({"partition":root.name,"path":relative,"bytes":size})
                if "/etc/init/" in "/"+relative and name.endswith(".rc"):
                    record["init"]+=1
                    if len(out["init"])<max_records:out["init"].append({"partition":root.name,"path":relative,"bytes":size})
                if name.endswith(".ko"):
                    record["ko"]+=1
                    if len(out["modules"])<max_records:
                        out["modules"].append({"partition":root.name,"path":relative,"bytes":size,
                            "vermagic":modinfo(full,"vermagic"),"depends":modinfo(full,"depends"),
                            "signature_id":modinfo(full,"sig_id")})
                if size>=64 and size<1<<30 and (".so" in name or "/bin/" in "/"+relative or "/lib" in "/"+relative):
                    try:
                        with full.open("rb") as f:magic=f.read(4)
                        if magic != b"\x7fELF":continue
                        info=elfinfo(full)
                        record["so"]+=int(".so" in name)
                        if len(out["elfs"])<max_records:
                            out["elfs"].append({"partition":root.name,"path":relative,"bytes":size,**info})
                    except Exception as e:
                        if len(out["errors"])<120:out["errors"].append({"path":root.name+"/"+relative,"error":type(e).__name__})
        out["partitions"].append(record)
    if not out["partitions"]:raise SystemExit("No read-only mounted partitions were found")
    for f in sorted(a.images.rglob("*.img")):
        if not f.is_file() or any(s in f.name.lower() for s in PRIVATE):continue
        out["images"].append({"path":f.relative_to(a.images).as_posix(),"bytes":f.stat().st_size,"sha256":digest(f)})
    known=collections.defaultdict(list)
    for v in out["elfs"]:
        ref=v["partition"]+"/"+v["path"]
        known[(v["bits"],pathlib.PurePosixPath(v["path"]).name)].append(ref)
        if v["soname"]:known[(v["bits"],v["soname"])].append(ref)
    unresolved=collections.Counter()
    resolved=0
    for v in out["elfs"]:
        for dependency in v["needed"]:
            if (v["bits"],dependency) in known:resolved+=1
            else:unresolved[dependency]+=1
    out["dependency_review"]={"matched_by_filename_not_namespace":resolved,
         "unmatched_in_mounted_partitions_not_proven_missing":dict(unresolved.most_common()),
         "limitations":"Android linker namespaces, APEX, runtime dlopen and ABI not checked."}
    out["summary"]={"mounts":len(out["partitions"]),"elfs":len(out["elfs"]),
         "modules":len(out["modules"]),"vintf":len(out["vintf"]),
         "init_rc":len(out["init"]),"images":len(out["images"]),"unmatched_sonames":len(unresolved)}
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.markdown.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    lines=["# Mist full firmware partition research","","Source: original verified OS3.0.304.0.WPUMIXM fastboot firmware.","",
      "| Partition | Files | .so ELF | .ko | VINTF | init RC |","|---|---:|---:|---:|---:|---:|"]
    for r in out["partitions"]:
        lines.append("| "+r["partition"]+" | "+" | ".join(str(r[k]) for k in ("files","so","ko","vintf","init"))+" |")
    lines+=["","Total parsed ELF records: "+str(len(out["elfs"])),
      "Total kernel modules: "+str(len(out["modules"])),
      "Unique unmatched SONAMEs in scanned partitions: "+str(len(unresolved))+" (not proven missing).",
      "","## Common unmatched dependencies",""]
    for name,n in unresolved.most_common(70):lines.append("- "+name+": "+str(n))
    lines+=["","## Important verification gaps","",
       "The inventory does not verify linker namespaces or APEX, device boot, module ABI, VINTF compatibility, AVB signatures, DTBO board applicability or SELinux compilation.",""]
    a.markdown.write_text("\n".join(lines))
    print(json.dumps(out["summary"],indent=2))
if __name__=="__main__":main()
