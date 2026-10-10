import hashlib,json,mmap,struct,uuid
from pathlib import Path
base=Path('/home/jlc/ariadne-p4-20261010/work/repin-79938');base.mkdir(exist_ok=False)
original=Path('/mnt/d/Services/dump-ledger-runtime/data/vault/dump_79938FAE443F4021A4F7B6C215/original.dmp')
exe=Path('/mnt/d/symcache-dump79938-20261008/lceda-pro.exe/6A87C949d708000/lceda-pro.exe');pdb=Path('/mnt/d/symcache-dump79938-20261008/electron.exe.pdb/A7877FFB94F2DB3E4C4C44205044422E1/electron.exe.pdb')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
assert sha(original)=='342084c90b6e361ab94fb91a920f871581eba970810f99384d5dce00ee6d7353'
assert sha(exe)=='b537ad7b96136655b6cf640bd5a715a62a132dde6196acc925bf739164a1be3b'
assert sha(pdb)=='eab012ef555c641b2e10d314e58f02d01baa277b28f9ad5442e31c918c920ed9'
entry=0x7ff63cba6c50;end=entry+0x5e;seed=entry+0x44;tid=0x97f4
with original.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as raw:
 n,d=struct.unpack_from('<II',raw,8);streams={k:(rva,size) for k,size,rva in [struct.unpack_from('<III',raw,d+12*i) for i in range(n)]}
 rva,_=streams[9];n,offset=struct.unpack_from('<QQ',raw,rva);contributors=[]
 for i in range(n):
  address,size=struct.unpack_from('<QQ',raw,rva+16+16*i);contributors.append((address,size,offset));offset+=size
 def read(va,size):
  buf=bytearray(size);covered=bytearray(size);origins=[]
  for address,length,offset in contributors:
   lo=max(va,address);hi=min(va+size,address+length)
   if lo>=hi:continue
   block=raw[offset+lo-address:offset+hi-address]
   for j,b in enumerate(block,lo-va):
    if covered[j]:assert buf[j]==b,'conflicting original capture'
    else:buf[j]=b;covered[j]=1
   origins.append(dict(address=hex(address),size=length,fileOffset=offset,selectedOffset=offset+lo-address,selectedStart=hex(lo),selectedBytes=hi-lo))
  assert all(covered),'capture hole';return bytes(buf),origins
 thread_rva,_=streams[3];count=struct.unpack_from('<I',raw,thread_rva)[0]
 thread=bytearray(next(raw[thread_rva+4+48*i:thread_rva+4+48*(i+1)] for i in range(count) if struct.unpack_from('<I',raw,thread_rva+4+48*i)[0]==tid))
 stack,size,_=struct.unpack_from('<QII',thread,24);tctx_size,tctx=struct.unpack_from('<II',thread,40)
 exception,_=streams[6];assert struct.unpack_from('<I',raw,exception)[0]==tid
 assert struct.unpack_from('<I',raw,exception+8)[0]==0xc0000005
 assert struct.unpack_from('<Q',raw,exception+24)[0]==seed
 ectx_size,ectx=struct.unpack_from('<II',raw,exception+160);assert struct.unpack_from('<Q',raw,ectx+0xf8)[0]==seed and struct.unpack_from('<Q',raw,ectx+0xb8)[0]==1
 module_rva,_=streams[4];modules=struct.unpack_from('<I',raw,module_rva)[0];module=next(module_rva+4+108*i for i in range(modules) if struct.unpack_from('<Q',raw,module_rva+4+108*i)[0]==0x7ff63bae0000)
 cvsize,cv=struct.unpack_from('<II',raw,module+76);assert raw[cv:cv+4]==b'RSDS';guid=str(uuid.UUID(bytes_le=raw[cv+4:cv+20]));age=struct.unpack_from('<I',raw,cv+20)[0];assert guid=='a7877ffb-94f2-db3e-4c4c-44205044422e' and age==1
 # Retain admitted metadata plus every referenced module-name/CV payload.
 prefix=max(rva+size for k,(rva,size) in streams.items() if k in [4,6,7,16]);prefix=max(prefix,tctx+tctx_size,ectx+ectx_size)
 for i in range(modules):
  m=module_rva+4+108*i;name=struct.unpack_from('<I',raw,m+20)[0];prefix=max(prefix,name+4+struct.unpack_from('<I',raw,name)[0])
  for loc in [76,84]:
   length,offset=struct.unpack_from('<II',raw,m+loc);prefix=max(prefix,offset+length)
 data=bytearray(raw[:prefix])
 def append(blob,align=4):
  data.extend(b'\0'*((-len(data))%align));offset=len(data);data.extend(blob);return offset
 trva=append(struct.pack('<I',1)+thread)
 spans=sorted([(stack,size,'thread-stack'),(entry,0x5e,'AdvanceIterator'),(0x757c1fc35920,32,'iterator-map'),(0x757c1f0ce000,0x200,'first-values')])
 mrva=append(b'\0'*(16+16*len(spans)),8);data.extend(b'\0'*((-len(data))%8));struct.pack_into('<QQ',data,mrva,len(spans),len(data));ranges=[]
 for i,(va,length,name) in enumerate(spans):
  body,origins=read(va,length);offset=len(data);data.extend(body);struct.pack_into('<QQ',data,mrva+16+16*i,va,length)
  if va<=stack and stack+size<=va+length:struct.pack_into('<I',data,trva+4+36,offset+stack-va)
  ranges.append(dict(name=name,address=hex(va),bytes=length,projectionOffset=offset,sha256=hashlib.sha256(body).hexdigest(),contributors=origins))
 kept={k:streams[k] for k in [4,6,7,16]};kept.update({3:(trva,52),9:(mrva,16+16*len(spans))})
 directory=append(b''.join(struct.pack('<III',k,size,rva) for k,(rva,size) in sorted(kept.items())));struct.pack_into('<II',data,8,len(kept),directory);struct.pack_into('<I',data,16,0);struct.pack_into('<Q',data,24,0)
 for k in [4,6,7,16]:
  rva,length=streams[k];assert data[rva:rva+length]==raw[rva:rva+length]
 assert data[tctx:tctx+tctx_size]==raw[tctx:tctx+tctx_size] and data[ectx:ectx+ectx_size]==raw[ectx:ectx+ectx_size]
 # Matching PE supplies a boundary/byte witness only, never analysis fallback.
 with exe.open('rb') as ef,mmap.mmap(ef.fileno(),0,access=mmap.ACCESS_READ) as pe:
  nt=struct.unpack_from('<I',pe,0x3c)[0];sections=struct.unpack_from('<H',pe,nt+6)[0];optsize=struct.unpack_from('<H',pe,nt+20)[0];optional=nt+24
  assert struct.unpack_from('<I',pe,nt+8)[0]==0x6a87c949 and struct.unpack_from('<I',pe,optional+56)[0]==0xd708000
  rva=entry-0x7ff63bae0000;sect=optional+optsize
  for i in range(sections):
   off=sect+40*i;vsize,vaddr,rsize,roff=struct.unpack_from('<IIII',pe,off+8)
   if vaddr<=rva< vaddr+max(vsize,rsize):fileoff=roff+rva-vaddr;break
  captured,_=read(entry,0x5e);assert captured==pe[fileoff:fileoff+0x5e]
  assert captured[:7]==bytes.fromhex('488b114c8b4108') and captured[0x44:0x47]==bytes.fromhex('458a10')
 path=base/'capture.dmp';path.write_bytes(data)
 record=dict(schema='ariadne.repin-candidate-inspection/v1',original=dict(path=str(original),sha256=sha(original),bytes=len(raw),platform='windows',thread=hex(tid)),derivative=dict(path=str(path),sha256=sha(path),bytes=len(data),prefixBytes=prefix,publishedStreams=sorted(kept),ranges=ranges),companion=dict(path=str(exe),sha256=sha(exe),timestamp='0x6a87c949',imageSize='0x0d708000',imageBase='0x00007ff63bae0000',pdbSha256=sha(pdb),pdbGuid=guid,pdbAge=age),query=dict(entry=f'0x{entry:016x}',seed=f'0x{seed:016x}',producer=f'0x{entry+3:016x}',memory_access=0),code=dict(bytesHex=captured.hex(),sha256=hashlib.sha256(captured).hexdigest(),matchesCompanion=True),metadataAndContextsIdentical=True,threadContextMatchesException=False,selectedOverlapsAgree=True,scope='selected capture-only Windows function/stack/map/values; no earlier execution or root-cause assertion')
 (base/'inspection.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['derivative','code','companion']}),flush=True);print('Derivative',len(data),sha(path),flush=True)
