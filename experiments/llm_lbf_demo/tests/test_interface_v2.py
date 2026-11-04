"""Offline invariants for the single development-only interface correction."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1.common import ROOT,read_json
from experiments.llm_lbf_demo.e1.controller import payload as old_payload,assert_policy_only_difference
from experiments.llm_lbf_demo.p0.prepare import bundle
from experiments.llm_lbf_demo.p0.interface_v2.controller import payload,CLARIFICATION
from experiments.llm_lbf_demo.p0.interface_v2.experiment import protocol,run,development_worlds,P0,validate_approval


class TestCapacityGroundingV2(unittest.TestCase):
    def test_original_freeze_is_still_exact(self):
        self.assertEqual(bundle(read_json(P0/'live.proposed.json')),read_json(P0/'live.final.freeze.json')['binding'])

    def test_clarification_is_scaffold_only_and_does_not_mutate(self):
        state=development_worlds()[0]['state'];before=copy.deepcopy(state)
        new=payload(state,'policy');old=old_payload(state,'policy')
        self.assertEqual(new['messages'][1],old['messages'][1])
        self.assertEqual(new['messages'][0]['content'],old['messages'][0]['content']+CLARIFICATION)
        self.assertEqual(state,before)
        self.assertEqual(set(json.loads(new['messages'][1]['content'])),{'objective','state','policy'})

    def test_policy_only_interventions_reject_other_changes(self):
        state=development_worlds()[0]['state']
        a,b=payload(state,'require'),payload(state,'forbid')
        assert_policy_only_difference(a,b)
        changed=copy.deepcopy(b);changed['messages'][0]['content']+=' preference'
        with self.assertRaises(ValueError):assert_policy_only_difference(a,changed)

    def test_twenty_four_slots_paired_arms_and_budget(self):
        p=protocol();self.assertEqual(len(p['slots']),24);self.assertEqual(p['independent_families'],3)
        self.assertEqual(p['reserved_worst_case_usd'],'0.0727584')
        self.assertEqual(p['request_settings']['max_completion_tokens'],256)
        self.assertTrue(all(s['world']['split']=='development' for s in p['slots']))
        pairs={}
        for s in p['slots']:pairs.setdefault((s['world']['family_id'],s['model']['id'],s['language']),{})[s['arm']]=s
        self.assertEqual(len(pairs),12)
        for arms in pairs.values():
            self.assertEqual(set(arms),{'original','clarified'})
            self.assertEqual(arms['original']['request']['messages'][1],arms['clarified']['request']['messages'][1])

    def test_old_spending_approval_cannot_authorize_new_experiment(self):
        with self.assertRaises(PermissionError):validate_approval(read_json(P0/'spending-approval.json'),protocol())
        with tempfile.TemporaryDirectory() as tmp,patch('experiments.llm_lbf_demo.p0.interface_v2.experiment.P0Provider') as provider:
            with self.assertRaises(PermissionError):run(tmp,dry_run=False)
            provider.assert_not_called()

    def test_fixtures_do_not_prove_a_model_improvement(self):
        for mode,status in [('oracle','GOOD'),('idle','VACUOUS'),('malformed','FORMAT')]:
            with tempfile.TemporaryDirectory() as tmp:
                r=run(tmp,mode=mode)
                self.assertTrue(r['infrastructure_validation'])
                self.assertEqual(r['statuses'],{status:24})
                self.assertEqual(r['requests'],24)
                self.assertIsNone(r['observed_token_cost_usd'])
                self.assertFalse(r['formal_gate_passed'])
                self.assertFalse(r['held_out_E1_authorized'])
                with self.assertRaises(ValueError):run(tmp,mode=mode)


if __name__=='__main__':unittest.main()
