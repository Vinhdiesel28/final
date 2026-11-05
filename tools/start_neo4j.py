"""Create ignored local credentials and start the project Neo4j container."""
import json, os, secrets, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'.local_config.json'
if not path.exists():
    path.write_text(json.dumps({'NEO4J_PASSWORD':secrets.token_hex(20),
        'NEO4J_URI':'bolt://127.0.0.1:7687','KNOWLEDGE_BACKEND':'neo4j'}))
env=os.environ.copy(); env.update(json.loads(path.read_text()))
docker=r'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
subprocess.run([docker,'compose','up','-d'],cwd=ROOT,env=env,check=True)
print('Neo4j started. Credentials are in ignored .local_config.json.')
