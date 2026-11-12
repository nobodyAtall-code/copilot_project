#!/usr/bin/env python3
"""Independently cross-check LP partition sizes from pinned lpunpack-go.

This validates independent parsing of per-partition allocation, NOT group
maxima: lpunpack-go does not expose group membership or group maximum sizes.
"""
import argparse
import json
from pathlib import Path
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--python-report',type=Path,required=True)
    p.add_argument('--go-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    original=json.loads(args.python_report.read_text())
    independent=json.loads(args.go_report.read_text())
    if not original.get('integrity_checks_passed'):
        raise SystemExit('Python LP checksums/slot consistency did not pass')
    parts=original['slots'][0]['primary']['data']['partitions']
    expected={item['name']:item['size'] for item in parts if item['size']}
    missing=sorted(set(expected)-set(independent))
    unexpected=sorted(set(independent)-set(expected))
    differing={k:{'python':expected[k],'go':independent[k]} for k in expected.keys()&independent.keys() if expected[k]!=independent[k]}
    result={'independent_tool':'lpunpack-go pinned 073a3302a3c3ffae01633989e6dd1e60b6de15b7',
            'comparison':'nonzero logical partition names and allocated sizes',
            'expected':expected,'independent':independent,
            'missing':missing,'unexpected':unexpected,'differing':differing,
            'partition_sizes_match':not (missing or unexpected or differing),
            'group_maxima_independently_verified':False,
            'boardconfig_or_ota_layout_validated':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'partition_sizes_match':result['partition_sizes_match'],
                      'partitions':len(expected),'missing':missing,'unexpected':unexpected,
                      'differing':differing},indent=2))
    if not result['partition_sizes_match']:
        raise SystemExit(2)
if __name__=='__main__':main()
