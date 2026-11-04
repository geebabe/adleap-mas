"""Prepare, authorize, smoke-check and freeze P0; never launches without --live."""
import argparse
import copy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from ...e1.common import ROOT as E1,canonical,digest,read_json
from ..interface_v2.controller import payload
from ...e1.executor import EXECUTOR_VERSION,executor_source_hash
from .runner import run,slots_for,code_hashes
from ...e1.safeguards import validate_live,preflight_cost
from ...e1.worlds import load_manifest,witness_acceptance
from ..transport import P0Provider,SETTINGS
from ..report import report,pending_report

ROOT=Path(__file__).resolve().parent
DEFAULT_PROPOSAL=ROOT/'live.proposed.json'


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bundle(proposal):
    from ..prepare import bundle as original_bundle
    from ..interface_v2.controller import SYSTEM,VERSION
    from ..interface_v2.experiment import protocol as diagnostic_protocol
    prior=read_json(ROOT.parent/'live.proposed.json')
    original=read_json(ROOT.parent/'live.final.freeze.json')
    if original_bundle(prior)!=original['binding']:raise ValueError('original v1 freeze changed')
    diagnostic=read_json(ROOT.parent/'interface_v2/protocol.frozen.json')
    if digest(diagnostic_protocol())!=diagnostic['protocol_hash']:raise ValueError('diagnostic adapter/source changed')
    if (proposal['models']!=prior['models'] or proposal['thresholds']!=prior['thresholds']
        or proposal['request_settings']!=prior['request_settings']
        or proposal.get('formal_attempt_number')!=2 or proposal.get('further_prompt_tuning_allowed') is not False):
        raise ValueError('final attempt must preserve models, thresholds, settings and the tested clarification')
    binding=original_bundle(proposal)
    binding.update(e1_code_hashes=code_hashes(),corrected_system_sha256=digest(SYSTEM),
        corrected_adapter_version=VERSION,diagnostic_protocol_hash=diagnostic['protocol_hash'],
        original_v1_binding_hash=original['binding_hash'],formal_attempt_number=2,
        first_gate_journal_sha256=file_sha(ROOT.parent/'runs/gate-001/attempts.jsonl'))
    return binding


def runtime_models(proposal,binding):
    models=copy.deepcopy(proposal['models'])
    for model in models:model['p0_transport_contract_hash']=digest(binding)
    return models


def smoke_slots(worlds):
    family=next(w['family_id'] for w in worlds if w['split']=='development')
    chosen=[copy.deepcopy(s) for s in slots_for(worlds,'gate') if s['family_id']==family and s['repeat']==0]
    for s in chosen:
        s.pop('slot_id');s['stage']='smoke';s['slot_id']=digest(s)
    assert len(chosen)==4 and all(s['gold']==s['presented']=='P0' for s in chosen)
    return chosen


def budget(proposal,phase):
    worlds=load_manifest();policies=read_json(E1/'e1_policies.json')
    slots=smoke_slots(worlds) if phase=='smoke' else slots_for(worlds,'gate')
    by_id={w['family_id']:w for w in worlds}
    requests={s['slot_id']:payload(by_id[s['family_id']]['state'],policies['languages'][s['language']]['P0'][0]) for s in slots}
    ceiling=proposal['budgets_usd'][phase]
    worst=preflight_cost(slots,proposal['models'],requests,ceiling)
    return {'phase':phase,'scheduled_calls':len(slots),'maximum_provider_attempts':len(slots)*3,
            'worst_case_usd':round(worst,10),'dollar_ceiling':ceiling,
            'maximum_conservative_prompt_bound':max(len(str(r).encode())+512 for r in requests.values())}


def authorize(proposal,spending,phase):
    if spending.get('approved') is not True or not spending.get('approved_by') or not spending.get('approved_at'):
        raise PermissionError('live spending not authorized; no provider requests are permitted')
    if spending.get('proposal_hash')!=digest(proposal) or phase not in spending.get('phases',[]):
        raise PermissionError('spending authorization must match this proposal and phase')
    amount=spending.get('max_usd',{}).get(phase)
    if type(amount) not in (int,float) or amount<budget(proposal,phase)['worst_case_usd']:
        raise PermissionError('phase authorization does not cover reserved retry-inclusive budget')
    return min(amount,proposal['budgets_usd'][phase])


def write_new(path,value):
    with Path(path).open('x') as handle:handle.write(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def validate_smoke(path,proposal,binding):
    from ...e1.journal import Journal
    events=Journal.read(path);cfg=events[0]['config']
    active=cfg.get('config') or {}
    if active.get('workflow_phase')!='smoke' or active.get('p0_binding_hash')!=digest(binding):
        raise ValueError('smoke journal is not from this frozen development-only contract')
    result=report(path,proposal,'smoke')
    if (result['infrastructure_validation'] or not result['complete'] or
        not all(r['compatibility_observed'] and r['attempts_with_unknown_cost']==0 for r in result['conditions'])):
        raise PermissionError('real provider compatibility remains unverified; formal gate blocked')
    return result


def execute(phase,proposal,output,spending,approval,*,live=False,freeze_path=None):
    if phase not in ('smoke','gate'):raise ValueError('only development smoke or P0 gate permitted')
    expected=ROOT/'runs'/('smoke-002' if phase=='smoke' else 'gate-002')
    if Path(output).resolve()!=expected.resolve():raise PermissionError('this authorization permits only the fixed second-attempt run directory')
    if not live:raise PermissionError('explicit --live flag required; preparation is not approval')
    binding=bundle(proposal);ceiling=authorize(proposal,spending,phase)
    models=runtime_models(proposal,binding)
    active={**proposal,'models':models,'explicit_live_approval':True,'dollar_ceiling':ceiling,
            'workflow_phase':phase,'p0_binding_hash':digest(binding)}
    # Validate human review before constructing any provider transport.
    validate_live(active,approval,binding['policy_hash'],'gate')
    if phase=='gate':
        if not freeze_path:raise PermissionError('final configuration must be frozen after real smoke checks')
        final=read_json(freeze_path)
        if final['binding']!=binding or final['binding_hash']!=digest(binding):raise ValueError('final configuration changed')
        smoke_path=Path(final['smoke_journal'])
        if file_sha(smoke_path)!=final['smoke_journal_sha256']:raise ValueError('compatibility evidence changed')
        validate_smoke(smoke_path,proposal,binding)
        active['final_freeze_hash']=digest(final)
    worlds=load_manifest()
    slots=smoke_slots(worlds) if phase=='smoke' else slots_for(worlds,'gate')
    assert all(next(w for w in worlds if w['family_id']==s['family_id'])['split']=='development' for s in slots)
    result=run(output,worlds,read_json(E1/'e1_policies.json'),dry_run=False,stage='gate',
               slots=slots,config=active,approval=approval,provider=P0Provider())
    return result


def freeze(proposal,smoke_journal,approval,output):
    binding=bundle(proposal)
    # Offline finalization does not grant spending approval.
    dummy={**proposal,'models':runtime_models(proposal,binding),'explicit_live_approval':True,'dollar_ceiling':proposal['budgets_usd']['gate']}
    validate_live(dummy,approval,binding['policy_hash'],'gate')
    result=validate_smoke(smoke_journal,proposal,binding)
    write_new(output,{'status':'FINAL_P0_CONFIGURATION_FROZEN','binding':binding,'binding_hash':digest(binding),
        'proposal':proposal,'smoke_journal':str(Path(smoke_journal).resolve()),
        'smoke_journal_sha256':file_sha(smoke_journal),'compatibility_report':result,
        'frozen_at':datetime.now(timezone.utc).isoformat(),'spending_authorized_by_freeze':False})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['inspect','smoke','freeze','gate','report'])
    p.add_argument('--proposal',type=Path,default=DEFAULT_PROPOSAL)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--live',action='store_true');p.add_argument('--spending-approval',type=Path)
    p.add_argument('--human-approval',type=Path);p.add_argument('--smoke-journal',type=Path)
    p.add_argument('--final-config',type=Path);p.add_argument('--journal',type=Path)
    p.add_argument('--report-kind',choices=['smoke','gate'],default='gate')
    args=p.parse_args();proposal=read_json(args.proposal)
    if args.action=='inspect':
        write_new(args.output,{'status':'PROPOSED_NOT_AUTHORIZED','binding':bundle(proposal),
            'budgets':[budget(proposal,phase) for phase in ('smoke','gate')],
            'pending_gate_report':pending_report(proposal),'provider_calls_made':0})
    elif args.action=='report':
        if not args.journal:p.error('--journal is required')
        write_new(args.output,report(args.journal,proposal,args.report_kind))
    elif args.action=='freeze':
        if not args.smoke_journal or not args.human_approval:p.error('real --smoke-journal and --human-approval required')
        freeze(proposal,args.smoke_journal,read_json(args.human_approval),args.output)
    else:
        if not args.live or not args.spending_approval or not args.human_approval:
            p.error('--live, spending approval and human approval are required; no calls made')
        print(canonical(execute(args.action,proposal,args.output,read_json(args.spending_approval),
            read_json(args.human_approval),live=args.live,freeze_path=args.final_config)))


if __name__=='__main__':main()
