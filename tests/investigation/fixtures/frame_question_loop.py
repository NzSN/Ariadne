#!/usr/bin/env python3
"""Independent loop/point control encoding; synthetic breakpoint, not Crashpad."""
import argparse,importlib.util,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('frame_bytes',ROOT/'tests/input/fixtures/make_frame_paths.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def payload():
    data=bytearray(mod.build('diamond'));count,directory=struct.unpack_from('<II',data,8)
    streams={kind:(size,offset) for kind,size,offset in (struct.unpack_from('<III',data,directory+12*i) for i in range(count))}
    image=struct.unpack_from('<I',data,streams[5][1]+16)[0]
    data[image+0x204:image+0x219]=bytes.fromhex('48c7c10000000048ffc14883f90572f74883c420c3')
    thread=streams[3][1]+4;context=struct.unpack_from('<I',data,thread+44)[0]
    struct.pack_into('<Q',data,context+248,0x40020b);struct.pack_into('<Q',data,context+128,2) # RCX=2 at the third before-INC visit.
    exception=streams[6][1];struct.pack_into('<Q',data,exception+24,0x40020b);struct.pack_into('<I',data,exception+8,0x80000003);struct.pack_into('<I',data,exception+32,0)
    return bytes(data)
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();out=Path(__file__).with_name('evidence')/'frame-question-loop.dmp';expected=payload()
    if a.check:assert out.read_bytes()==expected
    else:out.write_bytes(expected)
    print('loop/point fixture: independent bytes match')
if __name__=='__main__':main()
