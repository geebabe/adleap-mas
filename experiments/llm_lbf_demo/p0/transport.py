"""Standard-tier non-streaming Chat Completions transport; called only after guards."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from ..e1.common import canonical
from ..e1.providers import InfrastructureError

SETTINGS = {'temperature':0,'max_completion_tokens':256,'response_format':{'type':'json_object'},
            'n':1,'stream':False,'store':False,'service_tier':'default'}


class P0Provider:
    infrastructure_validation = False
    def complete(self,request,model):
        key=os.environ.get('OPENAI_API_KEY')
        if not key:raise ValueError('OPENAI_API_KEY required; .env is never loaded')
        body={**request,**SETTINGS,'model':model['id']}
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
        # Preserve the full envelope, including actual model/tier and all token usage.
        # A malformed model response is scored once, never repaired or retried.
        return {'raw':data['choices'][0]['message']['content'],'raw_provider_response':data,
                'request_id':request_id or data.get('id'),'model':data.get('model'),
                'fingerprint':data.get('system_fingerprint'),'usage':data.get('usage',{}),
                'effective_request':body,'api_calls':1,'cost_usd':None}
