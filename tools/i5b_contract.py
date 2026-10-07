"""Source/tool identity and independent timing admission for I5b records."""
import math
from pathlib import Path
import statistics
from i5a_native_contract import (environment, native_manifest, sha, strict_json,
    source_inventory as previous_sources, tool_hashes as previous_tools,
    validate_backend_receipt, validate_phase_rows)

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='ariadne.zero-base-offset-assessment/v1'
PROFILE='windows-amd64-av-scalar-mov-base-displacement-v1'
PERFORMANCE=ROOT/'tests/input/fixtures/i5b/performance.json'


def sources():
    result=previous_sources()
    paths=list((ROOT/'tools').glob('*i5b*.py'))
    paths += [ROOT/'Specs'/name for name in ['AriadneZeroBaseOffset.tla','ZeroBaseOffset.cfg','check-zero-base-offset.sh']]
    for p in paths: result[str(p.relative_to(ROOT))]=sha(p)
    return dict(sorted(result.items()))


def tools():
    return {**previous_tools(),'target/release/i5b':sha(ROOT/'target/release/i5b')}


def contract():
    record=strict_json(PERFORMANCE.read_text())
    expected={'warmups':1,'measuredRepeats':5,'maxPhaseMedianMs':10,'maxCliMedianMs':1500,
              'maxEvidence':64,'maxClaims':64}
    if record.get('schema')!='ariadne.i5b-performance-contract/v1' or any(
        type(record.get(k)) is not int or record[k]!=v for k,v in expected.items()):
        raise ValueError('changed or malformed frozen I5b contract')
    return record


def validate_measurements(rows, expected_names):
    frozen=contract()
    if len(rows)!=len(expected_names) or {r.get('case') for r in rows}!=set(expected_names):
        raise ValueError('measurement corpus is incomplete or duplicated')
    manifest=native_manifest()
    results=[]
    for row in rows:
        report=row['coreReport']
        validate_backend_receipt(report,manifest)
        assessment=row['assessment']
        if (assessment.get('schema')!=SCHEMA or assessment.get('profile')!=PROFILE
            or assessment['identity']['artifact_sha256']!=report['identity']['artifact_sha256']
            or assessment['identity']['query_id']!=report['identity']['query_id']
            or assessment['conclusion']!=row['expectedConclusion']
            or assessment['question']['site']!=report['query']['seeds'][0]
            or assessment['question']['memory_access']!=0):
            raise ValueError('assessment/capture/query/oracle binding differs')
        samples=row['cliSamples']
        if len(samples)!=frozen['warmups']+frozen['measuredRepeats']:
            raise ValueError('missing CLI samples')
        for n,sample in enumerate(samples):
            if (type(sample.get('run')) is not int or sample['run']!=n
                or type(sample.get('elapsedMs')) not in [int,float]
                or not math.isfinite(sample['elapsedMs']) or sample['elapsedMs']<=0
                or sample['outputHashes']!=row['outputHashes']
                or sample['backendReceipt']!=report['analysis_backend']
                or sample['artifactSha256']!=report['identity']['artifact_sha256']):
                raise ValueError('invalid or unbound CLI timing sample')
        translated=dict(warmups=1,repeats=5,phaseMedianBudgetMs=10,cliMedianBudgetMs=1500)
        conclusion={'consistent_with_evidence':'ConsistentWithEvidence',
                    'refuted_under_premises':'RefutedUnderPremises','unknown':'Unknown'}[row['expectedConclusion']]
        phases=validate_phase_rows(row['phaseRows'],report,manifest,translated,
            conclusion=conclusion,output_sha256=row['phaseOutputSha256'])
        cli=statistics.median(s['elapsedMs'] for s in samples[1:])
        phase=statistics.median(phases)
        results.append(dict(case=row['case'],cliMedianMs=cli,phaseMedianMs=phase,
            cliSpreadMs=max(s['elapsedMs'] for s in samples[1:])-min(s['elapsedMs'] for s in samples[1:]),
            phaseSpreadMs=max(phases)-min(phases),met=cli<=1500 and phase<=10))
    return results
