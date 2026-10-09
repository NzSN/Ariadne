"""Negative controls for narrowly declared profile metadata normalization."""
import copy,hashlib,json,unittest
from bap_profile_migration import V2,V3,canonical,replacements,normalize_text
class MigrationTests(unittest.TestCase):
 def documents(self,profile):
  semantic=dict(helper_sha256='a'*64,runtime_sha256='b'*64,ast_sha256='c'*64,projection=profile)
  report=dict(identity=dict(decoder_target='x64',decoder_build='LLVM',decoder_protocol=2,effects_ruleset=profile,location_catalogue='cells'),preparation=dict(sites=[dict(va='0x0000000000001000',semantic=semantic)]),analysis=dict(slice=['0x0000000000001000']))
  facts=[[0x1000,'a'*64,'b'*64,'c'*64,profile]];binding=hashlib.sha256(json.dumps(facts,separators=(',',':')).encode()).hexdigest()
  scope='d'*64 if profile==V2 else 'e'*64;key='evidence:'+('f'*64 if profile==V2 else '0'*64)
  explanation=dict(identity=dict(semantic_profile=':'.join(['x64','LLVM','2',profile,'cells',binding])),scope_id=scope,
   evidence=[dict(id=key,scope_id=scope,instruction=dict(projection=profile,bytes_hex='4889d8',helper_sha256='a'*64,gaps=[]))],
   facts=[],claims=[],origins=[dict(evidence_id=key)])
  return report,explanation
 def normalized(self,report,explanation):
  values=replacements(report,explanation)
  return canonical(json.loads(normalize_text(canonical(dict(report=report,explanation=explanation)),values)))
 def test_profile_and_resolved_ids_are_the_only_permitted_changes(self):
  old=self.documents(V2);new=self.documents(V3)
  self.assertEqual(self.normalized(*old),self.normalized(*new))
  for field,value in [('bytes_hex','4889c8'),('helper_sha256','1'*64),('gaps',['lost-data']),('projection','unreviewed')]:
   bad=copy.deepcopy(new);bad[1]['evidence'][0]['instruction'][field]=value
   self.assertNotEqual(self.normalized(*old),self.normalized(*bad))
  bad=copy.deepcopy(new);bad[0]['analysis']['slice']=[]
  self.assertNotEqual(self.normalized(*old),self.normalized(*bad))
 def test_invalid_binding_scope_and_unresolved_references_are_rejected(self):
  report,explanation=self.documents(V3)
  for mutation in ['binding','scope','reference','profile']:
   r,e=copy.deepcopy((report,explanation))
   if mutation=='binding':e['identity']['semantic_profile']='unbound'
   if mutation=='scope':e['evidence'][0]['scope_id']='bad'
   if mutation=='reference':e['origins'][0]['evidence_id']='evidence:missing'
   if mutation=='profile':r['identity']['effects_ruleset']='v4'
   with self.assertRaises(ValueError):self.normalized(r,e)
if __name__=='__main__':unittest.main()
