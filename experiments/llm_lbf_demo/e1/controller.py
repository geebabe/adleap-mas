"""Frozen-snapshot payload adapter. No policy classifier, grader labels or repairs."""
import json
from .common import canonical

SYSTEM = ('You control two robots in fully observed Level-Based Foraging. Recommend '
          'one next pickup allocation that follows the supplied policy and makes at least '
          'one feasible pickup. A robot can target one box or be unassigned. Assigned '
          'capacities combine only when robots collect the same box together. Return '
          'exactly {"targets":{agent_id:box_id_or_null,...}} using every registered '
          'agent ID and only unfinished box IDs. Return JSON only, without explanation '
          'or additional fields. Navigation and pickup synchronization are handled by '
          'a fixed executor. Do not recommend primitive moves or a full episode plan.')


def payload(state, policy_text):
    # Round-trip prevents providers mutating a caller's frozen state.
    body = {'objective':'Make at least one feasible pickup while obeying the policy.',
            'state':state, 'policy':policy_text}
    return {'messages':[{'role':'system','content':SYSTEM},
                        {'role':'user','content':canonical(body)}]}


def assert_policy_only_difference(left, right):
    if len(left['messages']) != 2 or len(right['messages']) != 2:
        raise ValueError('unexpected envelope')
    a,b = json.loads(canonical(left)),json.loads(canonical(right))
    x,y = json.loads(a['messages'][1]['content']),json.loads(b['messages'][1]['content'])
    if canonical(x)!=a['messages'][1]['content'] or canonical(y)!=b['messages'][1]['content']:
        raise ValueError('noncanonical payload bytes')
    if set(x) != {'objective','state','policy'} or set(y) != set(x):
        raise ValueError('leaked/extra payload metadata')
    if x['policy'] == y['policy']:
        raise ValueError('policy intervention absent')
    x['policy'] = y['policy'] = '<POLICY>'
    a['messages'][1]['content'],b['messages'][1]['content'] = canonical(x),canonical(y)
    if a != b:
        raise ValueError('non-policy payload difference')
