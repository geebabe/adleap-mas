"""Thin bridge to the recovered executor; upstream and recovered code unchanged."""
import random
from .. import testbed as recovered
from .common import digest


class SpecDefect(RuntimeError):
    pass


def make_env(state, seed=0):
    random.seed(seed)
    if recovered.LBF.LevelForagingEnv.action_dict != {0:'East',1:'West',2:'North',3:'South',4:'Load'}:
        raise SpecDefect('native action mapping changed')
    agents = [recovered.LBF.Agent(a['id'],None,tuple(a['position']),a['direction'],1.,1.,a['level']) for a in state['agents']]
    tasks = [recovered.LBF.Task(t['id'],tuple(t['position']),t['level']) for t in state['tasks']]
    for task,original in zip(tasks,state['tasks']):
        task.completed = original['completed']
    for a in agents:
        a.smart_parameters['ntasks'] = sum(not t.completed for t in tasks)
    return recovered.LBF.LevelForagingEnv(tuple(state['shape']), {'agents':agents,'tasks':tasks,
        'adhoc_agent_index':agents[0].index,'obstacles':[tuple(p) for p in state['obstacles']]},display=False)


def load_attempts(env, actions):
    attempts = {}
    for a in env.components['agents']:
        if actions[a.index] == 4:
            task = recovered.LBF.there_is_task(env,a.position,a.direction)
            if task is not None:
                attempts.setdefault(task.index,[]).append(a.index)
    return attempts


def replay(state, targets, gold='P0', seed=0, horizon=40, navigator=None):
    """Original recommendation verdict is never passed in or changed here."""
    trace = []
    result = {'status':'EXECUTOR','success':False,'diagnosis':'40-tick horizon exhausted',
              'substitutions':[],'joint_load_attempts':0,'forbidden_joint_load_attempts':0,
              'forbidden_successful_pickups':0,'ticks':0,'trace':trace,'seed':seed}
    try:
        env = make_env(state, seed)
        navigator = navigator or recovered.navigate
        for tick in range(horizon):
            before = recovered.snapshot(env)
            actions,error = navigator(env,dict(targets))
            if error:
                result['diagnosis'] = error
                break
            attempts = load_attempts(env,actions)
            joint = [tid for tid,members in attempts.items() if len(members)>1]
            result['joint_load_attempts'] += len(joint)
            result['forbidden_joint_load_attempts'] += len(joint) if gold == 'F' else 0
            info = recovered.step_joint(env,actions)
            finished = [t.index for t in info['just_finished_tasks']]
            result['forbidden_successful_pickups'] += sum(
                gold == 'F' and tid in joint or gold == 'R' and len(attempts.get(tid,[])) != 2 for tid in finished)
            # No executor-side target reassignment is allowed or hidden.
            unexpected = [tid for tid in attempts if tid not in targets.values()]
            if unexpected:
                result['substitutions'].append({'tick':tick,'unexpected_tasks':unexpected})
            trace.append({'tick':tick,'targets':dict(targets),'before':before,'actions':actions,
                          'attempts':attempts,'pickups':finished,'after':recovered.snapshot(env)})
            if finished:
                result.update(success=not result['substitutions'],status='SUCCESS' if not result['substitutions'] else 'EXECUTOR',
                              diagnosis=None if not result['substitutions'] else 'executor substituted targets')
                break
    except SpecDefect as exc:
        result.update(status='SPEC',diagnosis=str(exc))
    except Exception as exc:
        result.update(diagnosis='executor exception: '+type(exc).__name__)
    result['ticks'] = len(trace)
    result['trace_hash'] = digest(trace)
    return result
