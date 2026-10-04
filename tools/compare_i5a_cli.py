#!/usr/bin/env python3
"""Compare unchanged first-question output against its retained pre-I5a oracle."""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from rust_layout import source_files
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def sources():
 paths=source_files();paths.add(ROOT/'tools/compare_i5a_cli.py')
 return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)}
def main():
 before=sources();work=Path(tempfile.mkdtemp(prefix='ariadne-i5a-equivalence-'))
 baseline=ROOT/'evidence/Ariadne/investigation-correctness-validation.json'
 expected=json.loads(baseline.read_text())['defaultOutputEquivalence']['after']
 build=subprocess.run(['cargo','build','--offline','--locked','--release','--bin','ariadne-minidump'],cwd=ROOT,capture_output=True,text=True)
 if build.returncode:raise SystemExit(build.stdout+build.stderr)
 env={**os.environ,'ARIADNE_BAP_HELPER':str(ROOT/'target/ariadne-bap-lift'),'BAP_RUNTIME_ROOT':str(ROOT/'tmp/bap-setup/stable')}
 cases=[('linux','tests/input/fixtures/stage_b_linux.dmp','401000','401006'),('windows','tests/input/fixtures/stage_b_windows.dmp','7ff700001000','7ff700001006'),('not','tests/input/fixtures/bap_precision_linux.dmp','401000','401006'),('real-linux','tmp/priority1/chromium-member-uaf.dmp','566817922dc5','566817922e42')]
 actual={}
 for label,dump,entry,site in cases:
  out=work/label
  run=subprocess.run([str(ROOT/'target/release/ariadne-minidump'),str(ROOT/dump),'--decoder-reference',str(ROOT/'target/ariadne-llvm-mc'),'--entry',entry,'--explain-fault-address',site,'--memory-access','0','--output-dir',str(out)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
  if run.returncode:raise SystemExit(run.stdout+run.stderr)
  actual[label]={p.name:sha(p) for p in out.iterdir() if p.is_file()}
 stable=before==sources()
 result=dict(schema='ariadne.i5a-cli-equivalence/v1',passed=stable and actual==expected,sourcesStable=stable,sourceHashes=before,baselineRecordSha256=sha(baseline),expected=expected,actual=actual,reports=sum(map(len,actual.values())),scope='Retained output hashes are comparison oracles only; no old acceptance record is reused as current qualification.')
 (work/'report.json').write_text(json.dumps(result,indent=2)+'\n');print('Report:',work/'report.json',flush=True)
 if not result['passed']:raise SystemExit('default reports changed or sources unstable')
if __name__=='__main__':main()
