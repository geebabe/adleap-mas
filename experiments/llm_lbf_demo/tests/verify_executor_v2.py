"""Verify immutable v1 evidence against v2 witnesses, labels and payload controls."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import EXECUTOR_VERSION,executor_source_hash
from experiments.llm_lbf_demo.e1.worlds import load_manifest,witness_acceptance
from verify_e1_evidence import verify as verify_historical


def verify():
    evidence=ROOT/'evidence/executor-v2'
    baseline=read_json(evidence/'preservation-baseline.json')
    checked=0
    unchanged=['e1/e1_manifest.jsonl','e1/e1_manifest.lock.json','e1/e1_policies.json',
               'e1/e1_oracle.py','e1/controller.py','testbed.py','tests/test_testbed.py']
    for name,sha in baseline.items():
        if name.startswith('e1/evidence/') or name in unchanged:
            assert hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest()==sha,name
            checked+=1
    for name in ('executor.py','worlds.py','run_e1.py','E1_OFFLINE_ACCEPTANCE_REPORT.md','README.md'):
        assert hashlib.sha256((evidence/('before-'+name)).read_bytes()).hexdigest()==baseline['e1/'+name]
    worlds=load_manifest();by_family={w['family_id']:w for w in worlds}
    old=[json.loads(line) for line in (ROOT/'evidence/e1_witnesses.jsonl').read_text().splitlines()]
    new=[json.loads(line) for line in (evidence/'witnesses.jsonl').read_text().splitlines()]
    key=lambda row:(row['family_id'],canonical(row['targets']))
    before={key(r):r for r in old};after={key(r):r for r in new}
    assert len(before)==len(after)==864 and before.keys()==after.keys()
    tick_changes=Counter();transitions=Counter()
    for identity,prior in before.items():
        current=after[identity];world=by_family[current['family_id']]
        assert prior['verdict']==current['verdict']==score(canonical({'targets':current['targets']}),world['state'],'P0')
        assert prior['state_hash']==current['state_hash']==world['state_hash']
        result=current['executor'];assert result['seed']==prior['executor']['seed']==world['simulator_seed']
        assert result['executor_version']==EXECUTOR_VERSION and result['executor_source_hash']==executor_source_hash()
        assert not result['substitutions']
        for tick in result['trace']:
            assert tick['targets']==current['targets']
            assert sum(a in (0,1,2,3) for a in tick['actions'].values())<=1
            for aid,proposed in tick['proposed_actions'].items():
                actual=tick['actions'][aid]
                assert actual==proposed or proposed in (0,1,2,3) and actual is None
                if proposed==4:assert actual==4
        transitions[prior['executor']['status']+' -> '+result['status']]+=1
        delta=result['ticks']-prior['executor']['ticks']
        tick_changes['fewer' if delta<0 else 'more' if delta>0 else 'same']+=1
    replay_before=read_json(evidence/'before.json');replay_after=read_json(evidence/'after.json')
    assert replay_before['world']==replay_after['world'] and replay_before['targets']==replay_after['targets']
    identity=(replay_before['world']['family_id'],canonical(replay_before['targets']))
    assert replay_before['executor']==before[identity]['executor']
    assert replay_after['executor']==after[identity]['executor']
    historical=verify_historical()
    return {'executor_version':EXECUTOR_VERSION,'executor_source_hash':executor_source_hash(),
        'before':{'status':replay_before['executor']['status'],'ticks':replay_before['executor']['ticks'],
                  'trace_hash':replay_before['executor']['trace_hash']},
        'after':{'status':replay_after['executor']['status'],'ticks':replay_after['executor']['ticks'],
                 'trace_hash':replay_after['executor']['trace_hash']},
        'witnesses':witness_acceptance(worlds),'worlds':len(worlds),'dropped_allocations':0,
        'outcome_transitions':dict(transitions),'tick_changes':dict(tick_changes),
        'historical_and_frozen_files_unchanged':checked,
        'witness_labels_unchanged':864,'historical_recommendation_labels_unchanged':4*3024,
        'policy_only_pairs_verified':4*1440,'historical_verification':historical,
        'api_calls':0,'bilingual_approval':'unverified','model_provider_availability':'unverified',
        'real_P0_performance':'unverified'}


if __name__=='__main__':print(canonical(verify()))
