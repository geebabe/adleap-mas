import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import testbed as tb


class TestPolicy2Action(unittest.TestCase):
    def test_astar(self):
        self.assertEqual(tb.astar((0,0),(2,0),(3,2),set()), [0,0])
        self.assertEqual(len(tb.astar((0,0),(2,0),(3,2),{(1,0)})),4)
        self.assertIsNone(tb.astar((0,0),(2,0),(3,1),{(1,0)}))

    def test_real_upstream_and_noop(self):
        self.assertTrue(Path(tb.LBF.__file__).is_relative_to(tb.VENDOR))
        env = tb.make_env(tb.SCENARIOS['prohibited'])
        before = tb.snapshot(env)
        tb.step_joint(env, {'A':None,'B':None})
        self.assertEqual(tb.snapshot(env),before)
        tb.step_joint(env, {'A':0,'B':None})
        self.assertEqual(env.components['agents'][0].position,(1,1)) # blocked by task
        self.assertEqual(env.components['agents'][0].direction,0)

    def test_structural_and_grounding(self):
        env = tb.make_env(tb.SCENARIOS['conditional'])
        for bad in ({}, {'A':5,'B':None}, {'A':True,'B':0}, {'A':'0','B':4}):
            with self.assertRaises(ValueError):
                tb.step_joint(env,bad)
        good = {'interpretation':tb.SCENARIOS['conditional']['constraints'], 'assignments':{'A':'near','B':None}}
        self.assertIsNone(tb.validate_decision(good, env))
        good['assignments']['A'] = 'missing'
        self.assertTrue(tb.validate_decision(good,env).startswith('grounding'))
        good['interpretation'] = {'cooperation':'allow','before':[1]}
        self.assertTrue(tb.validate_decision(good,env).startswith('structure'))

    def test_observable_attempt_and_exception(self):
        env = tb.make_env(tb.SCENARIOS['heavy_permitted'])
        a,b = env.components['agents']
        b.position,b.direction = (2,2), 3*tb.math.pi/2
        actions = {'A':4,'B':4}
        forbid = tb.SCENARIOS['prohibited']['constraints']
        self.assertEqual(tb.audit(env,actions,forbid)[1][0]['rule'],'forbidden_cooperation')
        self.assertFalse(tb.audit(env,actions,tb.SCENARIOS['exception']['constraints'])[1])
        env.components['tasks'][0].level = .5
        self.assertTrue(tb.audit(env,actions,tb.SCENARIOS['exception']['constraints'])[1])
        self.assertFalse(tb.audit(env,{'A':None,'B':None},forbid)[1])
        # A alone cannot lift the heavy task; precedence still flags the attempt.
        env.components['tasks'][0].level = 1.5
        self.assertEqual(tb.audit(env,{'A':4,'B':None},tb.SCENARIOS['conditional']['constraints'])[1][0]['rule'],'precedence')
        tb.step_joint(env,{'A':4,'B':None})
        self.assertFalse(env.components['tasks'][0].completed)
        tb.step_joint(env,actions)
        self.assertTrue(env.components['tasks'][0].completed)

    def test_all_scenarios_and_paired_tradeoff(self):
        for scenario in tb.SCENARIOS:
            with self.subTest(scenario=scenario):
                ref = tb.run(scenario,'reference')
                fake = tb.run(scenario,'llm_mock')
                self.assertTrue(ref['compliant_completion'],ref)
                self.assertTrue(fake['compliant_completion'],fake)
                self.assertEqual(ref['steps'],fake['steps'])
        blind = tb.run('conditional','blind')
        reference = tb.run('conditional','reference')
        free = tb.run('unrestricted_pair','reference')
        self.assertEqual(blind['initial_state_hash'],reference['initial_state_hash'])
        self.assertEqual(free['initial_state_hash'],reference['initial_state_hash'])
        self.assertEqual(blind['completed'],2)
        self.assertFalse(blind['observable_compliant'])
        self.assertLess(blind['steps'],reference['steps'])
        self.assertLess(blind['first_completion_step'],reference['first_completion_step'])

    def test_mock_failure_paths(self):
        for mode,prefix in [('malformed','structure'),('ungrounded','grounding'),('idle','action_selection')]:
            with self.subTest(mode=mode):
                result = tb.run('conditional','llm_mock',fake_mode=mode)
                self.assertTrue(result['failure_reason'].startswith(prefix),result)
                self.assertFalse(result['compliant_completion'])
                self.assertEqual(result['api_calls'],0)
        mistaken = tb.run('conditional','llm_mock',fake_mode='misinterpret')
        self.assertFalse(all(mistaken['interpretation_matches']))
        self.assertGreater(mistaken['violation_count'],0)
        misselect = tb.run('conditional','llm_mock',fake_mode='misselect')
        self.assertTrue(all(misselect['interpretation_matches']))
        self.assertGreater(misselect['violation_count'],0)
        short = tb.run('conditional',horizon=1)
        self.assertIn('horizon',short['failure_reason'])

    def test_optional_llm_backend_without_network(self):
        from llm_backend import OpenAIBackend
        with self.assertRaises(PermissionError):
            OpenAIBackend()
        with self.assertRaises(PermissionError):
            tb.run('conditional','llm')
        class InjectedBackend:
            usage = {'prompt_tokens':10,'completion_tokens':5,'estimated_cost_usd':0}
            def complete(self, request):
                return tb.FakeLLM().complete(request)
        result = tb.run('conditional','llm',llm=InjectedBackend())
        self.assertTrue(result['compliant_completion'])
        self.assertEqual(result['api_calls'],2) # backend invocations, injected here
        class BrokenBackend:
            def complete(self, request):
                raise TimeoutError('secret must not appear')
        broken = tb.run('conditional','llm',llm=BrokenBackend())
        self.assertEqual(broken['failure_reason'],'inference: TimeoutError')
        self.assertIsNone(broken['estimated_cost_usd'])

    def test_no_path(self):
        env = tb.make_env(tb.SCENARIOS['conditional'])
        env.components['obstacles'] = [(6,1),(8,1),(7,0),(7,2)]
        _,error = tb.navigate(env,{'A':'far','B':None})
        self.assertIn('planning',error)

    def test_log_reproducibility_and_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'run.jsonl'
            one = tb.run('conditional','reference',seed=7,output=path)
            two = tb.run('conditional','reference',seed=7)
            self.assertEqual(one,two)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(rows[-1],one)
            self.assertEqual(len([r for r in rows if r['type']=='transition']),one['steps'])
            with self.assertRaises(FileExistsError):
                tb.run('conditional',output=path)


if __name__ == '__main__':
    unittest.main()
