"""Offline verification of the authorized VI/smoke/P0 artifacts. No network calls."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[4];sys.path.insert(0,str(REPO))
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import assert_policy_only_difference
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import replay,EXECUTOR_VERSION,executor_source_hash
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.e1.worlds import load_manifest,witness_acceptance
from experiments.llm_lbf_demo.p0.prepare import bundle
from experiments.llm_lbf_demo.p0.report import usage_cost,report

BASE=REPO/'experiments/llm_lbf_demo';PREP=BASE/'pilot/next-steps-20261104'
VI=BASE/'pilot/vietnamese-development-sweep-20261104-01';P0=BASE/'p0'
policies=read_json(ROOT/'e1_policies.json');proposal=read_json(P0/'live.proposed.json')
final=read_json(P0/'live.final.freeze.json')
assert final['binding']==bundle(proposal) and final['binding_hash']==digest(final['binding'])
assert read_json(P0/'human-approval.json')['approved'] is True
assert read_json(P0/'human-approval.json')['policy_hash']==digest(policies)
assert hashlib.sha256(Path(final['smoke_journal']).read_bytes()).hexdigest()==final['smoke_journal_sha256']
vi=read_json(VI/'results.json');config=read_json(VI/'configuration.json');events=Journal.read(VI/'attempts.jsonl')
assert len(vi['rows'])==vi['api_requests']==108 and not vi['fatal_blocker']
assert not vi['held_out_E1_authorized'] and not vi['formal_gate_passed']
assert sum(e['event']=='started' for e in events)==sum(e['event']=='response' for e in events)==sum(e['event']=='terminal' for e in events)==108
assert len({e['response']['request_id'] for e in events if e['event']=='response'})==108
for name,sha in config['source_hashes'].items():assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==sha
worlds={w['family_id']:w for w in config['worlds']};assert len(worlds)==12
vi_cost=Decimal(0)
for r in vi['rows']:
    assert worlds[r['world']]['split']=='development'
    response=read_json(VI/r['response_file'])['response']
    assert response['raw']==r['raw_response'] and response['effective_request']['messages']==r['prompt']['messages']
    assert score(r['raw_response'],worlds[r['world']]['state'],r['policy'])==r['grading']
    assert r['actual_model']==config['model']['id']
    if r['targets'] is not None:assert replay(worlds[r['world']]['state'],r['targets'],r['policy'],r['simulator_seed'])==r['executor']
    cost=usage_cost(response,config['model']);assert cost==r['observed_cost_usd'];vi_cost+=Decimal(str(cost))
assert vi_cost==Decimal(vi['observed_usage_cost_usd'])

phase_summaries={};total_cost=vi_cost;reserved=Decimal(str(vi['reserved_upper_bound_usd']));requests=108
for phase,expected in [('smoke',4),('gate',144)]:
    directory=P0/'runs'/f'{phase}-001';events=Journal.read(directory/'attempts.jsonl')
    starts=[e for e in events if e['event']=='started']
    responses={(e['slot_id'],e['attempt']):e['response'] for e in events if e['event']=='response'}
    terminals={e['slot_id']:e for e in events if e['event']=='terminal'}
    assert len(terminals)==expected and len(starts)==len(responses)
    assert all(s['split']=='development' and s['slot']['stage']==phase for s in starts)
    if phase=='gate':
        assert min(datetime.fromisoformat(s['timestamp']) for s in starts)>=datetime.fromisoformat(final['frozen_at'])
        assert events[0]['config']['config']['final_freeze_hash']==digest(final)
    snapshots=Counter();usage=Counter();phase_cost=Decimal(0);paired={};replayed=0
    for s in starts:
        response=responses[s['slot_id'],s['attempt']]
        assert response['model']==s['model']['id']
        assert response['effective_request']['messages']==s['request']['messages']
        snapshots[response['model']]+=1
        cost=usage_cost(response,s['model']);assert cost is not None;phase_cost+=Decimal(str(cost))
        usage['prompt_tokens']+=response['usage']['prompt_tokens']
        usage['completion_tokens']+=response['usage']['completion_tokens']
        usage['cached_input_tokens']+=(response['usage'].get('prompt_tokens_details') or {}).get('cached_tokens',0)
        assert score(response['raw'],s['state'],s['grader_policy'])==terminals[s['slot_id']]['verdict']
        t=terminals[s['slot_id']]
        if t.get('executor'):
            fresh=replay(s['state'],t['verdict']['targets'],s['grader_policy'],s['simulator_seed'])
            stored=read_json(directory/t['executor']['trace_file'])
            assert fresh==stored['result'] and digest(fresh)==t['executor']['record_hash'];replayed+=1
        slot=s['slot'];paired.setdefault((slot['family_id'],slot['model_role'],slot['repeat']),{})[slot['language']]=s['request']
    for group in paired.values():assert_policy_only_difference(group['EN'],group['VI'])
    result=report(directory/'attempts.jsonl',proposal,phase)
    assert result==read_json(directory/('P0_REPORT.json' if phase=='gate' else 'SMOKE_REPORT.json'))
    phase_reserve=sum(Decimal(str(s['reserved_usd'])) for s in starts)
    assert phase_reserve<=Decimal(str(proposal['budgets_usd'][phase]))
    phase_summaries[phase]={'requests':len(starts),'slots':expected,'actual_snapshots':dict(snapshots),
        'usage':dict(usage),'observed_token_cost_usd':str(phase_cost),'reserved_upper_bound_usd':str(phase_reserve),
        'unknown_cost_attempts':sum(c['attempts_with_unknown_cost'] for c in result['conditions']),
        'infrastructure_failed_attempts':sum(c['infrastructure_failed_attempts'] for c in result['conditions']),
        'independently_regraded':len(responses),'independently_replayed':replayed,
        'policy_only_language_pairs_verified':len(paired),'report_complete':result['complete']}
    total_cost+=phase_cost;reserved+=phase_reserve;requests+=len(starts)
assert total_cost<=reserved<=Decimal('2.55')
summary={'status':'REAL_DEVELOPMENT_AND_P0_ARTIFACTS_VERIFIED','new_provider_requests':requests,
    'VI':{'requests':108,'regraded':108,'replayed':108,'observed_token_cost_usd':str(vi_cost)},
    'phases':phase_summaries,'observed_total_token_cost_usd':str(total_cost),
    'durable_reservations_total_usd':str(reserved),'authorized_total_cap_usd':2.55,'cost_is_invoice':False,
    'frozen_config_sha256':hashlib.sha256((P0/'live.final.freeze.json').read_bytes()).hexdigest(),
    'executor_version':EXECUTOR_VERSION,'executor_sha256':executor_source_hash(),
    'existing_864_witnesses':witness_acceptance(load_manifest()),
    'formal_P0_passed':read_json(P0/'runs/gate-001/P0_REPORT.json')['held_out_E1_authorized'],
    'held_out_model_requests':0,'held_out_spending_authorized':False,
    'formal_E1_complete':False,'full_episode_extension_implemented':False,
    'replays_do_not_change_recommendation_labels':True,'no_prompt_model_or_threshold_changes':True}
with (PREP/'FINAL_VERIFICATION.json').open('x') as f:f.write(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(canonical(summary))
