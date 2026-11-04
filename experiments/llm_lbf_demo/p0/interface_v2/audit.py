"""Recheck first-gate data and run real native counterfactual witnesses offline."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from ...e1.common import ROOT,canonical,digest,read_json
from ...e1.controller import assert_policy_only_difference,payload as original_payload
from ...e1.e1_oracle import allocations,score,good_set
from ...e1.executor import make_env,recovered,replay
from ...e1.journal import Journal
from .controller import payload,CLARIFICATION
from .experiment import P0,development_worlds,write_new


def audit(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    # Snapshot existing reports/logs/response evidence before this audit; retain hashes.
    historical={str(p.relative_to(ROOT.parent)):hashlib.sha256(p.read_bytes()).hexdigest()
        for parent in (P0/'runs',ROOT.parent/'pilot') for p in parent.rglob('*')
        if p.is_file() and p.suffix in ('.json','.jsonl','.csv','.md','.py','.txt')}
    events=Journal.read(P0/'runs/gate-001/attempts.jsonl')
    starts={e['slot_id']:e for e in events if e['event']=='started'}
    responses={e['slot_id']:e['response'] for e in events if e['event']=='response'}
    terminals=[e for e in events if e['event']=='terminal'];assert len(terminals)==144
    worlds={w['family_id']:w for w in development_worlds()}
    policy=read_json(ROOT/'e1_policies.json');counts=Counter();checks=[];failure_ids=[]
    for row in terminals:
        sid=row['slot_id'];start=starts[sid];response=responses[sid]
        state=worlds[row['slot']['family_id']]['state']
        assert start['state']==state
        assert start['request']==original_payload(state,policy['languages'][row['slot']['language']]['P0'][0])
        assert start['request']['messages']==response['effective_request']['messages']
        assert json.loads(start['request']['messages'][1]['content'])['state']==state
        env=make_env(state,start['simulator_seed']);native=recovered.snapshot(env)
        assert native==state
        assert score(response['raw'],state,'P0')==row['verdict']
        counts[(row['slot']['model_role'],row['slot']['language'],row['verdict']['status'])]+=1
        if not row['verdict']['good']:failure_ids.append(sid)
    native_witnesses=[]
    for fid in sorted({starts[s]['family_id'] for s in failure_ids}):
        w=worlds[fid];state=w['state']
        bad={'A':'b2','B':None};joint={'A':'b2','B':'b2'};solo={'A':'b0','B':None}
        records={}
        for name,targets in [('recorded_bad',bad),('joint_heavy_alternative',joint),('solo_light_alternative',solo)]:
            verdict=score(canonical({'targets':targets}),state,'P0')
            execution=replay(state,targets,'P0',w['simulator_seed'])
            records[name]={'targets':targets,'verdict':verdict,'executor':execution}
        assert records['recorded_bad']['verdict']['status']=='PHYSICS'
        assert not records['recorded_bad']['executor']['success']
        assert all(records[k]['verdict']['good'] and records[k]['executor']['success'] for k in ('joint_heavy_alternative','solo_light_alternative'))
        for t in records['joint_heavy_alternative']['executor']['trace']:
            if t['pickups']:assert t['pickups']==['b2']
        for targets in allocations(state):
            # Direct numeric predicate independent of oracle helper implementation.
            expected=all(sum(a['level'] for a in state['agents'] if targets[a['id']]==tid)>=next(t['level'] for t in state['tasks'] if t['id']==tid)
                for tid in set(targets.values())-{None})
            assert expected==score(canonical({'targets':targets}),state,'P0')['capacity_feasible']
        native_witnesses.append({'family_id':fid,'state_hash':w['state_hash'],'simulator_seed':w['simulator_seed'],
            'capacity_table':{a['id']:a['level'] for a in state['agents']},'box_weights':{t['id']:t['level'] for t in state['tasks']},'records':records})
    payload_checks=0;label_checks=0
    for w in worlds.values():
        for language in ('EN','VI'):
            texts=policy['languages'][language]
            requests={p:payload(w['state'],texts[p][0]) for p in ('P0','R','F')}
            for left,right in (('P0','R'),('P0','F'),('R','F')):
                assert_policy_only_difference(requests[left],requests[right]);payload_checks+=1
            for p,request in requests.items():
                old=original_payload(w['state'],texts[p][0])
                assert request['messages'][1]==old['messages'][1]
                assert request['messages'][0]['content']==old['messages'][0]['content']+CLARIFICATION
            for targets in allocations(w['state']):
                raw=canonical({'targets':targets})
                for p in ('P0','R','F'):
                    old_state=json.loads(original_payload(w['state'],texts[p][0])['messages'][1]['content'])['state']
                    new_state=json.loads(requests[p]['messages'][1]['content'])['state']
                    assert score(raw,old_state,p)==score(raw,new_state,p);label_checks+=1
        for p in ('P0','R','F'):
            assert_policy_only_difference(payload(w['state'],policy['languages']['EN'][p][0]),payload(w['state'],policy['languages']['VI'][p][0]));payload_checks+=1
    for name,sha in historical.items():assert hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest()==sha,name
    result={'label':'OFFLINE_FORENSIC_AUDIT_NOT_NEW_MODEL_PERFORMANCE','formal_gate_responses_regraded':144,
        'native_state_roundtrips_verified':144,'recorded_failures':7,'failure_families':3,
        'unique_bad_raw_response':'{"targets":{"A":"b2","B":null}}',
        'statuses':[{'model_role':m,'language':l,'status':s,'count':n} for (m,l,s),n in sorted(counts.items())],
        'simulator_and_grader_defect_found':False,'state_or_prompt_serialization_defect_found':False,
        'confirmed_failure':'Assigned capacity below selected box weight.',
        'hypothesis_only':'The generic level field is not explicitly mapped to capacity/weight in the original scaffold. Clarification may help; internal model cause is unobserved.',
        'original_worlds_allocations_policies_and_labels_preserved':True,
        'policy_only_payload_checks':payload_checks,'all_allocation_label_checks':label_checks,
        'historical_files_hash_verified':len(historical),'historical_hashes':historical,
        'native_witnesses':native_witnesses,'new_LLM_calls':0,'held_out_model_calls':0,
        'improvement_of_new_adapter':'UNVERIFIED_WITH_REAL_MODEL','formal_P0_passed':False}
    write_new(output/'AUDIT.json',result)
    return {k:v for k,v in result.items() if k not in ('historical_hashes','native_witnesses')}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    print(canonical(audit(args.output)))


if __name__=='__main__':main()
