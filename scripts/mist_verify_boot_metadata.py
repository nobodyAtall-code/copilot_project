#!/usr/bin/env python3
"""Read-only SHA-locked AVB descriptor, DTBO entry and vendor DTB evidence.

Parses structured metadata, not cryptographic authentication or board matching.
No private bootconfig, raw boot images, keys or proprietary binaries in output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

IMAGES=("vbmeta.img","vbmeta_system.img","dtbo.img","vendor_boot.img")
TAG_NAMES={0:"property",1:"hashtree",2:"hash",3:"kernel_cmdline",4:"chain_partition"}

def num(b,p,fmt="I",endian=">"):
    return struct.unpack_from(endian+fmt,b,p)[0]

def require(cond,msg):
    if not cond: raise ValueError(msg)

def bounded(data,offset,count):
    require(0<=offset<=len(data) and 0<=count<=len(data)-offset,"Out-of-bounds stock metadata")
    return data[offset:offset+count]

def digest(b):
    return hashlib.sha256(b).hexdigest()

def parse_avb(path):
    # Header only: AVB0 magic, required version, auth/aux tables and descriptors.
    data=path.read_bytes()
    require(len(data)>=256 and data[:4]==b"AVB0","Invalid AVB header")
    auth,aux=struct.unpack_from(">QQ",data,12)
    alg=num(data,28)
    require(256+auth+aux<=len(data),"AVB auth/aux size overflow")
    puboff,pubsz=struct.unpack_from(">QQ",data,64)
    descoff,descsz=struct.unpack_from(">QQ",data,96)
    auxdata=bounded(data,256+auth,aux)
    public_key=bounded(auxdata,puboff,pubsz)
    descriptors=bounded(auxdata,descoff,descsz)
    result={"required_libavb_version":list(struct.unpack_from(">II",data,4)),
      "algorithm_type":alg,"authentication_block_bytes":auth,"auxiliary_block_bytes":aux,
      "public_key_sha256":digest(public_key) if public_key else None,
      "rollback_index_from_image":num(data,112,"Q"),
      "vbmeta_flags":num(data,120),
      "rollback_index_location":num(data,124),
      "descriptors":[],"cryptographic_signature_verified":False,
      "runtime_rollback_state_verified":False}
    off=0
    while off<len(descriptors):
        require(len(descriptors)-off>=16,"Truncated AVB descriptor header")
        tag,length=struct.unpack_from(">QQ",descriptors,off)
        require(length<=len(descriptors)-off-16,"AVB descriptor exceeds table")
        body=descriptors[off+16:off+16+length]
        entry={"tag":tag,"type":TAG_NAMES.get(tag,"other"),"data_bytes":length}
        if tag==4: # AvbChainPartitionDescriptor: 4+4+4+64 bytes header
            require(len(body)>=76,"Short AVB chain descriptor")
            rollback_location,name_len,key_len=struct.unpack_from(">III",body,0)
            require(76+name_len+key_len<=len(body),"Short AVB chain name/key")
            name=body[76:76+name_len].decode("utf-8","replace")
            key=body[76+name_len:76+name_len+key_len]
            entry.update(partition=name,rollback_location=rollback_location,
                         public_key_sha256=digest(key))
        elif tag==2: # AvbHashDescriptor: image_size, hash alg, four lengths/flags, 60 reserved
            require(len(body)>=116,"Short AVB hash descriptor")
            image_size=num(body,0,"Q")
            hash_alg=body[8:40].split(b"\0",1)[0].decode("ascii","replace")
            nlen,slen,dlen,flags=struct.unpack_from(">IIII",body,40)
            require(116+nlen+slen+dlen<=len(body),"Short AVB hash name/salt/digest")
            entry.update(partition=body[116:116+nlen].decode("utf-8","replace"),
                         image_size=image_size,hash_algorithm=hash_alg,
                         salt_bytes=slen,digest_bytes=dlen,flags=flags)
        elif tag==1: # AvbHashtreeDescriptor: inspect tag and length only, avoid overinterpreting
            entry["note"]="hashtree descriptor present; full verity parameters not validated"
        result["descriptors"].append(entry)
        off+=16+length
    return result

def fdt_header(blob,offset,limit):
    header=bounded(blob,offset,40)
    require(len(header)==40 and num(header,0)==0xd00dfeed,"Invalid FDT magic")
    size=num(header,4)
    require(40<=size<=limit,"FDT size invalid")
    return {"fdt_total_size":size,"fdt_version":num(header,20),
            "fdt_last_comp_version":num(header,24)}

def parse_dtbo(path):
    b=path.read_bytes()
    require(len(b)>=32 and num(b,0)==0xd7b7ab1e,"Invalid DTBO header")
    total,header,stride,count,offset,page,version=struct.unpack_from(">7I",b,4)
    require(32<=header<=total<=len(b),"Invalid DTBO total header length")
    require(stride>=32 and count<=2048 and offset+stride*count<=total,
            "Invalid DTBO entry table")
    entries=[]
    for i in range(count):
        size,start,board_id,rev,*custom=struct.unpack_from(">8I",b,offset+i*stride)
        require(start+size<=total,"DTBO entry payload exceeds table total")
        fdt=fdt_header(b,start,size)
        entries.append({"index":i,"id":board_id,"revision":rev,"custom":custom,
                        "dt_size":size,"dt_offset":start,
                        "sha256":digest(bounded(b,start,size)),**fdt})
    return {"header_version":version,"total_bytes":total,"entry_count":count,
            "entries":entries,"applicable_board_ids_verified":False}

def parse_vendor_dtb(path):
    b=path.read_bytes()
    require(b[:8]==b"VNDRBOOT","No vendor_boot magic")
    page=num(b,12,"I","<")
    ramdisk=num(b,24,"I","<")
    header=num(b,2096,"I","<")
    dtbsize=num(b,2100,"I","<")
    require(512<=page<=65536 and page&(page-1)==0,"Invalid page size")
    align=lambda n: ((n+page-1)//page)*page
    start=align(header)+align(ramdisk)
    dtb=bounded(b,start,dtbsize)
    require(dtbsize>=40,"Missing vendor DTB")
    # Concatenated DTBs are common: scan only FDT-sized sequential blobs.
    entries=[]
    cursor=0
    while cursor+40<=len(dtb):
        if dtb[cursor:cursor+4]!=bytes.fromhex("d00dfeed"):
            # Padding between DTBs is allowed but never infer device match.
            if all(v==0 for v in dtb[cursor:]):break
            raise ValueError("Unexpected vendor DTB byte at "+str(cursor))
        h=fdt_header(dtb,cursor,len(dtb)-cursor)
        length=h["fdt_total_size"]
        entries.append({"index":len(entries),"offset":cursor,"sha256":digest(dtb[cursor:cursor+length]),**h})
        cursor+=length
        while cursor<len(dtb) and dtb[cursor]==0 and cursor%4:cursor+=1
    require(bool(entries),"No valid FDT in vendor_boot DTB payload")
    return {"vendor_dtb_bytes":dtbsize,"dtbs":entries,
            "dtbo_compatibility_verified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--images-dir",type=Path,required=True)
    p.add_argument("--sha256-file",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    expected={}
    for line in a.sha256_file.read_text().splitlines():
        words=line.split()
        if len(words)==2:expected[Path(words[1].lstrip("*")).name]=words[0].lower()
    report={"source":"SHA256-locked original stock boot artifacts, OS3.0.304.0.WPUMIXM",
            "images":{},"stock_metadata_structures_valid":False,
            "avb_signatures_verified":False,"dtbo_board_compatibility_verified":False,
            "safe_to_flash":False}
    for name in IMAGES:
        path=a.images_dir/name
        require(path.is_file() and name in expected,"Missing stock artifact "+name)
        actual=hashlib.file_digest(path.open("rb"),"sha256").hexdigest()
        require(actual==expected[name],"SHA256 mismatch "+name)
        info=(parse_avb(path) if name.startswith("vbmeta") else
              parse_dtbo(path) if name=="dtbo.img" else parse_vendor_dtb(path))
        report["images"][name]={"sha256":actual,"sha256_verified":True,**info}
    report["stock_metadata_structures_valid"]=True
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"stock_metadata_structures_valid":True,
                      "dtbo_entries":report["images"]["dtbo.img"]["entry_count"],
                      "vendor_dtbs":len(report["images"]["vendor_boot.img"]["dtbs"]),
                      "vbmeta_descriptor_counts":{n:len(report["images"][n]["descriptors"]) for n in ("vbmeta.img","vbmeta_system.img")}},
                     indent=2))
if __name__=="__main__":
    main()
