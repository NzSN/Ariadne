"""Negative controls for I5b timing, native identity and corpus admission."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import i5b_contract as subject
from test_i5a_native_contract import NativeContractTests


class I5bContractTests(unittest.TestCase):
    def setUp(self):
        fixture=NativeContractTests();fixture.setUp()
        self.manifest=fixture.manifest
        report=fixture.report
        self.row=dict(case='case',coreReport=report,expectedConclusion='consistent_with_evidence',
            assessment=dict(schema=subject.SCHEMA,profile=subject.PROFILE,identity=report['identity'],
                question=dict(site=report['query']['seeds'][0],memory_access=0),conclusion='consistent_with_evidence'),
            phaseRows=fixture.rows,phaseOutputSha256='e'*64,outputHashes={'report.json':'f'*64},
            cliSamples=[dict(run=n,elapsedMs=100,outputHashes={'report.json':'f'*64},
                backendReceipt=report['analysis_backend'],artifactSha256=report['identity']['artifact_sha256']) for n in range(6)])

    def check(self,row):
        with patch.object(subject,'native_manifest',return_value=self.manifest):
            return subject.validate_measurements([row],['case'])

    def test_valid_and_over_budget_are_separate(self):
        self.assertTrue(self.check(self.row)[0]['met'])
        bad=copy.deepcopy(self.row)
        for sample in bad['cliSamples']:sample['elapsedMs']=9000
        self.assertFalse(self.check(bad)[0]['met'])
        bad=copy.deepcopy(self.row)
        for row in bad['phaseRows']:
            row.update(binding_ns='10000000',assessment_ns='10000000',render_ns='10000000',total_ns='30000000')
        self.assertFalse(self.check(bad)[0]['met'])

    def test_missing_or_unbound_samples_do_not_qualify(self):
        changes=[lambda r:r['cliSamples'].pop(),lambda r:r['phaseRows'].pop(),
            lambda r:r['cliSamples'][2].update(elapsedMs=float('nan')),
            lambda r:r['cliSamples'][2].update(artifactSha256='0'*64),
            lambda r:r['cliSamples'][2].update(outputHashes={}),
            lambda r:r['cliSamples'][2].update(run=0),
            lambda r:r['phaseRows'][2].update(backend_query='0'*64),
            lambda r:r['assessment'].update(conclusion='unknown'),
            lambda r:r['assessment']['question'].update(site='0x0000000000401007')]
        for change in changes:
            bad=copy.deepcopy(self.row);change(bad)
            with self.assertRaises(ValueError):self.check(bad)

    def test_corpus_duplicates_and_changed_contract_are_rejected(self):
        with patch.object(subject,'native_manifest',return_value=self.manifest):
            with self.assertRaises(ValueError):subject.validate_measurements([self.row,self.row],['case'])
        frozen=subject.contract()
        frozen['maxCliMedianMs']=9000
        with patch.object(subject,'strict_json',return_value=frozen):
            with self.assertRaises(ValueError):subject.contract()


class AggregateReuseTests(unittest.TestCase):
    def test_reuse_requires_complete_current_source_tool_and_dependency_closure(self):
        import check_i5b
        import check_i5a
        import i5a_native_contract as contract
        record = dict(passed=True, sourcesStable=True, toolsStable=True,
                      sourceFixtureAcceptancePassed=True, defaultNativeVerified=True,
                      sourceHashes={'source':'hash'}, tools={'tool':'hash'}, helperManifest={'helper':'hash'},
                      qualificationEnvironment={'snapshot':'hash'},
                      gates=[dict(gate=name,exitCode=0) for name in sorted(contract.GATES)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            with patch.object(check_i5a,'sources',return_value=record['sourceHashes']), \
                 patch.object(contract,'tool_hashes',return_value=record['tools']), \
                 patch.object(contract,'native_manifest',return_value=record['helperManifest']), \
                 patch.object(check_i5b,'active_identity',return_value=record['qualificationEnvironment']):
                path.write_text(json.dumps(record))
                self.assertEqual(check_i5b.retained_aggregate(path,'i5a-regression'),record)
                changes = [lambda r:r.update(passed=False), lambda r:r.update(sourcesStable=False),
                           lambda r:r.update(toolsStable=False), lambda r:r.update(defaultNativeVerified=False),
                           lambda r:r.update(sourceFixtureAcceptancePassed=False),
                           lambda r:r.update(sourceHashes={}), lambda r:r.update(tools={}),
                           lambda r:r.update(helperManifest={}),lambda r:r.update(qualificationEnvironment={}),
                           lambda r:r['gates'].pop(), lambda r:r['gates'][0].update(exitCode=1),
                           lambda r:r['gates'][0].update(gate=r['gates'][1]['gate'])]
                for change in changes:
                    bad=copy.deepcopy(record);change(bad);path.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):check_i5b.retained_aggregate(path,'i5a-regression')

    def test_native_reuse_rejects_candidate_partial_and_foreign_helper_records(self):
        import check_i5b
        import check_bap_core
        import i5a_native_contract as contract
        # A real retained producer record supplies the independent gate shape;
        # only live identities are mocked to exercise admission controls.
        record = json.loads((subject.ROOT/'evidence/Ariadne/i5b-qualification.json').read_text())[
            'records']['native-core-stage-e-input-bap-regressions']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'report.json'
            with patch.object(check_bap_core,'sources',return_value=record['sourceHashes']), \
                 patch.object(check_bap_core,'tools_inventory',return_value=record['tools']), \
                 patch.object(contract,'native_manifest',return_value=record['records']['generatedReplay']['helperManifest']), \
                 patch.object(check_i5b,'active_identity',return_value=record['tools']['qualificationEnvironment']):
                path.write_text(json.dumps(record))
                self.assertEqual(check_i5b.retained_aggregate(path,'native-core-stage-e-input-bap-regressions'),record)
                changes = [lambda r:r.update(stage2Qualified=False),lambda r:r.update(candidateOnly=True),
                           lambda r:r['gates'].pop(),lambda r:r.update(sourceHashes={}),
                           lambda r:r.update(tools={}),lambda r:r['tools'].update(qualificationEnvironment={}),
                           lambda r:r['records']['generatedReplay'].update(helperManifest={})]
                for change in changes:
                    bad=copy.deepcopy(record);change(bad);path.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):check_i5b.retained_aggregate(path,'native-core-stage-e-input-bap-regressions')


if __name__=='__main__':unittest.main()
