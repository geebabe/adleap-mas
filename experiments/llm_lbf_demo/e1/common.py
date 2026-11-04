"""Stable serialization and protocol constants. No model or simulator dependency."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARSER_VERSION = 'e1-parser-1'
ORACLE_VERSION = 'e1-oracle-1'
PROTOCOL_VERSION = 'e1-offline-1'
TOLERANCE = 1e-9


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())
