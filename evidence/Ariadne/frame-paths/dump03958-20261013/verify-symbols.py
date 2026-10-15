import hashlib,json,struct,uuid
from pathlib import Path
DUMP=Path('D:/Services/dump-ledger-runtime/data/vault/dump_03958DA4FCA844A786262A1053/original.dmp')
PDB=Path('D:/symcache-dump03958-20261009/electron.exe.pdb/A7877FFB94F2DB3E4C4C44205044422E1/electron.exe.pdb')
def read(f,o,n):f.seek(o);return f.read(n)
with DUMP.open('rb') as f:
 h=read(f,0,32);count,rva=struct.unpack_from('<II',h,8)
 entries=[struct.unpack('<III',read(f,rva+i*12,12)) for i in range(count)]
 _,size,off=next(x for x in entries if x[0]==4)
 modules=struct.unpack('<I',read(f,off,4))[0]
 for i in range(modules):
  m=read(f,off+4+i*108,108);name_rva=struct.unpack_from('<I',m,20)[0];length=struct.unpack('<I',read(f,name_rva,4))[0]
  name=read(f,name_rva+4,length).decode('utf-16le')
  if name.lower().endswith('electron.exe'):
   base,image_size,checksum,timestamp=struct.unpack_from('<QIII',m,0);cv_size,cv_rva=struct.unpack_from('<II',m,76);cv=read(f,cv_rva,cv_size)
   assert cv[:4]==b'RSDS'; dump_guid=str(uuid.UUID(bytes_le=cv[4:20]));dump_age=struct.unpack_from('<I',cv,20)[0];pdb_name=cv[24:].split(b'\0')[0].decode();break
with PDB.open('rb') as f:
 h=read(f,0,56);assert h.startswith(b'Microsoft C/C++ MSF 7.00');bs,_,nb,ds,_,bm=struct.unpack_from('<6I',h,32)
 directory_blocks=struct.unpack('<'+'I'*((ds+bs-1)//bs),read(f,bm*bs,4*((ds+bs-1)//bs)))
 directory=b''.join(read(f,b*bs,bs) for b in directory_blocks)[:ds];ns=struct.unpack_from('<I',directory,0)[0];sizes=struct.unpack_from('<'+'I'*ns,directory,4);at=4+4*ns
 for i,sz in enumerate(sizes):
  blocks=0 if sz==0xffffffff else (sz+bs-1)//bs
  ids=struct.unpack_from('<'+'I'*blocks,directory,at);at+=4*blocks
  if i==1:
   info=b''.join(read(f,b*bs,bs) for b in ids)[:sz];age=struct.unpack_from('<I',info,8)[0];guid=str(uuid.UUID(bytes_le=info[12:28]));break
assert guid==dump_guid and age==dump_age
sha=hashlib.sha256()
with PDB.open('rb') as f:
 for data in iter(lambda:f.read(8*1024*1024),b''):sha.update(data)
print(json.dumps({'dump_module':{'base':hex(base),'image_size':image_size,'timestamp':hex(timestamp),'codeview_guid':dump_guid,'age':dump_age,'pdb_name':pdb_name},'cached_pdb':{'path':str(PDB),'bytes':PDB.stat().st_size,'guid':guid,'age':age,'sha256':sha.hexdigest()},'identity_equal':True,'symbol_endpoint':'https://192.168.150.219:4080/symbols','cache_scope':'existing identity-keyed cache; prior store-backed acquisition, fresh matching private-symbol CDB load'},indent=2))
