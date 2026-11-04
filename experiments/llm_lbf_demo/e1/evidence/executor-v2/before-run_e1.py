"""Run frozen E1 slots. --dry-run is mandatory unless --live is explicit."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import random
import time
from .common import ROOT,canonical,digest,read_json,PARSER_VERSION,ORACLE_VERSION,PROTOCOL_VERSION
from .controller import payload
from .e1_oracle import score
from .executor import replay
from .journal import Journal
from .providers import FakeProvider,LiveProvider,InfrastructureError
from .safeguards import validate_live,preflight_cost,estimate_attempt
from .worlds import load_manifest,witness_acceptance


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
    files=list(ROOT.glob('*.py'))+[ROOT.parent/'testbed.py',ROOT.parent/'requirements.lock',ROOT.parent/'upstream.lock.json']
    return {str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def gate_binding(models,policies,worlds):
    from .controller import SYSTEM
    return digest({'models':models,'policy_hash':digest(policies),'manifest_hash':digest(worlds),
                   'system':SYSTEM,'parser':PARSER_VERSION,'oracle':ORACLE_VERSION,'code':code_hashes()})


def _replay_cached(output,world,targets,gold):
    key=digest({'state':world['state_hash'],'targets':targets,'gold':gold,'seed':world['simulator_seed']})
    path=output/'replays'/f'{key}.json'
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        stored=read_json(path); result=stored['result']
        if stored['key']!=key or digest(result)!=stored['hash']:raise ValueError('replay cache integrity failure')
    else:
        result=replay(world['state'],targets,gold,world['simulator_seed'])
        with path.open('x') as f:
            f.write(canonical({'key':key,'hash':digest(result),'result':result})+'\n');f.flush();os.fsync(f.fileno())
    return {**{k:v for k,v in result.items() if k!='trace'},'trace_file':str(path.relative_to(output)),'record_hash':digest(result)}


def run(output,worlds,policies,*,mode='oracle',stage='all',dry_run=True,provider=None,
        config=None,approval=None,gate=None,slots=None,max_new_slots=None):
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
    configuration={'version':PROTOCOL_VERSION,'infrastructure_validation':dry_run,'fixture':mode if dry_run else None,
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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    modes=p.add_mutually_exclusive_group(required=True)
    modes.add_argument('--dry-run',action='store_true');modes.add_argument('--live',action='store_true')
    p.add_argument('--fixture',choices=['oracle','blind','idle','malformed'],default='oracle')
    p.add_argument('--stage',choices=['all','gate','e1'],default='all')
    p.add_argument('--manifest',type=Path,default=ROOT/'e1_manifest.jsonl')
    p.add_argument('--policies',type=Path,default=ROOT/'e1_policies.json')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--live-config',type=Path);p.add_argument('--human-approval',type=Path);p.add_argument('--gate-journal',type=Path)
    args=p.parse_args()
    worlds=load_manifest(args.manifest);policies=read_json(args.policies)
    if args.live and args.stage=='all':p.error('live gate and E1 must be separate runs')
    if args.live and (not args.live_config or not args.human_approval):p.error('live configuration and human approval required')
    gate=None
    if args.gate_journal:
        from .analyze_e1 import analyze
        gate=analyze(args.gate_journal)
    result=run(args.output,worlds,policies,mode=args.fixture,stage=args.stage,dry_run=args.dry_run,
               config=read_json(args.live_config) if args.live_config else None,
               approval=read_json(args.human_approval) if args.human_approval else None,gate=gate)
    print(canonical(result))


if __name__=='__main__':main()
