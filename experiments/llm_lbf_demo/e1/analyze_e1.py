"""Strict paired analysis; family-cluster uncertainty, never sample inflation."""
import argparse
from collections import Counter,defaultdict
import json
import math
from pathlib import Path
import numpy as np
from .common import canonical
from .journal import Journal


def cluster_intervals(values,seed=4103,resamples=10000):
    """Columns are matched EN/VI family means; bootstrap rows jointly."""
    values=np.asarray(values,dtype=float)
    if len(values)==0:return None
    samples=np.random.default_rng(seed).integers(0,len(values),(resamples,len(values)))
    draws=values[samples].mean(axis=1)
    metrics={'EN':draws[:,0],'VI':draws[:,1],'VI_minus_EN':draws[:,1]-draws[:,0]}
    observed={'EN':values[:,0].mean(),'VI':values[:,1].mean(),
              'VI_minus_EN':(values[:,1]-values[:,0]).mean()}
    return {key:{'estimate':float(observed[key]),'ci95':[float(x) for x in np.quantile(v,[.025,.975])],
                 'degenerate':bool(np.ptp(v)==0),'boundary':bool(observed[key] in (0.,1.) if key!='VI_minus_EN' else False)}
            for key,v in metrics.items()}


def _rate(rows,predicate):return sum(bool(predicate(r)) for r in rows)/len(rows) if rows else None


def marginals(rows):
    physical=[r for r in rows if r['verdict'].get('physical_valid')]
    replayed=[r['executor'] for r in rows if r.get('executor')]
    return {'slots':len(rows),'statuses':dict(Counter(r['verdict']['status'] for r in rows)),
        'strict_goodness':_rate(rows,lambda r:r['verdict']['good']),
        'parse_rate':_rate(rows,lambda r:r['verdict'].get('format_valid')),
        'capacity_rate':_rate(rows,lambda r:r['verdict'].get('capacity_feasible')),
        'geometry_rate':_rate(rows,lambda r:r['verdict'].get('geometric_feasible')),
        'physical_rate':_rate(rows,lambda r:r['verdict'].get('physical_valid')),
        'false_idle_rate':_rate(rows,lambda r:r['verdict']['status']=='VACUOUS'),
        'joint_assignment_rate':_rate(rows,lambda r:r['verdict'].get('joint_assignment')),
        'policy_violation_unconditional':_rate(rows,lambda r:r['verdict']['status']=='POLICY'),
        'policy_violation_given_physical':_rate(physical,lambda r:not r['verdict'].get('policy_compliant')),
        'replay':{'replayed':len(replayed),'successful_pickups':sum(r['success'] for r in replayed),
                  'executor_failures':sum(r['status']=='EXECUTOR' for r in replayed),
                  'spec_defects':sum(r['status']=='SPEC' for r in replayed),
                  'forbidden_joint_load_attempts':sum(r['forbidden_joint_load_attempts'] for r in replayed),
                  'forbidden_successful_pickups':sum(r['forbidden_successful_pickups'] for r in replayed),
                  'substitutions':sum(len(r['substitutions']) for r in replayed),
                  'mean_ticks':sum(r['ticks'] for r in replayed)/len(replayed) if replayed else None}}


def analyze(path,resamples=10000):
    events=Journal.read(path)
    config=events[0]['config']
    rows=[e for e in events if e['event']=='terminal']
    if len({r['slot_id'] for r in rows})!=len(rows):raise ValueError('duplicate completed slots')
    complete=len(rows)==config['slot_count'] and all(r['verdict']['comparison_valid'] and
                (not r['executor'] or r['executor']['status']!='SPEC') for r in rows)
    output={'infrastructure_validation':config['infrastructure_validation'],'complete':complete,
            'manifest_hash':config['manifest_hash'],'gate_binding':config['gate_binding'],
            'config_hash':events[0]['config_hash'],'expected_slots':config['slot_count'],
            'completed_slots':len(rows),'api_attempts':0 if config['infrastructure_validation'] else
                sum(e['event']=='started' for e in events),
            'model_findings':False if config['infrastructure_validation'] else complete,
            'overall':marginals(rows),'gate':[],'models':{},'family_unit':'generated world, not repeat/paraphrase',
            'uncertainty':{'method':'paired family-cluster percentile bootstrap','resamples':resamples,'seed':4103}}
    for role in ('primary','replication'):
        for language in ('EN','VI'):
            gate=[r for r in rows if r['slot']['stage']=='gate' and r['slot']['model_role']==role and r['slot']['language']==language]
            rates=marginals(gate)
            passed=(len(gate)==36 and all(r['verdict']['comparison_valid'] for r in gate) and
                rates['parse_rate']>=.98 and rates['physical_rate']>=.95 and rates['strict_goodness']>=.80)
            output['gate'].append({'model_role':role,'language':language,'passed':passed,
                                   'eligible_live_evidence':not config['infrastructure_validation'],**rates})
        test=[r for r in rows if r['slot']['stage']=='e1' and r['slot']['model_role']==role]
        paired=defaultdict(dict)
        for row in test:
            s=row['slot'];key=(s['family_id'],s['language'],s['paraphrase'],s['repeat'])
            if s['gold'] in paired[key]:raise ValueError('duplicate arm')
            paired[key][s['gold']]=row
        pairs=[]
        for key,arms in paired.items():
            valid=set(arms)=={'R','F'} and all(r['verdict']['comparison_valid'] and
                     (not r['executor'] or r['executor']['status']!='SPEC') for r in arms.values())
            pairs.append({'family_id':key[0],'language':key[1],'paraphrase':key[2],'repeat':key[3],
                          'pairpass':int(all(r['verdict']['good'] for r in arms.values())) if valid else None,
                          'stratum':next(iter(arms.values()))['stratum']})
        families=sorted({r['family_id'] for r in pairs})
        values=[];family_rows=[]
        for family in families:
            match=[r for r in pairs if r['family_id']==family]
            means=[]
            for lang in ('EN','VI'):
                scores=[r['pairpass'] for r in match if r['language']==lang]
                means.append(sum(scores)/6 if len(scores)==6 and None not in scores else None)
            family_rows.append({'family_id':family,'EN':means[0],'VI':means[1],'stratum':match[0]['stratum']})
            if None not in means:values.append(means)
        interpretable=complete and len(values)==60 and len(pairs)==720
        intervals=cluster_intervals(values,resamples=resamples) if interpretable else None
        all_variants=sum(r['EN']==1 and r['VI']==1 for r in family_rows)
        exact=None
        if interpretable and all_variants==60:
            exact={'estimand':'family passes every EN/VI paraphrase/repeat pair','successes':60,'families':60,
                   'method':'two-sided exact binomial, all successes','ci95':[.025**(1/60),1.]}
        model={'pairs':len(pairs),'pairs_per_language':dict(Counter(r['language'] for r in pairs)),
               'families':len(families),'pairpass':sum(r['pairpass'] for r in pairs)/len(pairs)
                    if pairs and all(r['pairpass'] is not None for r in pairs) else None,
               'primary_EN_and_secondary_VI':intervals,'all_variants_family_event':exact,
               'family_means':family_rows,'marginals':marginals(test),
               'by_policy':{g:marginals([r for r in test if r['slot']['gold']==g]) for g in ('R','F')},
               'strata':{stratum:cluster_intervals([[r['EN'],r['VI']] for r in family_rows
                    if r['stratum']==stratum and r['EN'] is not None and r['VI'] is not None],resamples=resamples)
                    if interpretable else None for stratum in ('light','mixed')}}
        if intervals:
            lower,upper=intervals['EN']['ci95']
            model['H1_target_assessment']='supports target within testbed' if lower>=.8 else 'contradicts target' if upper<.8 else 'inconclusive'
            lo,hi=intervals['VI_minus_EN']['ci95']
            model['language_margin_assessment']=('within practical margins' if lo>=-.1 and hi<=.1 else
                'VI disadvantage beyond margin' if hi<-.1 else 'VI advantage beyond margin' if lo>.1 else 'inconclusive')
            if config['infrastructure_validation']:
                model['H1_target_assessment']='NOT A MODEL FINDING: '+model['H1_target_assessment']
                model['language_margin_assessment']='NOT A MODEL FINDING: '+model['language_margin_assessment']
        output['models'][role]=model
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('journal',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=analyze(args.journal)
    with args.output.open('x') as f:f.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(canonical({'complete':result['complete'],'infrastructure_validation':result['infrastructure_validation'],
                     'pairpass':{k:v['pairpass'] for k,v in result['models'].items()}}))


if __name__=='__main__':main()
