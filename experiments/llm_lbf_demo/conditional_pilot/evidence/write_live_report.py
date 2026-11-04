"""Verify/describe real conditional responses; zero API access."""
from collections import Counter
from decimal import Decimal
import csv
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[4];sys.path.insert(0,str(REPO))
from experiments.llm_lbf_demo.e1.common import canonical,digest,read_json
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.conditional_pilot import pilot as p

HERE=p.HERE;OUT=HERE/'evidence/live-001'
config=read_json(OUT/'configuration.json');contract=config['contract'];results=read_json(OUT/'results.json')
analysis=read_json(OUT/'ANALYSIS.json');events=Journal.read(OUT/'attempts.jsonl');rows=results['rows']
assert not config['infrastructure_validation'] and digest(p.protocol())==config['protocol_hash']
starts=[e for e in events if e['event']=='started'];responses={e['slot_id']:e['response'] for e in events if e['event']=='response'}
terminals=[e for e in events if e['event']=='terminal'];slots={s['slot_id']:s for s in contract['slots']}
assert len(rows)==len(terminals)==72 and len(starts)<=72
assert len({s['slot_id'] for s in starts})==len(starts)
assert len({r['request_id'] for r in responses.values()})==len(responses)
assert len(starts)==results['api_requests']
assert Decimal(results['reserved_upper_bound_usd'])<=Decimal('.15')
for name,value in read_json(HERE/'evidence/preservation-baseline.json').items():
    assert p.sha(p.E1.parent/name)==value,name
records=[];failure_examples=[];usage=Counter();actual_models=Counter();total=Decimal(0);branch_checks=0;pattern_checks=0
for row in rows:
    slot=slots[row['slot_id']];state=slot['world']['state'];g=row.get('grading') or {}
    record={'world':row['world'],'branch':row['branch'],'language':row['language'],'repetition':row['repetition'],
        'status':row['status'],'raw_response':row['raw_response'],'allocation':canonical(g.get('targets')),
        'format_valid':g.get('format_valid'),'capacity_feasible':g.get('capacity_feasible'),
        'geometric_feasible':g.get('geometric_feasible'),'progress':g.get('progress'),
        'policy_compliant':g.get('policy_compliant'),'good':g.get('good'),
        'executor_status':(row.get('executor') or {}).get('status'),
        'pickup_boxes':canonical([tid for tick in (row.get('executor') or {}).get('trace',[]) for tid in tick['pickups']]),
        'conditional_pickup_violations':len((row.get('pickup_audit') or {}).get('violations',[])),
        'latency_seconds':row.get('latency_seconds'),'observed_cost_usd':row['observed_cost_usd']}
    response=responses.get(row['slot_id'])
    if response:
        assert response['model']==contract['model']['id'];actual_models[response['model']]+=1
        assert row['raw_response']==response['raw']
        assert response['effective_request']=={**slot['request'],**contract['request_settings'],'model':contract['model']['id']}
        u=response['usage'];usage['prompt_tokens']+=u['prompt_tokens'];usage['completion_tokens']+=u['completion_tokens']
        usage['cached_input_tokens']+=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0)
        if row['observed_cost_usd'] is not None:total+=Decimal(str(row['observed_cost_usd']))
        # A direct numeric/pattern cross-check separate from the conditional grader.
        caps=[a['level'] for a in state['agents']]
        heavy=[t['id'] for t in state['tasks'] if not t['completed']
            and not any(t['level']<=c for c in caps) and t['level']<=sum(caps)]
        assert row['branch']==('joint_required' if heavy else 'solo_required');branch_checks+=1
        if g.get('targets') is not None:
            targets=g['targets'];vals=list(targets.values());active=[v for v in vals if v is not None]
            if heavy:policy_ok=len(set(vals))==1 and vals[0] in heavy
            else:
                weights={t['id']:t['level'] for t in state['tasks'] if not t['completed']}
                policy_ok=bool(active) and len(active)==len(set(active)) and all(
                    targets[a['id']] is None or weights[targets[a['id']]]<=a['level'] for a in state['agents'])
            assert policy_ok==g['policy_compliant'];pattern_checks+=1
    if not g.get('good'):
        failure_examples.append({'slot':slot,'raw_response':row['raw_response'],'independent_grading':row.get('grading'),
            'executor':row.get('executor'),'conditional_pickup_audit':row.get('pickup_audit'),'infrastructure_failure':row.get('failure')})
    records.append(record)
assert str(total)==results['observed_token_cost_usd'] or Decimal(results['observed_token_cost_usd'])==total
with (OUT/'world_repetition_results.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
p.write_new(OUT/'FAILURE_EXAMPLES.json',{'count':len(failure_examples),'examples':failure_examples})
heavy_stats=[]
for branch in ('solo_required','joint_required'):
    for lang in ('EN','VI'):
        rs=[r for r in rows if r['branch']==branch and r['language']==lang]
        selected_count=0;pickup_count=0
        for row in rs:
            state=slots[row['slot_id']]['world']['state'];caps=[a['level'] for a in state['agents']]
            heavy={t['id'] for t in state['tasks'] if not t['completed'] and max(caps)<t['level']<=sum(caps)}
            targets=(row.get('grading') or {}).get('targets') or {}
            selected_count+=any(v in heavy for v in targets.values())
            pickup_count+=sum(tid in heavy for tick in (row.get('executor') or {}).get('trace',[]) for tid in tick['pickups'])
        heavy_stats.append({'branch':branch,'language':lang,'calls':len(rs),
            'jointly_only_selected_recommendations':selected_count,'jointly_only_pickups':pickup_count})
verification={'status':'REAL_CONDITIONAL_DEVELOPMENT_PILOT_COMPLETE' if not results['fatal_blocker'] else 'PILOT_STOPPED_WITH_RETAINED_FAILURES',
    'protocol_hash':config['protocol_hash'],'actual_model_counts':dict(actual_models),
    'requests':len(starts),'responses':len(responses),'terminal_slots':len(terminals),'automatic_retries':0,
    'independent_families':12,'families_per_branch':6,'calls_per_branch_language':18,
    'independent_regrades':analysis['independent_regrades'],'independent_replays':analysis['independent_replays'],
    'independent_numeric_branch_checks':branch_checks,'independent_numeric_policy_checks':pattern_checks,
    'usage':dict(usage),'actual_token_cost_usd':str(total),'reserved_usd':results['reserved_upper_bound_usd'],'hard_cap_usd':.15,
    'unknown_cost_attempts':results['unknown_cost_attempts'],'fatal_blocker':results['fatal_blocker'],
    'failure_examples':len(failure_examples),'jointly_only_outcomes':heavy_stats,
    'historical_files_hash_verified_unchanged':len(read_json(HERE/'evidence/preservation-baseline.json')),
    'prior_tests_passed_unchanged_source':62,'held_out_calls':0,'formal_gate_passed_by_this_pilot':False,
    'causal_complexity_effect_established':False,'novelty_claim':False}
p.write_new(OUT/'VERIFICATION.json',verification)
lookup={(r['world'],r['language'],r['repetition']):r for r in rows}
lines=['# Real conditional-policy development pilot','',
    'Completed 5 November 2026 using the reviewed EN/VI conditional policy and separately approved USD 0.15 cap. **Exploratory development evidence, not formal E1 or a causal complexity experiment.**','',
    'Model: `gpt-4o-mini-2024-07-18`. The exact final capacity clarification, JSON schema/parser, physical predicates and `e1-motion-2` executor were preserved. All original 12 development worlds were retained, with the same worlds in both languages and three fresh-context repetitions. No held-out calls, output repair or target substitution.','',
    '## Goodness by branch and language','',
    'Each row has 18 calls from six independent worlds. Format/capacity/policy failure flags are reported separately and can overlap; repeated calls are not independent worlds.','',
    '| Branch | Language | Strict GOOD | Rate | Format failures | Capacity failures | Geometry failures | Policy failures | Native first pickups | Conditional pickup violations |',
    '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for c in analysis['conditions']:
    f=c['failure_flags_nonexclusive']
    lines.append(f"| {c['branch']} | {c['language']} | {c['strict_good']}/18 | {100*c['strict_goodness_rate']:.1f}% | {f['format']} | {f['capacity']} | {f['geometry']} | {f['policy']} | {c['executor_pickups']} | {c['conditional_pickup_violations']} |")
lines+=['','Geometry and progress remain independent of conditional policy compliance. A successful native pickup never changes a failed recommendation label. Infrastructure errors and remaining NOT_RUN slots, if present, are retained in all original denominators.','',
    '## Every world and repetition','',
    '| World | Branch | EN repetitions 1 / 2 / 3 | VI repetitions 1 / 2 / 3 |','|---|---|---|---|']
for w in contract['worlds']:
    wid=w['family_id'];branch=lookup[wid,'EN',1]['branch']
    en=' / '.join(lookup[wid,'EN',r]['status'] for r in (1,2,3));vi=' / '.join(lookup[wid,'VI',r]['status'] for r in (1,2,3))
    lines.append(f'| {wid} | {branch} | {en} | {vi} |')
lines+=['','All 72 individual allocations, raw responses, independent flags, native outcomes, latency and cost are in `world_repetition_results.csv`. Full prompts/envelopes are in `attempts.jsonl`; complete traces and pickup audits are in `results.json`.','',
    '## Jointly-only boxes','',
    '| Branch | Language | Recommendations selecting a jointly-only box | Actual jointly-only pickups |','|---|---|---:|---:|']
for r in heavy_stats:lines.append(f"| {r['branch']} | {r['language']} | {r['jointly_only_selected_recommendations']} | {r['jointly_only_pickups']} |")
lines+=['','The joint branch requires both robots to target a jointly-only, jointly-feasible box; cooperation on a light box alone does not satisfy it. All mixed development worlds have b2 as the unique qualifying box.','',
    '## Retained failures','']
if not failure_examples:lines.append('No recommendation or infrastructure failure was observed in these 72 calls. This is a finite development observation, not evidence of zero underlying error probability.')
else:
    lines+=['All failures are retained without repair in `FAILURE_EXAMPLES.json`.','']
    for i,f in enumerate(failure_examples,1):
        s=f['slot'];g=f['independent_grading'] or {}
        lines += [f"{i}. {s['world']['family_id']}, {s['language']}, repetition {s['repetition']}: `{f['raw_response']}`; label `{g.get('status','INFRA/NOT_RUN')}`; failure flags `{g.get('failure_flags')}`."]
lines+=['', '## Verification and spending','',
    f"Exactly {len(starts)} API requests, {len(responses)} responses and {len(terminals)} terminal slots; zero retries. All {analysis['independent_regrades']} saved responses were independently regraded; {analysis['independent_replays']} saved simulator traces and conditional pickup audits independently rerun with identical results. A separate arithmetic/pattern check verified {branch_checks} branch labels and {pattern_checks} policy labels. All {verification['historical_files_hash_verified_unchanged']} historical files still match their preservation hashes. The unchanged source passed all 62 tests before live execution.",'',
    f"Actual token usage: {usage['prompt_tokens']} input, {usage['completion_tokens']} output, {usage['cached_input_tokens']} cached input. Usage-derived cost: **USD {total}**, not an invoice. Conservative reservation: **USD {results['reserved_upper_bound_usd']}**, below the **USD 0.15** hard cap. Unknown-cost attempts: {results['unknown_cost_attempts']}. Exact model/settings matched the approved frozen protocol.",'',
    '## Interpretation limits','',
    '- Twelve independent development worlds; six per branch. Three repetitions do not multiply the independent sample size.',
    '- Joint-branch worlds are the mixed group and solo-branch worlds are the light group. Branch comparisons confound layout/weights with the required branch.',
    '- This pilot tests conditional-policy application. It does not isolate a causal complexity effect, establish general policy understanding or novelty, or compare planners.',
    '- No held-out E1 or full-episode controller was run. The conditional pilot does not replace the original formal P0/E1 protocol.','',
    '## Executed commands','', '```bash',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot run --live --approval experiments/llm_lbf_demo/conditional_pilot/approval.json --output experiments/llm_lbf_demo/conditional_pilot/evidence/live-001',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.conditional_pilot.pilot report --output experiments/llm_lbf_demo/conditional_pilot/evidence/live-001',
    '```','',
    'These commands completed; existing output is preserved and the runner refuses to repeat it. Regrading/replay requires no API calls.']
with (OUT/'RESULTS.md').open('x') as f:f.write('\n'.join(lines)+'\n')
print(canonical(verification))
