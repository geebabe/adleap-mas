"""Read-only verification of the full checked-in offline artifacts (zero network)."""
from collections import Counter,defaultdict
import hashlib
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from experiments.llm_lbf_demo.e1.common import ROOT,canonical,digest,read_json
from experiments.llm_lbf_demo.e1.controller import assert_policy_only_difference
from experiments.llm_lbf_demo.e1.e1_oracle import score
from experiments.llm_lbf_demo.e1.journal import Journal
from experiments.llm_lbf_demo.e1.providers import FakeProvider
from experiments.llm_lbf_demo.e1.run_e1 import run,slots_for,code_hashes
from experiments.llm_lbf_demo.e1.worlds import load_manifest,generate,witness_acceptance


def verify():
    worlds=load_manifest();assert worlds==generate()
    policies=read_json(ROOT/'e1_policies.json');slots=slots_for(worlds)
    assert Counter(s['stage'] for s in slots)=={'gate':144,'e1':2880}
    report={'families':len(worlds),'manifest_hash':digest(worlds),'slot_counts':dict(Counter(s['stage'] for s in slots)),
            'witnesses':witness_acceptance(worlds),'fixtures':{},'api_calls':0}
    by_id={w['family_id']:w for w in worlds}
    for mode,want in [('oracle',1.),('blind',0.),('idle',0.),('malformed',0.)]:
        folder=ROOT/'evidence'/f'dry-{mode}'
        events=Journal.read(folder/'attempts.jsonl');config=events[0]['config']
        # Historical runs remain valid evidence for their recorded executor,
        # but must not be resumed under newer executor code.
        current=code_hashes();historical=config['code_hashes']!=current
        for name,sha in config['code_hashes'].items():
            source=ROOT.parent/name
            if hashlib.sha256(source.read_bytes()).hexdigest()!=sha:
                source=ROOT/'evidence/executor-v2'/('before-'+Path(name).name)
            assert hashlib.sha256(source.read_bytes()).hexdigest()==sha,name
        assert config['manifest_hash']==digest(worlds) and config['policy_hash']==digest(policies)
        assert config['slot_hash']==digest(slots)
        terminals={e['slot_id']:e for e in events if e['event']=='terminal'}
        starts={e['slot_id']:e for e in events if e['event']=='started'}
        responses={e['slot_id']:e for e in events if e['event']=='response'}
        assert len(terminals)==len(starts)==len(responses)==3024
        assert len(events)==1+3*3024
        pairs=defaultdict(dict);mismatches=0
        for sid,row in terminals.items():
            s=row['slot'];start=starts[sid]
            assert start['state']==by_id[s['family_id']]['state']
            assert responses[sid]['response']['api_calls']==0
            assert start['prompt_hash']==digest(start['request'])
            assert score(responses[sid]['response']['raw'],start['state'],s['gold'])==row['verdict']
            if s['stage']=='e1':
                key=(s['family_id'],s['model_role'],s['language'],s['paraphrase'],s['repeat'])
                pairs[key][s['gold']]=(start,responses[sid],row)
                if mode=='oracle':
                    wrong=score(responses[sid]['response']['raw'],start['state'],'F' if s['gold']=='R' else 'R')
                    assert wrong['status']=='POLICY';mismatches+=1
        assert len(pairs)==1440
        for arms in pairs.values():
            assert set(arms)=={'R','F'}
            assert_policy_only_difference(arms['R'][0]['request'],arms['F'][0]['request'])
            assert int(arms['R'][2]['verdict']['good'] and arms['F'][2]['verdict']['good'])==want
            if mode=='blind':assert arms['R'][1]['response']['raw']==arms['F'][1]['response']['raw']
        analysis=read_json(folder/'analysis.json')
        assert analysis['complete'] and analysis['infrastructure_validation'] and not analysis['model_findings']
        for role in ('primary','replication'):
            model=analysis['models'][role]
            assert model['pairpass']==want and model['pairs']==720 and model['families']==60
            assert model['pairs_per_language']=={'EN':360,'VI':360}
            assert model['marginals']['slots']==1440
            for lang in ('EN','VI'):
                metric=model['primary_EN_and_secondary_VI'][lang]
                assert metric['estimate']==want and metric['degenerate']
            if mode=='oracle':
                exact=model['all_variants_family_event']
                assert exact['families']==60 and .94<exact['ci95'][0]<.95
        before=hashlib.sha256((folder/'attempts.jsonl').read_bytes()).hexdigest()
        with patch.object(FakeProvider,'complete',side_effect=AssertionError('completed request repeated')):
            if historical:
                try:run(folder,worlds,policies,mode=mode)
                except ValueError as exc:assert 'incompatible' in str(exc)
                else:raise AssertionError('historical run resumed with changed executor')
            else:
                resumed=run(folder,worlds,policies,mode=mode)
                assert resumed['api_calls']==0
        assert before==hashlib.sha256((folder/'attempts.jsonl').read_bytes()).hexdigest()
        report['fixtures'][mode]={'slots':3024,'pairs':1440,'pairpass':want,'label_mismatch_rejections':mismatches,
                                 'resume_unchanged':True,'historical_resume_rejected':historical,
                                 'recommendation_labels_unchanged':True,'statuses':analysis['overall']['statuses']}
    # Recovery implementation and original artifacts remain byte-identical.
    old=read_json(ROOT.parent/'evidence/final/summary.json')[0]
    for name,sha in old['provenance']['files'].items():
        assert hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest()==sha,name
    return report


if __name__=='__main__':print(canonical(verify()))
