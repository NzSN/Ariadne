"""Strict v2-to-v3 metadata migration; preserve the historical byte oracle."""
import copy,hashlib,io,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
V2='bap-bit-provenance-v2';V3='bap-bit-provenance-v3'
# P0's pre-runtime source snapshot; verified against all frozen source hashes.
BASELINE_REVISION='ebb2e534e8da339f498f20d0a9e1e0b8506a3bdd'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def legacy_source_build(output):
 output=Path(output);source=output/'source';source.mkdir(parents=True)
 head=BASELINE_REVISION
 frozen=json.loads((ROOT/'evidence/Ariadne/bap-admission/p0-contract-freeze.json').read_text())
 for name,expected in frozen['baselineSourceHashes'].items():
  raw=subprocess.check_output(['git','show',head+':'+name],cwd=ROOT)
  if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Git baseline differs from frozen P0 source: '+name)
 raw=subprocess.check_output(['git','archive',head,'src','Cargo.toml','Cargo.lock','native/bap/toolchain.lock.json'],cwd=ROOT)
 with tarfile.open(fileobj=io.BytesIO(raw)) as tar:tar.extractall(source,filter='data')
 sources={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file()}
 manifest=source/'Cargo.toml';original=manifest.read_text()
 old='path = "../MirrorRust"';new='path = "'+str(ROOT.parent/'MirrorRust')+'"'
 if original.count(old)!=1:raise ValueError('legacy dependency path anchor differs')
 manifest.write_text(original.replace(old,new))
 command=['cargo','build','--offline','--locked','--release','--manifest-path',str(manifest),'--target-dir',str(output/'build'),'--bin','ariadne-minidump']
 result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=600)
 (output/'build.log').write_text(result.stdout+result.stderr)
 if result.returncode:raise ValueError('frozen source build failed: '+result.stdout[-1000:]+result.stderr[-2000:])
 executable=output/'build/release/ariadne-minidump'
 return executable,dict(revision=head,sourceHashes=sources,effectiveManifestSha256=sha(manifest),
  manifestChange='only optional MirrorRust dependency path rebased to the selected sealed dependency view',executableSha256=sha(executable))
def profile_binding(report,explanation):
 identity=report['identity'];sites=report['preparation']['sites']
 facts=[[int(s['va'],16),(s.get('semantic') or {}).get('helper_sha256'),(s.get('semantic') or {}).get('runtime_sha256'),
          (s.get('semantic') or {}).get('ast_sha256'),(s.get('semantic') or {}).get('projection')] for s in sites]
 binding=hashlib.sha256(json.dumps(facts,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
 expected=':'.join([identity['decoder_target'],identity['decoder_build'],str(identity['decoder_protocol']),identity['effects_ruleset'],identity['location_catalogue'],binding])
 if explanation['identity']['semantic_profile']!=expected:raise ValueError('semantic profile does not bind exact site/tool facts')
def replacements(report,explanation):
 """Normalize only declared profile metadata and its resolved content graph IDs."""
 profile=report['identity']['effects_ruleset']
 if profile not in (V2,V3):raise ValueError('unexpected comparison profile')
 profile_binding(report,explanation)
 values={profile:'bap-bit-provenance-profile-migration',explanation['identity']['semantic_profile']:'validated-projection-profile-migration',
         explanation['scope_id']:'validated-projection-scope-migration'}
 definitions={}
 for field in ['evidence','facts','claims']:
  for row in explanation[field]:
   if row['id'] in definitions or row['scope_id']!=explanation['scope_id']:raise ValueError('duplicate/wrong-scope comparison record')
   definitions[row['id']]=row
 active=set()
 def replace(value):
  if isinstance(value,str):
   if value in definitions:return resolve(value)
   if value in values:return values[value]
   if value.startswith(('evidence:','fact:','claim:')):raise ValueError('unresolved content reference')
   return value
  if isinstance(value,list):return [replace(x) for x in value]
  if isinstance(value,dict):return {k:replace(v) for k,v in value.items() if k not in ('id','scope_id')}
  return value
 def resolve(key):
  if key in values:return values[key]
  if key in active:raise ValueError('cyclic content references')
  active.add(key);body=replace(definitions[key]);active.remove(key)
  values[key]=key.split(':')[0]+':'+hashlib.sha256(canonical(body).encode()).hexdigest()
  return values[key]
 for key in definitions:resolve(key)
 replace(explanation)
 return values
def normalize_text(text,mapping):
 for original,replacement in sorted(mapping.items(),key=lambda pair:len(pair[0]),reverse=True):text=text.replace(original,replacement)
 return text
def compare_directories(legacy,current):
 legacy=Path(legacy);current=Path(current)
 validator=ROOT/'target/release/bap-admission-validate'
 result=subprocess.run([validator,legacy/'explanation.json',current/'explanation.json'],capture_output=True,text=True)
 if result.returncode:raise ValueError('invalid explanation content IDs: '+result.stderr)
 def load(directory):
  report=json.loads((directory/'report.json').read_text());explanation=json.loads((directory/'explanation.json').read_text())
  return report,explanation,replacements(report,explanation)
 _,_,old=load(legacy);_,_,new=load(current)
 for name in ['report.json','report.txt','report.dot','explanation.json','explanation.txt','explanation.dot']:
  a=normalize_text((legacy/name).read_text(),old);b=normalize_text((current/name).read_text(),new)
  if name.endswith('.json'):a=canonical(json.loads(a));b=canonical(json.loads(b))
  if a!=b:raise ValueError('projection migration changed non-profile output: '+name)
 return dict(profileMigrationVerified=True,reports=6,allowedChanges=['projection labels','validated semantic-profile binding','resolved scope/evidence/fact/claim IDs'])
