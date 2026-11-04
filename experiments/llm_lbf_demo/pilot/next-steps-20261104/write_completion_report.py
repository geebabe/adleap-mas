"""Write local reports from completed artifacts only; no provider access."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[4];sys.path.insert(0,str(REPO))
from experiments.llm_lbf_demo.e1.common import canonical,read_json
from experiments.llm_lbf_demo.e1.journal import Journal
BASE=REPO/'experiments/llm_lbf_demo';PREP=BASE/'pilot/next-steps-20261104'
VI=BASE/'pilot/vietnamese-development-sweep-20261104-01';GATE=BASE/'p0/runs/gate-001'
summary=read_json(PREP/'FINAL_VERIFICATION.json');a=read_json(VI/'analysis.json');comparison=read_json(VI/'EN_VI_COMPARISON.json')
gate=read_json(GATE/'P0_REPORT.json');smoke=read_json(BASE/'p0/runs/smoke-001/SMOKE_REPORT.json')
events=Journal.read(GATE/'attempts.jsonl')
starts={e['slot_id']:e for e in events if e['event']=='started'}
responses={e['slot_id']:e['response'] for e in events if e['event']=='response'}
rows=[e for e in events if e['event']=='terminal']
failures=[]
for r in rows:
    if r['verdict']['good']:continue
    s=starts[r['slot_id']];response=responses[r['slot_id']]
    arithmetic=[]
    for task in s['state']['tasks']:
        agents=[agent for agent in s['state']['agents'] if r['verdict']['targets'][agent['id']]==task['id']]
        if agents:
            cap=sum(agent['level'] for agent in agents)
            arithmetic.append({'box':task['id'],'box_weight':task['level'],'assigned_agents':[agent['id'] for agent in agents],
                'assigned_capacity':cap,'capacity_sufficient':cap+1e-9>=task['level']})
    failures.append({'slot':r['slot'],'requested_model':s['model']['id'],'actual_model':response['model'],
        'state':s['state'],'exact_prompt':s['request'],'raw_response':response['raw'],'verdict':r['verdict'],
        'capacity_arithmetic':arithmetic,'executor':r['executor'],
        'diagnosis':'Capacity-infeasible recommendation; not an executor stall or simulator defect.',
        'internal_model_cause':'Not identifiable from an allocation-only response.'})
with (GATE/'FAILURE_EXAMPLES.json').open('x') as f:f.write(json.dumps({'count':len(failures),'failures':failures},ensure_ascii=False,indent=2)+'\n')
with (GATE/'P0_CONDITIONS.csv').open('x',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(gate['conditions'][0]));writer.writeheader();writer.writerows(gate['conditions'])

vlines=['# Matched Vietnamese development sweep — exploratory evidence','',
    'Completed 4 November 2026 after explicit human semantic and spending approval. Same model snapshot, prompt scaffold, parser, grader, executor and worlds as the English sweep; only the policy field changes language. No prompt tuning.','',
    'Model: `gpt-4o-mini-2024-07-18`. Executor: `e1-motion-2`. Twelve independent development families, three fresh-context repetitions per policy. No held-out calls.','',
    '| Policy | Strict GOOD | Parseable | Capacity valid | Geometry valid | First pickup | Token cost USD |',
    '|---|---:|---:|---:|---:|---:|---:|']
for policy,row in a['per_policy'].items():
    vlines.append(f"| {policy} | {row['strict_good']}/36 | {row['parseable']}/36 | {row['capacity_feasible']}/36 | {row['geometrically_feasible']}/36 | {row['successful_pickups']}/36 | {row['observed_usage_cost_usd']} |")
vlines += ['', 'R/F PairPass: **36/36** versus English **33/36**. All Vietnamese world/repetition cells are GOOD/GOOD/GOOD (P0/R/F). The entire observed difference is development-007: EN 0/3 paired passes, VI 3/3. Other worlds are 3/3 in both languages.','',
    'The paired family bootstrap interval for VI minus EN is [0, 0.25], using 12 families and 10,000 resamples (seed 20261104). This does not establish a general language advantage. Collection was sequential by language rather than randomized across languages. The VI-only bootstrap [1,1] is degenerate; it is not evidence of certainty. As a separate boundary summary, 12/12 worlds passed all three R/F pairs; a two-sided exact binomial interval for that family event is ['+f'{0.025**(1/12):.6f}'+', 1].','',
    'No recommendation selected a jointly-only box. These successes do not demonstrate cooperative collection of boxes that require combined capacity. No malformed responses, idle allocations, capacity failures, infrastructure failures, executor stalls, substitutions or SPEC defects were observed in this VI sweep.','',
    '| Policy | Selected box levels (box counted once per recommendation) |','|---|---|']
all_rows=read_json(VI/'results.json')['rows']
for policy in ('P0','R','F'):
    levels=Counter(b['level'] for r in all_rows if r['policy']==policy for b in r['selected_boxes'])
    vlines.append('| '+policy+' | '+', '.join(f'{level}: {count}' for level,count in sorted(levels.items()))+' |')
vlines += ['',f"Actual token usage: {a['usage']['prompt_tokens']} input, {a['usage']['completion_tokens']} output, {a['usage']['cached_input_tokens']} cached input. Usage-derived cost **USD {a['observed_usage_cost_usd']}**, not an invoice. Exactly 108 requests, zero retries; durable reservation USD 0.1785888 under the USD 1 cap.",'',
    'All raw envelopes, prompts and per-call grades/replays are retained. See `results.json`, `analysis.json`, `EN_VI_COMPARISON.json` and `world_repetition_results.csv`. This is not a formal E1 gate result.']
with (VI/'RESULTS.md').open('x') as f:f.write('\n'.join(vlines)+'\n')

lines=['# Authorized next steps — completion and acceptance report','',
    'Completed 4 November 2026. **Formal P0 completed but FAILED overall. Held-out E1 remains BLOCKED.** No held-out model calls were made.','',
    '## Completed requirements','',
    '- Recorded the user\'s explicit approval of all EN/VI meanings and the combined USD 2.55 cap in `USER_APPROVAL.json`; policy bytes remain unchanged. External human/spending records are stored separately.',
    '- Completed the matched Vietnamese exploratory development sweep: 108/108 GOOD, R/F PairPass 36/36, all first-pickup replays successful, zero retries. English remains 33/36 PairPass; the 12 worlds, rather than calls/repetitions, are the independent families.',
    '- Completed four separate development-only compatibility calls: both exact models and both languages accepted the frozen settings and returned the requested snapshot IDs. Smoke is not part of the formal gate.',
    '- Froze the final P0 configuration AFTER real smoke and BEFORE all formal calls. Freeze SHA-256: `'+summary['frozen_config_sha256']+'`.',
    '- Completed the entire formal 144-call randomized, language-interleaved P0 schedule. No worlds or failed responses dropped. No retries, fallback model, prompt/threshold changes or recommendation substitutions.',
    '- Independently regraded all 256 new responses. Independently reran 108 VI, 4 smoke and 137 valid formal replays. All replay records match. The seven invalid formal recommendations remain failures in their 36-call denominators and were not executed by the frozen formal runner.',
    '- Verified unchanged frozen source hashes and 864/864 existing executor witness records. These are verification of saved witness evidence, not a newly generated 864-rollout batch.','',
    '## Formal P0 result','',
    'Each row contains 36 calls. Parseability, geometric validity and progressive goodness are separate measurements. Physical validity requires both capacity and geometry. Thresholds: parseability >=98%, physical validity >=95%, goodness >=80%; with 36 calls, these require 36, 35 and 29 successes respectively.','',
    '| Exact snapshot | Language | Parse | Capacity / physical | Geometry | Progressive GOOD | Infra | Cost USD | Result |',
    '|---|---|---:|---:|---:|---:|---:|---:|---|']
for r in gate['conditions']:
    n=r['scheduled_calls'];cnt=lambda key:round(r[key]*n)
    lines.append(f"| {r['model_snapshot']} | {r['language']} | {cnt('parseability')}/{n} | {cnt('physical_validity')}/{n} | {cnt('geometric_validity')}/{n} | {cnt('progressive_goodness')}/{n} | {r['infrastructure_failed_attempts']} | {r['observed_usage_cost_usd']:.8f} | {'PASS' if r['passed'] else 'FAIL'} |")
lines += ['',
    'Both GPT-4.1-mini conditions fail the physical-validity threshold. All 144 responses were parseable; no infrastructure failures or unknown-cost attempts occurred. Geometry was feasible for all allocations. There were 137 GOOD and 7 PHYSICS outcomes, no POLICY/FORMAT/VACUOUS/SPEC outcomes. All 137 valid replays reached a first pickup; no executor failures or substitutions occurred.','',
    '## All seven failures','',
    'These are capacity-infeasible recommendations, independently checked against the numeric state, not rollouts that happened to stall. Allocation-only outputs do not reveal whether the internal cause was arithmetic, grounding or interpretation. No simulator/spec defect was found. Every failure and exact prompt/raw response is retained in `../../p0/runs/gate-001/FAILURE_EXAMPLES.json`.','',
    '| Model role | Language | World | Repeat (0-based) | Raw response | Insufficient capacity |','|---|---|---|---:|---|---|']
for r in failures:
    s=r['slot'];bad=[t for t in r['capacity_arithmetic'] if not t['capacity_sufficient']]
    arithmetic='; '.join(f"{'+'.join(t['assigned_agents'])}: {t['assigned_capacity']} < {t['box_weight']} ({t['box']})" for t in bad)
    lines.append(f"| {s['model_role']} | {s['language']} | {s['family_id']} | {s['repeat']} | `{r['raw_response']}` | {arithmetic} |")
lines += ['', '## Costs and remaining blockers','',
    '| New phase | Requests | Observed token cost USD | Authorized phase cap USD |','|---|---:|---:|---:|',
    '| Vietnamese development | 108 | 0.00590340 | 1.00 |',
    '| Separate compatibility smoke | 4 | 0.00041195 | 0.05 |',
    '| Formal P0 | 144 | 0.01486100 | 1.50 |',
    '| Total under this authorization | 256 | **'+summary['observed_total_token_cost_usd']+'** | **2.55** |','',
    'Costs apply the frozen verified prices to actual token usage; they are not invoices. No retries. Total durable reservation was approximately USD 0.6272656. All caps included permitted retries; none were needed. Official price sources: [GPT-4o-mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [GPT-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).','',
    'Human semantic review and account-level provider compatibility are now verified for this configuration. Overall real P0 performance is verified **below the required floor** because the replication model fails in both languages. The primary model passed both conditions, but this does not authorize removing the replication conditions from the frozen protocol.','',
    'Held-out E1 remains blocked by the failed required P0 gate and has no spending authorization. No prompt, model or threshold was changed after results. The full-episode extension remains deferred.','',
    'The next permissible research step is a documented, separately versioned development-only interface correction if warranted by the capacity errors, followed by a new frozen P0 gate. The specification allows one such correction; this report does not perform it, assert that it will fix the model, or authorize another paid run. Retain this failed gate as evidence.','',
    '## Artifacts and reproduction','',
    '- `FINAL_VERIFICATION.json`: independent grades/replays, counts, costs, unchanged bindings and blocked held-out status.',
    '- `../../p0/live.final.freeze.json`: final immutable-by-hash settings and smoke binding.',
    '- `../../p0/runs/smoke-001/SMOKE_REPORT.json`: separate compatibility report.',
    '- `../../p0/runs/gate-001/P0_REPORT.json` and `GATE_ACCEPTANCE.json`: formal four-condition results and matching gate binding.',
    '- `../../p0/runs/gate-001/attempts.jsonl`: hash-chained exact prompts, all raw provider envelopes, usage and terminal labels.',
    '- `../vietnamese-development-sweep-20261104-01/`: all 108 raw responses, allocations, grades, traces, CSV and matched EN/VI analysis.',
    '- `tests-final.txt`: complete offline test suite output (41 tests).','',
    'Executed commands from repository root (do not rerun paid phases in a new directory to repeat them):','', '```bash',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/run_vietnamese_sweep.py --approval experiments/llm_lbf_demo/pilot/next-steps-20261104/vietnamese-approval.json',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/analyze_vietnamese_sweep.py',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/execute_p0_authorized.py smoke --output experiments/llm_lbf_demo/p0/runs/smoke-001',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m experiments.llm_lbf_demo.p0.prepare freeze --human-approval experiments/llm_lbf_demo/p0/human-approval.json --smoke-journal experiments/llm_lbf_demo/p0/runs/smoke-001/attempts.jsonl --output experiments/llm_lbf_demo/p0/live.final.freeze.json',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python experiments/llm_lbf_demo/pilot/next-steps-20261104/execute_p0_authorized.py gate --final-config experiments/llm_lbf_demo/p0/live.final.freeze.json --output experiments/llm_lbf_demo/p0/runs/gate-001',
    '```','',
    'Free offline suite command:','', '```bash',
    'MPLCONFIGDIR=/private/tmp/p2a-mpl /opt/anaconda3/envs/policy2action/bin/python -m unittest discover -s experiments/llm_lbf_demo/tests -v',
    '```','',
    'The verifier/analyzers use exclusive creation for their report outputs. Preserve existing outputs; for a fresh audit, direct them to copies rather than deleting evidence. Configured credentials were loaded privately and never written to artifacts.']
with (PREP/'NEXT_STEPS_ACCEPTANCE_REPORT.md').open('x') as f:f.write('\n'.join(lines)+'\n')
print(canonical({'report':str(PREP/'NEXT_STEPS_ACCEPTANCE_REPORT.md'),'failures_saved':len(failures),
    'formal_P0_passed':gate['held_out_E1_authorized'],'cost_usd':summary['observed_total_token_cost_usd']}))
