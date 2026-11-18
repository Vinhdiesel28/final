"""Load optional local credentials; deployment environment always takes precedence."""
import json
import os
from pathlib import Path

def load_local():
    env_path=Path(__file__).resolve().parents[1]/'.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
            key,value=line.split('=',1)
            os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))
    path = Path(__file__).resolve().parents[1] / '.local_config.json'
    if path.exists():
        for key, value in json.loads(path.read_text()).items():
            os.environ.setdefault(key, str(value))

load_local()
