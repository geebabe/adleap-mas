"""Execute the previously prepared P0 workflow after recorded user authorization.

Loads the configured key privately into the process; never writes it to artifacts.
No prompt, parser, grader, model, transport setting or executor changes.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(REPO))
os.chdir(REPO)
from dotenv import dotenv_values
from experiments.llm_lbf_demo.e1.common import canonical,read_json
from experiments.llm_lbf_demo.p0.prepare import execute,budget

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('phase',choices=['smoke','gate'])
p.add_argument('--output',type=Path,required=True)
p.add_argument('--final-config',type=Path)
a=p.parse_args()
root=REPO/'experiments/llm_lbf_demo/p0'
proposal=read_json(root/'live.proposed.json')
spending=read_json(root/'spending-approval.json')
approval=read_json(root/'human-approval.json')
# Static disjoint phase caps enforce the user's combined new-spending ceiling.
assert sum(Decimal(str(v)) for v in spending['max_usd'].values())+Decimal('1')<=Decimal('2.55')
assert budget(proposal,a.phase)['worst_case_usd']<=spending['max_usd'][a.phase]
key=os.environ.get('OPENAI_API_KEY','').strip() or (dotenv_values(REPO/'.env').get('OPENAI_API_KEY') or '').strip()
if not key or key=='your_openai_api_key_here':raise SystemExit('BLOCKER: configured API credential absent')
os.environ['OPENAI_API_KEY']=key
import truststore
truststore.inject_into_ssl()
# Refuse a second independent invocation; compatible resume stays in the same journal.
a.output.mkdir(parents=True,exist_ok=True)
record=a.output/'launch-record.json'
if not record.exists():
    with record.open('x') as f:f.write(canonical({'phase':a.phase,'wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'proposal':str(root/'live.proposed.json'),'approval_records':[str(root/'human-approval.json'),str(root/'spending-approval.json')],
        'phase_budget':budget(proposal,a.phase),'combined_cap_usd':2.55,'held_out_launch_authorized':False})+'\n')
result=execute(a.phase,proposal,a.output,spending,approval,live=True,freeze_path=a.final_config)
print(canonical(result),flush=True)
