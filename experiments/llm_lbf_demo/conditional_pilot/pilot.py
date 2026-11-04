"""Prepare/run/report one 72-call conditional development pilot; approval required."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import random
import time
from ..e1.common import ROOT as E1,canonical,digest,read_json
from ..e1.controller import assert_policy_only_difference
from ..e1.e1_oracle import good_set as physical_good_set
from ..e1.executor import replay,EXECUTOR_VERSION,executor_source_hash
from ..e1.journal import Journal
from ..e1.worlds import validate_manifest
from ..p0.interface_v2.controller import payload,SYSTEM
from ..p0.report import usage_cost
from ..p0.transport import P0Provider,SETTINGS
from .grader import classify,score,good_set,audit_pickups

HERE=Path(__file__).resolve().parent
VERSION='conditional-development-pilot-1'
LIVE_OUTPUT=HERE/'evidence/live-001'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path,value):
    with Path(path).open('x') as f:f.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def worlds():
    # Filter development before validation/scoring; no held-out slots or grading.
    selected=[json.loads(line) for line in (E1/'e1_manifest.jsonl').read_text().splitlines()
              if json.loads(line)['split']=='development']
    if len(selected)!=12:raise ValueError('expected the existing 12 development worlds')
    validate_manifest(selected,full=False)
    return selected


def coverage(selected):
    rows=[]
    for w in selected:
        branch=classify(w['state']);valid=good_set(w['state'])
        rows.append({'world':w['family_id'],'split':w['split'],'state_hash':w['state_hash'],
            'capacities':{a['id']:a['level'] for a in w['state']['agents']},
            'remaining_box_weights':{t['id']:t['level'] for t in w['state']['tasks'] if not t['completed']},
            **branch,'eligible':bool(valid),'good_allocation_count':len(valid)})
    counts=Counter(r['branch'] for r in rows if r['eligible'])
    return {'worlds':rows,'eligible_worlds':sum(r['eligible'] for r in rows),
        'independent_worlds_by_branch':dict(counts),
        'missing_branches':[b for b in ('joint_required','solo_required') if not counts[b]],
        'ineligible_worlds':[r['world'] for r in rows if not r['eligible']],
        'worlds_changed_or_generated':0,'held_out_worlds_used':0,
        'confound':'joint_required coincides with mixed worlds; solo_required with light worlds. No causal complexity isolation.'}


def protocol():
    policies=read_json(HERE/'policies.json');selected=worlds();covered=coverage(selected)
    if covered['missing_branches']:raise ValueError('missing branch coverage; report gap rather than generate worlds')
    eligible={r['world'] for r in covered['worlds'] if r['eligible']}
    selected=[w for w in selected if w['family_id'] in eligible]
    freeze_path=E1.parent/'p0/final_gate_v2/live.final.freeze.json';frozen=read_json(freeze_path)
    # Bind to the final tested physical clarification, parser, executor and transport.
    for name,value in frozen['binding']['e1_code_hashes'].items():
        if sha(E1.parent/name)!=value:raise ValueError('frozen dependency changed: '+name)
    if digest(SYSTEM)!=frozen['binding']['corrected_system_sha256']:raise ValueError('capacity clarification changed')
    if executor_source_hash()!=frozen['binding']['executor']['executor_source_hash']:raise ValueError('executor changed')
    gate=read_json(E1.parent/'p0/final_gate_v2/runs/gate-002/P0_REPORT.json')
    if not gate['complete'] or not all(c['passed'] for c in gate['conditions']):raise ValueError('expected preserved passed P0')
    model=next(m for m in frozen['proposal']['models'] if m['role']=='primary')
    prices=read_json(HERE/'pricing.json')
    if model['id']!=prices['snapshot'] or model['id']!='gpt-4o-mini-2024-07-18':raise ValueError('unexpected model snapshot')
    for k in ('input_usd_per_million','cached_input_usd_per_million','output_usd_per_million'):
        if model[k]!=prices[k]:raise ValueError('verified prices do not match the frozen model')
    if SETTINGS!=frozen['proposal']['request_settings']:raise ValueError('transport settings changed')
    rng=random.Random(51105);blocks=[(w,r) for w in selected for r in (1,2,3)];rng.shuffle(blocks)
    slots=[]
    for world,rep in blocks:
        languages=['EN','VI'];rng.shuffle(languages)
        for lang in languages:
            s={'world':world,'repetition':rep,'language':lang,'request':payload(world['state'],policies[lang])}
            s['slot_id']=digest(s);slots.append(s)
        assert_policy_only_difference(slots[-2]['request'],slots[-1]['request'])
    reserve=(Decimal(model['max_input_tokens'])*Decimal(str(model['input_usd_per_million']))+
             Decimal(model['max_output_tokens'])*Decimal(str(model['output_usd_per_million'])))/Decimal(1000000)
    assert all(len(str(s['request']).encode())+512<=model['max_input_tokens'] for s in slots)
    assert reserve*len(slots)<=Decimal('.15')
    sources=sorted(HERE.glob('*.py'))+[E1.parent/'p0/transport.py',E1.parent/'p0/report.py']
    return {'version':VERSION,'scope':'EXPLORATORY_DEVELOPMENT_CONDITIONAL_APPLICATION_ONLY',
        'policy_hash':digest(policies),'policies':policies,'coverage':covered,'worlds':selected,
        'model':model,'request_settings':SETTINGS,'executor_version':EXECUTOR_VERSION,
        'executor_sha256':executor_source_hash(),'system_sha256':digest(SYSTEM),
        'existing_final_freeze_sha256':sha(freeze_path),'manifest_file_sha256':sha(E1/'e1_manifest.jsonl'),
        'source_hashes':{str(p.relative_to(E1.parent)):sha(p) for p in sources},
        'scheduled_calls':len(slots),'fresh_context':True,'repetitions_per_world_language':3,
        'independent_families':len(selected),'repetitions_are_not_independent_worlds':True,
        'randomization_seed':51105,'automatic_retries':0,'maximum_requests':len(slots),
        'reserved_per_attempt_usd':str(reserve),'worst_case_reservation_usd':str(reserve*len(slots)),
        'spending_ceiling_usd':.15,'verified_pricing':prices,'slots':slots,
        'claim_limits':['Does not isolate the causal effect of complexity.','No novelty or general policy-understanding claim.',
                        'No full-episode or held-out evaluation.'],
        'formal_gate_result':False,'held_out_calls_authorized':False}


def validate_approval(approval,contract):
    amount=approval.get('max_usd')
    if (approval.get('approved') is not True or not approval.get('approved_by') or not approval.get('approved_at')
        or approval.get('protocol_hash')!=digest(contract) or approval.get('policy_hash')!=contract['policy_hash']
        or approval.get('bilingual_semantics_approved') is not True
        or type(amount) not in (int,float) or not math.isfinite(amount) or amount<contract['spending_ceiling_usd']):
        raise PermissionError('new bilingual semantic approval and USD 0.15 pilot authorization must match this protocol')


def fixture_response(mode,state):
    if mode=='oracle':return canonical({'targets':good_set(state)[0]})
    if mode=='wrong_branch':
        alternatives=[a for a in physical_good_set(state,'P0') if not score(canonical({'targets':a}),state)['policy_compliant']]
        return canonical({'targets':alternatives[0]})
    if mode=='idle':return canonical({'targets':{a['id']:None for a in state['agents']}})
    if mode=='malformed':return 'not JSON'
    raise ValueError('unknown fixture')


def run(output,*,dry_run=True,mode='oracle',approval=None):
    contract=protocol()
    frozen=read_json(HERE/'protocol.frozen.json')
    if frozen['protocol_hash']!=digest(contract):raise ValueError('prepared protocol changed; retain evidence and re-review before live')
    if not dry_run:
        validate_approval(approval or {},contract)
        if Path(output).resolve()!=LIVE_OUTPUT.resolve():raise PermissionError('only the approved fresh live-001 directory is permitted')
    output=Path(output)
    if (output/'attempts.jsonl').exists():raise ValueError('existing attempt journal retained; never repeat an uncertain request')
    output.mkdir(parents=True,exist_ok=True)
    write_new(output/'configuration.json',{'contract':contract,'protocol_hash':digest(contract),
        'infrastructure_validation':dry_run,'approval':approval if not dry_run else None})
    model=contract['model'];reserve=Decimal(contract['reserved_per_attempt_usd']);reserved=Decimal(0)
    provider=None if dry_run else P0Provider();rows=[];fatal=None
    with Journal(output/'attempts.jsonl') as log:
        log.append({'event':'run','protocol_hash':digest(contract),'infrastructure_validation':dry_run})
        for slot in contract['slots']:
            sid=slot['slot_id'];state=slot['world']['state']
            row={'slot_id':sid,'world':slot['world']['family_id'],'branch':classify(state)['branch'],
                 'language':slot['language'],'repetition':slot['repetition'],'grading':None,'executor':None,
                 'pickup_audit':None,'raw_response':None,'usage':None,'actual_model':None,'observed_cost_usd':None}
            if fatal:
                row.update(status='NOT_RUN',failure=fatal);rows.append(row);log.append({'event':'terminal',**row});continue
            if not dry_run and reserved+reserve>Decimal(str(contract['spending_ceiling_usd'])):
                raise PermissionError('next durable reservation would exceed the hard pilot ceiling')
            log.append({'event':'started','slot_id':sid,'slot':slot,'reserved_usd':str(reserve if not dry_run else 0),
                        'timestamp':datetime.now(timezone.utc).isoformat()})
            if not dry_run:reserved+=reserve
            started=time.perf_counter()
            try:
                response=({'raw':fixture_response(mode,state),'model':'fixture-only','usage':{},'infrastructure_validation':True}
                          if dry_run else provider.complete(slot['request'],model))
            except Exception as exc:
                # The reused transport exposes sanitized HTTP/error types, no headers/key.
                fatal={'type':type(exc).__name__,'message':str(exc),'action':'stop; zero retries'}
                row.update(status='INFRA',failure=fatal,latency_seconds=time.perf_counter()-started)
                log.append({'event':'infrastructure_error','slot_id':sid,'failure':fatal})
            else:
                row['latency_seconds']=time.perf_counter()-started
                log.append({'event':'response','slot_id':sid,'response':response,'latency_seconds':row['latency_seconds']})
                verdict=score(response['raw'],state)
                execution=(replay(state,verdict['targets'],'P0',slot['world']['simulator_seed'])
                           if verdict.get('targets') is not None else None)
                pickup=audit_pickups(state,execution) if execution else None
                row.update(status=verdict['status'],grading=verdict,executor=execution,pickup_audit=pickup,
                    raw_response=response['raw'],usage=response.get('usage'),actual_model=response.get('model'),
                    observed_cost_usd=usage_cost(response,model) if not dry_run else None,failure=None)
                if not dry_run:
                    u=response.get('usage') or {}
                    if response.get('model')!=model['id']:fatal={'type':'ModelMismatch'}
                    if row['observed_cost_usd'] is None or u.get('prompt_tokens',10001)>model['max_input_tokens'] or u.get('completion_tokens',257)>model['max_output_tokens']:
                        fatal={'type':'UnknownCostOrTokenContractViolation'}
            rows.append(row);log.append({'event':'terminal',**row})
            if not dry_run:print(canonical({'completed':len(rows),'scheduled':len(contract['slots']),'latest_status':row['status']}),flush=True)
    known=[Decimal(str(r['observed_cost_usd'])) for r in rows if r['observed_cost_usd'] is not None]
    result={'scope':contract['scope'],'infrastructure_validation':dry_run,'rows':rows,'scheduled_calls':len(rows),
        'api_requests':0 if dry_run else sum(e['event']=='started' for e in log.events),
        'fixture_requests':sum(e['event']=='started' for e in log.events) if dry_run else 0,
        'automatic_retries':0,'reserved_upper_bound_usd':str(reserved),
        'observed_token_cost_usd':str(sum(known)) if known else None,
        'unknown_cost_attempts':sum(r['status']!='NOT_RUN' and r['observed_cost_usd'] is None for r in rows) if not dry_run else 0,
        'fatal_blocker':fatal,'held_out_calls':0,'formal_gate_passed':False}
    write_new(output/'results.json',result);return result


def report(directory):
    directory=Path(directory);results=read_json(directory/'results.json');config=read_json(directory/'configuration.json')
    contract=config['contract'];rows=results['rows'];events=Journal.read(directory/'attempts.jsonl')
    responses={e['slot_id']:e['response'] for e in events if e['event']=='response'}
    slots={s['slot_id']:s for s in contract['slots']}
    if digest(protocol())!=config['protocol_hash']:raise ValueError('source/config changed since execution')
    regraded=0;replayed=0
    for row in rows:
        if row['slot_id'] not in responses:continue
        slot=slots[row['slot_id']];response=responses[row['slot_id']]
        if score(response['raw'],slot['world']['state'])!=row['grading']:raise ValueError('independent regrade mismatch')
        regraded+=1
        if not results['infrastructure_validation']:
            if response.get('effective_request')!={**slot['request'],**contract['request_settings'],'model':contract['model']['id']}:
                raise ValueError('actual wire request differs from frozen protocol')
            if usage_cost(response,contract['model'])!=row['observed_cost_usd']:raise ValueError('cost mismatch')
        if row['executor']:
            fresh=replay(slot['world']['state'],row['grading']['targets'],'P0',slot['world']['simulator_seed'])
            if fresh!=row['executor'] or audit_pickups(slot['world']['state'],fresh)!=row['pickup_audit']:
                raise ValueError('independent replay/audit mismatch')
            replayed+=1
    summaries=[];family_rows=[]
    for branch in ('solo_required','joint_required'):
        for language in ('EN','VI'):
            selected=[r for r in rows if r['branch']==branch and r['language']==language]
            n=len(selected);families=sorted({r['world'] for r in selected})
            def count(key):return sum(bool(r.get('grading') and r['grading'].get(key)) for r in selected)
            flags={k:sum(bool(r.get('grading') and r['grading']['failure_flags'].get(k)) for r in selected)
                   for k in ('format','capacity','geometry','progress','policy','specification')}
            known=[Decimal(str(r['observed_cost_usd'])) for r in selected if r['observed_cost_usd'] is not None]
            summaries.append({'branch':branch,'language':language,'scheduled_calls':n,'independent_worlds':len(families),
                'strict_good':count('good'),'strict_goodness_rate':count('good')/n if n else None,
                'format_valid':count('format_valid'),'capacity_valid':count('capacity_feasible'),
                'geometry_valid':count('geometric_feasible'),'policy_compliant':count('policy_compliant'),
                'failure_flags_nonexclusive':flags,'statuses':dict(Counter(r['status'] for r in selected)),
                'executor_pickups':sum(bool(r['executor'] and r['executor']['success']) for r in selected),
                'conditional_pickup_violations':sum(len(r['pickup_audit']['violations']) for r in selected if r['pickup_audit']),
                'observed_token_cost_usd':str(sum(known)) if known else None})
            for world in families:
                rs=[r for r in selected if r['world']==world]
                family_rows.append({'world':world,'branch':branch,'language':language,'repetitions':len(rs),
                    'good_count':sum(bool(r.get('grading') and r['grading']['good']) for r in rs),
                    'statuses_by_repetition':{str(r['repetition']):r['status'] for r in rs}})
    value={'scope':'DEVELOPMENT_CONDITIONAL_APPLICATION_NOT_CAUSAL_COMPLEXITY_OR_NOVELTY',
        'infrastructure_validation':results['infrastructure_validation'],'conditions':summaries,'family_results':family_rows,
        'independent_families':contract['independent_families'],'repetitions_are_not_independent':True,
        'failure_counts_overlap':True,'api_requests':results['api_requests'],'automatic_retries':0,
        'observed_token_cost_usd':results['observed_token_cost_usd'],'unknown_cost_attempts':results['unknown_cost_attempts'],
        'independent_regrades':regraded,'independent_replays':replayed,
        'failures':[r for r in rows if not (r.get('grading') or {}).get('good')],
        'held_out_calls':0,'formal_gate_passed':False,'fatal_blocker':results['fatal_blocker']}
    write_new(directory/'ANALYSIS.json',value)
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run','report'])
    p.add_argument('--output',type=Path);m=p.add_mutually_exclusive_group();m.add_argument('--dry-run',action='store_true');m.add_argument('--live',action='store_true')
    p.add_argument('--fixture',choices=['oracle','wrong_branch','idle','malformed'],default='oracle');p.add_argument('--approval',type=Path)
    args=p.parse_args()
    if args.action=='prepare':
        contract=protocol();write_new(HERE/'COVERAGE.json',contract['coverage'])
        write_new(HERE/'protocol.frozen.json',{'protocol_hash':digest(contract),'contract':contract,'live_spending_authorized':False})
        write_new(HERE/'approval.template.json',{'approved':False,'approved_by':None,'approved_at':None,
            'bilingual_semantics_approved':False,'policy_hash':contract['policy_hash'],'protocol_hash':digest(contract),'max_usd':.15})
        print(canonical({'coverage':contract['coverage'],'calls':contract['scheduled_calls'],
            'worst_case_usd':contract['worst_case_reservation_usd'],'hard_cap_usd':.15}));return
    if args.output is None:p.error('--output required')
    if args.action=='report':
        value=report(args.output);print(canonical({k:v for k,v in value.items() if k not in ('failures','family_results')}));return
    if not args.dry_run and not args.live:p.error('explicit --dry-run or --live required')
    approval=read_json(args.approval) if args.approval else None
    if args.live:
        validate_approval(approval or {},protocol())
        from dotenv import dotenv_values
        key=os.environ.get('OPENAI_API_KEY','').strip() or (dotenv_values(E1.parents[2]/'.env').get('OPENAI_API_KEY') or '').strip()
        if not key:raise SystemExit('BLOCKER: configured API credential absent')
        os.environ['OPENAI_API_KEY']=key
        import truststore
        truststore.inject_into_ssl()
    result=run(args.output,dry_run=args.dry_run,mode=args.fixture,approval=approval)
    print(canonical({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
