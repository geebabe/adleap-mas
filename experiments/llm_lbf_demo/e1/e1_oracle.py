"""Independent recommendation predicates. Never imports controller or executor."""
from collections import Counter, deque
from functools import lru_cache
import itertools
import json
import math
from .common import canonical, TOLERANCE


class FormatError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FormatError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def parse(raw, state):
    """No fences, substring extraction, coercion, legacy flags, or JSON repair."""
    if not isinstance(raw, str):
        raise FormatError('response must be text')
    try:
        value = json.loads(raw, object_pairs_hook=_unique,
                           parse_constant=lambda value: (_ for _ in ()).throw(FormatError('nonfinite JSON')))
    except (json.JSONDecodeError, TypeError, RecursionError) as exc:
        raise FormatError('invalid JSON') from exc
    if not isinstance(value, dict) or set(value) != {'targets'}:
        raise FormatError('expected exactly targets; legacy/extra flags are rejected')
    targets = value['targets']
    agents = {a['id'] for a in state['agents']}
    active = {t['id'] for t in state['tasks'] if not t['completed']}
    if not isinstance(targets, dict) or set(targets) != agents:
        raise FormatError('expected exact registered agent IDs')
    if any(t is not None and (not isinstance(t, str) or t not in active) for t in targets.values()):
        raise FormatError('unknown/completed/translated target ID')
    return targets


def allocations(state):
    ids = sorted(a['id'] for a in state['agents'])
    values = sorted(t['id'] for t in state['tasks'] if not t['completed']) + [None]
    return [dict(zip(ids, pair)) for pair in itertools.product(values, repeat=len(ids))]


def capacity_feasible(state, targets):
    levels = {a['id']: a['level'] for a in state['agents']}
    tasks = {t['id']: t for t in state['tasks'] if not t['completed']}
    for tid in {t for t in targets.values() if t is not None}:
        capacity = math.fsum(levels[aid] for aid, target in targets.items() if target == tid)
        if capacity + TOLERANCE < tasks[tid]['level']:
            return False
    return True


@lru_cache(maxsize=4096)
def _geometry(state_json, targets_json):
    """Exact joint-position BFS, independent of A*/rollout success.

    Active boxes remain blocked. One assigned robot moves per edge; an unassigned
    robot is fixed. A goal has all assigned robots at distinct adjacent cells.
    This conservative reachability predicate is sufficient for the declared open
    worlds; obstacles are supported for diagnostic tests, not additional scope.
    """
    state, targets = json.loads(state_json), json.loads(targets_json)
    agents = sorted(state['agents'], key=lambda a: a['id'])
    tasks = {t['id']: tuple(t['position']) for t in state['tasks'] if not t['completed']}
    blocked = {tuple(p) for p in state['obstacles']} | set(tasks.values())
    start = tuple(tuple(a['position']) for a in agents)
    shape = state['shape']
    if len(set(start)) != len(start) or any(p in blocked for p in start):
        return False
    if any(not (0 <= p[0] < shape[0] and 0 <= p[1] < shape[1]) for p in start):
        return False
    goals = [tasks[targets[a['id']]] if targets[a['id']] is not None else None for a in agents]
    def done(positions):
        return all(g is None or abs(p[0]-g[0])+abs(p[1]-g[1]) == 1 for p,g in zip(positions, goals))
    seen, queue = {start}, deque([start])
    while queue:
        positions = queue.popleft()
        if done(positions):
            return True
        for i, goal in enumerate(goals):
            if goal is None:
                continue
            x,y = positions[i]
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nxt = x+dx,y+dy
                if nxt in blocked or nxt in positions or not (0 <= nxt[0] < shape[0] and 0 <= nxt[1] < shape[1]):
                    continue
                candidate = positions[:i]+(nxt,)+positions[i+1:]
                if candidate not in seen:
                    seen.add(candidate)
                    queue.append(candidate)
    return False


def geometric_feasible(state, targets):
    return _geometry(canonical(state), canonical(targets))


def policy_satisfied(targets, gold):
    counts = Counter(t for t in targets.values() if t is not None)
    if gold == 'R':
        return all(n == 2 for n in counts.values())
    if gold == 'F':
        return all(n == 1 for n in counts.values())
    if gold == 'P0':
        return True
    raise ValueError('unknown grader condition')


def score(raw, state, gold, spec_defect=None):
    result = dict(status='FORMAT', good=False, format_valid=False, capacity_feasible=False,
                  geometric_feasible=False, physical_valid=False, progress=False,
                  policy_compliant=False, joint_assignment=False, targets=None,
                  comparison_valid=True, spec_defect=spec_defect)
    try:
        targets = parse(raw, state)
    except FormatError as exc:
        result['reason'] = str(exc)
    else:
        cap = capacity_feasible(state, targets)
        geo = geometric_feasible(state, targets)
        progress = any(t is not None for t in targets.values())
        policy = policy_satisfied(targets, gold)
        result.update(targets=targets, format_valid=True, capacity_feasible=cap,
                      geometric_feasible=geo, physical_valid=cap and geo, progress=progress,
                      policy_compliant=policy, joint_assignment=any(
                          n > 1 for n in Counter(t for t in targets.values() if t is not None).values()))
        # Native upstream uses exact >=. Do not silently credit tolerance-only lifts.
        for task in state['tasks']:
            members = [a['level'] for a in state['agents'] if targets[a['id']] == task['id']]
            if members and sum(members) < task['level'] <= math.fsum(members)+TOLERANCE:
                spec_defect = 'capacity tolerance disagrees with native exact comparison'
        status = 'PHYSICS' if not cap or not geo else 'VACUOUS' if not progress else 'POLICY' if not policy else 'GOOD'
        result.update(status=status, good=status == 'GOOD')
    if spec_defect:
        result.update(status='SPEC', good=False, comparison_valid=False, spec_defect=spec_defect)
    return result


def good_set(state, gold):
    return [a for a in allocations(state) if score(canonical({'targets':a}), state, gold)['good']]
