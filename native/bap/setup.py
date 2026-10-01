#!/usr/bin/env python3
"""Fetch/extract hash-pinned BAP runtime archives locally, or verify an extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
LOCK=Path(__file__).with_name('toolchain.lock.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,default=ROOT/'tmp/bap-setup/stable')
    parser.add_argument('--cache',type=Path,default=ROOT/'tmp/bap-setup')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();lock=json.loads(LOCK.read_text())
    if not args.check:
        args.cache.mkdir(parents=True,exist_ok=True);args.runtime.mkdir(parents=True,exist_ok=True)
        for asset in lock['assets']:
            path=args.cache/asset['file']
            if not path.exists():
                url=('https://archive.ubuntu.com/ubuntu/pool/main/libf/libffi/'+asset['file'] if asset['file'].startswith('libffi') else 'https://github.com/BinaryAnalysisPlatform/bap/releases/download/v2.5.0/'+asset['file'])
                urllib.request.urlretrieve(url,path)
            if sha(path)!=asset['sha256']:raise SystemExit(f'archive hash mismatch: {path}')
            subprocess.run(['dpkg-deb','-x',str(path),str(args.runtime)],check=True)
    for relative,digest in lock['files'].items():
        path=args.runtime/relative
        if not path.is_file() or sha(path)!=digest:raise SystemExit(f'missing/changed BAP runtime file: {path}')
    ffi=args.runtime/'usr/lib/x86_64-linux-gnu/libffi.so.6'
    if not ffi.is_file():raise SystemExit('matching libffi6 runtime unavailable')
    print(f'Pinned BAP runtime verified: {args.runtime}')


if __name__=='__main__':main()
