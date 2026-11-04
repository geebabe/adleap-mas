"""Explicit infrastructure fixtures and a guarded, injected/lazy live transport."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .common import canonical, read_json, ROOT
from .e1_oracle import good_set


class InfrastructureError(RuntimeError):
    def __init__(self,message='provider unavailable',request_id=None):
        super().__init__(message);self.request_id=request_id


class FakeProvider:
    infrastructure_validation = True
    def __init__(self,mode='oracle',policies=None):
        self.mode=mode;self.calls=0
        self.policies=policies or read_json(ROOT/'e1_policies.json')
    def complete(self,request,model):
        self.calls+=1
        body=json.loads(request['messages'][1]['content']);state=body['state']
        if self.mode=='malformed':raw='{broken'
        elif self.mode=='idle':raw=canonical({'targets':{a['id']:None for a in state['agents']}})
        else:
            if self.mode=='oracle':
                matches={gold for lang in self.policies['languages'].values() for gold,texts in lang.items() if body['policy'] in texts}
                if len(matches)!=1:raise ValueError('unknown/ambiguous fixture policy')
                options=good_set(state,matches.pop())
            elif self.mode=='blind':
                options=good_set(state,'P0')
                options=sorted(options,key=lambda a:(sum(v is not None for v in a.values()),canonical(a)))
            else:raise ValueError('unknown fixture')
            raw=canonical({'targets':options[0]})
        return {'raw':raw,'raw_provider_response':{'fixture':self.mode,'content':raw},
                'request_id':f'fake-{self.calls}','model':model['id'],'fingerprint':'scripted-offline',
                'usage':{'input_tokens':None,'output_tokens':None},'api_calls':0,'cost_usd':0}


class LiveProvider:
    infrastructure_validation = False
    def __init__(self,transport=None):
        self.transport=transport or self._http
    @staticmethod
    def _http(request,model):
        key=os.environ.get('OPENAI_API_KEY')
        if not key:raise ValueError('OPENAI_API_KEY is required; no .env is read')
        body={**request,'model':model['id'],'temperature':model['temperature'],
              'max_tokens':model['max_output_tokens'],'response_format':{'type':'json_object'}}
        req=Request('https://api.openai.com/v1/chat/completions',data=canonical(body).encode(),
                    headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=60) as handle:
                data=json.load(handle);request_id=handle.headers.get('x-request-id')
        except HTTPError as exc:
            if exc.code==429 or 500<=exc.code<600:
                raise InfrastructureError(f'HTTP {exc.code}',exc.headers.get('x-request-id')) from None
            raise ValueError(f'non-retryable HTTP {exc.code}') from None
        except (TimeoutError,URLError,ConnectionError) as exc:
            raise InfrastructureError(type(exc).__name__) from None
        # Only documented provider-envelope extraction, no content repair.
        return {'raw':data['choices'][0]['message']['content'],'raw_provider_response':data,
                'request_id':request_id or data.get('id'),'model':data.get('model'),
                'fingerprint':data.get('system_fingerprint'),'usage':data.get('usage',{}),
                'api_calls':1,'cost_usd':None}
    def complete(self,request,model):
        return self.transport(request,model)
