"""Offline verification/reporting only. Does not import a provider transport."""
from collections import Counter,defaultdict
from decimal import Decimal
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

REPO=Path('/Users/phoenix/PycharmProjects/adleap-mas');sys.path.insert(0,str(REPO))
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import assert_policy_only_difference
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import replay
from experiments.llm_lbf_demo.e1.journal import Journal
OUT=REPO/'experiments/llm_lbf_demo/pilot/english-development-sweep-20261104-01'
results=read_json(OUT/'results.json');config=read_json(OUT/'configuration.json');rows=results['rows']
events=Journal.read(OUT/'attempts.jsonl')
assert len(rows)==108 and config['scheduled_calls']==108
assert results['api_requests']<=108 and Decimal(str(results['reserved_upper_bound_usd']))<=1
assert not results['held_out_E1_authorized'] and not results['formal_gate_passed']
for name,sha in config['source_hashes'].items():assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==sha,name
worlds={w['family_id']:w for w in config['worlds']};assert len(worlds)==12 and all(w['split']=='development' for w in worlds.values())
response_events={e['condition']:e for e in events if e['event']=='response'}
for r in rows:
    if r['grading'] is not None:
        assert score(r['raw_response'],worlds[r['world']]['state'],r['policy'])==r['grading']
        assert r['actual_model']==config['model']['id']
        response=response_events[r['condition']]['response']
        assert response['raw']==r['raw_response'] and response['effective_request']['messages']==r['prompt']['messages']
        for k,v in config['request_settings'].items():assert response['effective_request'][k]==v
        if r['targets'] is not None:
            redo=replay(worlds[r['world']]['state'],r['targets'],r['policy'],r['simulator_seed'])
            assert redo==r['executor'],r['condition']
    assert r['world'] in worlds

def good(r):return bool(r.get('grading') and r['grading']['good'])
def numerator(rs,key):return sum(bool(r.get('grading') and r['grading'].get(key)) for r in rs)
def group_summary(rs):
    return {'conditions':len(rs),'statuses':dict(Counter(r['status'] for r in rs)),
        'strict_good':sum(good(r) for r in rs),'strict_goodness_rate':sum(good(r) for r in rs)/len(rs),
        'parseable':numerator(rs,'format_valid'),'capacity_feasible':numerator(rs,'capacity_feasible'),
        'geometrically_feasible':numerator(rs,'geometric_feasible'),'physically_valid':numerator(rs,'physical_valid'),
        'policy_pattern_compliant':numerator(rs,'policy_compliant'),
        'executor_statuses':dict(Counter(r['executor']['status'] if r.get('executor') else 'NOT_RUN' for r in rs)),
        'successful_pickups':sum(bool(r.get('executor') and r['executor']['success']) for r in rs),
        'jointly_only_selected_recommendations':sum(any(t['jointly_only'] for t in r['selected_boxes']) for r in rs),
        'jointly_only_pickups':sum(tid in {b['task'] for b in r['selected_boxes'] if b['jointly_only']}
            for r in rs for tick in (r.get('executor') or {}).get('trace',[]) for tid in tick['pickups']),
        'observed_usage_cost_usd':str(sum(Decimal(str(r['observed_cost_usd'])) for r in rs if r['observed_cost_usd'] is not None))}

per_policy={p:group_summary([r for r in rows if r['policy']==p]) for p in ('P0','R','F')}
by_world=[];pairs=[];lookup={(r['world'],r['repetition'],r['policy']):r for r in rows}
for wid,world in worlds.items():
    cells=[];pair_scores=[]
    for rep in (1,2,3):
        ordered=[lookup[wid,rep,p] for p in ('P0','R','F')]
        assert_policy_only_difference(ordered[1]['prompt'],ordered[2]['prompt'])
        pair=int(good(ordered[1]) and good(ordered[2]));pair_scores.append(pair)
        pairs.append({'world':wid,'repetition':rep,'pairpass':pair,'R_status':ordered[1]['status'],'F_status':ordered[2]['status']})
        cells.append({'repetition':rep,'statuses':{r['policy']:r['status'] for r in ordered},
                      'allocations':{r['policy']:r['targets'] for r in ordered},'pairpass':pair})
    rs=[r for r in rows if r['world']==wid]
    by_world.append({'world':wid,'stratum':world['stratum'],'agent_capacities':{a['id']:a['level'] for a in world['state']['agents']},
        'boxes':[{'id':t['id'],'level':t['level'],'jointly_only':t['level']>max(a['level'] for a in world['state']['agents'])}
                 for t in world['state']['tasks']],
        'repetitions':cells,'pairpass_count':sum(pair_scores),'pairpass_denominator':3,**group_summary(rs)})
family_means=np.array([w['pairpass_count']/3 for w in by_world])
rng=np.random.default_rng(20261104)
bootstrap=family_means[rng.integers(0,12,(10000,12))].mean(axis=1)
failure_groups=defaultdict(list)
for r in rows:
    if not good(r) or not (r.get('executor') or {}).get('success',False):
        g=r.get('grading') or {};e=r.get('executor') or {}
        signature=(r['status'],g.get('capacity_feasible'),g.get('geometric_feasible'),g.get('policy_compliant'),e.get('status'))
        failure_groups[signature].append(r)
examples=[]
for signature,rs in failure_groups.items():
    examples.append({'signature':list(signature),'count':len(rs),'examples':[{
        'condition':r['condition'],'world':r['world'],'repetition':r['repetition'],'policy':r['policy'],
        'raw_response':r['raw_response'],'grading':r['grading'],'selected_boxes':r['selected_boxes'],
        'agent_capacities':{a['id']:a['level'] for a in worlds[r['world']]['state']['agents']},
        'executor_status':(r.get('executor') or {}).get('status'),'executor_diagnosis':(r.get('executor') or {}).get('diagnosis'),
        'failure':r.get('failure')} for r in rs[:3]]})
usage_rows=[e['response']['usage'] for e in response_events.values()]
usage={'prompt_tokens':sum(u['prompt_tokens'] for u in usage_rows),
       'cached_input_tokens':sum((u.get('prompt_tokens_details') or {}).get('cached_tokens',0) for u in usage_rows),
       'completion_tokens':sum(u['completion_tokens'] for u in usage_rows)}
summary={'label':'EXPLORATORY_ENGLISH_DEVELOPMENT_EVIDENCE','formal_gate_passed':False,'held_out_E1_authorized':False,
    'independent_families':12,'repeats_are_not_independent_families':True,'scheduled_calls':108,
    'api_requests':results['api_requests'],'automatic_retries':0,'per_policy':per_policy,
    'pairpass':{'passed':sum(p['pairpass'] for p in pairs),'pairs':36,'rate':sum(p['pairpass'] for p in pairs)/36,
        'family_cluster_bootstrap_95_ci':[float(v) for v in np.quantile(bootstrap,[.025,.975])],
        'resamples':10000,'seed':20261104,'degenerate_interval':bool(np.ptp(bootstrap)==0)},
    'by_world':by_world,'pairs':pairs,'distinct_failure_examples':examples,'usage':usage,
    'observed_usage_cost_usd':results['observed_usage_cost_usd'],'cost_is_invoiced':False,
    'unknown_cost_attempts':results['unknown_cost_attempts'],'reserved_upper_bound_usd':results['reserved_upper_bound_usd'],
    'all_conditions':group_summary(rows)}
with (OUT/'analysis.json').open('x') as f:f.write(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (OUT/'world_repetition_results.csv').open('x',newline='') as f:
    fields=['world','stratum','repetition','policy','allocation','status','capacity_feasible','geometric_feasible','policy_compliant',
            'selected_boxes','jointly_only_selected','executor_status','pickup_tasks','ticks','latency_seconds','observed_cost_usd','raw_response']
    writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
    for r in rows:
        g=r.get('grading') or {};e=r.get('executor') or {}
        writer.writerow({'world':r['world'],'stratum':r['stratum'],'repetition':r['repetition'],'policy':r['policy'],
            'allocation':canonical(r['targets']),'status':r['status'],'capacity_feasible':g.get('capacity_feasible'),
            'geometric_feasible':g.get('geometric_feasible'),'policy_compliant':g.get('policy_compliant'),
            'selected_boxes':canonical(r['selected_boxes']),'jointly_only_selected':any(b['jointly_only'] for b in r['selected_boxes']),
            'executor_status':e.get('status'),'pickup_tasks':canonical([tid for tick in e.get('trace',[]) for tid in tick['pickups']]),
            'ticks':e.get('ticks'),'latency_seconds':r['latency_seconds'],'observed_cost_usd':r['observed_cost_usd'],'raw_response':r['raw_response']})
policies=read_json(ROOT/'e1_policies.json')
with (OUT/'VI_POLICIES_FOR_REVIEW.json').open('x') as f:
    f.write(json.dumps({'status':'AWAITING_HUMAN_SEMANTIC_APPROVAL','matched_English_paraphrase':0,
        'texts':{p:policies['languages']['VI'][p][0] for p in ('P0','R','F')},
        'no_Vietnamese_API_calls_made':True},ensure_ascii=False,indent=2)+'\n')
print(canonical({'per_policy':per_policy,'pairpass':summary['pairpass'],'all_conditions':summary['all_conditions'],
                 'usage':usage,'failure_groups':examples}))
