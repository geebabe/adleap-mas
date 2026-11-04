"""Formal conditional predicate, independent of text/provider/controller/executor.

Reuse the existing strict parser and independent physical checks through P0 score.
Branch selection uses only unfinished boxes and actual capacities, never rollout.
"""
from collections import Counter
import math
from ..e1.common import canonical
from ..e1.e1_oracle import score as physical_score,allocations

GRADER_VERSION='conditional-grader-1'


def classify(state):
    agents=state['agents']
    if len(agents)!=2 or len({a['id'] for a in agents})!=2:
        raise ValueError('conditional policy requires exactly two distinct robots')
    levels=[a['level'] for a in agents]
    tasks=[t for t in state['tasks'] if not t['completed']]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in levels+[t['level'] for t in tasks]):
        raise ValueError('finite positive capacities and box weights required')
    # Exact native inequality, including equality at the lifting threshold.
    candidates=sorted(t['id'] for t in tasks if max(levels)<t['level']<=sum(levels))
    return {'branch':'joint_required' if candidates else 'solo_required',
            'jointly_only_feasible_box_ids':candidates}


def score(raw,state):
    try:condition=classify(state)
    except (KeyError,TypeError,ValueError) as exc:
        return {'status':'SPEC','good':False,'comparison_valid':False,'spec_defect':str(exc),
                'format_valid':False,'capacity_feasible':False,'geometric_feasible':False,
                'physical_valid':False,'progress':False,'policy_compliant':False,'targets':None,
                'branch':None,'failure_flags':{'specification':True}}
    result=physical_score(raw,state,'P0')
    result.update(condition,grader_version=GRADER_VERSION,branch_rule_satisfied=False,
                  policy_compliant=False)
    targets=result['targets']
    if targets is not None:
        values=list(targets.values())
        if condition['branch']=='joint_required':
            follows=(values[0]==values[1] and values[0] in condition['jointly_only_feasible_box_ids'])
            result['branch_rule_satisfied']=follows
        else:
            counts=Counter(v for v in values if v is not None)
            follows=bool(counts) and all(n==1 for n in counts.values())
            result['branch_rule_satisfied']=follows
            weights={t['id']:t['level'] for t in state['tasks'] if not t['completed']}
            follows=follows and all(targets[a['id']] is None or a['level']>=weights[targets[a['id']]] for a in state['agents'])
        result['policy_compliant']=follows
        if result['comparison_valid'] and result['physical_valid'] and result['progress']:
            result.update(status='GOOD' if follows else 'POLICY',good=follows)
    result['failure_flags']={
        'format':not result['format_valid'],
        'capacity':result['format_valid'] and not result['capacity_feasible'],
        'geometry':result['format_valid'] and not result['geometric_feasible'],
        'progress':result['format_valid'] and not result['progress'],
        'policy':result['format_valid'] and not result['policy_compliant'],
        'specification':not result['comparison_valid']}
    return result


def good_set(state):
    return [a for a in allocations(state) if score(canonical({'targets':a}),state)['good']]


def audit_pickups(state,execution):
    """Separate realized-event audit; does not alter recommendation or executor."""
    condition=classify(state);violations=[];pickups=[]
    capacities={a['id']:a['level'] for a in state['agents']}
    weights={t['id']:t['level'] for t in state['tasks']}
    for tick in execution['trace']:
        for box in tick['pickups']:
            members=tick['attempts'].get(box,[])
            compliant=(box in condition['jointly_only_feasible_box_ids'] and set(members)==set(capacities)
                if condition['branch']=='joint_required' else
                len(members)==1 and capacities[members[0]]>=weights[box])
            event={'tick':tick['tick'],'box':box,'loading_agents':members,'conditional_policy_compliant':compliant}
            pickups.append(event)
            if not compliant:violations.append(event)
    return {'branch':condition['branch'],'pickup_events':pickups,'violations':violations,
            'no_pickup':not pickups,'recommendation_label_changed':False}
