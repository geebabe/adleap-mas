"""Versioned copy of the frozen runner for corrected P0 only; no held-out entry point."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import time
from ...e1.common import ROOT,canonical,digest,read_json,PARSER_VERSION,ORACLE_VERSION,PROTOCOL_VERSION
from ..interface_v2.controller import payload
from ...e1.e1_oracle import score
from ...e1.executor import EXECUTOR_VERSION,executor_source_hash,replay
from ...e1.journal import Journal
from ...e1.providers import FakeProvider,LiveProvider,InfrastructureError
from ...e1.safeguards import validate_live,preflight_cost,estimate_attempt
from ...e1.worlds import load_manifest,witness_acceptance


def now():return datetime.now(timezone.utc).isoformat()


def slots_for(worlds,stage='all',seed=4102):
    rng=random.Random(seed);slots=[]
    stages=['gate','e1'] if stage=='all' else [stage]
    for phase in stages:
        selected=[w for w in worlds if w['split']==('development' if phase=='gate' else 'test')]
        blocks=[(w,role,p,r) for w in selected for role in ('primary','replication')
                for p in (range(1) if phase=='gate' else range(2)) for r in range(3)]
        rng.shuffle(blocks)
        for w,role,p,r in blocks:
            languages=['EN','VI'];rng.shuffle(languages)
            for language in languages:
                arms=['P0'] if phase=='gate' else ['R','F'];rng.shuffle(arms)
                for gold in arms:
                    s={'stage':phase,'family_id':w['family_id'],'model_role':role,
                       'language':language,'paraphrase':p,'repeat':r,'gold':gold,'presented':gold}
                    s['slot_id']=digest(s);slots.append(s)
    return slots


def code_hashes():
    from ...e1.run_e1 import code_hashes as original_hashes
    values=original_hashes()
    files=list(Path(__file__).resolve().parent.glob('*.py'))+[Path(__file__).resolve().parents[1]/'interface_v2/controller.py']
    for p in files:values[str(p.relative_to(ROOT.parent))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return values


def gate_binding(models,policies,worlds):
    from ..interface_v2.controller import SYSTEM
    return digest({'models':models,'policy_hash':digest(policies),'manifest_hash':digest(worlds),
                   'system':SYSTEM,'parser':PARSER_VERSION,'oracle':ORACLE_VERSION,'code':code_hashes()})


def _replay_cached(output,world,targets,gold):
    key=digest({'state':world['state_hash'],'targets':targets,'gold':gold,'seed':world['simulator_seed'],
                'executor_version':EXECUTOR_VERSION,'executor_source_hash':executor_source_hash()})
    path=output/'replays'/f'{key}.json'
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        stored=read_json(path); result=stored['result']
        if (stored['key']!=key or digest(result)!=stored['hash'] or
            result.get('executor_version')!=EXECUTOR_VERSION or result.get('executor_source_hash')!=executor_source_hash()):
            raise ValueError('replay cache integrity/version failure')
    else:
        result=replay(world['state'],targets,gold,world['simulator_seed'])
        with path.open('x') as f:
            f.write(canonical({'key':key,'hash':digest(result),'result':result})+'\n');f.flush();os.fsync(f.fileno())
    return {**{k:v for k,v in result.items() if k!='trace'},'trace_file':str(path.relative_to(output)),'record_hash':digest(result)}


def run(output,worlds,policies,*,mode='oracle',stage='all',dry_run=True,provider=None,
        config=None,approval=None,gate=None,slots=None,max_new_slots=None):
    if stage!='gate' or slots is None or any(s['stage'] not in ('gate','smoke') for s in slots):
        raise PermissionError('corrected workflow permits explicit development P0/smoke slots only')
    if any(next(w for w in worlds if w['family_id']==s['family_id'])['split']!='development' for s in slots):
        raise PermissionError('held-out worlds are blocked')
    if not dry_run and provider is None:raise PermissionError('explicit frozen transport required')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    slots=slots if slots is not None else slots_for(worlds,stage)
    by_family={w['family_id']:w for w in worlds}
    if len({s['slot_id'] for s in slots})!=len(slots):raise ValueError('duplicate slots')
    models=([{'role':'primary','id':'fixture-primary'},{'role':'replication','id':'fixture-replication'}]
            if dry_run else config['models'])
    by_role={m['role']:m for m in models}
    requests={s['slot_id']:payload(by_family[s['family_id']]['state'],
              policies['languages'][s['language']][s['presented']][s['paraphrase']]) for s in slots}
    binding=gate_binding(models,policies,worlds)
    estimated_ceiling=0
    if not dry_run:
        validate_live(config,approval,digest(policies),stage,gate,digest(worlds),binding)
        estimated_ceiling=preflight_cost(slots,models,requests,config['dollar_ceiling'])
        witnesses=witness_acceptance(worlds)
        if not witnesses['accepted']:
            raise PermissionError('offline executor witness regression blocks live launch: '+canonical(witnesses['failures']))
    provider=provider or (FakeProvider(mode,policies) if dry_run else LiveProvider())
    if dry_run and not getattr(provider,'infrastructure_validation',False):
        raise PermissionError('dry run refuses a non-fixture provider')
    if not dry_run and getattr(provider,'infrastructure_validation',False):
        raise PermissionError('live run refuses fixture evidence')
    configuration={'version':'p0-corrected-final-2','infrastructure_validation':dry_run,'fixture':mode if dry_run else None,
        'executor_version':EXECUTOR_VERSION,'executor_source_hash':executor_source_hash(),
        'manifest_hash':digest(worlds),'policy_hash':digest(policies),'slot_hash':digest(slots),'slot_count':len(slots),
        'models':models,'code_hashes':code_hashes(),'parser':PARSER_VERSION,'oracle':ORACLE_VERSION,
        'gate_binding':binding,'stage':stage,'config':config if not dry_run else None,
        'approval_hash':digest(approval) if approval else None,'estimated_retry_reserved_usd':estimated_ceiling,
        'upstream_commit':read_json(ROOT.parent/'upstream.lock.json')['commit']}
    config_hash=digest(configuration)
    with Journal(output/'attempts.jsonl') as log:
        if not log.events:
            log.append({'event':'run','config':configuration,'config_hash':config_hash,'timestamp':now()})
        elif log.events[0].get('config_hash')!=config_hash:
            raise ValueError('incompatible manifest/prompt/model/policy/config resume')
        terminals={e['slot_id']:e for e in log.events if e['event']=='terminal'}
        if len(terminals)!=sum(e['event']=='terminal' for e in log.events):raise ValueError('duplicate terminal slot')
        new=0
        for slot in slots:
            sid=slot['slot_id']
            if sid in terminals:continue
            if max_new_slots is not None and new>=max_new_slots:break
            world=by_family[slot['family_id']];request=requests[sid];model=by_role[slot['model_role']]
            events=[e for e in log.events if e.get('slot_id')==sid]
            starts=[e for e in events if e['event']=='started']
            responses=[e for e in events if e['event']=='response']
            failures=[e for e in events if e['event']=='infra']
            if starts and len(starts)>len(responses)+len(failures):
                raise RuntimeError('uncertain in-flight request; reconcile provider before resuming, never automatically resend')
            response=responses[-1]['response'] if responses else None
            fatal=None
            for attempt in range(len(starts),3):
                if response is not None:break
                reserve=0 if dry_run else estimate_attempt(request,model)
                reserved=sum(e.get('reserved_usd',0) for e in log.events if e['event']=='started')
                if not dry_run and reserved+reserve>config['dollar_ceiling']+1e-12:
                    raise PermissionError('durable reservation would exceed dollar ceiling')
                start=time.perf_counter()
                log.append({'event':'started','slot_id':sid,'attempt':attempt,'slot':slot,
                    'family_id':world['family_id'],'split':world['split'],'stratum':world['stratum'],
                    'state_hash':world['state_hash'],'state':world['state'],'prompt_hash':digest(request),
                    'request':request,'presented_policy':policies['languages'][slot['language']][slot['presented']][slot['paraphrase']],
                    'presented_policy_hash':digest(policies['languages'][slot['language']][slot['presented']][slot['paraphrase']]),
                    'grader_policy':slot['gold'],'model':model,'simulator_seed':world['simulator_seed'],
                    'generation_seed':world['generation_seed'],'parser':PARSER_VERSION,'oracle':ORACLE_VERSION,
                    'policy_utf8_bytes':len(policies['languages'][slot['language']][slot['presented']][slot['paraphrase']].encode()),
                    'reserved_usd':reserve,'timestamp':now()})
                try:
                    response=provider.complete(request,model)
                except InfrastructureError as exc:
                    log.append({'event':'infra','slot_id':sid,'attempt':attempt,'timestamp':now(),
                        'request_id':exc.request_id,'error':type(exc).__name__,'latency_seconds':time.perf_counter()-start})
                    continue
                except Exception as exc:
                    fatal=type(exc).__name__
                    log.append({'event':'infra','slot_id':sid,'attempt':attempt,'timestamp':now(),
                        'error':fatal,'retryable':False,'latency_seconds':time.perf_counter()-start})
                    break
                log.append({'event':'response','slot_id':sid,'attempt':attempt,'response':response,
                            'latency_seconds':time.perf_counter()-start,'timestamp':now()})
            if response is None:
                verdict={'status':'INFRA','good':False,'comparison_valid':False,'reason':fatal or 'infrastructure retries exhausted'}
                execution=None
            else:
                verdict=score(response['raw'],world['state'],slot['gold'])
                execution=(_replay_cached(output,world,verdict['targets'],slot['gold'])
                           if verdict['physical_valid'] and verdict['progress'] and verdict['comparison_valid'] else None)
            row={'event':'terminal','slot_id':sid,'slot':slot,'stratum':world['stratum'],
                 'verdict':verdict,'executor':execution,'timestamp':now()}
            log.append(row);terminals[sid]=row;new+=1
        summary={'slots':len(slots),'terminal_slots':len(terminals),'complete':len(terminals)==len(slots) and
                 all(t['verdict']['comparison_valid'] and (not t['executor'] or t['executor']['status']!='SPEC') for t in terminals.values()),
                 'infrastructure_validation':dry_run,'api_calls':0 if dry_run else sum(e['event']=='started' for e in log.events),
                 'statuses':dict(Counter(e['verdict']['status'] for e in terminals.values()))}
    return summary

