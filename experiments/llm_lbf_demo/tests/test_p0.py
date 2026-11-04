"""Offline P0 preparation tests. Synthetic approval/HTTP data never leave temp dirs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1.common import canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import payload
from experiments.llm_lbf_demo.e1.executor import executor_source_hash,EXECUTOR_VERSION
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.e1.worlds import load_manifest
from experiments.llm_lbf_demo.p0 import transport
from experiments.llm_lbf_demo.p0.prepare import ROOT,E1,bundle,budget,authorize,execute,freeze,smoke_slots,validate_smoke
from experiments.llm_lbf_demo.p0.report import usage_cost,report,pending_report


class TestP0Preparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal=read_json(ROOT/'live.proposed.json')
        cls.worlds=load_manifest()
        cls.binding=bundle(cls.proposal)

    def test_executor_and_exact_policy_review_copy_frozen(self):
        locked=read_json(ROOT/'executor.freeze.json')
        self.assertEqual(locked['executor_version'],'e1-motion-2')
        self.assertEqual(locked['executor_source_hash'],executor_source_hash())
        self.assertEqual((ROOT/'review/e1_policies.json').read_bytes(),(E1/'e1_policies.json').read_bytes())
        with patch('experiments.llm_lbf_demo.p0.prepare.executor_source_hash',return_value='modified'):
            with self.assertRaisesRegex(ValueError,'frozen executor changed'):bundle(self.proposal)

    def test_exact_snapshot_proposal_and_retry_inclusive_budget(self):
        self.assertEqual([m['id'] for m in self.proposal['models']],
                         ['gpt-4o-mini-2024-07-18','gpt-4.1-mini-2025-04-14'])
        self.assertFalse(self.proposal['explicit_live_approval'])
        gate=budget(self.proposal,'gate');smoke=budget(self.proposal,'smoke')
        self.assertEqual(gate['scheduled_calls'],144);self.assertEqual(gate['maximum_provider_attempts'],432)
        self.assertAlmostEqual(gate['worst_case_usd'],1.3096512)
        self.assertAlmostEqual(smoke['worst_case_usd'],.0363792)
        self.assertLess(gate['maximum_conservative_prompt_bound'],10000)
        self.assertEqual(gate['dollar_ceiling'],1.50);self.assertEqual(smoke['dollar_ceiling'],.05)
        changed=copy.deepcopy(self.proposal);changed['models'][0]['max_output_tokens']=512
        with self.assertRaisesRegex(ValueError,'proposal settings disagree'):bundle(changed)

    def test_unauthorized_and_heldout_calls_blocked_before_transport(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(transport,'urlopen',side_effect=AssertionError('no network')) as http:
            with self.assertRaises(PermissionError):execute('smoke',self.proposal,tmp,{}, {},live=True)
            with self.assertRaises(PermissionError):execute('smoke',self.proposal,tmp,{}, {},live=False)
            with self.assertRaises(ValueError):execute('e1',self.proposal,tmp,{}, {},live=True)
            http.assert_not_called()
        spending={'approved':True,'approved_by':'SYNTHETIC TEST','approved_at':'test',
                  'proposal_hash':digest(self.proposal),'phases':['smoke'],'max_usd':{'smoke':.05}}
        self.assertEqual(authorize(self.proposal,spending,'smoke'),.05)
        with self.assertRaises(PermissionError):authorize(self.proposal,spending,'gate')
        spending['max_usd']['smoke']=.01
        with self.assertRaises(PermissionError):authorize(self.proposal,spending,'smoke')

    def test_smoke_development_only_and_does_not_enter_formal_gate(self):
        slots=smoke_slots(self.worlds);by_id={w['family_id']:w for w in self.worlds}
        self.assertEqual(len(slots),4)
        self.assertTrue(all(s['stage']=='smoke' and by_id[s['family_id']]['split']=='development' for s in slots))
        self.assertEqual({(s['model_role'],s['language']) for s in slots},
                         {('primary','EN'),('primary','VI'),('replication','EN'),('replication','VI')})

    def test_mocked_provider_parameters_and_raw_usage_preserved(self):
        model=self.proposal['models'][0]
        request=payload(self.worlds[0]['state'],'P0 fixture')
        data={'id':'synthetic','model':model['id'],'service_tier':'default',
              'usage':{'prompt_tokens':100,'completion_tokens':12},
              'choices':[{'message':{'content':'{"targets":{"A":"b0","B":null}}'}}]}
        with patch.dict(transport.os.environ,{'OPENAI_API_KEY':'SYNTHETIC_TEST'}),patch.object(transport,'urlopen') as http:
            handle=http.return_value.__enter__.return_value;handle.read.return_value=json.dumps(data).encode()
            handle.headers={'x-request-id':'synthetic-request'}
            result=transport.P0Provider().complete(request,model)
            body=json.loads(http.call_args.args[0].data)
            self.assertEqual(body,{**request,**transport.SETTINGS,'model':model['id']})
            self.assertEqual(result['raw_provider_response'],data)
            self.assertEqual(result['effective_request'],body)
            self.assertNotIn('max_tokens',body)

    def test_usage_cost_cached_unknown_and_never_fake_invoice(self):
        model=self.proposal['models'][0]
        response={'usage':{'prompt_tokens':100,'completion_tokens':20,'prompt_tokens_details':{'cached_tokens':40}}}
        self.assertAlmostEqual(usage_cost(response,model),.000024)
        for response in ({},{'usage':None},{'usage':{'prompt_tokens':100}}):
            self.assertIsNone(usage_cost(response,model))

    def journal_fixture(self,path,kind='gate',real=False,first_infra=False):
        slots=(__import__('experiments.llm_lbf_demo.e1.run_e1',fromlist=['slots_for']).slots_for(self.worlds,'gate')
               if kind=='gate' else smoke_slots(self.worlds))
        by_role={m['role']:m for m in self.proposal['models']}
        with Journal(path) as log:
            log.append({'event':'run','config_hash':'SYNTHETIC TEST ONLY','config':{
                'infrastructure_validation':not real,'config':{'workflow_phase':kind,'p0_binding_hash':digest(self.binding)},
                'executor_version':EXECUTOR_VERSION,'gate_binding':'synthetic','manifest_hash':digest(self.worlds)}})
            for i,s in enumerate(slots):
                model=by_role[s['model_role']];request={'messages':[{'role':'user','content':'synthetic development fixture'}]}
                if first_infra and i==0:
                    log.append({'event':'started','slot_id':s['slot_id'],'slot':s,'attempt':0,'request':request,'reserved_usd':.001})
                    log.append({'event':'infra','slot_id':s['slot_id'],'attempt':0})
                attempt=1 if first_infra and i==0 else 0
                log.append({'event':'started','slot_id':s['slot_id'],'slot':s,'attempt':attempt,'request':request,'reserved_usd':.001})
                log.append({'event':'response','slot_id':s['slot_id'],'attempt':attempt,'response':{
                    'model':model['id'],'effective_request':{**request,**transport.SETTINGS,'model':model['id']},
                    'raw_provider_response':{'service_tier':'default'},'usage':{'prompt_tokens':100,'completion_tokens':20}}})
                log.append({'event':'terminal','slot_id':s['slot_id'],'slot':s,'verdict':{'status':'GOOD','good':True,
                    'format_valid':True,'capacity_feasible':True,'geometric_feasible':True,'physical_valid':True,'comparison_valid':True}})

    def test_four_conditions_each_36_cost_and_infra_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attempts.jsonl';self.journal_fixture(path,first_infra=True)
            result=report(path,self.proposal)
            self.assertEqual(len(result['conditions']),4)
            self.assertFalse(result['held_out_E1_authorized']) # synthetic fixture never real evidence
            for row in result['conditions']:
                self.assertEqual(row['scheduled_calls'],36);self.assertEqual(row['completed_calls'],36)
                self.assertEqual(row['parseability'],1);self.assertEqual(row['capacity_validity'],1)
                self.assertEqual(row['geometric_validity'],1);self.assertEqual(row['progressive_goodness'],1)
                self.assertGreater(row['observed_usage_cost_usd'],0);self.assertFalse(row['cost_is_invoiced'])
            self.assertEqual(sum(r['infrastructure_failed_attempts'] for r in result['conditions']),1)
            self.assertEqual(sum(r['attempts_with_unknown_cost'] for r in result['conditions']),1)

    def test_real_smoke_required_before_final_freeze(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attempts.jsonl';self.journal_fixture(path,'smoke')
            with self.assertRaises(PermissionError):validate_smoke(path,self.proposal,self.binding)
            with self.assertRaises(ValueError):report(path,self.proposal,'gate')
        # Tests never generate an apparent real approval/frozen artifact.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):freeze(self.proposal,Path(tmp)/'missing',{},Path(tmp)/'final.json')
            self.assertFalse((Path(tmp)/'final.json').exists())

    def test_pending_report_is_not_observed_results(self):
        result=pending_report(self.proposal)
        self.assertEqual(result['paid_calls_made'],0);self.assertEqual(len(result['conditions']),4)
        for row in result['conditions']:
            self.assertEqual(row['scheduled_calls'],36);self.assertIsNone(row['observed_usage_cost_usd'])
            self.assertIsNone(row['parseability']);self.assertIsNone(row['passed'])


if __name__=='__main__':unittest.main()
