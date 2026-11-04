"""Independent conditional semantics and offline snapshot integration."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1.common import canonical,read_json,digest
from experiments.llm_lbf_demo.e1.controller import assert_policy_only_difference
from experiments.llm_lbf_demo.p0.interface_v2.controller import payload,SYSTEM
from experiments.llm_lbf_demo.conditional_pilot import grader as g,pilot as p


def raw(a,b):return canonical({'targets':{'A':a,'B':b}})


class TestConditionalPilot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worlds=p.worlds();cls.solo=cls.worlds[0]['state'];cls.joint=cls.worlds[6]['state']

    def test_real_coverage_is_six_per_branch_with_all_worlds_eligible(self):
        r=p.coverage(self.worlds)
        self.assertEqual(r['eligible_worlds'],12)
        self.assertEqual(r['independent_worlds_by_branch'],{'solo_required':6,'joint_required':6})
        self.assertFalse(r['missing_branches']);self.assertFalse(r['ineligible_worlds'])
        self.assertEqual(sum(x['good_allocation_count'] for x in r['worlds']),78)
        self.assertEqual(r['worlds_changed_or_generated'],0)

    def test_joint_branch_demands_the_right_box_and_both_robots(self):
        self.assertTrue(g.score(raw('b2','b2'),self.joint)['good'])
        light=g.score(raw('b0','b0'),self.joint)
        self.assertTrue(light['physical_valid']);self.assertEqual(light['status'],'POLICY')
        separate=g.score(raw('b0','b1'),self.joint)
        self.assertTrue(separate['physical_valid']);self.assertFalse(separate['policy_compliant'])
        weak=g.score(raw('b2',None),self.joint)
        self.assertEqual(weak['status'],'PHYSICS')
        self.assertTrue(weak['failure_flags']['capacity']);self.assertTrue(weak['failure_flags']['policy'])

    def test_solo_branch_permits_one_or_two_solo_tasks_and_rejects_idle_joint(self):
        self.assertTrue(g.score(raw('b0',None),self.solo)['good'])
        self.assertTrue(g.score(raw('b0','b1'),self.solo)['good'])
        self.assertEqual(g.score(raw('b0','b0'),self.solo)['status'],'POLICY')
        self.assertEqual(g.score(raw(None,None),self.solo)['status'],'VACUOUS')
        s=copy.deepcopy(self.solo);s['agents'][0]['level']=.5
        bad=g.score(raw('b2',None),s)
        self.assertEqual(bad['branch'],'solo_required') # B alone can lift b2.
        self.assertFalse(bad['capacity_feasible']);self.assertFalse(bad['policy_compliant'])

    def test_completed_impossible_and_equality_edges(self):
        s=copy.deepcopy(self.joint);s['tasks'][2]['completed']=True
        self.assertEqual(g.classify(s)['branch'],'solo_required')
        s=copy.deepcopy(self.joint);s['tasks'][2]['level']=1.
        self.assertEqual(g.classify(s)['branch'],'solo_required') # Exactly solo-liftable.
        s['tasks'][2]['level']=2.
        self.assertEqual(g.classify(s)['branch'],'joint_required') # Exactly jointly liftable.
        self.assertTrue(g.score(raw('b2','b2'),s)['good'])
        s['tasks'][2]['level']=2.1
        self.assertEqual(g.classify(s)['branch'],'solo_required') # Impossible box does not trigger IF.
        self.assertTrue(g.score(raw('b0',None),s)['good'])
        for t in s['tasks']:t['completed']=True
        self.assertEqual(g.good_set(s),[])
        missing=p.coverage([{**self.worlds[0],'state':s}])
        self.assertEqual(missing['eligible_worlds'],0);self.assertEqual(len(missing['missing_branches']),2)

    def test_multiple_candidates_and_renamed_ids_do_not_change_rule(self):
        s=copy.deepcopy(self.joint);s['tasks'][0]['level']=1.5
        self.assertEqual(g.classify(s)['jointly_only_feasible_box_ids'],['b0','b2'])
        self.assertTrue(g.score(raw('b0','b0'),s)['good']);self.assertTrue(g.score(raw('b2','b2'),s)['good'])
        for a in s['agents']:a['id']='robot-'+a['id']
        for t in s['tasks']:t['id']='box-'+t['id']
        r=g.score(canonical({'targets':{'robot-A':'box-b2','robot-B':'box-b2'}}),s)
        self.assertTrue(r['good'])

    def test_format_geometry_and_specification_stay_separate(self):
        for text in ('not JSON',raw('unknown',None),'{"targets":{"A":"b2"}}',
                     '{"targets":{"A":"b2","A":"b0","B":"b2"}}',
                     '{"targets":{"A":"b2","B":"b2"},"branch":"joint_required"}'):
            r=g.score(text,self.joint);self.assertEqual(r['status'],'FORMAT')
            self.assertTrue(r['failure_flags']['format']);self.assertFalse(r['failure_flags']['policy'])
        s=copy.deepcopy(self.joint);x,y=s['tasks'][2]['position']
        s['obstacles']=[[x+1,y],[x-1,y],[x,y+1],[x,y-1]]
        r=g.score(raw('b2','b2'),s)
        self.assertTrue(r['capacity_feasible']);self.assertTrue(r['policy_compliant'])
        self.assertFalse(r['geometric_feasible']);self.assertEqual(r['status'],'PHYSICS')
        s=copy.deepcopy(self.joint);s['agents'].append(copy.deepcopy(s['agents'][0]))
        self.assertEqual(g.score('not JSON',s)['status'],'SPEC')

    def test_protocol_72_matched_calls_uses_frozen_scaffold_and_no_gold_leak(self):
        c=p.protocol();self.assertEqual(c['scheduled_calls'],72)
        self.assertEqual(c['worst_case_reservation_usd'],'0.1190592')
        self.assertEqual(c['maximum_requests'],72);self.assertEqual(c['automatic_retries'],0)
        self.assertEqual(c['model']['id'],'gpt-4o-mini-2024-07-18')
        pairs={}
        for s in c['slots']:
            self.assertEqual(s['request']['messages'][0]['content'],SYSTEM)
            body=json.loads(s['request']['messages'][1]['content'])
            self.assertEqual(set(body),{'objective','policy','state'})
            self.assertEqual(body['state'],s['world']['state'])
            pairs.setdefault((s['world']['family_id'],s['repetition']),{})[s['language']]=s['request']
        self.assertEqual(len(pairs),36)
        for x in pairs.values():assert_policy_only_difference(x['EN'],x['VI'])

    def test_no_new_policy_or_spending_approval_blocks_before_transport(self):
        old=read_json(p.E1.parent/'p0/spending-approval.json')
        with self.assertRaises(PermissionError):p.validate_approval(old,p.protocol())
        with tempfile.TemporaryDirectory() as tmp,patch.object(p,'P0Provider') as provider:
            with self.assertRaises(PermissionError):p.run(tmp,dry_run=False)
            provider.assert_not_called()

    def test_real_executor_fixtures_and_reports_do_not_inflate_family_count(self):
        for mode,status in [('oracle','GOOD'),('wrong_branch','POLICY'),('idle','VACUOUS'),('malformed','FORMAT')]:
            with tempfile.TemporaryDirectory() as tmp:
                r=p.run(tmp,mode=mode);self.assertEqual(len(r['rows']),72)
                self.assertTrue(r['infrastructure_validation']);self.assertEqual(r['api_requests'],0)
                self.assertEqual({x['status'] for x in r['rows']},{status})
                a=p.report(tmp);self.assertEqual(len(a['conditions']),4)
                self.assertEqual(a['independent_families'],12)
                for c in a['conditions']:
                    self.assertEqual(c['scheduled_calls'],18);self.assertEqual(c['independent_worlds'],6)
                    self.assertEqual(c['strict_good'],18 if mode=='oracle' else 0)
                    if mode=='wrong_branch':
                        self.assertEqual(c['executor_pickups'],18)
                        self.assertEqual(c['conditional_pickup_violations'],18)
                self.assertFalse(a['formal_gate_passed'])
                with self.assertRaises(ValueError):p.run(tmp,mode=mode)


if __name__=='__main__':unittest.main()
