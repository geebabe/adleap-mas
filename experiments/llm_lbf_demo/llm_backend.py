"""Optional paid backend. Construction requires explicit opt-in; tests use injection."""
import json
import os
from urllib.request import Request, urlopen

SYSTEM = '''You are a centralized Level-Based Foraging controller. Return one JSON object
with exactly interpretation and assignments. interpretation has cooperation (allow,
forbid, or heavy_exception) and before (list of [prerequisite_task_id, task_id]).
assignments maps every agent ID to an unfinished task ID or null. Interpret the
natural language policy, then select feasible joint targets. Task loads require
sum of participating capacities >= task level. Multiple agents on the same task
coordinate simultaneous loading. Prefer a solo agent when sufficient. before rules
prohibit even attempting a load before the prerequisite is completed. Do not use
unknown IDs. The caller handles A* movement, facing and synchronization. An idle
assignment for every agent terminates execution with incomplete work. Policy
compliance and task completion are measured independently. Return JSON only.'''


class OpenAIBackend:
    def __init__(self, *, approved=False, model='gpt-4o-mini', input_per_million=None,
                 output_per_million=None, max_calls=10):
        if not approved:
            raise PermissionError('Paid inference disabled; explicit approval is required')
        if input_per_million is None or output_per_million is None:
            raise ValueError('Provide current token prices for estimated cost logging')
        if min(input_per_million, output_per_million) < 0 or max_calls < 1:
            raise ValueError('Prices must be nonnegative and max_calls positive')
        self.model = model
        self.prices = (input_per_million, output_per_million)
        self.max_calls = max_calls
        self.calls = 0
        self.usage = {}

    def complete(self, request):
        if self.calls >= self.max_calls:
            raise RuntimeError('API call budget exhausted')
        key = os.environ.get('OPENAI_API_KEY')
        if not key:
            raise RuntimeError('OPENAI_API_KEY is required')
        self.calls += 1
        body = {'model':self.model, 'temperature':0, 'max_tokens':600,
                'response_format':{'type':'json_object'}, 'messages':[
                    {'role':'system','content':SYSTEM},
                    {'role':'user','content':json.dumps(request)}]}
        req = Request('https://api.openai.com/v1/chat/completions',
                      data=json.dumps(body).encode(), headers={
                          'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with urlopen(req, timeout=60) as response:
            payload = json.load(response)
        usage = payload.get('usage', {})
        self.usage = {'prompt_tokens':usage.get('prompt_tokens'),
                      'completion_tokens':usage.get('completion_tokens'),
                      'model':payload.get('model'), 'response_id':payload.get('id'),
                      'system_fingerprint':payload.get('system_fingerprint')}
        self.usage['estimated_cost_usd'] = (
            (usage['prompt_tokens']*self.prices[0]+usage['completion_tokens']*self.prices[1])/1e6
            if 'prompt_tokens' in usage and 'completion_tokens' in usage else None)
        return payload['choices'][0]['message']['content']
