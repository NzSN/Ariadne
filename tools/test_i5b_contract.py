"""Negative controls for I5b timing, native identity and corpus admission."""
import copy
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


if __name__=='__main__':unittest.main()
