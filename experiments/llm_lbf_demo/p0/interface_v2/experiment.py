"""24-call matched diagnostic, not a formal gate. No network without approval."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import time
from ...e1.common import ROOT,canonical,digest,read_json
from ...e1.controller import payload as original_payload
from ...e1.e1_oracle import good_set,score
from ...e1.executor import replay
from ...e1.journal import Journal
from ..prepare import bundle
from ..report import usage_cost
from ..transport import P0Provider,SETTINGS
from .controller import VERSION,payload

HERE=Path(__file__).resolve().parent
P0=HERE.parent


def development_worlds():
    return [json.loads(line) for line in (ROOT/'e1_manifest.jsonl').read_text().splitlines()
            if json.loads(line)['split']=='development']


def protocol():
    proposal=read_json(P0/'live.proposed.json')
    old_freeze=read_json(P0/'live.final.freeze.json')
    # New files live below a subdirectory; the entire v1 binding must stay valid.
    if bundle(proposal)!=old_freeze['binding']:raise ValueError('original frozen v1 contract changed')
    worlds={w['family_id']:w for w in development_worlds()}
    failures=read_json(P0/'runs/gate-001/FAILURE_EXAMPLES.json')['failures']
    families=sorted({f['slot']['family_id'] for f in failures})
    assert len(families)==3 and all(w in worlds for w in families)
    policies=read_json(ROOT/'e1_policies.json')
    slots=[]
    # Paired arms within each world/model/language; seed fixed before new calls.
    rng=random.Random(4206)
    blocks=[(family,model,lang) for family in families for model in proposal['models'] for lang in ('EN','VI')]
    rng.shuffle(blocks)
    for family,model,lang in blocks:
        arms=['original','clarified'];rng.shuffle(arms)
        for arm in arms:
            world=worlds[family];builder=original_payload if arm=='original' else payload
            slot={'world':world,'model':model,'language':lang,'arm':arm,'policy':'P0',
                  'request':builder(world['state'],policies['languages'][lang]['P0'][0])}
            slot['slot_id']=digest(slot);slots.append(slot)
    def reserve(model):return (Decimal(model['max_input_tokens'])*Decimal(str(model['input_usd_per_million']))+
        Decimal(model['max_output_tokens'])*Decimal(str(model['output_usd_per_million'])))/Decimal(1000000)
    bound=sum(reserve(s['model']) for s in slots)
    assert len(slots)==24 and bound<=Decimal('.10')
    assert all(len(str(s['request']).encode())+512<=s['model']['max_input_tokens'] for s in slots)
    files=sorted(HERE.glob('*.py'))
    return {'version':VERSION,'label':'POSTHOC_DEVELOPMENT_DIAGNOSTIC_NOT_FORMAL_P0_OR_E1',
        'hypothesis':'Explicitly grounding level fields and the per-box capacity inequality may reduce capacity-infeasible recommendations.',
        'selection':'All three development families with a PHYSICS failure in the first formal P0; post-hoc selection, not a generalization sample.',
        'independent_families':3,'scheduled_requests':24,'fresh_context':True,'retries':0,'spending_ceiling_usd':.10,
        'reserved_worst_case_usd':str(bound),'models':proposal['models'],'request_settings':SETTINGS,
        'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'preserved_v1_binding_hash':old_freeze['binding_hash'],'policy_hash':digest(policies),
        'failed_gate_sha256':hashlib.sha256((P0/'runs/gate-001/attempts.jsonl').read_bytes()).hexdigest(),
        'randomization_seed':4206,'slots':slots,'held_out_E1_authorized':False,'formal_gate_passed':False,
        'decision_rule':'Descriptive matched results only. Do not tune/select another prompt variant; any subsequent formal gate uses all 12 development worlds and unchanged thresholds.'}


def write_new(path,value):
    with Path(path).open('x') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def validate_approval(approval,contract):
    if (approval.get('approved') is not True or not approval.get('approved_by') or not approval.get('approved_at')
        or approval.get('protocol_hash')!=digest(contract)
        or type(approval.get('max_usd')) not in (int,float) or approval['max_usd']<.10):
        raise PermissionError('new 24-call diagnostic requires matching USD 0.10 authorization; prior phase approval is not reused')
    semantic=read_json(P0/'human-approval.json')
    if not semantic['approved'] or semantic['policy_hash']!=contract['policy_hash']:
        raise PermissionError('unchanged EN/VI policy approval required')


def run(output,*,dry_run=True,mode='oracle',approval=None,provider=None):
    contract=protocol()
    if not dry_run:validate_approval(approval or {},contract)
    if provider is None and not dry_run:provider=P0Provider()
    if dry_run and provider is not None:raise ValueError('fixture run cannot accept a real provider')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if (output/'attempts.jsonl').exists():raise ValueError('existing diagnostic retained; refusing repeat or uncertain resend')
    write_new(output/'configuration.json',{'protocol':contract,'protocol_hash':digest(contract),
              'infrastructure_validation':dry_run,'approval':approval if not dry_run else None})
    rows=[];reserved=Decimal(0);cost=Decimal(0);fatal=None
    with Journal(output/'attempts.jsonl') as log:
        log.append({'event':'run','infrastructure_validation':dry_run,'protocol_hash':digest(contract)})
        for slot in contract['slots']:
            model=slot['model'];sid=slot['slot_id'];state=slot['world']['state']
            if fatal:
                rows.append({'slot_id':sid,'status':'NOT_RUN','failure':fatal});continue
            amount=(Decimal(model['max_input_tokens'])*Decimal(str(model['input_usd_per_million']))+
                    Decimal(model['max_output_tokens'])*Decimal(str(model['output_usd_per_million'])))/Decimal(1000000)
            if not dry_run and reserved+amount>Decimal('.10'):raise PermissionError('hard reservation ceiling exceeded')
            log.append({'event':'started','slot_id':sid,'slot':slot,'reserved_usd':str(amount if not dry_run else 0),
                        'timestamp':datetime.now(timezone.utc).isoformat()})
            if not dry_run:reserved+=amount
            started=time.perf_counter()
            try:
                if dry_run:
                    raw=(canonical({'targets':good_set(state,'P0')[0]}) if mode=='oracle' else
                         canonical({'targets':{a['id']:None for a in state['agents']}}) if mode=='idle' else 'not JSON')
                    response={'raw':raw,'model':'fixture-only','usage':{},'infrastructure_validation':True}
                else:response=provider.complete(slot['request'],model)
            except Exception as exc:
                # Transport only returns sanitized error types/messages. Never log a key/header.
                fatal={'type':type(exc).__name__,'message':'Provider/transport failure; no retry or further requests.'}
                row={'slot_id':sid,'status':'INFRA','failure':fatal,'grading':None,'executor':None,'observed_cost_usd':None}
                log.append({'event':'infra','slot_id':sid,'failure':fatal});rows.append(row);continue
            log.append({'event':'response','slot_id':sid,'response':response,'latency_seconds':time.perf_counter()-started})
            # Retain every response before independent parsing/grading.
            verdict=score(response['raw'],state,'P0')
            execution=replay(state,verdict['targets'],'P0',slot['world']['simulator_seed']) if verdict['targets'] is not None else None
            observed=usage_cost(response,model) if not dry_run else None
            if not dry_run:
                if response.get('model')!=model['id']:fatal={'type':'ModelMismatch'}
                usage=response.get('usage') or {}
                if (observed is None or usage.get('prompt_tokens',10001)>model['max_input_tokens']
                    or usage.get('completion_tokens',257)>model['max_output_tokens']):fatal={'type':'UnknownCostOrTokenContractViolation'}
                if observed is not None:cost+=Decimal(str(observed))
            row={'slot_id':sid,'world':slot['world']['family_id'],'language':slot['language'],'arm':slot['arm'],
                 'model_role':model['role'],'status':verdict['status'],'grading':verdict,'executor':execution,
                 'actual_model':response.get('model'),'raw_response':response['raw'],'observed_cost_usd':observed}
            rows.append(row);log.append({'event':'terminal',**row})
    result={'version':VERSION,'infrastructure_validation':dry_run,'scheduled_slots':24,'rows':rows,
            'requests':sum(e['event']=='started' for e in log.events),
            'statuses':dict(Counter(r['status'] for r in rows)),
            'reserved_upper_bound_usd':str(reserved),'observed_token_cost_usd':str(cost) if not dry_run else None,
            'fatal_blocker':fatal,'held_out_E1_authorized':False,'formal_gate_passed':False}
    write_new(output/'results.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','run']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--live',action='store_true');p.add_argument('--approval',type=Path)
    p.add_argument('--fixture',choices=['oracle','idle','malformed'],default='oracle')
    args=p.parse_args()
    if args.action=='prepare':
        value=protocol();write_new(args.output,{'protocol_hash':digest(value),'protocol':value,'live_spending_authorized':False});return
    approval=read_json(args.approval) if args.approval else None
    if args.live:
        validate_approval(approval or {},protocol())
        from dotenv import dotenv_values
        key=os.environ.get('OPENAI_API_KEY','').strip() or (dotenv_values(ROOT.parents[2]/'.env').get('OPENAI_API_KEY') or '').strip()
        if not key:raise SystemExit('BLOCKER: configured API credential absent')
        os.environ['OPENAI_API_KEY']=key
        import truststore
        truststore.inject_into_ssl()
    result=run(args.output,dry_run=not args.live,mode=args.fixture,approval=approval)
    print(canonical({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
