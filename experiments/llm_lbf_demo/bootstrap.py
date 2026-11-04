"""Fetch immutable upstream; never touch the parent checkout's src/."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
lock = json.loads((root / 'upstream.lock.json').read_text())
dest = root / 'vendor/adleap-mas'
if not dest.exists():
    subprocess.run(['git', 'clone', lock['url'], str(dest)], check=True)
subprocess.run(['git', '-C', str(dest), 'checkout', '--detach', lock['commit']], check=True)
