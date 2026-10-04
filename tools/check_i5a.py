#!/usr/bin/env python3
"""Source/fixture I5a acceptance with separate, unexercised real-Windows tiers."""
import argparse,hashlib,json,os,subprocess,tempfile,time
from datetime import datetime,timezone
from pathlib import Path
from rust_layout import source_files
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=source_files()
 for tree in ['native/bap','native/llvm_mc']:
  paths.update(p for p in (ROOT/tree).rglob('*') if p.is_file() and p.suffix!='.md' and '__pycache__' not in p.parts)
 paths.update(ROOT/p for p in ['tools/check_i5a.py','tools/check_i5a_mutations.py','tools/measure_i5a.py','tools/compare_i5a_cli.py','tools/check_investigation.py','tools/check_investigation_mutations.py','tools/measure_investigation.py','tools/investigation_budget.py','tools/test_investigation_budget.py','tools/check_rust_layout.py'])
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def retained(path):
 data=json.loads(path.read_text())
 if not data.get('passed') or not data.get('sourcesStable') or not data.get('sourceHashes') or any(sha(ROOT/p)!=d for p,d in data['sourceHashes'].items()):raise RuntimeError('stale/nonpassing retained record: '+str(path))
 for p,d in data.get('tools',{}).items():
  if p.startswith(('target/','tmp/')) and sha(ROOT/p)!=d:raise RuntimeError('retained tool changed: '+p)
 return data

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ['mutations','measurements','equivalence','investigation']:parser.add_argument('--'+name+'-record',type=Path)
 args=parser.parse_args();before=sources();work=Path(tempfile.mkdtemp(prefix='ariadne-i5a-acceptance-'))
 env={**os.environ,'ARIADNE_LLVM_MC':str(ROOT/'target/ariadne-llvm-mc'),'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 graph=ROOT/'tmp/graphviz-headers/root'
 if (graph/'usr/bin/dot').is_file():
  env['ARIADNE_DOT']=str(graph/'usr/bin/dot');env['GVBINDIR']=str(graph/'usr/lib/x86_64-linux-gnu/graphviz');env['LD_LIBRARY_PATH']=str(graph/'usr/lib/x86_64-linux-gnu')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
 gates=[('fixtures',['python3','tests/input/fixtures/make_i5a.py','--check']),('format',['cargo','fmt','--all','--','--check']),('root-tests',['cargo','test','--offline','--locked']),('core-tests',['cargo','test','--offline','--locked','--no-default-features']),('clippy',['cargo','clippy','--offline','--locked','--all-features','--all-targets','--','-D','warnings']),('investigation-feature',['cargo','clippy','--offline','--locked','--no-default-features','--features','investigation','--all-targets','--','-D','warnings']),('layout',['python3','tools/check_rust_layout.py']),('native-corpus-cli',['cargo','test','--offline','--locked','--release','--test','input_i5a','--','--include-ignored']),('mutations',['python3','tools/check_i5a_mutations.py']),('equivalence',['python3','tools/compare_i5a_cli.py']),('measurements',['python3','tools/measure_i5a.py']),('investigation',['python3','tools/check_investigation.py'])]
 rows=[];nested={};print('I5a acceptance artifacts:',work,flush=True)
 for name,command in gates:
  start=time.monotonic();reuse=getattr(args,name+'_record',None)
  try:
   if reuse:data=retained(reuse);nested[name]=data;code=0;output=f'Reused exact source/tool-checked record: {reuse}\n'
   else:
    run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=2400);code=run.returncode;output=run.stdout+run.stderr
    for line in output.splitlines():
     if line.startswith('Report: '):nested[name]=json.loads(Path(line[8:]).read_text())
   if name in ['mutations','equivalence','measurements','investigation'] and (code==0 and not nested.get(name,{}).get('passed')):raise RuntimeError('no passing nested '+name)
  except (OSError,RuntimeError,subprocess.TimeoutExpired) as e:code=-1;output=str(e)
  log=work/(name+'.log');log.write_text(output);rows.append(dict(gate=name,command=['source-tool-check',str(reuse)] if reuse else command,exitCode=code,seconds=round(time.monotonic()-start,3),log=str(log)))
  print(name,'PASS' if code==0 else 'FAIL',flush=True)
 stable=before==sources();passed=stable and all(r['exitCode']==0 for r in rows)
 result=dict(schema='ariadne.i5a-acceptance/v1',recordedUtc=datetime.now(timezone.utc).isoformat(),passed=passed,sourceFixtureAcceptancePassed=passed,controlledRealWindowsAcceptancePassed=False,originalWindowsI4AcceptancePassed=False,sourcesStable=stable,sourceHashes=before,gates=rows,records=nested,missing=['No independently qualified controlled real Windows I5a case supplied; source/fixture tier only.','Original pinned Windows I4 artifact remains a separate unmet requirement.'],tools={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'target/ariadne-bap-lift',ROOT/'target/ariadne-llvm-mc',ROOT/'native/bap/toolchain.lock.json']},scope='Finite windows-amd64-av-scalar-mov-v1 source/fixture conformance; captured context and lifting premises remain explicit. No real Windows, root-cause or ISA-step qualification.')
 (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
