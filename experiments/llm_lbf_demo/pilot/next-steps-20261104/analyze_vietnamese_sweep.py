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
OUT=REPO/'experiments/llm_lbf_demo/pilot/vietnamese-development-sweep-20261104-01'
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
summary={'label':'EXPLORATORY_VIETNAMESE_DEVELOPMENT_EVIDENCE','formal_gate_passed':False,'held_out_E1_authorized':False,
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
with (OUT/'VI_POLICIES_USED.json').open('x') as f:
    f.write(json.dumps({'status':'HUMAN_APPROVAL_RECORDED_SEPARATELY','matched_English_paraphrase':0,
        'texts':{p:policies['languages']['VI'][p][0] for p in ('P0','R','F')},
        'authorization':config['authorization']},ensure_ascii=False,indent=2)+'\n')
print(canonical({'per_policy':per_policy,'pairpass':summary['pairpass'],'all_conditions':summary['all_conditions'],
                 'usage':usage,'failure_groups':examples}))

english_dir=REPO/'experiments/llm_lbf_demo/pilot/english-development-sweep-20261104-01'
english=read_json(english_dir/'results.json')
english_config=read_json(english_dir/'configuration.json')
assert config['worlds']==english_config['worlds']
assert config['model']==english_config['model'] and config['request_settings']==english_config['request_settings']
en_lookup={(r['world'],r['repetition'],r['policy']):r for r in english['rows']}
for r in rows:assert_policy_only_difference(en_lookup[r['world'],r['repetition'],r['policy']]['prompt'],r['prompt'])
comparison={'label':'EXPLORATORY_MATCHED_DEVELOPMENT_COMPARISON_NOT_FORMAL_E1',
    'independent_families':12,'english_results_sha256':hashlib.sha256((english_dir/'results.json').read_bytes()).hexdigest(),
    'only_policy_field_changes':True,'source_hashes_match':config['source_hashes']==english_config['source_hashes'],
    'limitations':['Languages collected in separate sequential sweeps; not randomized language order.',
                  'Repetitions are nested within 12 development worlds; not independent families.',
                  'No formal gate or held-out inference is established by these sweeps.'],
    'by_policy':{},'by_world':[],'held_out_E1_authorized':False}
paired_family_deltas=[]
for wid in worlds:
    def pair_pass(lookup,rep):return int(good(lookup[wid,rep,'R']) and good(lookup[wid,rep,'F']))
    en_pass=sum(pair_pass(en_lookup,r) for r in (1,2,3));vi_pass=sum(pair_pass(lookup,r) for r in (1,2,3))
    paired_family_deltas.append((vi_pass-en_pass)/3)
    comparison['by_world'].append({'world':wid,'EN_pairpass':en_pass,'VI_pairpass':vi_pass,'pairs_per_language':3})
rng=np.random.default_rng(20261104)
deltas=np.array(paired_family_deltas)
boot=deltas[rng.integers(0,12,(10000,12))].mean(axis=1)
comparison['pairpass']={'EN_passed':sum(w['EN_pairpass'] for w in comparison['by_world']),
    'VI_passed':sum(w['VI_pairpass'] for w in comparison['by_world']),'pairs_per_language':36,
    'VI_minus_EN_rate':float(deltas.mean()),'paired_family_bootstrap_95_ci':[float(v) for v in np.quantile(boot,[.025,.975])],
    'degenerate_interval':bool(np.ptp(boot)==0),'resamples':10000,'seed':20261104}
for p in ('P0','R','F'):
    comparison['by_policy'][p]={'EN':group_summary([r for r in english['rows'] if r['policy']==p]),'VI':per_policy[p]}
with (OUT/'EN_VI_COMPARISON.json').open('x') as f:f.write(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n')
print(canonical({'matched_comparison':comparison}))
