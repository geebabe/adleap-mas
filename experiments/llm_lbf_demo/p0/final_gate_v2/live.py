"""Credential-private entry point for the two explicitly authorized live phases."""
import os
import sys
from dotenv import dotenv_values
from ...e1.common import ROOT
from .workflow import main

if __name__=='__main__':
    if len(sys.argv)<2 or sys.argv[1] not in ('smoke','gate') or '--live' not in sys.argv:
        raise SystemExit('Only smoke/gate with --live supported; use workflow for offline actions')
    key=os.environ.get('OPENAI_API_KEY','').strip() or (dotenv_values(ROOT.parents[2]/'.env').get('OPENAI_API_KEY') or '').strip()
    if not key:raise SystemExit('BLOCKER: configured API credential absent')
    os.environ['OPENAI_API_KEY']=key
    import truststore
    truststore.inject_into_ssl()
    main()
