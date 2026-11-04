"""Seeded family generation, ID/symmetry/translation duplicate rejection, witnesses."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
from .common import ROOT, canonical, digest, read_json
from .e1_oracle import allocations, score, good_set
from .executor import EXECUTOR_VERSION,executor_source_hash,replay

WITNESS_PATH = ROOT/'evidence/executor-v2/witnesses.jsonl'


def hand_fixture():
    return {'shape':[8,8],'obstacles':[],
        'agents':[{'id':'A','position':[1,1],'direction':0.,'level':1.},
                  {'id':'B','position':[6,1],'direction':0.,'level':1.}],
        'tasks':[{'id':i,'position':p,'level':v,'completed':False} for i,p,v in
                 [('b0',[2,4],.6),('b1',[5,4],.8),('b2',[4,6],1.6)]]}


def identity(state):
    """Conservative equivalence: strip IDs, translations, rotations/reflections.

    Directions are fixed East in generated worlds and do not create new families.
    Capacity/weight and entity role remain attached to each transformed point.
    """
    points = [('a',a['level'],*a['position']) for a in state['agents']]+[
              ('t',t['level'],*t['position']) for t in state['tasks']]
    variants=[]
    for swap in (False,True):
        for sx in (-1,1):
            for sy in (-1,1):
                transformed=[(kind,level,sx*(y if swap else x),sy*(x if swap else y)) for kind,level,x,y in points]
                xmin,ymin=min(p[2] for p in transformed),min(p[3] for p in transformed)
                variants.append(sorted((kind,level,x-xmin,y-ymin) for kind,level,x,y in transformed))
    return digest(min(variants))


def generate(seed=20261104):
    rng=random.Random(seed)
    worlds=[]; seen=set()
    for split,count in [('development',12),('test',60)]:
        for index in range(count):
            stratum='light' if index < count//2 else 'mixed'
            while True:
                positions=rng.sample([(x,y) for x in range(1,7) for y in range(1,7)],5)
                capacities=[rng.choice([.8,1.,1.2,1.4]) for _ in range(2)]
                levels=[.4,.6,round(max(capacities)+.2,1) if stratum=='mixed' else round(min(capacities)*.75,1)]
                state={'shape':[8,8],'obstacles':[],
                       'agents':[{'id':aid,'position':list(p),'direction':0.,'level':level}
                                 for aid,p,level in zip(['A','B'],positions[:2],capacities)],
                       'tasks':[{'id':tid,'position':list(p),'level':level,'completed':False}
                                for tid,p,level in zip(['b0','b1','b2'],positions[2:],levels)]}
                ident=identity(state)
                if ident not in seen:
                    seen.add(ident);break
            r,f=good_set(state,'R'),good_set(state,'F')
            if not r or not f or {canonical(a) for a in r}&{canonical(a) for a in f}:
                raise ValueError('SPEC: invalid good sets; do not silently resample oracle defects')
            worlds.append({'family_id':f'{split}-{index:03d}','split':split,'stratum':stratum,
                           'generation_seed':seed,'simulator_seed':seed+len(worlds),
                           'state':state,'state_hash':digest(state),'identity_hash':ident,
                           'good_set_hashes':{'R':digest(r),'F':digest(f)}})
    return worlds


def validate_manifest(worlds, full=True):
    if full:
        assert Counter(w['split'] for w in worlds)=={'development':12,'test':60}
        assert Counter(w['stratum'] for w in worlds if w['split']=='test')=={'light':30,'mixed':30}
    assert len({w['family_id'] for w in worlds})==len(worlds)
    assert len({identity(w['state']) for w in worlds})==len(worlds), 'duplicate/relabeling/symmetry leakage'
    for w in worlds:
        s=w['state'];assert digest(s)==w['state_hash'] and identity(s)==w['identity_hash']
        assert s['shape']==[8,8] and not s['obstacles'] and len(s['agents'])==2 and len(s['tasks'])==3
        assert {a['id'] for a in s['agents']}=={'A','B'} and {t['id'] for t in s['tasks']}=={'b0','b1','b2'}
        positions=[tuple(v['position']) for v in s['agents']+s['tasks']]
        assert len(set(positions))==5 and all(1<=x<=6 and 1<=y<=6 for x,y in positions)
        assert all(not t['completed'] for t in s['tasks'])
        capacities=[a['level'] for a in s['agents']]
        assert sum(t['level']<=min(capacities) for t in s['tasks'])>=2
        assert all(t['level']<=sum(capacities) for t in s['tasks'])
        assert sum(t['level']>max(capacities) for t in s['tasks'])==(w['stratum']=='mixed')
        sets={g:good_set(s,g) for g in ('R','F')}
        assert sets['R'] and sets['F'] and not ({canonical(a) for a in sets['R']}&{canonical(a) for a in sets['F']})
        assert w['good_set_hashes']=={g:digest(a) for g,a in sets.items()}
    return digest(worlds)


def load_manifest(path=ROOT/'e1_manifest.jsonl', full=True):
    worlds=[json.loads(line) for line in Path(path).read_text().splitlines()]
    validate_manifest(worlds,full)
    return worlds


def write_manifest(path, worlds):
    validate_manifest(worlds)
    with Path(path).open('x') as f:
        for w in worlds:f.write(canonical(w)+'\n')


def write_witnesses(worlds,path):
    counts=Counter()
    with Path(path).open('x') as f:
        for world in worlds:
            for targets in allocations(world['state']):
                verdict=score(canonical({'targets':targets}),world['state'],'P0')
                if verdict['good']:
                    result=replay(world['state'],targets,seed=world['simulator_seed'])
                    row={'family_id':world['family_id'],'state_hash':world['state_hash'],
                         'targets':targets,'verdict':verdict,'executor':result}
                    f.write(canonical(row)+'\n');counts[result['status']]+=1
    return dict(counts)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=ROOT/'e1_manifest.jsonl')
    p.add_argument('--witnesses',type=Path,default=WITNESS_PATH)
    args=p.parse_args()
    worlds=generate();write_manifest(args.manifest,worlds)
    print(canonical({'worlds':len(worlds),'manifest_hash':digest(worlds),
                     'executor_witnesses':write_witnesses(worlds,args.witnesses)}))


def witness_acceptance(worlds,path=WITNESS_PATH,*,expected_version=EXECUTOR_VERSION):
    expected={(w['family_id'],canonical(a)) for w in worlds for a in good_set(w['state'],'P0')}
    rows=[json.loads(line) for line in Path(path).read_text().splitlines()]
    actual={(r['family_id'],canonical(r['targets'])) for r in rows}
    if actual!=expected or len(rows)!=len(actual):raise ValueError('incomplete/duplicate executor witness coverage')
    by_id={w['family_id']:w for w in worlds}
    failures=[]
    for row in rows:
        result=row['executor']
        if row['state_hash']!=by_id[row['family_id']]['state_hash'] or digest(result['trace'])!=result['trace_hash']:
            raise ValueError('witness state/trace hash mismatch')
        if expected_version is not None and (result.get('executor_version')!=expected_version or
                result.get('executor_source_hash')!=executor_source_hash()):
            raise ValueError('stale executor witness version/source hash')
        if not result['success']:
            failures.append({'family_id':row['family_id'],'targets':row['targets'],'status':result['status'],'diagnosis':result['diagnosis']})
    return {'covered':len(rows),'successes':len(rows)-len(failures),'failures':failures,'accepted':not failures}


if __name__=='__main__':main()
