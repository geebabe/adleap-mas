"""Authorized exploratory English development sweep; unchanged six-call pilot contract."""
import csv
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError

REPO=Path('/Users/phoenix/PycharmProjects/adleap-mas');os.chdir(REPO);sys.path.insert(0,str(REPO))
from dotenv import dotenv_values
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import payload
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import replay,EXECUTOR_VERSION,executor_source_hash
from experiments.llm_lbf_demo.e1.worlds import validate_manifest
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.p0 import transport
from experiments.llm_lbf_demo.p0.report import usage_cost

OUT=REPO/'experiments/llm_lbf_demo/pilot/english-development-sweep-20261104-01'
if (OUT/'attempts.jsonl').exists():raise SystemExit('Refusing to repeat an existing sweep')
pilot=read_json(REPO/'experiments/llm_lbf_demo/pilot/exploratory-20261104-01/configuration.json')
model=pilot['model'];assert model['id']=='gpt-4o-mini-2024-07-18'
assert transport.SETTINGS==pilot['request_settings'] and EXECUTOR_VERSION==pilot['executor_version']
assert executor_source_hash()==pilot['executor_source_hash']
worlds=[json.loads(line) for line in (ROOT/'e1_manifest.jsonl').read_text().splitlines() if json.loads(line)['split']=='development']
assert len(worlds)==12;validate_manifest(worlds,full=False)
policies=read_json(ROOT/'e1_policies.json')
preflight=read_json(REPO/'experiments/llm_lbf_demo/p0/evidence/preflight-final.json')
for name in ('controller.py','e1_oracle.py','executor.py'):
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==preflight['binding']['e1_code_hashes']['e1/'+name]
for c in pilot['conditions']:
    w=next(w for w in worlds if w['family_id']==c['world'])
    assert payload(w['state'],policies['languages']['EN'][c['policy']][0])==c['prompt']
conditions=[(w,repeat,p) for w in worlds for repeat in (1,2,3) for p in ('P0','R','F')]
requests=[payload(w['state'],policies['languages']['EN'][p][0]) for w,repeat,p in conditions]
assert len(conditions)==108 and all(len(str(r).encode())+512<=model['max_input_tokens'] for r in requests)
reserve=(Decimal(model['max_input_tokens'])*Decimal(str(model['input_usd_per_million']))+
         Decimal(model['max_output_tokens'])*Decimal(str(model['output_usd_per_million'])))/Decimal(1000000)
assert reserve*108<=Decimal('1')
key=os.environ.get('OPENAI_API_KEY','').strip() or (dotenv_values(REPO/'.env').get('OPENAI_API_KEY') or '').strip()
if not key or key=='your_openai_api_key_here':raise SystemExit('BLOCKER: configured OPENAI_API_KEY absent')
os.environ['OPENAI_API_KEY']=key
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:pass

def safe(value):return re.sub(r'sk-[A-Za-z0-9_.*-]+','[REDACTED]',str(value).replace(key,'[REDACTED]'))
def save(name,value):
    with (OUT/name).open('x') as f:f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())

source_files=[ROOT/name for name in ('controller.py','e1_oracle.py','executor.py','common.py','e1_policies.json','e1_manifest.jsonl')]
source_files += [REPO/'experiments/llm_lbf_demo/p0/transport.py',REPO/'experiments/llm_lbf_demo/p0/report.py',ROOT.parent/'testbed.py']
save('configuration.json',{'label':'EXPLORATORY_ENGLISH_DEVELOPMENT_SWEEP','language':'EN','independent_families':12,
    'scheduled_calls':108,'max_api_requests':108,'automatic_retries':0,'spending_ceiling_usd':1,
    'reserved_per_attempt_usd':float(reserve),'worst_case_reserved_usd':float(reserve*108),
    'model':model,'request_settings':transport.SETTINGS,'executor_version':EXECUTOR_VERSION,
    'executor_source_hash':executor_source_hash(),'policy_paraphrase':0,
    'schedule':'manifest world order, repetitions 1/2/3, P0/R/F; fresh two-message context per request',
    'source_hashes':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
    'worlds':worlds,'conditions':[{'world':w['family_id'],'repetition':rep,'policy':p,'prompt':req}
                               for (w,rep,p),req in zip(conditions,requests)],
    'held_out_worlds_used':0,'held_out_E1_authorized':False,'formal_gate_passed':False,
    'authorization':'Current user authorized this exploratory 108-condition English development sweep under USD 1'})

network=transport.urlopen;count=0;reserved=Decimal(0);error_detail=None

def guarded(request,timeout=60):
    global count,reserved,error_detail
    if count>=108 or reserved+reserve>Decimal('1'):raise RuntimeError('Hard request or USD 1 reservation cap reached')
    if request.full_url!='https://api.openai.com/v1/chat/completions':raise RuntimeError('Unexpected endpoint')
    count+=1;reserved+=reserve
    try:return network(request,timeout=timeout)
    except HTTPError as exc:
        try:
            e=json.loads(exc.read().decode('utf-8','replace')).get('error',{})
            error_detail={'http_status':exc.code,'code':safe(e.get('code')),'type':safe(e.get('type')),'message':safe(e.get('message'))}
        except Exception:error_detail={'http_status':exc.code,'message':'Uninterpretable provider error body'}
        raise
    except Exception as exc:
        error_detail={'type':type(exc).__name__,'message':safe(exc)};raise
transport.urlopen=guarded
rows=[];fatal=None
with Journal(OUT/'attempts.jsonl') as log:
    log.append({'event':'sweep','label':'EXPLORATORY_ENGLISH_DEVELOPMENT_SWEEP','timestamp':datetime.now(timezone.utc).isoformat(),
                'scheduled_calls':108,'max_api_requests':108,'automatic_retries':0,'spending_ceiling_usd':1,
                'independent_families':12,'held_out_E1_authorized':False})
    for index,((world,repeat,policy),request) in enumerate(zip(conditions,requests),1):
        stem=f'{index:03d}-{world["family_id"]}-r{repeat}-{policy}'
        row={'condition':index,'world':world['family_id'],'stratum':world['stratum'],'repetition':repeat,'policy':policy,
             'prompt':request,'requested_model':model['id'],'simulator_seed':world['simulator_seed']}
        if fatal:
            row.update(status='NOT_RUN',failure=fatal,grading=None,executor=None,actual_model=None,
                       targets=None,latency_seconds=None,observed_cost_usd=None,raw_response=None,selected_boxes=[])
            rows.append(row);save(stem+'.json',row);continue
        if reserved+reserve>Decimal('1'):
            fatal={'type':'BudgetCap','message':'Next verified reservation would exceed USD 1'}
            row.update(status='NOT_RUN',failure=fatal,grading=None,executor=None,actual_model=None,
                       targets=None,latency_seconds=None,observed_cost_usd=None,raw_response=None,selected_boxes=[])
            rows.append(row);save(stem+'.json',row);continue
        log.append({'event':'started','condition':index,'world':world,'policy':policy,'repetition':repeat,
                    'prompt':request,'prompt_hash':digest(request),'reserved_usd':float(reserve),
                    'timestamp':datetime.now(timezone.utc).isoformat()})
        error_detail=None;start=time.perf_counter()
        try:response=transport.P0Provider().complete(request,model)
        except Exception as exc:
            error=error_detail or {'type':type(exc).__name__,'message':safe(exc)}
            row.update(status='INFRA',failure=error,grading=None,executor=None,targets=None,actual_model=None,
                       latency_seconds=time.perf_counter()-start,observed_cost_usd=None,raw_response=None,selected_boxes=[])
            log.append({'event':'infrastructure_error','condition':index,'failure':error,'latency_seconds':row['latency_seconds']})
            if error.get('http_status') in (400,401,403,404) or error.get('code') in ('insufficient_quota','invalid_api_key'):
                fatal=error
        else:
            latency=time.perf_counter()-start
            log.append({'event':'response','condition':index,'response':response,'latency_seconds':latency})
            save(stem+'-response.json',{'prompt':request,'response':response,'latency_seconds':latency})
            verdict=score(response['raw'],world['state'],policy)
            execution=replay(world['state'],verdict['targets'],policy,world['simulator_seed']) if verdict['targets'] is not None else {
                'status':'NOT_RUN','success':False,'diagnosis':'no valid parsed allocation','trace':[]}
            selected=[]
            if verdict['targets'] is not None:
                for task in world['state']['tasks']:
                    members=[a for a in world['state']['agents'] if verdict['targets'][a['id']]==task['id']]
                    if members:selected.append({'task':task['id'],'level':task['level'],'assigned_agents':[a['id'] for a in members],
                        'assigned_capacity':sum(a['level'] for a in members),'jointly_only':task['level']>max(a['level'] for a in world['state']['agents'])})
            row.update(status=verdict['status'],failure=None,actual_model=response.get('model'),targets=verdict['targets'],
                       raw_response=response['raw'],grading=verdict,executor=execution,latency_seconds=latency,
                       observed_cost_usd=usage_cost(response,model),usage=response.get('usage'),selected_boxes=selected,
                       response_file=stem+'-response.json')
            if response.get('model')!=model['id']:
                fatal={'type':'ModelMismatch','message':'Returned snapshot differs from the frozen pilot snapshot'}
            usage=response.get('usage',{})
            if usage.get('prompt_tokens',10001)>10000 or usage.get('completion_tokens',257)>256:
                fatal={'type':'BudgetContractViolation','message':'Observed usage exceeds the pre-reserved token bounds'}
        save(stem+'.json',row);rows.append(row)
        log.append({'event':'terminal','condition':index,'world':row['world'],'policy':policy,'repetition':repeat,
                    'status':row['status'],'allocation':row['targets'],'grading':row['grading'],
                    'executor_status':row.get('executor',{}).get('status') if row.get('executor') else None,
                    'observed_cost_usd':row['observed_cost_usd'],'result_file':stem+'.json'})
        if index%9==0 or row['status']!='GOOD':
            print(canonical({'completed_conditions':index,'api_requests':count,'latest_world':row['world'],'latest_status':row['status'],
                'good_so_far':sum(bool(r.get('grading') and r['grading']['good']) for r in rows),'reserved_usd':float(reserved)}),flush=True)
    total=sum(Decimal(str(r['observed_cost_usd'])) for r in rows if r.get('observed_cost_usd') is not None)
    save('results.json',{'label':'EXPLORATORY_ENGLISH_DEVELOPMENT_SWEEP','rows':rows,'scheduled_calls':108,'api_requests':count,
        'automatic_retries':0,'reserved_upper_bound_usd':float(reserved),'observed_usage_cost_usd':str(total),
        'unknown_cost_attempts':sum(r['status']=='INFRA' for r in rows),'fatal_blocker':fatal,
        'held_out_E1_authorized':False,'formal_gate_passed':False,'independent_families':12})
print(canonical({'output':str(OUT),'api_requests':count,'observed_usage_cost_usd':str(total),'fatal_blocker':fatal}),flush=True)
