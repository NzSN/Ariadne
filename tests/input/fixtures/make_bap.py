#!/usr/bin/env python3
"""Controlled coverage fixture: captured MOV, NOT, store and opaque RET."""
import argparse
from pathlib import Path
import make_stage_b as base
base.CODE=bytes.fromhex('4889d8 48f7d0 c70005000000 c3')
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
for name,platform,entry in base.PROGRAMS:
 dest=Path(__file__).with_name(name.replace('stage_b_','bap_precision_'))
 data=base.build(platform,entry)
 if args.check:
  if dest.read_bytes()!=data:raise SystemExit(f'fixture differs: {dest}')
 else:dest.write_bytes(data)
 print(dest.name,len(data))
