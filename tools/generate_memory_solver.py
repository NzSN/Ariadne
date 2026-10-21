#!/usr/bin/env python3
"""Derive the reviewed finite Memory solver copy; never replace its authority."""
import argparse,hashlib,json
from pathlib import Path
OLD_BLOCK = 'And(x, m) == Bit(x,0)*Bit(m,0) + 2*Bit(x,1)*Bit(m,1)\n             + 4*Bit(x,2)*Bit(m,2) + 8*Bit(x,3)*Bit(m,3)\n\\* @type: (Str, Int, Int) => Int;\nForward(kind, x, c) ==\n  CASE kind = "copy" -> x\n    [] kind = "add" -> (x+c) % Modulus\n    [] kind = "sub" -> (x-c) % Modulus\n    [] kind = "and" -> And(x,c)\n    [] OTHER -> c'

def sha(data):return hashlib.sha256(data).hexdigest()
def need(test,message):
 if not test:raise SystemExit(message)
def table(name,rows):
 return '\\* @type: Seq(Seq(Int));\n'+name+' == <<\n'+',\n'.join('  <<'+', '.join(map(str,row))+'>>'for row in rows)+'\n>>\n'
def rename(source,name):
 old='MODULE AriadneMemoryRefinement ';need(source.count(old)==1,'module header differs');return source.replace(old,'MODULE '+name+' ',1)
def write(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data.encode()if isinstance(data,str)else data)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--specs',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();specs=a.specs.resolve();controls=specs/'memory-lookup';profile=json.loads((controls/'profile.json').read_text());source=(specs/'AriadneMemoryRefinement.tla').read_bytes();need(sha(source)==profile['authority_sha256'],'algebraic authority differs from qualified finite profile');text=source.decode()
 values=range(16);tables={kind:[[{'add':(x+c)&15,'sub':(x-c)&15,'and':x&c}[kind]for c in values]for x in values]for kind in ['add','sub','and']}
 for x in values:
  for c in values:
   need(tables['add'][x][c]==(x+c)%16 and tables['sub'][x][c]==(x-c)%16 and tables['and'][x][c]==sum(2**p*((x//2**p)%2)*((c//2**p)%2)for p in range(4)),'literal arithmetic differs')
 block=''.join(table(name,tables[kind])for name,kind in [('AddTable','add'),('SubTable','sub'),('AndTable','and')])
 block+='\\* Lookup indices are admitted 0..15 values, shifted to TLA+ 1-based sequences.\n\\* Generic outside-carrier integer arguments remain solely with the authority.\n\\* @type: (Int, Int) => Int;\nAnd(x, m) == AndTable[x+1][m+1]\n\\* @type: (Str, Int, Int) => Int;\nForward(kind, x, c) ==\n  CASE kind = "copy" -> x\n    [] kind = "add" -> AddTable[x+1][c+1]\n    [] kind = "sub" -> SubTable[x+1][c+1]\n    [] kind = "and" -> And(x,c)\n    [] OTHER -> c'
 before='\\* @type: (Int, Int) => Int;\n'+OLD_BLOCK;need(text.count(before)==1,'And/Forward seam differs');solver=text.replace(before,block,1);need(solver.replace(block,before,1)==text,'unrelated algebra bytes changed');need(sha(solver.encode())==profile['solver_sha256'],'deterministic lookup copy differs from qualified bytes')
 inputs={}
 for name,row in profile['partition_inputs'].items():
  need(Path(name).name==name and (name.startswith('MemoryPair')or name=='MemoryRefinement.cfg'),'unexpected partition filename')
  data=(specs/name).read_bytes();need(len(data)==row['bytes']and sha(data)==row['sha256'],'partition/config differs: '+name);inputs[name]=data
 control_data={}
 need(set(profile['control_inputs'])=={'FiniteLookupEquality.tla','FiniteLookupPointwise.cfg','FiniteLookupWhole.cfg'},'equality control inventory differs')
 for name,row in profile['control_inputs'].items():
  data=(controls/name).read_bytes();need(len(data)==row['bytes']and sha(data)==row['sha256'],'equality control differs: '+name);control_data[name]=data
 std=(specs/'Apalache.tla').read_bytes();license_data=(specs/'Apalache.LICENSE').read_bytes();need(len(std)==6500 and sha(std)==profile['standard_module_sha256'],'pinned standard module differs');need(sha(license_data)==profile['license_sha256'],'standard-module license differs')
 out=a.output.resolve();need(not out.exists(),'use a fresh output directory; existing data is never overwritten');out.mkdir(parents=True)
 write(out/'authority/AriadneMemoryRefinement.tla',source);write(out/'authority/MemoryRefinement.cfg',inputs['MemoryRefinement.cfg']);write(out/'solver/AriadneMemoryRefinement.tla',solver)
 for name,data in inputs.items():write(out/'solver'/name,data)
 write(out/'controls/AriadneMemoryRefinementAlgebra.tla',rename(text,'AriadneMemoryRefinementAlgebra'));write(out/'controls/AriadneMemoryRefinementLookup.tla',rename(solver,'AriadneMemoryRefinementLookup'))
 for name,data in control_data.items():write(out/'controls'/name,data)
 for directory in ['authority','solver','controls']:
  write(out/directory/'Apalache.tla',std);write(out/directory/'Apalache.LICENSE',license_data)
 manifest={'schema':'ariadne.memory-solver-materialization/v1','authority_sha256':sha(source),'solver_sha256':sha(solver.encode()),'profile_sha256':sha((controls/'profile.json').read_bytes()),'generator_sha256':sha(Path(__file__).read_bytes()),'carrier':profile['carrier'],'scope':profile['scope'],'files':{str(p.relative_to(out)):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())}for p in sorted(out.rglob('*'))if p.is_file()}}
 write(out/'manifest.json',json.dumps(manifest,indent=2)+'\n');print('Finite Memory solver artifacts: '+str(out))
if __name__=='__main__':main()
