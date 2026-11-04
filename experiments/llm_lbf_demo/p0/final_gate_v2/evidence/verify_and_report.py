"""Offline verification/reporting of the second formal P0; no API calls."""
from collections import Counter
from datetime import datetime
from decimal import Decimal
import csv
import difflib
import hashlib
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[5];sys.path.insert(0,str(REPO))
from experiments.llm_lbf_demo.e1.common import ROOT as E1,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import assert_policy_only_difference
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import replay
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.e1.worlds import load_manifest,witness_acceptance
from experiments.llm_lbf_demo.p0.report import usage_cost,report
from experiments.llm_lbf_demo.p0.interface_v2.controller import payload
from experiments.llm_lbf_demo.p0.final_gate_v2.workflow import ROOT,bundle,write_new

proposal=read_json(ROOT/'live.proposed.json');final=read_json(ROOT/'live.final.freeze.json')
assert final['binding']==bundle(proposal) and final['binding_hash']==digest(final['binding'])
assert hashlib.sha256(Path(final['smoke_journal']).read_bytes()).hexdigest()==final['smoke_journal_sha256']
policies=read_json(E1/'e1_policies.json')
historical=read_json(ROOT.parent/'interface_v2/evidence/audit-001/AUDIT.json')['historical_hashes']
for name,sha in historical.items():assert hashlib.sha256((E1.parent/name).read_bytes()).hexdigest()==sha,name
phase_stats={};total=Decimal(0);reserved=Decimal(0);failures=[];csv_rows=[];snapshots=Counter();requests=0
reports={}
for phase,expected in [('smoke',4),('gate',144)]:
    directory=ROOT/'runs'/('smoke-002' if phase=='smoke' else 'gate-002')
    events=Journal.read(directory/'attempts.jsonl')
    starts=[e for e in events if e['event']=='started']
    responses={(e['slot_id'],e['attempt']):e for e in events if e['event']=='response'}
    terminals={e['slot_id']:e for e in events if e['event']=='terminal'}
    assert len(terminals)==expected
    assert len({e['response']['request_id'] for e in responses.values()})==len(responses)
    if phase=='gate':
        assert min(datetime.fromisoformat(s['timestamp']) for s in starts)>=datetime.fromisoformat(final['frozen_at'])
        assert events[0]['config']['config']['final_freeze_hash']==digest(final)
    phase_cost=Decimal(0);phase_reserved=Decimal(0);usage=Counter();unknown=0;regraded=0;replayed=0;pairs={}
    for s in starts:
        assert s['split']=='development' and s['slot']['stage']==phase
        expected_request=payload(s['state'],policies['languages'][s['slot']['language']]['P0'][0])
        assert s['request']==expected_request
        phase_reserved+=Decimal(str(s['reserved_usd']))
        pairs.setdefault((s['family_id'],s['slot']['model_role'],s['slot']['repeat']),{})[s['slot']['language']]=s['request']
        event=responses.get((s['slot_id'],s['attempt']))
        if event is None:unknown+=1;continue
        response=event['response'];snapshots[response['model']]+=1
        assert response['model']==s['model']['id']
        assert response['effective_request']=={**expected_request,**proposal['request_settings'],'model':s['model']['id']}
        cost=usage_cost(response,s['model'])
        if cost is None:unknown+=1
        else:phase_cost+=Decimal(str(cost))
        u=response['usage'];usage['prompt_tokens']+=u['prompt_tokens'];usage['completion_tokens']+=u['completion_tokens']
        usage['cached_input_tokens']+=(u.get('prompt_tokens_details') or {}).get('cached_tokens',0)
        verdict=score(response['raw'],s['state'],'P0')
        assert verdict==terminals[s['slot_id']]['verdict'];regraded+=1
        row=terminals[s['slot_id']]
        if row.get('executor'):
            fresh=replay(s['state'],verdict['targets'],'P0',s['simulator_seed'])
            stored=read_json(directory/row['executor']['trace_file'])
            assert fresh==stored['result'] and digest(fresh)==row['executor']['record_hash'];replayed+=1
        if phase=='gate':
            csv_rows.append({'world':s['family_id'],'model':response['model'],'language':s['slot']['language'],
                'repeat':s['slot']['repeat'],'status':verdict['status'],'format_valid':verdict['format_valid'],
                'capacity_feasible':verdict['capacity_feasible'],'geometric_feasible':verdict['geometric_feasible'],
                'good':verdict['good'],'raw_response':response['raw'],'token_cost_usd':cost,
                'latency_seconds':event['latency_seconds'],'executor_status':(row.get('executor') or {}).get('status')})
            if not verdict['good']:
                arithmetic=[]
                for box in s['state']['tasks']:
                    members=[a for a in s['state']['agents'] if (verdict['targets'] or {}).get(a['id'])==box['id']]
                    if members:arithmetic.append({'box':box['id'],'weight':box['level'],
                        'agents':[a['id'] for a in members],'capacity':sum(a['level'] for a in members)})
                failures.append({'slot':s['slot'],'actual_model':response['model'],'state':s['state'],
                    'exact_prompt':s['request'],'raw_response':response['raw'],'verdict':verdict,
                    'capacity_arithmetic':arithmetic,'executor':row.get('executor')})
    for pair in pairs.values():
        if set(pair)=={'EN','VI'}:assert_policy_only_difference(pair['EN'],pair['VI'])
    reports[phase]=report(directory/'attempts.jsonl',proposal,phase)
    stored_report=read_json(directory/('P0_REPORT.json' if phase=='gate' else 'SMOKE_REPORT.json'))
    assert reports[phase]==stored_report
    phase_stats[phase]={'slots':expected,'provider_attempts':len(starts),'responses':len(responses),
        'infra_failed_attempts':sum(e['event']=='infra' for e in events),'attempts_with_unknown_cost':unknown,
        'observed_token_cost_usd':str(phase_cost),'reservation_usd':str(phase_reserved),'usage':dict(usage),
        'regraded':regraded,'replayed':replayed,'policy_only_language_pairs_checked':len(pairs)}
    assert phase_reserved<=Decimal(str(proposal['budgets_usd'][phase]))
    total+=phase_cost;reserved+=phase_reserved;requests+=len(starts)
assert reserved<=Decimal('1.55')
gate=reports['gate'];original=read_json(ROOT.parent/'runs/gate-001/P0_REPORT.json')
old={(r['model_role'],r['language']):r for r in original['conditions']}
blocked=[];comparison=[]
for r in gate['conditions']:
    prior=old[r['model_role'],r['language']]
    comparison.append({'model':r['model_snapshot'],'language':r['language'],
        'first_gate_physical_valid':round(prior['physical_validity']*36),'second_gate_physical_valid':round(r['physical_validity']*36),
        'calls_per_gate':36,'second_gate_passed':r['passed']})
    if not r['passed']:blocked.append({'model':r['model_snapshot'],'language':r['language'],
        'failed_first_gate':not prior['passed'],'failed_second_gate':True,'confirmatory_E1':'BLOCKED'})
write_new(ROOT/'runs/gate-002/FAILURE_EXAMPLES.json',{'count':len(failures),'failures':failures})
with (ROOT/'runs/gate-002/conditions.csv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(csv_rows[0]));w.writeheader();w.writerows(csv_rows)
verification={'status':'SECOND_FINAL_P0_COMPLETE_PASSED' if gate['held_out_E1_authorized'] else 'SECOND_FINAL_P0_COMPLETE_FAILED',
    'formal_attempt_number':2,'phase_stats':phase_stats,'new_provider_attempts':requests,'actual_model_counts':dict(snapshots),
    'observed_token_cost_usd':str(total),'total_durable_reservation_usd':str(reserved),'authorized_cap_usd':1.55,
    'cost_is_invoice':False,'tests_passed':53,'historical_files_hash_verified_unchanged':len(historical),
    'existing_executor_witness_acceptance':witness_acceptance(load_manifest()),
    'freeze_sha256':hashlib.sha256((ROOT/'live.final.freeze.json').read_bytes()).hexdigest(),
    'old_and_new_gate_comparison':comparison,'blocked_after_final_attempt':blocked,
    'P0_prerequisite_passed':gate['held_out_E1_authorized'],
    'held_out_spending_authorized':False,'held_out_calls':0,'further_prompt_corrections_allowed':False,
    'third_gate_authorized':False,'no_recommendations_repaired_or_substituted':True}
write_new(ROOT/'FINAL_VERIFICATION.json',verification)
# A machine-readable stop record distinguishes gate eligibility from spending authority.
write_new(ROOT/'PROTOCOL_STATUS.json',{'formal_attempts_completed':2,
    'required_P0_passed':gate['held_out_E1_authorized'],'blocked_model_language_conditions':blocked,
    'held_out_E1':('GATE_PREREQUISITE_MET_BUT_SEPARATE_BUDGET_REQUIRED' if gate['held_out_E1_authorized'] else 'BLOCKED_REQUIRED_FINAL_P0_FAILED'),
    'held_out_requests':0,'held_out_spending_authorized':False,'further_interface_corrections_allowed':False,
    'third_formal_gate_authorized':False,'protocol_amendment_required_for_any_change_to_models_thresholds_or_scope':True})
lines=['# Second and final formal P0 — acceptance report','',
    'Completed 4 November 2026. **'+('All four required P0 conditions passed.' if gate['held_out_E1_authorized'] else 'The required corrected P0 gate FAILED. Held-out E1 remains BLOCKED.')+'**','',
    'This is formal attempt 2 using the single previously tested `p0-capacity-grounding-2` clarification. No prompt variant, model, threshold, policy, parser, grader, executor, world or seed was changed in response to these outcomes.','',
    '## Verification and execution','',
    '- Recorded the user\'s approval of the exact proposed second/final gate and USD 1.55 cap (smoke USD 0.05; gate USD 1.50), including infrastructure retries.',
    '- Complete offline suite passed: 53 tests, including original recovery/E1/P0 tests and corrected-adapter, fixture, resume, prerequisite and held-out-blocking checks.',
    '- Rechecked official prices on 4 November 2026: [GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini). Input/output rates remain USD 0.15/0.60 and 0.40/1.60 per million tokens. Budgets reserve uncached input and all allowed retries.',
    '- Four new development-only smoke calls succeeded with exact snapshots/settings. Smoke outcomes remain separate from the formal gate.',
    '- Created a new final freeze after smoke and before formal calls. SHA-256 `'+verification['freeze_sha256']+'`.',
    '- Completed every one of the 144 formal slots: all 12 development worlds, both languages, both models and three fresh-context repetitions. Exact schedule and prompts retained in `REQUEST_SCHEDULE.json`; all responses and failures retained in hash-chained journals.',
    '- Independently regraded all saved responses and reran all applicable executor traces with exact matches. Verified policy-only language comparisons, frozen bindings and 525 historical-file hashes. Existing 864/864 witness evidence is still accepted; this is not a newly generated witness batch.','',
    '## Formal results','',
    'Each model/language row has 36 calls. Required thresholds: parseability >=98% (36/36), physical validity >=95% (35/36), progressive goodness >=80% (29/36). Capacity and geometry are independent recommendation labels; rollout success never changes them.','',
    '| Exact model snapshot | Language | Parse | Capacity | Geometry | Progressive GOOD | Infra attempts | Token cost USD | Result |',
    '|---|---|---:|---:|---:|---:|---:|---:|---|']
for r in gate['conditions']:
    n=lambda field:round(r[field]*36)
    lines.append(f"| {r['model_snapshot']} | {r['language']} | {n('parseability')}/36 | {n('capacity_validity')}/36 | {n('geometric_validity')}/36 | {n('progressive_goodness')}/36 | {r['infrastructure_failed_attempts']} | {(r['observed_usage_cost_usd'] or 0):.8f} | {'PASS' if r['passed'] else 'FAIL'} |")
lines+=['','All outcomes remain in their original denominators. The independent unit is the development world (12 families), not the 144 requests. Gate thresholds are engineering floors, not proof of general policy understanding.','',
    '## Every remaining recommendation failure','',
    '| Model | Language | World | Repeat (0-based) | Raw response | Capacity calculation |','|---|---|---|---:|---|---|']
for f in failures:
    s=f['slot'];bad=[a for a in f['capacity_arithmetic'] if a['capacity']<a['weight']]
    reason='; '.join(f"{'+'.join(a['agents'])}: {a['capacity']} < {a['weight']} ({a['box']})" for a in bad) or f['verdict']['status']
    lines.append(f"| {f['actual_model']} | {s['language']} | {s['family_id']} | {s['repeat']} | `{f['raw_response']}` | {reason} |")
if not failures:lines.append('| — | — | — | — | No failures | — |')
lines+=['','All failures have exact prompts, native states, raw outputs and independent labels in `runs/gate-002/FAILURE_EXAMPLES.json`. Physically invalid recommendations are not replayed by the frozen formal protocol; they remain failures, not missing data.','',
    '## First versus second gate','',
    '| Model | Language | First physical validity | Second physical validity | Second result |','|---|---|---:|---:|---|']
for r in comparison:lines.append(f"| {r['model']} | {r['language']} | {r['first_gate_physical_valid']}/36 | {r['second_gate_physical_valid']}/36 | {'PASS' if r['second_gate_passed'] else 'FAIL'} |")
lines+=['','These are repeated development evaluations after a documented correction, not held-out causal estimates or a model leaderboard. The failed first gate is preserved.','',
    '## Spending and stopping decision','',
    '| Phase | Provider attempts | Regraded | Replayed | Token cost USD | Durable reservation USD |','|---|---:|---:|---:|---:|---:|']
for phase,s in phase_stats.items():lines.append(f"| {phase} | {s['provider_attempts']} | {s['regraded']} | {s['replayed']} | {s['observed_token_cost_usd']} | {float(s['reservation_usd']):.7f} |")
lines+=['',f"Total observed usage-derived cost: **USD {total}**, within the separately authorized USD 1.55 cap; total durable reservation approximately USD {float(reserved):.7f}. These are token-based costs, not invoices. Unknown-cost failed attempts, if any, are separately reserved and reported rather than treated as free.",'',
    ('All required conditions passed. Held-out E1 has no spending authorization and was not run; prepare its separate finite budget and frozen matching transport contract before launch.' if gate['held_out_E1_authorized'] else
     'At least one required condition failed the final permitted gate. Apply the preregistered stopping rule: the failed model/language condition is blocked from confirmatory E1. The complete required two-model/two-language protocol remains blocked. No third gate, additional prompt correction, model substitution or threshold relaxation is authorized. Any change requires an explicit protocol amendment, preserving both failed gates and the diagnostic.'),
    '', 'No held-out worlds were sent to a provider. No full-episode controller, new architecture or graphics work was added.','',
    '## Artifacts and reproduction','',
    '- `live.proposed.json`, `PREREGISTRATION.json`, `spending-approval.json`, `REQUEST_SCHEDULE.json`: unchanged settings, authorization, schedule and exact prompts.',
    '- `live.final.freeze.json`: final corrected binding and successful real smoke evidence.',
    '- `runs/smoke-002/SMOKE_REPORT.json`: separate model/language compatibility results.',
    '- `runs/gate-002/P0_REPORT.json`, `conditions.csv`, `FAILURE_EXAMPLES.json`: all formal outcomes and cost by condition.',
    '- `runs/*/attempts.jsonl` and `replays/*.json`: durable exact wire requests, complete provider envelopes, usage and simulator traces.',
    '- `FINAL_VERIFICATION.json`, `PROTOCOL_STATUS.json`: independent verification and stopping decision.',
    '- `RUNNER_PROVENANCE.json`, `evidence/runner.patch`, `tests-before-live.txt`: versioned adapter integration and complete test evidence.','',
    'Actual live commands (completed; compatible resume uses the SAME output directory):','', '```bash',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.final_gate_v2.live smoke --live --proposal experiments/llm_lbf_demo/p0/final_gate_v2/live.proposed.json --spending-approval experiments/llm_lbf_demo/p0/final_gate_v2/spending-approval.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --output experiments/llm_lbf_demo/p0/final_gate_v2/runs/smoke-002',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.final_gate_v2.live gate --live --proposal experiments/llm_lbf_demo/p0/final_gate_v2/live.proposed.json --final-config experiments/llm_lbf_demo/p0/final_gate_v2/live.final.freeze.json --spending-approval experiments/llm_lbf_demo/p0/final_gate_v2/spending-approval.json --human-approval experiments/llm_lbf_demo/p0/human-approval.json --output experiments/llm_lbf_demo/p0/final_gate_v2/runs/gate-002',
    '```','',
    'Free offline test command:','', '```bash',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v',
    '```']
with (ROOT/'FINAL_P0_ACCEPTANCE_REPORT.md').open('x') as f:f.write('\n'.join(lines)+'\n')
patch=''.join(difflib.unified_diff((E1/'run_e1.py').read_text().splitlines(True),(ROOT/'runner.py').read_text().splitlines(True),
    fromfile='preserved-e1/run_e1.py',tofile='p0/final_gate_v2/runner.py'))
with (ROOT/'evidence/runner.patch').open('x') as f:f.write(patch)
print(canonical(verification))
