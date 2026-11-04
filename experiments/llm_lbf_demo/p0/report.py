"""P0-only four-condition reporting, with usage-derived costs and unknown charges."""
from collections import Counter
from decimal import Decimal
from ..e1.journal import Journal
from .transport import SETTINGS


def usage_cost(response,model):
    usage=response.get('usage') or {}
    if not isinstance(usage,dict):return None
    input_tokens=usage.get('prompt_tokens');output_tokens=usage.get('completion_tokens')
    details=usage.get('prompt_tokens_details') or {}
    if not isinstance(details,dict):return None
    cached=details.get('cached_tokens',0)
    if any(type(n) is not int or n<0 for n in (input_tokens,output_tokens,cached)) or cached>input_tokens:
        return None
    return float(((Decimal(input_tokens-cached)*Decimal(str(model['input_usd_per_million'])))+
                  Decimal(cached)*Decimal(str(model['cached_input_usd_per_million']))+
                  Decimal(output_tokens)*Decimal(str(model['output_usd_per_million'])))/Decimal(1000000))


def report(path,proposal,kind='gate'):
    events=Journal.read(path);config=events[0]['config']
    if (config.get('config') or {}).get('workflow_phase')!=kind:
        raise ValueError('smoke and formal P0 reports must remain separate')
    starts=[e for e in events if e['event']=='started']
    terminals={e['slot_id']:e for e in events if e['event']=='terminal'}
    responses={};errors={}
    for e in events:
        if e['event']=='response':responses[e['slot_id'],e['attempt']]=e['response']
        if e['event']=='infra':errors[e['slot_id'],e['attempt']]=e
    rows=[]
    for model in proposal['models']:
        for language in ('EN','VI'):
            selected=[e for e in starts if e['slot']['model_role']==model['role'] and e['slot']['language']==language]
            ids={e['slot_id'] for e in selected};done=[terminals[s] for s in ids if s in terminals]
            expected=36 if kind=='gate' else 1
            def rate(field):return sum(bool(r['verdict'].get(field)) for r in done)/expected
            known=[];unknown=0;infrastructure=0;compatible=True
            for attempt in selected:
                key=attempt['slot_id'],attempt['attempt'];response=responses.get(key)
                if key in errors:infrastructure+=1
                cost=usage_cost(response,model) if response else None
                if cost is None:unknown+=1
                else:known.append(cost)
                if response:
                    envelope=response.get('raw_provider_response',{})
                    tier=envelope.get('service_tier')
                    effective=response.get('effective_request',{})
                    compatible &= (response.get('model')==model['id'] and tier in ('default',None)
                                   and effective.get('model')==model['id'] and
                                   effective.get('messages')==attempt['request']['messages'] and
                                   all(effective.get(k)==v for k,v in SETTINGS.items()))
                    usage=response.get('usage') or {}
                    if cost is not None:
                        compatible &= (usage['prompt_tokens']<=model['max_input_tokens'] and
                                       usage['completion_tokens']<=model['max_output_tokens'])
            observed=sum(known) if known else None
            passed=(len(done)==expected and all(r['verdict'].get('comparison_valid') for r in done)
                    and rate('format_valid')>=.98 and rate('physical_valid')>=.95 and rate('good')>=.8)
            rows.append({'model_role':model['role'],'model_snapshot':model['id'],'language':language,
                'scheduled_calls':expected,'completed_calls':len(done),'provider_attempts':len(selected),
                'parseability':rate('format_valid') if done else None,
                'capacity_validity':rate('capacity_feasible') if done else None,
                'geometric_validity':rate('geometric_feasible') if done else None,
                'physical_validity':rate('physical_valid') if done else None,
                'progressive_goodness':rate('good') if done else None,
                'infrastructure_failed_attempts':infrastructure,
                'exhausted_infrastructure_slots':sum(r['verdict']['status']=='INFRA' for r in done),
                'observed_usage_cost_usd':observed,'attempts_with_unknown_cost':unknown,
                'reserved_upper_bound_usd':sum(e['reserved_usd'] for e in selected),
                'cost_is_invoiced':False,'compatibility_observed':bool(selected) and compatible,
                'statuses':dict(Counter(r['verdict']['status'] for r in done)),
                'passed':passed if kind=='gate' else None})
    real=config.get('infrastructure_validation') is False
    complete=len(terminals)==(144 if kind=='gate' else 4) and all(
        r['verdict'].get('comparison_valid') for r in terminals.values())
    return {'kind':'formal_P0_gate' if kind=='gate' else 'development_provider_compatibility_smoke_ONLY',
        'infrastructure_validation':not real,'formal_gate_eligible':kind=='gate' and real,
        'complete':complete,'held_out_E1_authorized':kind=='gate' and real and complete and
            all(r['passed'] and r['compatibility_observed'] for r in rows),
        'thresholds':{'parseability':.98,'physical_validity':.95,'progressive_goodness':.80},
        'conditions':rows,'total_observed_usage_cost_usd':sum(r['observed_usage_cost_usd'] or 0 for r in rows)
            if any(r['observed_usage_cost_usd'] is not None for r in rows) else None,
        'cost_note':'Observed token usage at frozen prices; not an invoice. Unknown failed-call charges are not zero.',
        'executor_version':config.get('executor_version'),'config_hash':events[0]['config_hash'],
        'gate_binding':config['gate_binding'],'manifest_hash':config['manifest_hash']}


def pending_report(proposal):
    return {'kind':'formal_P0_gate','status':'NOT_RUN','paid_calls_made':0,'held_out_E1_authorized':False,
        'conditions':[{'model_role':m['role'],'model_snapshot':m['id'],'language':lang,
            'scheduled_calls':36,'completed_calls':0,'parseability':None,'capacity_validity':None,
            'geometric_validity':None,'physical_validity':None,'progressive_goodness':None,
            'infrastructure_failed_attempts':None,'exhausted_infrastructure_slots':None,
            'observed_usage_cost_usd':None,'passed':None}
            for m in proposal['models'] for lang in ('EN','VI')]}
