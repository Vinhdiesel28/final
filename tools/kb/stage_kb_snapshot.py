"""Publish a built KB bundle to a staged Neo4j/Qdrant snapshot."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import settings
from services.hybrid_kb import ingest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    try:
        ingest(bundle, activate=False)
    except Exception as exc:
        print(f"Staging failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(bundle["version"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
