"""One authorized six-request exploratory development pilot; never a formal gate."""
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime,timezone
from decimal import Decimal
from urllib.error import HTTPError

REPO=Path('/Users/phoenix/PycharmProjects/adleap-mas')
os.chdir(REPO);sys.path.insert(0,str(REPO))
from dotenv import dotenv_values
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import payload
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.executor import replay,make_env,recovered,EXECUTOR_VERSION,executor_source_hash
from experiments.llm_lbf_demo.e1.worlds import load_manifest
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.p0 import transport
from experiments.llm_lbf_demo.p0.report import usage_cost

OUT=REPO/'experiments/llm_lbf_demo/pilot/exploratory-20261104-01'
OUT.mkdir(exist_ok=True)
if (OUT/'attempts.jsonl').exists():raise SystemExit('Refusing to repeat an existing pilot')
key=os.environ.get('OPENAI_API_KEY','').strip()
if not key:key=(dotenv_values(REPO/'.env').get('OPENAI_API_KEY') or '').strip()
if not key or key=='your_openai_api_key_here':raise SystemExit('BLOCKER: configured OPENAI_API_KEY is absent')
os.environ['OPENAI_API_KEY']=key
# Native operating-system trust store; certificate verification stays enabled.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

model=read_json(REPO/'experiments/llm_lbf_demo/p0/live.proposed.json')['models'][0]
assert model['id']=='gpt-4o-mini-2024-07-18'
assert (model['input_usd_per_million'],model['cached_input_usd_per_million'],model['output_usd_per_million'])==(.15,.075,.6)
assert EXECUTOR_VERSION=='e1-motion-2'
assert executor_source_hash()==read_json(REPO/'experiments/llm_lbf_demo/p0/executor.freeze.json')['executor_source_hash']
worlds=load_manifest();policies=read_json(ROOT/'e1_policies.json')
selected=[next(w for w in worlds if w['split']=='development' and w['stratum']==kind) for kind in ('light','mixed')]
conditions=[(w,p) for w in selected for p in ('P0','R','F')]
requests=[payload(w['state'],policies['languages']['EN'][p][0]) for w,p in conditions]
assert len(conditions)==6 and all(len(str(r).encode())+512<=10000 for r in requests)
reserve=(Decimal(10000)*Decimal('.15')+Decimal(256)*Decimal('.6'))/Decimal(1000000)
assert reserve*6<=Decimal('1')

def safe(value):
    text=str(value).replace(key,'[REDACTED]')
    return re.sub(r'sk-[A-Za-z0-9_.*-]+','[REDACTED]',text)

def save(name,value):
    with (OUT/name).open('x') as f:f.write(canonical(value)+'\n');f.flush();os.fsync(f.fileno())

save('configuration.json',{'label':'EXPLORATORY_DEVELOPMENT_PILOT','not_formal_P0':True,
    'held_out_E1_authorized':False,'authorization':'User explicitly authorized at most six API requests and USD 1',
    'max_api_requests':6,'spending_ceiling_usd':1,'worst_case_reserved_usd':float(reserve*6),
    'request_settings':transport.SETTINGS,'model':model,'executor_version':EXECUTOR_VERSION,
    'executor_source_hash':executor_source_hash(),'pricing_source':'https://developers.openai.com/api/docs/models/gpt-4o-mini',
    'worlds':selected,'conditions':[{'world':w['family_id'],'policy':p,'prompt':r} for (w,p),r in zip(conditions,requests)]})

real_urlopen=transport.urlopen
count=0;reserved=Decimal(0);error_detail=None

def audited_urlopen(request,timeout=60):
    global count,reserved,error_detail
    if count>=6 or reserved+reserve>Decimal('1'):raise RuntimeError('Hard request/spend cap reached')
    count+=1;reserved+=reserve
    try:
        return real_urlopen(request,timeout=timeout)
    except HTTPError as exc:
        try:
            body=json.loads(exc.read().decode('utf-8','replace'));e=body.get('error',{})
            error_detail={'http_status':exc.code,'code':safe(e.get('code')),'type':safe(e.get('type')),'message':safe(e.get('message'))}
        except Exception:
            error_detail={'http_status':exc.code,'message':'Provider HTTP error; body not interpretable'}
        raise
    except Exception as exc:
        error_detail={'type':type(exc).__name__,'message':safe(exc)}
        raise
transport.urlopen=audited_urlopen
rows=[];blocker=None
with Journal(OUT/'attempts.jsonl') as log:
    log.append({'event':'pilot','label':'EXPLORATORY_DEVELOPMENT_PILOT','timestamp':datetime.now(timezone.utc).isoformat(),
                'max_api_requests':6,'spending_ceiling_usd':1,'held_out_E1_authorized':False})
    for index,((world,policy),request) in enumerate(zip(conditions,requests),1):
        if blocker:
            rows.append({'world':world['family_id'],'stratum':world['stratum'],'policy':policy,'status':'NOT_RUN',
                         'blocker':blocker,'targets':None,'physical_validity':None,'policy_compliance':None,
                         'pickup_outcome':'not run','latency_seconds':None,'observed_cost_usd':None})
            continue
        stem=f'{index:02d}-{world["family_id"]}-{policy}'
        row={'world':world['family_id'],'stratum':world['stratum'],'policy':policy,'requested_model':model['id']}
        log.append({'event':'started','condition':index,'world':world,'policy':policy,'prompt':request,
                    'prompt_hash':digest(request),'reserved_usd':float(reserve),'timestamp':datetime.now(timezone.utc).isoformat()})
        error_detail=None;start=time.perf_counter()
        try:
            response=transport.P0Provider().complete(request,model)
        except Exception as exc:
            blocker=error_detail or {'type':type(exc).__name__,'message':safe(exc)}
            row.update(status='INFRA',blocker=blocker,targets=None,physical_validity=None,policy_compliance=None,
                       pickup_outcome='not run',latency_seconds=time.perf_counter()-start,observed_cost_usd=None)
            log.append({'event':'infrastructure_error','condition':index,**row})
            save(stem+'.json',row);rows.append(row)
            print(canonical({'condition':index,'status':'BLOCKED','blocker':blocker}),flush=True)
            continue
        latency=time.perf_counter()-start
        # Durable raw response before any parsing, grading, replay or rendering.
        log.append({'event':'response','condition':index,'latency_seconds':latency,'response':response})
        save(stem+'-response.json',{'prompt':request,'latency_seconds':latency,'response':response})
        verdict=score(response['raw'],world['state'],policy)
        execution=replay(world['state'],verdict['targets'],policy,world['simulator_seed']) if verdict['targets'] is not None else {
            'status':'NOT_RUN','success':False,'diagnosis':'no valid parsed allocation','trace':[]}
        cost=usage_cost(response,model)
        row.update(status=verdict['status'],actual_model=response.get('model'),targets=verdict['targets'],
                   physical_validity=verdict['physical_valid'],policy_compliance=verdict['policy_compliant'],
                   pickup_outcome=execution['status'],latency_seconds=latency,observed_cost_usd=cost,
                   grading=verdict,executor=execution,prompt=request,raw_response=response['raw'],response_file=stem+'-response.json')
        save(stem+'.json',row)
        log.append({'event':'terminal','condition':index,'summary':{k:v for k,v in row.items() if k not in ('executor','prompt','raw_response')},
                    'trace_file':stem+'.json'})
        rows.append(row)
        print(canonical({k:row[k] for k in ('world','policy','actual_model','targets','status','pickup_outcome','latency_seconds','observed_cost_usd')}),flush=True)
        if response.get('model')!=model['id']:
            blocker={'type':'ModelMismatch','message':'Returned model differs from configured snapshot; stopping'}
        usage=response.get('usage',{})
        if usage.get('prompt_tokens',10001)>10000 or usage.get('completion_tokens',257)>256:
            blocker={'type':'BudgetContractViolation','message':'Usage outside reserved bounds; stopping'}
    save('results.json',{'label':'EXPLORATORY_DEVELOPMENT_PILOT','rows':rows,'api_requests':count,
        'reserved_upper_bound_usd':float(reserved),'observed_usage_cost_usd':sum(r.get('observed_cost_usd') or 0 for r in rows),
        'unknown_cost_attempts':sum(r['status']=='INFRA' for r in rows),'held_out_E1_authorized':False,
        'formal_P0_passed':False,'blocker':blocker})

# Record native upstream visualization after all requests; no further inference.
try:
    import pygame
    from PIL import Image
    for index,row in enumerate(rows,1):
        trace=row.get('executor',{}).get('trace',[])
        if not trace:continue
        world=next(w for w in selected if w['family_id']==row['world'])
        env=make_env(world['state'],world['simulator_seed']);env.display=True;env.render_mode='rgb_array'
        env.reset();frames=[Image.fromarray(env.render(mode='rgb_array'))]
        try:
            for tick in trace:
                recovered.step_joint(env,tick['actions'])
                assert recovered.snapshot(env)==tick['after']
                frames.append(Image.fromarray(env.render(mode='rgb_array')))
            frames[0].save(OUT/f'{index:02d}-{row["world"]}-{row["policy"]}.gif',save_all=True,
                           append_images=frames[1:],duration=500,loop=0)
        finally:env.close()
    save('render-status.json',{'native_renderer':'completed','files':[p.name for p in OUT.glob('*.gif')]})
except Exception as exc:
    save('render-status.json',{'native_renderer':'unavailable','type':type(exc).__name__,'message':safe(exc)})
print(canonical({'output':str(OUT),'api_requests':count,'reserved_upper_bound_usd':float(reserved),'blocker':blocker}),flush=True)
