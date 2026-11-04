"""Corrected final-gate integration, isolation and fail-closed prerequisites."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1.common import ROOT,digest,read_json
from experiments.llm_lbf_demo.e1.controller import assert_policy_only_difference
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.e1.worlds import load_manifest
from experiments.llm_lbf_demo.p0.interface_v2.controller import payload,SYSTEM
from experiments.llm_lbf_demo.p0.interface_v2.experiment import protocol
from experiments.llm_lbf_demo.p0.final_gate_v2 import workflow as w,runner


class TestFinalGateV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal=read_json(w.DEFAULT_PROPOSAL);cls.worlds=load_manifest()
        cls.policies=read_json(ROOT/'e1_policies.json');cls.binding=w.bundle(cls.proposal)
        cls.approval=read_json(w.ROOT.parent/'human-approval.json')

    def test_existing_diagnostic_and_original_binding_preserved(self):
        frozen=read_json(w.ROOT.parent/'interface_v2/protocol.frozen.json')
        self.assertEqual(digest(protocol()),frozen['protocol_hash'])
        self.assertEqual(self.binding['formal_attempt_number'],2)
        self.assertEqual(w.budget(self.proposal,'gate')['scheduled_calls'],144)
        self.assertAlmostEqual(w.budget(self.proposal,'gate')['worst_case_usd'],1.3096512)
        self.assertAlmostEqual(w.budget(self.proposal,'smoke')['worst_case_usd'],.0363792)
        self.assertNotEqual(self.binding['e1_code_hashes'],read_json(w.ROOT.parent/'live.final.freeze.json')['binding']['e1_code_hashes'])
        changed=copy.deepcopy(self.proposal);changed['models'][0]['id']='another-model'
        with self.assertRaises(ValueError):w.bundle(changed)

    def test_all_144_prompts_use_exact_tested_clarification(self):
        by={x['family_id']:x for x in self.worlds};groups={}
        for s in runner.slots_for(self.worlds,'gate'):
            request=runner.payload(by[s['family_id']]['state'],self.policies['languages'][s['language']]['P0'][0])
            self.assertEqual(request,payload(by[s['family_id']]['state'],self.policies['languages'][s['language']]['P0'][0]))
            self.assertEqual(request['messages'][0]['content'],SYSTEM)
            groups.setdefault((s['family_id'],s['model_role'],s['repeat']),{})[s['language']]=request
        self.assertEqual(len(groups),72)
        for g in groups.values():assert_policy_only_difference(g['EN'],g['VI'])

    def test_complete_fixture_and_compatible_resume(self):
        slots=runner.slots_for(self.worlds,'gate')
        with tempfile.TemporaryDirectory() as tmp:
            result=runner.run(tmp,self.worlds,self.policies,stage='gate',slots=slots)
            self.assertEqual(result['statuses'],{'GOOD':144});self.assertTrue(result['infrastructure_validation'])
            events=Journal.read(Path(tmp)/'attempts.jsonl');count=len(events)
            self.assertTrue(all(e['request']['messages'][0]['content']==SYSTEM for e in events if e['event']=='started'))
            runner.run(tmp,self.worlds,self.policies,stage='gate',slots=slots)
            self.assertEqual(len(Journal.read(Path(tmp)/'attempts.jsonl')),count)
            other=copy.deepcopy(slots);other.reverse()
            with self.assertRaisesRegex(ValueError,'incompatible'):runner.run(tmp,self.worlds,self.policies,stage='gate',slots=other)

    def test_idle_and_malformed_keep_all_failure_slots(self):
        for mode,status in [('idle','VACUOUS'),('malformed','FORMAT')]:
            with tempfile.TemporaryDirectory() as tmp:
                result=runner.run(tmp,self.worlds,self.policies,mode=mode,stage='gate',slots=runner.slots_for(self.worlds,'gate'))
                self.assertEqual(result['terminal_slots'],144);self.assertEqual(result['statuses'],{status:144})

    def test_old_smoke_fake_smoke_and_missing_freeze_block(self):
        with self.assertRaises(ValueError):w.validate_smoke(w.ROOT.parent/'runs/smoke-001/attempts.jsonl',self.proposal,self.binding)
        with tempfile.TemporaryDirectory() as tmp:
            runner.run(tmp,self.worlds,self.policies,stage='gate',slots=w.smoke_slots(self.worlds))
            with self.assertRaises((ValueError,PermissionError)):w.validate_smoke(Path(tmp)/'attempts.jsonl',self.proposal,self.binding)
        spending={'approved':True,'approved_by':'SYNTHETIC TEST ONLY','approved_at':'test',
                  'proposal_hash':digest(self.proposal),'phases':['gate'],'max_usd':{'gate':1.5}}
        with patch.object(w,'P0Provider') as provider:
            with self.assertRaisesRegex(PermissionError,'final configuration'):
                w.execute('gate',self.proposal,w.ROOT/'runs/gate-002',spending,self.approval,live=True)
            provider.assert_not_called()

    def test_heldout_extra_directory_and_absent_approval_block_before_transport(self):
        with patch.object(w,'P0Provider') as provider:
            with self.assertRaises(ValueError):w.execute('e1',self.proposal,'unused',{}, {},live=True)
            with self.assertRaises(PermissionError):w.execute('smoke',self.proposal,'another-directory',{}, {},live=True)
            with self.assertRaises(PermissionError):w.execute('smoke',self.proposal,w.ROOT/'runs/smoke-002',{}, {},live=True)
            provider.assert_not_called()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):runner.run(tmp,self.worlds,self.policies,stage='e1',slots=runner.slots_for(self.worlds,'e1'))


if __name__=='__main__':unittest.main()
