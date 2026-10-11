#!/usr/bin/env python3
"""Independent PE/unwind/stack encodings; synthetic minidumps, not real captures."""
from pathlib import Path
import argparse
import json
import hashlib
import struct

HERE=Path(__file__).resolve().parent/'frame_paths'
BASE=0x400000


def build(name):
    image=bytearray(b'\xcc'*4096)
    image[:64]=bytes(64);image[:2]=b'MZ';struct.pack_into('<I',image,60,0x80)
    image[0x80:0x98]=bytes(24);image[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<HHI',image,0x84,0x8664,1,1);struct.pack_into('<H',image,0x94,240)
    image[0x98:0x188]=bytes(240);struct.pack_into('<H',image,0x98,0x20b)
    struct.pack_into('<Q',image,0x98+24,BASE);struct.pack_into('<I',image,0x98+56,4096)
    struct.pack_into('<I',image,0x98+108,16);struct.pack_into('<II',image,0x98+136,0x800,36)
    # Code follows the header, at RVAs 0x200/0x300/0x400.
    for begin in [0x200,0x300,0x400]:
        image[begin:begin+0x40]=b'\x90'*0x40
        image[begin:begin+4]=bytes.fromhex('4883ec20')
    image[0x206:0x20e]=bytes.fromhex('488b004883c420c3')
    image[0x304:0x311]=bytes.fromhex('85c9740490eb0490eb00909090')
    image[0x310:0x315]=b'\xe8'+struct.pack('<i',0x200-0x315)
    image[0x315:0x31a]=bytes.fromhex('4883c420c3')
    image[0x410:0x415]=b'\xe8'+struct.pack('<i',0x300-0x415)
    image[0x415:0x41a]=bytes.fromhex('4883c420c3')
    for i,begin in enumerate([0x200,0x300,0x400]):
        struct.pack_into('<III',image,0x800+i*12,begin,begin+0x40,0x900+i*16)
        image[0x900+i*16:0x906+i*16]=bytes([1,4,1,0,4,0x32])
    stack=bytearray(256);pc=BASE+0x206;flags=0x100003;rbp=0
    returns=[(0x20,BASE+0x315),(0x48,BASE+0x415),(0x70,0)]
    if name=='recursive':
        pc=BASE+0x306
        image[0x310:0x315]=b'\xe8'+struct.pack('<i',0x300-0x315)
        returns=[(0x20,BASE+0x315),(0x48,BASE+0x315),(0x70,0)]
    if name=='control-only':flags=0x100001
    if name=='missing-control':flags=0x100002
    if name=='prologue':pc=BASE+0x201
    if name=='epilogue':pc=BASE+0x209
    if name=='chained':image[0x900]=0x21
    if name=='unsorted-table':image[0x800:0x818]=image[0x80c:0x818]+image[0x800:0x80c]
    if name=='large-alloc-16':image[0x900:0x908]=bytes([1,4,2,0,4,1,4,0])
    if name=='large-alloc-32':image[0x900:0x90a]=bytes([1,4,3,0,4,0x11,32,0,0,0])
    if name=='push-rbx':
        image[0x200:0x205]=bytes.fromhex('534883ec20')
        image[0x900:0x908]=bytes([1,5,2,0,5,0x32,1,0x30])
        struct.pack_into('<Q',stack,0x20,0x12345678)
        returns=[(0x28,BASE+0x315),(0x50,BASE+0x415),(0x78,0)]
    if name=='save-rbp':
        image[0x204:0x212]=bytes.fromhex('48896c241090488b004883c420c3')
        pc=BASE+0x20a;rbp=0x12345678
        image[0x900:0x90a]=bytes([1,9,3,0,9,0x54,2,0,4,0x32])
        struct.pack_into('<Q',stack,0x10,0x12345678)
    if name=='frame-pointer':
        rbp=0x1010
        image[0x200:0x215]=bytes.fromhex('554883ec20488d6c24109090488b004883c4205dc3')
        pc=BASE+0x20c
        image[0x900:0x90a]=bytes([1,10,3,0x15,10,3,5,0x32,1,0x50])
        struct.pack_into('<Q',stack,0x20,0xbeef)
        returns=[(0x28,BASE+0x315),(0x50,BASE+0x415),(0x78,0)]
    assert len(image)==4096, 'code insertion shifted PE RVAs'
    for offset,value in returns:struct.pack_into('<Q',stack,offset,value)
    data=bytearray(32);streams=[]
    def append(b):offset=len(data);data.extend(b);return offset
    def stream(kind,b):off=append(b);streams.append((kind,len(b),off));return off
    system=bytearray(56);system[0]=9;system[6]=1;struct.pack_into('<I',system,20,2);stream(7,system)
    image_off=append(image);stack_off=append(stack)
    image_len=0x800 if name=='missing-table-bytes' else len(image)
    stream(5,struct.pack('<I',2)+struct.pack('<QII',BASE,image_len,image_off)+struct.pack('<QII',0x1000,len(stack),stack_off))
    context=bytearray(1232);struct.pack_into('<I',context,48,flags)
    struct.pack_into('<Q',context,152,0x1000);struct.pack_into('<Q',context,160,rbp);struct.pack_into('<Q',context,248,pc)
    if name=='push-rbx':struct.pack_into('<Q',context,144,0x12345678)
    context_off=append(context)
    thread=bytearray(48);struct.pack_into('<I',thread,0,17);struct.pack_into('<QII',thread,24,0x1000,len(stack),stack_off);struct.pack_into('<II',thread,40,len(context),context_off)
    stream(3,struct.pack('<I',1)+thread)
    module=bytearray(108);module_name='frame-fixture.exe'.encode('utf-16-le');name_off=append(struct.pack('<I',len(module_name))+module_name)
    struct.pack_into('<QIIII',module,0,BASE,4096,0,1,name_off);stream(4,struct.pack('<I',1)+module)
    exception=bytearray(168);struct.pack_into('<I',exception,0,17);struct.pack_into('<IIQQI',exception,8,0xc0000005,0,0,pc,2);struct.pack_into('<QQ',exception,40,0,0);struct.pack_into('<II',exception,160,len(context),context_off);stream(6,exception)
    directory=len(data);struct.pack_into('<4sIII',data,0,b'MDMP',0xa793,len(streams),directory)
    for row in streams:data.extend(struct.pack('<III',*row))
    return bytes(data)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--regenerate',action='store_true');args=parser.parse_args()
    HERE.mkdir(exist_ok=True);rows=[]
    for name in ['diamond','recursive','control-only','missing-control','prologue','epilogue','chained','unsorted-table','missing-table-bytes','large-alloc-16','large-alloc-32','push-rbx','save-rbp','frame-pointer']:
        payload=build(name);p=HERE/(name+'.dmp')
        if p.exists() and not args.regenerate:assert p.read_bytes()==payload,'fixture bytes changed'
        else:p.write_bytes(payload)
        rows.append(dict(name=name,sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload)))
    (HERE/'manifest.json').write_text(json.dumps({'scope':'independent synthetic PE/unwind/stack fixtures','cases':rows},indent=2)+'\n')
    print('Frame capture fixtures PASS: 14 independent encodings.')
