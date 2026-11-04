"""Fail-closed preflight and worst-case attempt reservation. No network calls."""
import math
from .common import digest


def estimate_attempt(request,model):
    # Conservative UTF-8 byte bound plus envelope overhead, not measured tokens.
    tokens=len(str(request).encode())+512
    if tokens>model['max_input_tokens']:
        raise ValueError('configured input token ceiling below conservative bound')
    return (model['max_input_tokens']*model['input_usd_per_million']+
            model['max_output_tokens']*model['output_usd_per_million'])/1e6


def validate_live(config,approval,policy_hash,stage,gate=None,manifest_hash=None,gate_binding=None):
    if config.get('explicit_live_approval') is not True:
        raise PermissionError('explicit live approval required')
    if (approval.get('approved') is not True or not approval.get('reviewer') or not approval.get('reviewed_at')
        or approval.get('policy_hash')!=policy_hash):
        raise PermissionError('human bilingual semantic approval must match frozen policies')
    ceiling=config.get('dollar_ceiling')
    if type(ceiling) not in (float,int) or not math.isfinite(ceiling) or ceiling<=0:
        raise ValueError('finite positive dollar ceiling required')
    models=config.get('models',[])
    if len(models)!=2 or {m.get('role') for m in models}!={'primary','replication'} or len({m.get('id') for m in models})!=2:
        raise ValueError('two distinct preregistered model IDs required')
    for model in models:
        if not isinstance(model.get('id'),str) or not model['id'] or model['id'].startswith('fixture-') or model.get('snapshot_frozen') is not True:
            raise ValueError('explicit frozen real model IDs required')
        for key in ('input_usd_per_million','output_usd_per_million'):
            if type(model.get(key)) not in (float,int) or not math.isfinite(model[key]) or model[key]<0:
                raise ValueError('finite nonnegative prices required')
        for key in ('max_input_tokens','max_output_tokens'):
            if type(model.get(key)) is not int or model[key]<=0:raise ValueError('positive token ceilings required')
        if model.get('temperature')!=0:raise ValueError('freeze temperature 0 for E1')
    if stage!='gate':
        if not gate or gate.get('infrastructure_validation') is not False or not gate.get('complete'):
            raise PermissionError('completed real P0 gate required; fake gate never qualifies')
        if gate.get('manifest_hash')!=manifest_hash or gate.get('gate_binding')!=gate_binding:
            raise PermissionError('incompatible gate manifest/prompt/model/policy binding')
        if not all(g['passed'] for g in gate.get('gate',[])) or len(gate.get('gate',[]))!=4:
            raise PermissionError('failed/missing model-language P0 gate blocks confirmatory launch')
    return True


def preflight_cost(slots,models,requests,ceiling):
    by_role={m['role']:m for m in models}
    # Reserve two infrastructure retries for every slot, including requests whose
    # billable usage is unknown. This upper bound is never a claim of actual cost.
    total=sum(3*estimate_attempt(requests[s['slot_id']],by_role[s['model_role']]) for s in slots)
    if total>ceiling+1e-12:raise PermissionError(f'worst-case reserved estimate {total:.6f} exceeds ceiling {ceiling:.6f}')
    return total
