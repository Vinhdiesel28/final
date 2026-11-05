"""Load optional local credentials; deployment environment always takes precedence."""
import json
import os
from pathlib import Path

def load_local():
    path = Path(__file__).resolve().parents[1] / '.local_config.json'
    if path.exists():
        for key, value in json.loads(path.read_text()).items():
            os.environ.setdefault(key, str(value))

load_local()
