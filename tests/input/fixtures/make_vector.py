#!/usr/bin/env python3
"""Synthetic captured SSE move/store/load chain, independent of BAP output."""
import argparse
from pathlib import Path
import make_stage_b as base

base.CODE=bytes.fromhex('0f28c6 0f113424 0f103c24 c3')
args=argparse.ArgumentParser()
args.add_argument('--check',action='store_true')
options=args.parse_args()
for _,platform,entry in base.PROGRAMS:
    name='vector-windows.dmp' if platform==2 else 'vector-linux.dmp'
    path=Path(__file__).with_name(name)
    data=base.build(platform,entry)
    if options.check:
        if path.read_bytes()!=data:raise SystemExit(f'fixture differs: {path}')
    else:path.write_bytes(data)
    print(name,len(data))
