"""Policy2Action: centralized decisions, deterministic audit, real ADLEAP LBF.

Only the pinned checkout provides src imports. Paid inference requires opt-in.
"""
from __future__ import annotations
import argparse
import hashlib
import heapq
import importlib
from importlib.metadata import version
import itertools
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
LOCK = json.loads((ROOT / 'upstream.lock.json').read_text())
VENDOR = ROOT / 'vendor/adleap-mas'


def upstream():
    if not VENDOR.exists():
        raise RuntimeError('Run python experiments/llm_lbf_demo/bootstrap.py first')
    actual = subprocess.check_output(['git', '-C', str(VENDOR), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != LOCK['commit']:
        raise RuntimeError(f'Upstream pin mismatch: {actual}')
    dirty = subprocess.check_output(['git', '-C', str(VENDOR), 'status', '--porcelain', '--', 'src'], text=True)
    if dirty:
        raise RuntimeError('Pinned upstream src is modified')
    if 'src' in sys.modules and not str(getattr(sys.modules['src'], '__file__', '')).startswith(str(VENDOR)):
        raise RuntimeError('Parent src already imported; run in a fresh Python process')
    sys.path.insert(0, str(VENDOR))
    module = importlib.import_module('src.envs.LevelForagingEnv')
    if not Path(module.__file__).is_relative_to(VENDOR):
        raise RuntimeError('Wrong LBF module imported')
    return module


LBF = upstream()
MOVES = {0: (1, 0), 1: (-1, 0), 2: (0, 1), 3: (0, -1)}
SCENARIOS = json.loads((ROOT / 'scenarios.json').read_text())


def make_env(scenario, seed=0):
    random.seed(seed)
    # Matched initial state across conditional/unrestricted_pair and seeds.
    agents = [LBF.Agent('A', None, (1, 1), 0, 1., 1., 1.),
              LBF.Agent('B', None, (1, 3), 0, 1., 1., 1.)]
    tasks = [LBF.Task('near', (2, 1), 1.5 if scenario['heavy'] else .5),
             LBF.Task('far', (7, 1), .5)]
    # Pinned do_action decrements this field without guarding its None default.
    for agent in agents:
        agent.smart_parameters['ntasks'] = len(tasks)
    return LBF.LevelForagingEnv((9, 5), {'agents': agents, 'tasks': tasks,
        'adhoc_agent_index': 'A', 'obstacles': []}, display=False)


def snapshot(env):
    return {'shape': list(env.shape), 'obstacles': [list(p) for p in env.components['obstacles']],
            'agents': [{'id': a.index, 'position': list(a.position), 'direction': float(a.direction),
                        'level': a.level} for a in env.components['agents']],
            'tasks': [{'id': t.index, 'position': list(t.position), 'level': t.level,
                       'completed': t.completed} for t in env.components['tasks']]}


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def provenance():
    return {'files': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                      for name in ('testbed.py','llm_backend.py','scenarios.json','requirements.lock','upstream.lock.json')},
            'dependencies': {name: version(name) for name in ('numpy','gymnasium','matplotlib')}}


def manhattan(a, b):
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def astar(start, goal, shape, blocked):
    """Return shortest action list, or None; stable tie breaking."""
    queue = [(manhattan(start, goal), 0, start, [])]
    best = {start: 0}
    while queue:
        _, cost, pos, path = heapq.heappop(queue)
        if pos == goal:
            return path
        if cost != best[pos]:
            continue
        for action, (dx, dy) in MOVES.items():
            nxt = pos[0]+dx, pos[1]+dy
            if not (0 <= nxt[0] < shape[0] and 0 <= nxt[1] < shape[1]) or nxt in blocked:
                continue
            if cost+1 < best.get(nxt, math.inf):
                best[nxt] = cost+1
                heapq.heappush(queue, (cost+1+manhattan(nxt, goal), cost+1, nxt, path+[action]))
    return None


def cooperative_allowed(rules, task, agents):
    return rules['cooperation'] == 'allow' or (rules['cooperation'] == 'heavy_exception'
        and task.level > max(a.level for a in agents))


def eligible(task, env, rules):
    completed = {t.index for t in env.components['tasks'] if t.completed}
    return all(after != task.index or before in completed for before, after in rules['before'])


def validate_decision(decision, env):
    """Structural errors precede grounding; neither implies a policy violation."""
    if not isinstance(decision, dict) or set(decision) != {'interpretation', 'assignments'}:
        return 'structure: expected interpretation and assignments'
    rules = decision['interpretation']
    if (not isinstance(rules, dict) or set(rules) != {'cooperation', 'before'}
        or rules['cooperation'] not in ('allow', 'forbid', 'heavy_exception')
        or not isinstance(rules['before'], list)
        or any(not isinstance(p, list) or len(p) != 2 or any(not isinstance(x, str) for x in p)
               for p in rules['before'])):
        return 'structure: invalid interpretation'
    assignments = decision['assignments']
    ids = {a.index for a in env.components['agents']}
    if not isinstance(assignments, dict) or set(assignments) != ids:
        return 'structure: exact agent IDs required'
    active = {t.index for t in env.components['tasks'] if not t.completed}
    if any(v is not None and (not isinstance(v, str) or v not in active) for v in assignments.values()):
        return 'grounding: unknown or completed task'
    known = {t.index for t in env.components['tasks']}
    if any(x not in known for pair in rules['before'] for x in pair):
        return 'grounding: unknown rule task'
    return None


def choose(env, rules, aware=True):
    agents = env.components['agents']
    assignments = {a.index: None for a in agents}
    active = [t for t in env.components['tasks'] if not t.completed and (not aware or eligible(t, env, rules))]
    if not active:
        return assignments
    task = min(active, key=lambda t: (min(manhattan(a.position, t.position) for a in agents), t.index))
    solo = [a for a in agents if a.level >= task.level]
    if solo:
        agent = min(solo, key=lambda a: (manhattan(a.position, task.position), a.index))
        assignments[agent.index] = task.index
    elif sum(a.level for a in agents) >= task.level and (not aware or cooperative_allowed(rules, task, agents)):
        assignments = {a.index: task.index for a in agents}
    return assignments


class FakeLLM:
    """Scripted contract fixture, never evidence of language understanding."""
    def __init__(self, mode='correct'):
        self.mode = mode

    def complete(self, request):
        # Fixture lookup uses policy text; gold constraints are not in model input.
        rules = next(s['constraints'] for s in SCENARIOS.values() if s['text'] == request['policy'])
        rules = json.loads(json.dumps(rules))
        if self.mode == 'misinterpret':
            rules = {'cooperation': 'allow', 'before': []}
        # Build only assignments from the serialized state, not a simulator oracle.
        state = request['state']
        done = {t['id'] for t in state['tasks'] if t['completed']}
        tasks = [t for t in state['tasks'] if not t['completed'] and all(
            after != t['id'] or before in done for before, after in
            ([] if self.mode == 'misselect' else rules['before']))]
        agents = state['agents']
        assignment = {a['id']: None for a in agents}
        if tasks:
            t = min(tasks, key=lambda t: (min(manhattan(a['position'], t['position']) for a in agents), t['id']))
            solo = [a for a in agents if a['level'] >= t['level']]
            if solo:
                a = min(solo, key=lambda a: (manhattan(a['position'], t['position']), a['id']))
                assignment[a['id']] = t['id']
            elif rules['cooperation'] != 'forbid':
                assignment = {a['id']: t['id'] for a in agents}
        if self.mode == 'ungrounded':
            assignment['A'] = 'nonexistent'
        if self.mode == 'idle':
            assignment = {a['id']: None for a in agents}
        if self.mode == 'malformed':
            return '{broken'
        return json.dumps({'interpretation': rules, 'assignments': assignment})


def navigate(env, assignments):
    """A* to distinct interaction slots; serialize motion, synchronize loading.

    None is upstream do_action's actual no-op. A move into a task rotates in place.
    Conservative occupied-cell blocking avoids stochastic collision resolution.
    """
    agents = env.components['agents']
    actions = {a.index: None for a in agents}
    active = {t.index: t for t in env.components['tasks'] if not t.completed}
    blocked = set(env.components['obstacles']) | {t.position for t in active.values()}
    groups = {}
    for a in agents:
        if assignments[a.index] is not None:
            groups.setdefault(assignments[a.index], []).append(a)
    for tid, group in groups.items():
        task = active[tid]
        slots = [(task.position[0]-dx, task.position[1]-dy, action) for action, (dx,dy) in MOVES.items()]
        candidates = []
        for arrangement in itertools.permutations(slots, len(group)):
            plans = []
            for a, (x,y,face) in zip(group, arrangement):
                occupied = {b.position for b in agents if b.index != a.index}
                if not (0 <= x < env.shape[0] and 0 <= y < env.shape[1]) or (x,y) in blocked | occupied:
                    break
                path = astar(a.position, (x,y), env.shape, blocked | occupied)
                if path is None:
                    break
                plans.append((a, path, face))
            if len(plans) == len(group):
                candidates.append((sum(len(p) for _,p,_ in plans), arrangement, plans))
        if not candidates:
            return actions, 'planning: no reachable distinct slots'
        plans = min(candidates, key=lambda item: (item[0], item[1]))[2]
        ready = all(not path and a.direction == env.action2direction[face] for a,path,face in plans)
        if ready:
            for a,_,_ in plans:
                actions[a.index] = 4
        else:
            # One movement/turn per tick is conservative and deterministic.
            for a,path,face in plans:
                if path:
                    actions[a.index] = path[0]
                    break
                if a.direction != env.action2direction[face]:
                    actions[a.index] = face
                    break
    return actions, None


def validate_actions(env, actions):
    ids = {a.index for a in env.components['agents']}
    if not isinstance(actions, dict) or set(actions) != ids:
        return 'structure: exact joint action agent IDs required'
    if any(v is not None and (type(v) is not int or v not in range(5)) for v in actions.values()):
        return 'structure: actions must be None or integer 0..4'
    return None


def audit(env, actions, rules):
    """Observable violations: forbidden concurrent LOAD attempts or order attempts.

    Evaluate pre-state; unsuccessful prohibited attempts also count. Intent, private
    reasoning and unexecuted assignments are not observable action violations.
    """
    attempts = {}
    for a in env.components['agents']:
        if actions[a.index] == 4:
            t = LBF.there_is_task(env, a.position, a.direction)
            if t is not None:
                attempts.setdefault(t.index, []).append(a.index)
    violations = []
    for tid, participants in attempts.items():
        task = next(t for t in env.components['tasks'] if t.index == tid)
        if len(participants) > 1 and not cooperative_allowed(rules, task, env.components['agents']):
            violations.append({'rule': 'forbidden_cooperation', 'task': tid, 'agents': participants})
        if not eligible(task, env, rules):
            violations.append({'rule': 'precedence', 'task': tid, 'agents': participants})
    return attempts, violations


def step_joint(env, actions):
    error = validate_actions(env, actions)
    if error:
        raise ValueError(error)
    for a in env.components['agents']:
        a.next_action = actions[a.index]
    _, info = LBF.do_action(env)
    # do_action is the upstream simultaneous physical transition; env.step would
    # overwrite teammate decisions with decentralized reasoning policies.
    env.episode += 1
    return info


def run(scenario_name, condition='reference', seed=0, horizon=80, fake_mode='correct', output=None, llm=None):
    if output and Path(output).exists():
        raise FileExistsError(output)
    if condition not in ('blind', 'reference', 'llm_mock', 'llm'):
        raise ValueError('Unknown condition')
    if condition == 'llm' and llm is None:
        raise PermissionError('LLM condition requires an explicitly supplied backend')
    scenario = SCENARIOS[scenario_name]
    env = make_env(scenario, seed)
    initial = snapshot(env)
    records = []
    violations = []
    failure = None
    calls = 0
    api_calls = 0
    estimated_cost = 0
    first_completion = None
    actions_count = 0
    assignments = None
    interpretation = None
    decision_id = -1
    for tick in range(horizon):
        state = snapshot(env)
        if all(t.completed for t in env.components['tasks']):
            break
        active = {t.index for t in env.components['tasks'] if not t.completed}
        if assignments is None or any(v is not None and v not in active for v in assignments.values()):
            decision_id += 1
            request = {'policy': scenario['text'], 'state': state}
            start = time.perf_counter()
            raw = None
            usage = {}
            if condition in ('llm_mock', 'llm'):
                if condition == 'llm_mock':
                    calls += 1
                    raw = FakeLLM(fake_mode).complete(request)
                else:
                    api_calls += 1
                    try:
                        raw = llm.complete(request)
                        usage = llm.usage
                    except Exception as exc:
                        # Exception messages may contain credentials or remote content.
                        failure = 'inference: ' + type(exc).__name__
                        records.append({'type':'inference_error','tick':tick,'error':failure})
                        estimated_cost = None
                        break
                    cost = usage.get('estimated_cost_usd')
                    estimated_cost = estimated_cost + cost if estimated_cost is not None and cost is not None else None
                try:
                    decision = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    decision = None
            else:
                decision = {'interpretation': scenario['constraints'] if condition == 'reference'
                            else {'cooperation': 'allow', 'before': []},
                            'assignments': choose(env, scenario['constraints'], condition == 'reference')}
            error = validate_decision(decision, env)
            records.append({'type': 'decision', 'tick': tick, 'decision_id': decision_id,
                'request': request, 'raw_response': raw, 'decision': decision, 'validation_error': error,
                'latency_seconds': time.perf_counter()-start, 'api_calls': int(condition == 'llm'),
                'usage': usage, 'estimated_cost_usd': usage.get('estimated_cost_usd', 0),
                'interpretation_match': bool(isinstance(decision, dict) and decision.get('interpretation') == scenario['constraints'])})
            if error:
                failure = error
                break
            assignments = decision['assignments']
            interpretation = decision['interpretation']
        if all(v is None for v in assignments.values()):
            failure = 'action_selection: idle with unfinished tasks'
            break
        actions, error = navigate(env, assignments)
        if error:
            failure = error
            break
        attempts, step_violations = audit(env, actions, scenario['constraints'])
        # Audit only; never silently shield or repair policy violations.
        info = step_joint(env, actions)
        actions_count += sum(v is not None for v in actions.values())
        violations.extend(step_violations)
        finished = [t.index for t in info['just_finished_tasks']]
        if finished and first_completion is None:
            first_completion = tick+1
        records.append({'type': 'transition', 'tick': tick, 'decision_id': decision_id,
            'before': state, 'assignments': assignments, 'interpretation': interpretation,
            'actions': actions, 'attempts': attempts, 'violations': step_violations,
            'completed_now': finished, 'reward': info['action reward'], 'after': snapshot(env)})
    transitions = [r for r in records if r['type'] == 'transition']
    completed = sum(t.completed for t in env.components['tasks'])
    if completed < len(env.components['tasks']) and failure is None:
        failure = 'coordination_or_planning: horizon exhausted (cause unresolved)'
    summary = {'type': 'summary', 'scenario': scenario_name, 'condition': condition, 'seed': seed,
        'horizon': horizon, 'upstream_commit': LOCK['commit'], 'initial_state': initial,
        'provenance': provenance(),
        'initial_state_hash': digest(initial), 'policy': scenario['text'], 'constraints': scenario['constraints'],
        'completed': completed, 'total_tasks': len(env.components['tasks']),
        'completion_fraction': completed/len(env.components['tasks']), 'steps': len(transitions),
        'first_completion_step': first_completion, 'nonidle_actions': actions_count,
        'observable_compliant': not violations, 'violation_count': len(violations),
        'compliant_completion': completed == len(env.components['tasks']) and not violations,
        'failure_reason': failure, 'mock_calls': calls, 'api_calls': api_calls,
        'estimated_cost_usd': estimated_cost, 'cost_usd': 0 if api_calls == 0 else None,
        'interpretation_matches': [r['interpretation_match'] for r in records if r['type'] == 'decision']}
    if output:
        # Exclusive create preserves existing logs.
        with Path(output).open('x') as handle:
            for record in [{'type': 'metadata', 'python': sys.version, 'module': LBF.__file__}, *records, summary]:
                handle.write(json.dumps(record, sort_keys=True)+'\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=SCENARIOS, default='conditional')
    parser.add_argument('--condition', choices=['blind','reference','llm_mock','llm'], default='reference')
    parser.add_argument('--allow-paid-api', action='store_true', help='Explicit approval for paid inference')
    parser.add_argument('--model', default='gpt-4o-mini')
    parser.add_argument('--input-price', type=float, help='Current USD per million input tokens')
    parser.add_argument('--output-price', type=float, help='Current USD per million output tokens')
    parser.add_argument('--fake-mode', choices=['correct','misinterpret','misselect','ungrounded','idle','malformed'], default='correct')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--horizon', type=int, default=80)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--suite', type=Path, help='Create new directory with all paired runs and summary.json')
    args = parser.parse_args()
    if args.horizon < 1:
        parser.error('--horizon must be positive')
    if args.suite:
        args.suite.mkdir(parents=True, exist_ok=False)
        summaries = [run(s,c,seed,args.horizon,output=args.suite/f'{s}-{c}-{seed}.jsonl')
                     for s in SCENARIOS for c in ['blind','reference','llm_mock'] for seed in [0,1,2]]
        (args.suite/'summary.json').write_text(json.dumps(summaries, indent=2)+'\n')
        print(json.dumps({'runs':len(summaries), 'directory':str(args.suite)}))
    else:
        llm = None
        if args.condition == 'llm':
            from llm_backend import OpenAIBackend
            try:
                llm = OpenAIBackend(approved=args.allow_paid_api, model=args.model,
                    input_per_million=args.input_price, output_per_million=args.output_price)
            except (PermissionError, ValueError) as exc:
                parser.error(str(exc))
        print(json.dumps(run(args.scenario,args.condition,args.seed,args.horizon,args.fake_mode,args.output,llm),indent=2))


if __name__ == '__main__':
    main()
