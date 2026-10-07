#!/usr/bin/env python3
"""Real-code I5b mutations with unchanged independent observers and isolated builds."""
import argparse
import json
from pathlib import Path
import subprocess
from rust_layout import copy_sut
from i5b_contract import ROOT,environment,sha,sources

ZERO='src/investigation/zero_base_offset.rs'
OLD='src/investigation/zero_address.rs'
CORPUS='independent_corpus_covers_six_forms_and_admission_negatives'
BUDGET='budgets_binding_and_strict_decoding_preserve_unknown_or_errors'
MUTATIONS=[
 ('nonzero-base-as-zero',CORPUS,[(ZERO,'d.value == Some(0)','d.value == Some(1)')]),
 ('zero-displacement-as-offset',CORPUS,[(ZERO,'d.displacement.is_some_and(|n| n != 0)','d.displacement.is_some_and(|n| n == 0)')]),
 ('effective-zero-as-base-zero',CORPUS,[(ZERO,'d.value == Some(0)','d.address == Some(0)')]),
 ('index-as-encoded-base',CORPUS,[(ZERO,'r.base.as_deref().and_then(gpr_bank)','r.base.as_deref().or(r.index.as_deref()).and_then(gpr_bank)'),(ZERO,'if r.index.is_some()','if false')]),
 ('ignore-bil-displacement','decoded_bil_disagreement_and_missing_receipt_are_unknown',[(ZERO,'x.constant != r.displacement as u64','false')]),
 ('ignore-decoder-identity','decoded_bil_disagreement_and_missing_receipt_are_unknown',[(ZERO,'r.decoder_sha256.is_none()','false')]),
 ('drop-displacement',CORPUS,[(OLD,'let mut address = expression.constant;','let mut address = 0u64;')]),
 ('missing-register-zero-fill',CORPUS,[(OLD,'if let Some(value) = fields.get(format!("reg:{reg}").as_str()) {','if let Some(value) = Some(fields.get(format!("reg:{reg}").as_str()).unwrap_or(&0)) {')]),
 ('thread-context-substitution',CORPUS,[('src/input/fault_context.rs','let decoded = metadata.exception.as_ref().map(|e| &e.registers);','let decoded = metadata.threads.first().map(|e| &e.registers);')]),
 ('suppress-data-span-conflict',CORPUS,[(OLD,'d.gaps.insert("reported-data-address-mismatch".into());','let _ = &d.gaps;')]),
 ('ignore-query-binding',BUDGET,[('src/investigation/validate.rs','analyzer.request() != expected','false')]),
 ('ignore-receipt-recomputation',BUDGET,[('src/llvm_mc/address_reference.rs','!= Some(self)','.is_none()')]),
 ('ignore-evidence-limit',BUDGET,[(ZERO,'data.truncate(limits.max_evidence);','// omitted evidence limit')]),
 ('ignore-claim-limit',BUDGET,[(ZERO,'claims.truncate(limits.max_claims);','// omitted claim limit')]),
 ('definite-after-missing-evidence',CORPUS,[(ZERO,'let conclusion = if !d.gaps.is_empty() {','let conclusion = if false {')]),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();work=args.output.resolve();work.mkdir(parents=True,exist_ok=False)
    before=sources();sut=work/'sut';copy_sut(sut)
    observers={str(p.relative_to(sut)):sha(p) for p in (sut/'tests').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    checked=set();rows=[]
    for name,test,changes in MUTATIONS:
        command=['cargo','test','--offline','--locked','--release','--manifest-path',str(sut/'Cargo.toml'),
            '--target-dir',str(ROOT/'target/i5b-mutations'/work.name),'--test','input_i5b',test,'--','--exact']
        if test not in checked:
            baseline=subprocess.run(command,cwd=ROOT,env=environment(),capture_output=True,text=True,timeout=600)
            (work/(test+'-baseline.log')).write_text(baseline.stdout+baseline.stderr)
            if baseline.returncode or f'test {test} ... ok' not in baseline.stdout:
                raise RuntimeError('unchanged observer baseline failed: '+test)
            checked.add(test)
        originals={}
        try:
            for filename,old,new in changes:
                p=sut/filename;s=p.read_text();originals.setdefault(filename,s)
                if s.count(old)!=1: raise RuntimeError('nonunique mutation anchor: '+name)
                p.write_text(s.replace(old,new))
            result=subprocess.run(command,cwd=ROOT,env=environment(),capture_output=True,text=True,timeout=300)
        finally:
            for filename,text in originals.items(): (sut/filename).write_text(text)
        output=result.stdout+result.stderr;(work/(name+'.log')).write_text(output)
        detected=result.returncode==101 and f'test {test} ... FAILED' in output and 'could not compile' not in output
        rows.append(dict(mutation=name,test=test,detected=detected,exitCode=result.returncode))
        print(name,'detected' if detected else 'NOT DETECTED',flush=True)
        if not detected: raise RuntimeError('no intended behavioral mismatch: '+name)
    stable=before==sources();unchanged=all(sha(sut/p)==digest for p,digest in observers.items())
    record=dict(schema='ariadne.i5b-mutations/v1',passed=stable and unchanged and all(r['detected'] for r in rows),
        sourcesStable=stable,sourceHashes=before,observersUnchanged=unchanged,observerHashes=observers,mutants=rows)
    (work/'report.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Report:',work/'report.json',flush=True)
    raise SystemExit(0 if record['passed'] else 1)


if __name__=='__main__':main()
