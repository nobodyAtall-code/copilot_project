#!/usr/bin/env python3
"""Read-only Android liblp metadata audit; raw (non-sparse) super.img only.

Checks geometry and metadata checksums, group maximum capacities, all slots,
primary/backup consistency. Research output, not an automatic BoardConfig patch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SECTOR=512

def number(b, o, fmt):
    return struct.unpack_from('<'+fmt,b,o)[0]

def name(b):
    return b.partition(b'\0')[0].decode('ascii')

def verified(b, start, end, digest):
    out=bytearray(b)
    out[start:end]=bytes(end-start)
    return hashlib.sha256(out).digest()==digest

def read(f, position, size, total):
    if position<0 or size<0 or position+size>total:
        raise ValueError('Out-of-bounds LP read')
    f.seek(position)
    data=f.read(size)
    if len(data)!=size:
        raise ValueError('Short LP read')
    return data

def geometry(f, total):
    for pos in (4096,8192):
        if total<pos+52: continue
        b=read(f,pos,52,total)
        if number(b,0,'I')!=0x616c4467 or number(b,4,'I')!=52: continue
        if not verified(b,8,40,b[8:40]): continue
        max_size,slots,block=struct.unpack_from('<III',b,40)
        if max_size<=0 or max_size%SECTOR or not 1<=slots<=16 or block<512 or block & (block-1): continue
        return dict(offset=pos,max_size=max_size,slots=slots,logical_block_size=block,sha256_valid=True)
    raise ValueError('No valid standard LP geometry at byte 4096 or 8192')

def metadata(f,total,pos,max_size):
    area=read(f,pos,max_size,total)
    if number(area,0,'I')!=0x414c5030:
        raise ValueError('Bad LP header magic')
    major,minor,hsize=struct.unpack_from('<HHI',area,4)
    if major!=10 or minor>2 or hsize not in (128,132,136,140,144,148,152,156,160):
        raise ValueError('Unsupported header version or size')
    if not verified(area[:hsize],12,44,area[12:44]):
        raise ValueError('LP header SHA256 mismatch')
    length=number(area,44,'I')
    if length+hsize>max_size: raise ValueError('Metadata tables overflow')
    table=area[hsize:hsize+length]
    if hashlib.sha256(table).digest()!=area[48:80]:
        raise ValueError('LP tables SHA256 mismatch')
    tables=[]
    for pos,size in [(80,52),(92,24),(104,48),(116,64)]:
        start,count,element_size=struct.unpack_from('<III',area,pos)
        if element_size!=size or start>len(table) or count>(len(table)-start)//size:
            raise ValueError('Invalid LP descriptor')
        tables.append([table[start+i*size:start+(i+1)*size] for i in range(count)])
    partitions_table,extents_table,groups_table,blocks_table=tables
    if not groups_table or not blocks_table:
        raise ValueError('Missing LP groups or block devices')
    groups=[dict(name=name(x[:36]),flags=number(x,36,'I'),
                 maximum_size=number(x,40,'Q'),partitions=[])
            for x in groups_table]
    blocks=[dict(name=name(x[24:60]),first_logical_sector=number(x,0,'Q'),
                 size=number(x,16,'Q'),alignment=number(x,8,'I'),flags=number(x,60,'I'))
            for x in blocks_table]
    extents=[dict(sectors=number(x,0,'Q'),target_type=number(x,8,'I'),
                  source=number(x,20,'I'))
             for x in extents_table]
    entries=[]
    for x in partitions_table:
        pname=name(x[:36])
        attrs,first,count,group_index=struct.unpack_from('<IIII',x,36)
        if group_index>=len(groups) or first+count>len(extents):
            raise ValueError('Invalid group/extent reference: '+pname)
        selected=extents[first:first+count]
        if any(e['target_type'] not in (0,1) or (e['target_type']==0 and e['source']>=len(blocks)) for e in selected):
            raise ValueError('Invalid block/extent reference: '+pname)
        size=sum(e['sectors']*SECTOR for e in selected)
        group=groups[group_index]
        group['partitions'].append(pname)
        entries.append(dict(name=pname,attributes=attrs,size=size,
                            group=group['name'],extents=count))
    for group in groups:
        group['allocated_bytes']=sum(x['size'] for x in entries if x['group']==group['name'])
        group['within_maximum']=(group['maximum_size']==0 or group['allocated_bytes']<=group['maximum_size'])
    return dict(version=str(major)+'.'+str(minor),
                header_flags=number(area,128,'I') if hsize>=132 else 0,
                groups=groups,block_devices=blocks,partitions=entries,
                sha256_valid=True)

def inspect(path):
    total=path.stat().st_size
    with path.open('rb') as f:
        if read(f,0,4,total)==bytes.fromhex('3aff26ed'):
            raise ValueError('Input is Android sparse; run simg2img before inspection')
        geo=geometry(f,total)
        slots=[]
        base=4096+2*4096
        for i in range(geo['slots']):
            rec={'slot':i}
            for kind,off in [('primary',base+i*geo['max_size']),
                             ('backup',base+(geo['slots']+i)*geo['max_size'])]:
                try:
                    rec[kind]={'valid':True,'data':metadata(f,total,off,geo['max_size'])}
                except ValueError as err:
                    rec[kind]={'valid':False,'error':str(err)}
            rec['matching_copies']=(rec['primary']['valid'] and rec['backup']['valid']
                                    and rec['primary']['data']==rec['backup']['data'])
            slots.append(rec)
    ok=all(rec['matching_copies'] and
           all(g['within_maximum'] for g in rec['primary']['data']['groups'])
           for rec in slots)
    return dict(source=path.name,raw_bytes=total,geometry=geo,slots=slots,
                integrity_checks_passed=ok,production_boardconfig_validated=False)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('image',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=inspect(args.image)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    for rec in report['slots']:
        print('slot',rec['slot'],'copies match:',rec['matching_copies'])
        if rec['primary']['valid']:
            for group in rec['primary']['data']['groups']:
                print('  group',group['name'],'maximum',group['maximum_size'],
                      'allocated',group['allocated_bytes'],'partitions',','.join(group['partitions']))
    print('Integrity checks passed:',report['integrity_checks_passed'])
    if not report['integrity_checks_passed']:
        raise SystemExit(2)

if __name__=='__main__':
    main()
