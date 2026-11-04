"""Offline verification and matched descriptive analysis; no provider calls."""
from collections import Counter
from decimal import Decimal
import csv
import hashlib
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[5];sys.path.insert(0,str(REPO))
from experiments.llm_lbf_demo.e1.common import canonical,digest,read_json
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import replay
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.p0.report import usage_cost
from experiments.llm_lbf_demo.p0.interface_v2.experiment import HERE,protocol,write_new
from experiments.llm_lbf_demo.p0.interface_v2.controller import CLARIFICATION
OUT=HERE/'evidence/live-001'
frozen=read_json(HERE/'protocol.frozen.json');contract=protocol()
assert digest(contract)==frozen['protocol_hash']
config=read_json(OUT/'configuration.json');assert config['protocol']==contract and not config['infrastructure_validation']
results=read_json(OUT/'results.json');rows=results['rows'];assert len(rows)==24
slots={s['slot_id']:s for s in contract['slots']};events=Journal.read(OUT/'attempts.jsonl')
started=[e for e in events if e['event']=='started'];responses={e['slot_id']:e for e in events if e['event']=='response'}
assert len(started)<=24 and len({e['slot_id'] for e in started})==len(started)
assert len({e['response']['request_id'] for e in responses.values()})==len(responses)
count=0;replayed=0;total=Decimal(0);usage=Counter();diagnostics=[];records=[];families=set()
for r in rows:
    slot=slots[r['slot_id']];families.add(slot['world']['family_id'])
    record={'world':slot['world']['family_id'],'model_role':slot['model']['role'],'model_snapshot':slot['model']['id'],
        'language':slot['language'],'arm':slot['arm'],'slot_id':r['slot_id'],'status':r['status']}
    if r['slot_id'] in responses:
        response=responses[r['slot_id']]['response'];state=slot['world']['state']
        assert response['effective_request']=={**slot['request'],**contract['request_settings'],'model':slot['model']['id']}
        assert response['model']==slot['model']['id']
        assert score(response['raw'],state,'P0')==r['grading'];count+=1
        if r['grading']['targets'] is not None:
            redo=replay(state,r['grading']['targets'],'P0',slot['world']['simulator_seed'])
            assert redo==r['executor'];replayed+=1
        amount=usage_cost(response,slot['model']);assert amount==r['observed_cost_usd']
        if amount is not None:total+=Decimal(str(amount))
        u=response['usage'];usage['prompt_tokens']+=u['prompt_tokens'];usage['completion_tokens']+=u['completion_tokens']
        usage['cached_input_tokens']+=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0)
        record.update(raw_response=response['raw'],allocation=r['grading']['targets'],good=r['grading']['good'],
            format_valid=r['grading']['format_valid'],capacity_feasible=r['grading']['capacity_feasible'],
            geometric_feasible=r['grading']['geometric_feasible'],executor_status=(r.get('executor') or {}).get('status'),
            pickups=[t for tick in (r.get('executor') or {}).get('trace',[]) for t in tick['pickups']],
            latency_seconds=responses[r['slot_id']]['latency_seconds'],cost_usd=amount)
        if not r['grading']['good']:
            diagnostics.append({'slot':slot,'raw_response':response['raw'],'verdict':r['grading'],
                'executor_status':(r.get('executor') or {}).get('status'),
                'executor_diagnosis':(r.get('executor') or {}).get('diagnosis')})
    records.append(record)
assert total==Decimal(results['observed_token_cost_usd'])
assert Decimal(results['reserved_upper_bound_usd'])<=Decimal('.10')
lookup={(r['world'],r['model_role'],r['language'],r['arm']):r for r in records}
pairs=[]
for world,model,lang in sorted({k[:3] for k in lookup}):
    old,new=lookup[world,model,lang,'original'],lookup[world,model,lang,'clarified']
    a,b=slots[old['slot_id']]['request'],slots[new['slot_id']]['request']
    assert a['messages'][1]==b['messages'][1]
    assert b['messages'][0]['content']==a['messages'][0]['content']+CLARIFICATION
    pairs.append({'world':world,'model_role':model,'language':lang,
        'original_status':old['status'],'clarified_status':new['status'],
        'original_good':old.get('good',False),'clarified_good':new.get('good',False),
        'change':'improved' if not old.get('good',False) and new.get('good',False) else
                 'degraded' if old.get('good',False) and not new.get('good',False) else 'unchanged'})
conditions=[]
for model in ('primary','replication'):
    for lang in ('EN','VI'):
        for arm in ('original','clarified'):
            rs=[r for r in records if r['model_role']==model and r['language']==lang and r['arm']==arm]
            conditions.append({'model_role':model,'language':lang,'arm':arm,'slots':len(rs),
                'parseable':sum(r.get('format_valid',False) for r in rs),'capacity_valid':sum(r.get('capacity_feasible',False) for r in rs),
                'geometry_valid':sum(r.get('geometric_feasible',False) for r in rs),'strict_good':sum(r.get('good',False) for r in rs),
                'executor_statuses':dict(Counter(r.get('executor_status','NOT_RUN') for r in rs))})
report={'label':'REAL_POSTHOC_DEVELOPMENT_DIAGNOSTIC_NOT_FORMAL_P0_OR_E1','protocol_hash':frozen['protocol_hash'],
    'independent_families':3,'calls':results['requests'],'retries':0,'conditions':conditions,'matched_pairs':pairs,
    'pair_changes':dict(Counter(p['change'] for p in pairs)),
    'observed_token_cost_usd':str(total),'usage':dict(usage),'reserved_upper_bound_usd':results['reserved_upper_bound_usd'],
    'cost_is_invoice':False,'independent_regrades':count,'independent_replays':replayed,
    'failure_examples':diagnostics,'fatal_blocker':results['fatal_blocker'],
    'formal_P0_passed':False,'held_out_E1_authorized':False,'held_out_calls':0,
    'unchanged_v1_gate_evidence':True,
    'limitations':['Only three post-hoc failure-selected development worlds; not a generalization sample.',
                  'One fresh-context call per arm/condition; repeats may vary even at temperature 0.',
                  'Same single correction was frozen before these new calls; no further prompt selection.',
                  'No R/F conditions were tested here, and this is not a new 144-call P0 gate.']}
write_new(OUT/'ANALYSIS.json',report)
with (OUT/'conditions.csv').open('x',newline='') as f:
    fields=['world','model_role','model_snapshot','language','arm','status','format_valid','capacity_feasible','geometric_feasible',
            'good','executor_status','pickups','latency_seconds','cost_usd','raw_response']
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(records)
lines=['# Real capacity-grounding diagnostic results','',
    'Exploratory, post-hoc development evidence. Three independent worlds; 24 fresh-context calls, zero retries. Same exact models, settings, parser, grader, policies and executor; only the common system clarification changes between arms.','',
    '| Model role | Language | Scaffold | Parse | Capacity | Geometry | Strict GOOD | Executor outcomes |',
    '|---|---|---|---:|---:|---:|---:|---|']
for r in conditions:
    lines.append(f"| {r['model_role']} | {r['language']} | {r['arm']} | {r['parseable']}/3 | {r['capacity_valid']}/3 | {r['geometry_valid']}/3 | {r['strict_good']}/3 | {r['executor_statuses']} |")
lines+=['',f"Matched original→clarified outcomes: {report['pair_changes']} across 12 matched conditions nested in three worlds.",'',
    '| World | Model | Language | Original | Clarified |','|---|---|---|---|---|']
for p in pairs:lines.append(f"| {p['world']} | {p['model_role']} | {p['language']} | {p['original_status']} | {p['clarified_status']} |")
lines+=['',f"Usage-derived cost: **USD {total}**, not an invoice. Input tokens {usage['prompt_tokens']}; output tokens {usage['completion_tokens']}; cached input {usage['cached_input_tokens']}. Conservative reservation USD {results['reserved_upper_bound_usd']}; hard cap USD 0.10.",'',
    f'All {count} saved responses independently regraded and {replayed} saved executor traces independently rerun with identical results. Failed recommendations remain failures irrespective of replay success. Raw envelopes, actual IDs, prompts and usage are in `attempts.jsonl`; every verdict and trace is in `results.json`.','',
    'The first formal P0 remains failed. This diagnostic cannot pass a formal gate, unlock held-out E1 or establish general policy understanding, language superiority or planner superiority. Any new formal gate needs a new frozen binding and separate authorization; no such calls were made.','',
    '## Limitations','']+['- '+v for v in report['limitations']]
with (OUT/'RESULTS.md').open('x') as f:f.write('\n'.join(lines)+'\n')
print(canonical({k:v for k,v in report.items() if k not in ('matched_pairs','failure_examples','limitations')}))
