"""E1 offline protocol acceptance; never certifies human review or a live gate."""
from collections import Counter
import copy
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1 import e1_oracle as oracle
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import payload,assert_policy_only_difference,SYSTEM
from experiments.llm_lbf_demo.e1.executor import EXECUTOR_VERSION,coordinate_motion,make_env,replay,load_attempts,recovered
from experiments.llm_lbf_demo.e1.worlds import hand_fixture,load_manifest,generate,validate_manifest,identity,witness_acceptance
from experiments.llm_lbf_demo.e1.providers import FakeProvider,LiveProvider,InfrastructureError
from experiments.llm_lbf_demo.e1.run_e1 import run,slots_for,gate_binding,_replay_cached
from experiments.llm_lbf_demo.e1.analyze_e1 import analyze,cluster_intervals
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.e1.safeguards import validate_live,preflight_cost


class TestE1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=hand_fixture();cls.worlds=load_manifest();cls.policies=read_json(ROOT/'e1_policies.json')
        cls.smallslots=slots_for(cls.worlds)[:4]

    def test_hand_table_and_all_alternatives(self):
        s=self.state
        self.assertEqual(len(oracle.allocations(s)),16)
        self.assertEqual(len(oracle.good_set(s,'R')),3)
        self.assertEqual(len(oracle.good_set(s,'F')),6)
        for a,b,r,f in [('b2','b2',1,0),('b0','b1',0,1),('b0',None,0,1),('b0','b0',1,0),('b2',None,0,0),(None,None,0,0)]:
            raw=canonical({'targets':{'A':a,'B':b}})
            self.assertEqual(oracle.score(raw,s,'R')['good'],bool(r))
            self.assertEqual(oracle.score(raw,s,'F')['good'],bool(f))
        self.assertEqual(oracle.score('{"targets":{"A":null,"B":null}}',s,'R')['status'],'VACUOUS')
        for targets in oracle.good_set(s,'R')+oracle.good_set(s,'F'):
            self.assertTrue(replay(s,targets)['success'],targets)

    def test_strict_parser(self):
        bad=['{}','[]','null','{"targets":{"A":"b0","A":"b1","B":null}}',
             '{"targets":{"A":"b0","B":null},"targets":{"A":null,"B":null}}',
             '{"targets":{"A":NaN,"B":null}}',
             '{"targets":{"A":"b0","B":null},"cooperating":true}',
             '{"targets":{"A":"b0","B":null},"cooperating":false}',
             '{"targets":{"A":"thùng0","B":null}}',
             '{"targets":{"A":0,"B":null}}','```json\n{}\n```','{} trailing',
             '{"targets":{"A":"b0"}}']
        completed=copy.deepcopy(self.state);completed['tasks'][0]['completed']=True
        for raw in bad:
            with self.subTest(raw=raw):self.assertEqual(oracle.score(raw,self.state,'R')['status'],'FORMAT')
        self.assertEqual(oracle.score('{"targets":{"A":"b0","B":null}}',completed,'F')['status'],'FORMAT')

    def test_capacity_geometry_and_executor_are_separate(self):
        raw=canonical({'targets':{'A':'b2','B':None}})
        verdict=oracle.score(raw,self.state,'F')
        self.assertEqual(verdict['status'],'PHYSICS');self.assertTrue(verdict['geometric_feasible'])
        enclosed=copy.deepcopy(self.state)
        enclosed['obstacles']=[[1,4],[3,4],[2,3],[2,5]]
        feasible=canonical({'targets':{'A':'b0','B':None}})
        self.assertTrue(oracle.score(feasible,enclosed,'F')['capacity_feasible'])
        self.assertFalse(oracle.score(feasible,enclosed,'F')['geometric_feasible'])
        targets={'A':'b0','B':None}
        before=oracle.score(canonical({'targets':targets}),self.state,'F')
        stalled=replay(self.state,targets,navigator=lambda e,a:({'A':None,'B':None},None))
        self.assertEqual(stalled['status'],'EXECUTOR');self.assertTrue(before['good'])
        self.assertEqual(before,oracle.score(canonical({'targets':targets}),self.state,'F'))
        self.assertEqual(oracle.score(feasible,self.state,'F',spec_defect='injected semantic defect')['status'],'SPEC')
        tolerance=copy.deepcopy(self.state);tolerance['tasks'][0]['level']=1.+1e-10
        self.assertEqual(oracle.score(feasible,tolerance,'F')['status'],'SPEC')

    def test_ids_and_capacity_metamorphic(self):
        renamed=copy.deepcopy(self.state)
        for a in renamed['agents']:a['id']={'A':'Y','B':'X'}[a['id']]
        for t in renamed['tasks']:t['id']='renamed-'+t['id']
        for gold in ('R','F'):
            self.assertEqual(len(oracle.good_set(renamed,gold)),len(oracle.good_set(self.state,gold)))
        s=copy.deepcopy(self.state);s['tasks'][2]['level']=.8
        self.assertEqual(oracle.score('{"targets":{"A":"b2","B":null}}',s,'F')['status'],'GOOD')

    def test_gold_is_independent_of_presented_text(self):
        provider=FakeProvider('oracle');model={'id':'fixture'}
        en=self.policies['languages']['EN']
        for gold,other in [('R','F'),('F','R')]:
            good=provider.complete(payload(self.state,en[gold][0]),model)['raw']
            wrong=provider.complete(payload(self.state,en[other][0]),model)['raw']
            self.assertTrue(oracle.score(good,self.state,gold)['good'])
            self.assertEqual(oracle.score(wrong,self.state,gold)['status'],'POLICY')

    def test_payload_only_policy_changes_no_confounds(self):
        p=self.policies['languages']['EN']
        left,right=payload(self.state,p['R'][0]),payload(self.state,p['F'][0])
        assert_policy_only_difference(left,right)
        self.assertNotIn('Prefer a solo',SYSTEM)
        body=json.loads(left['messages'][1]['content'])
        self.assertEqual(set(body),{'state','policy','objective'})
        for key in ('gold','permissions','policy_id','good_set','reference','family_id'):
            self.assertNotIn(key,body)
        changed=copy.deepcopy(right);v=json.loads(changed['messages'][1]['content']);v['gold']='F';changed['messages'][1]['content']=canonical(v)
        with self.assertRaises(ValueError):assert_policy_only_difference(left,changed)
        changed=copy.deepcopy(right);changed['messages'][1]['content']+=' '
        with self.assertRaises(ValueError):assert_policy_only_difference(left,changed)
        changed=copy.deepcopy(right);v=json.loads(changed['messages'][1]['content']);v['objective']='different';changed['messages'][1]['content']=canonical(v)
        with self.assertRaises(ValueError):assert_policy_only_difference(left,changed)
        vi=self.policies['languages']['VI']
        assert_policy_only_difference(payload(self.state,p['P0'][0]),payload(self.state,vi['P0'][0]))
        self.assertEqual(self.policies['human_semantic_approval'],'awaiting_human_review')

    def test_native_actions_wait_load_and_failed_joint_attempt(self):
        env=make_env(self.state)
        before=recovered.snapshot(env);recovered.step_joint(env,{'A':None,'B':None})
        self.assertEqual(before,recovered.snapshot(env))
        recovered.step_joint(env,{'A':0,'B':None})
        self.assertEqual(env.components['agents'][0].position,(2,1))
        a,b=env.components['agents'];a.position=(3,6);a.direction=0;b.position=(5,6);b.direction=recovered.math.pi
        a.level=b.level=.1
        actions={'A':4,'B':4};self.assertEqual(len(load_attempts(env,actions)['b2']),2)
        info=recovered.step_joint(env,actions)
        self.assertEqual(info['coop'],0);self.assertFalse(env.components['tasks'][2].completed)

    def test_manifest_regeneration_splits_and_good_sets(self):
        self.assertEqual(self.worlds,generate())
        self.assertEqual(len(self.worlds),72)
        self.assertEqual(Counter(w['stratum'] for w in self.worlds if w['split']=='test'),{'light':30,'mixed':30})
        for w in self.worlds:
            a,b=oracle.good_set(w['state'],'R'),oracle.good_set(w['state'],'F')
            self.assertTrue(a and b)
            self.assertFalse({canonical(v) for v in a}&{canonical(v) for v in b})
        duplicate=copy.deepcopy(self.worlds);duplicate[1]['state']=copy.deepcopy(duplicate[0]['state'])
        with self.assertRaises(AssertionError):validate_manifest(duplicate)
        renamed=copy.deepcopy(self.state)
        for a in renamed['agents']:a['id']='other'+a['id']
        for t in renamed['tasks']:t['id']='other'+t['id']
        self.assertEqual(identity(self.state),identity(renamed))

    def test_executor_witness_coverage_retains_real_regression(self):
        old=witness_acceptance(self.worlds,ROOT/'evidence/e1_witnesses.jsonl',expected_version=None)
        self.assertEqual(old['covered'],864);self.assertEqual(old['successes'],863)
        self.assertFalse(old['accepted'])
        failure=old['failures'][0];self.assertEqual(failure['family_id'],'test-006')
        w=next(w for w in self.worlds if w['family_id']==failure['family_id'])
        self.assertTrue(oracle.score(canonical({'targets':failure['targets']}),w['state'],'F')['good'])
        legacy=replay(w['state'],failure['targets'],seed=w['simulator_seed'],navigator=recovered.navigate)
        self.assertEqual(legacy['status'],'EXECUTOR')
        self.assertEqual(legacy['trace_hash'],read_json(ROOT/'evidence/executor-v2/before.json')['executor']['trace_hash'])
        current=replay(w['state'],failure['targets'],seed=w['simulator_seed'])
        self.assertEqual(current['status'],'SUCCESS');self.assertEqual(current['ticks'],7)
        self.assertEqual(current['executor_version'],EXECUTOR_VERSION)
        self.assertFalse(current['substitutions'])
        report=witness_acceptance(self.worlds)
        self.assertEqual(report,{'covered':864,'successes':864,'failures':[],'accepted':True})

    def test_motion_arbitration_preserves_load_wait_and_inputs(self):
        proposals={'B':1,'A':2}
        self.assertEqual(coordinate_motion(proposals),{'B':None,'A':2})
        self.assertEqual(proposals,{'B':1,'A':2})
        for proposals in ({'A':4,'B':4},{'A':None,'B':None},{'A':4,'B':0},{'A':None,'B':3}):
            self.assertEqual(coordinate_motion(proposals),proposals)

    def test_motion_fix_is_not_family_seed_id_or_coordinate_specific(self):
        w=next(w for w in self.worlds if w['family_id']=='test-006')
        for dx,dy,seed in [(0,0,0),(1,1,91),(-1,0,1234)]:
            state=copy.deepcopy(w['state'])
            for entity in state['agents']+state['tasks']:
                entity['position']=[entity['position'][0]+dx,entity['position'][1]+dy]
            state['agents'][0]['id']='robot-z';state['agents'][1]['id']='robot-a'
            for t in state['tasks']:t['id']='renamed-'+t['id']
            targets={'robot-z':'renamed-b0','robot-a':'renamed-b2'}
            result=replay(state,targets,'F',seed)
            self.assertTrue(result['success'],result['diagnosis'])
            self.assertFalse(result['substitutions'])
            for tick in result['trace']:
                self.assertEqual(tick['targets'],targets)
                self.assertLessEqual(sum(a in (0,1,2,3) for a in tick['actions'].values()),1)

    def test_old_witnesses_do_not_certify_new_executor(self):
        with self.assertRaisesRegex(ValueError,'stale executor witness'):
            witness_acceptance(self.worlds,ROOT/'evidence/e1_witnesses.jsonl')

    def test_replay_cache_rejects_stale_executor_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);world=self.worlds[0]
            targets=oracle.good_set(world['state'],'F')[0]
            result=_replay_cached(output,world,targets,'F')
            self.assertEqual(result['executor_version'],EXECUTOR_VERSION)
            path=output/result['trace_file'];stored=read_json(path)
            stored['result']['executor_version']='e1-motion-1'
            stored['hash']=digest(stored['result'])
            path.write_text(canonical(stored)+'\n')
            with self.assertRaisesRegex(ValueError,'version failure'):
                _replay_cached(output,world,targets,'F')

    def test_slot_counts_and_pairing(self):
        slots=slots_for(self.worlds)
        self.assertEqual(Counter(s['stage'] for s in slots),{'gate':144,'e1':2880})
        self.assertEqual(len({s['slot_id'] for s in slots}),3024)
        for role in ('primary','replication'):
            e1=[s for s in slots if s['stage']=='e1' and s['model_role']==role]
            self.assertEqual(len(e1)//2,720)
            self.assertEqual(Counter(s['language'] for s in e1),{'EN':720,'VI':720})
        self.assertEqual(slots,slots_for(self.worlds))

    def test_controls_without_network(self):
        slots=slots_for(self.worlds,'e1')[:8]
        # First block includes both policies/languages; fixtures preserve strict failures.
        with tempfile.TemporaryDirectory() as tmp,patch.object(socket,'create_connection',side_effect=AssertionError('network forbidden')):
            for mode,expected in [('oracle',1.),('blind',0.),('idle',0.),('malformed',0.)]:
                out=Path(tmp)/mode
                result=run(out,self.worlds,self.policies,mode=mode,stage='e1',slots=slots)
                self.assertEqual(result['api_calls'],0)
                report=analyze(out/'attempts.jsonl',resamples=20)
                role=slots[0]['model_role']
                self.assertEqual(report['models'][role]['pairpass'],expected)
                if mode in ('idle','malformed'):self.assertEqual(report['overall']['strict_goodness'],0.)

    def test_resume_and_compatible_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=FakeProvider('oracle')
            run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots,max_new_slots=1)
            self.assertEqual(fake.calls,1)
            run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots)
            self.assertEqual(fake.calls,len(self.smallslots))
            before=Path(tmp,'attempts.jsonl').read_bytes()
            run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots)
            self.assertEqual(before,Path(tmp,'attempts.jsonl').read_bytes())
            changed=copy.deepcopy(self.policies);changed['version']='different'
            with self.assertRaises(ValueError):run(tmp,self.worlds,changed,provider=fake,slots=self.smallslots)
            with self.assertRaises(ValueError):run(tmp,self.worlds,self.policies,mode='blind',slots=self.smallslots)

    def test_response_durable_before_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake=FakeProvider('oracle');original=Journal.append
            def crash(log,event):
                if event['event']=='terminal':raise RuntimeError('simulated crash after durable response')
                return original(log,event)
            with patch.object(Journal,'append',crash),self.assertRaises(RuntimeError):
                run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots[:1])
            self.assertEqual(fake.calls,1)
            run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots[:1])
            self.assertEqual(fake.calls,1)

    def test_uncertain_request_is_not_resent(self):
        class Crash(FakeProvider):
            def complete(self,*args):self.calls+=1;raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as tmp:
            fake=Crash()
            with self.assertRaises(KeyboardInterrupt):run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots[:1])
            with self.assertRaisesRegex(RuntimeError,'uncertain'):run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots[:1])
            self.assertEqual(fake.calls,1)

    def test_retries_are_bounded_and_exhaustion_incomplete(self):
        class Flaky(FakeProvider):
            def __init__(self,failures):super().__init__();self.remaining=failures
            def complete(self,*args):
                if self.remaining:
                    self.remaining-=1;self.calls+=1;raise InfrastructureError('fixture timeout','fake-request')
                return super().complete(*args)
        for failures,complete in [(2,True),(3,False)]:
            with tempfile.TemporaryDirectory() as tmp:
                fake=Flaky(failures)
                result=run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots[:1])
                self.assertEqual(fake.calls,3);self.assertEqual(result['complete'],complete)
                run(tmp,self.worlds,self.policies,provider=fake,slots=self.smallslots[:1])
                self.assertEqual(fake.calls,3)
                self.assertEqual(sum(e['event']=='started' for e in Journal.read(Path(tmp)/'attempts.jsonl')),3)

    def test_journal_tampering_and_torn_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'journal.jsonl'
            with Journal(path) as log:log.append({'event':'test'})
            content=path.read_text();path.write_text(content.replace('"test"','"other"'))
            with self.assertRaises(ValueError):Journal.read(path)
            path.write_text(content+'{')
            with self.assertRaises(ValueError):Journal.read(path)

    def test_family_bootstrap_retains_pairs(self):
        values=[[0.,1.],[1.,0.],[.5,.5]]
        out=cluster_intervals(values,resamples=10000)
        self.assertAlmostEqual(out['VI_minus_EN']['estimate'],0)
        self.assertEqual(out,cluster_intervals(values,resamples=10000))
        self.assertTrue(cluster_intervals([[1.,1.]]*60)['EN']['degenerate'])

    def test_live_prerequisites_and_cost_without_transport(self):
        # Exercise provider-envelope extraction with a mocked HTTP handle only.
        # No live credential is read and no network transport can run here.
        from experiments.llm_lbf_demo.e1 import providers
        with patch.dict(providers.os.environ,{'OPENAI_API_KEY':'SYNTHETIC_TEST_ONLY'}),patch.object(providers,'urlopen') as http:
            handle=http.return_value.__enter__.return_value
            handle.read.return_value=json.dumps({'id':'fixture-response','model':'fixture-model',
                'choices':[{'message':{'content':'{"targets":{"A":"b0","B":null}}'}}],
                'usage':{'prompt_tokens':10,'completion_tokens':5}}).encode()
            handle.headers={'x-request-id':'fixture-request'}
            response=LiveProvider().complete(payload(self.state,self.policies['languages']['EN']['P0'][0]),
                {'id':'fixture-test-only','temperature':0,'max_output_tokens':256})
            self.assertEqual(response['request_id'],'fixture-request')
            self.assertEqual(oracle.score(response['raw'],self.state,'P0')['status'],'GOOD')
            body=json.loads(http.call_args.args[0].data)
            self.assertEqual(body['messages'][0]['content'],SYSTEM)
            self.assertEqual(body['max_tokens'],256)
        models=[{'role':role,'id':f'explicit-test-only-{role}','snapshot_frozen':True,
                 'temperature':0,'max_input_tokens':10000,'max_output_tokens':256,
                 'input_usd_per_million':1.,'output_usd_per_million':2.} for role in ('primary','replication')]
        config={'explicit_live_approval':True,'dollar_ceiling':100.,'models':models}
        # Synthetic test records are never written as real approvals/gate evidence.
        approval={'approved':True,'reviewer':'SYNTHETIC TEST ONLY','reviewed_at':'test','policy_hash':digest(self.policies)}
        with self.assertRaises(PermissionError):validate_live(config,{},digest(self.policies),'gate')
        no=copy.deepcopy(config);no['explicit_live_approval']=False
        with self.assertRaises(PermissionError):validate_live(no,approval,digest(self.policies),'gate')
        self.assertTrue(validate_live(config,approval,digest(self.policies),'gate'))
        fakegate={'complete':True,'infrastructure_validation':True}
        with self.assertRaises(PermissionError):validate_live(config,approval,digest(self.policies),'e1',fakegate)
        gate={'complete':True,'infrastructure_validation':False,'manifest_hash':'world','gate_binding':'matching',
              'gate':[{'passed':True}]*4}
        self.assertTrue(validate_live(config,approval,digest(self.policies),'e1',gate,'world','matching'))
        with self.assertRaises(PermissionError):validate_live(config,approval,digest(self.policies),'e1',gate,'different-world','matching')
        with self.assertRaises(PermissionError):validate_live(config,approval,digest(self.policies),'e1',gate,'world','changed-model-binding')
        gate['gate'][0]={'passed':False}
        with self.assertRaises(PermissionError):validate_live(config,approval,digest(self.policies),'e1',gate,'world','matching')
        request=payload(self.state,self.policies['languages']['EN']['P0'][0]);sid=self.smallslots[0]['slot_id']
        with self.assertRaises(PermissionError):preflight_cost(self.smallslots[:1],models,{sid:request},0)
        self.assertGreater(preflight_cost(self.smallslots[:1],models,{sid:request},100),0)
        self.assertNotEqual(gate_binding(models,self.policies,self.worlds),gate_binding(models[::-1],self.policies,self.worlds))
        with self.assertRaises(PermissionError):
            with tempfile.TemporaryDirectory() as tmp:run(tmp,self.worlds,self.policies,provider=LiveProvider(),slots=self.smallslots[:1])

    def test_gate_thresholds_and_fake_gate_not_live_evidence(self):
        class OneMalformed(FakeProvider):
            def complete(self,*args):
                result=super().complete(*args)
                if self.calls==1:result['raw']='{broken'
                return result
        for provider,expected_passes in [(FakeProvider(),4),(OneMalformed(),3)]:
            with tempfile.TemporaryDirectory() as tmp:
                result=run(tmp,self.worlds,self.policies,provider=provider,stage='gate')
                self.assertEqual(result['slots'],144)
                self.assertEqual(provider.calls,144) # bad model content is never retried
                report=analyze(Path(tmp)/'attempts.jsonl',resamples=20)
                self.assertTrue(report['complete'])
                self.assertEqual(sum(g['passed'] for g in report['gate']),expected_passes)
                self.assertTrue(all(not g['eligible_live_evidence'] for g in report['gate']))


if __name__=='__main__':unittest.main()
