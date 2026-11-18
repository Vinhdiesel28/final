"""Add one public web page to the local DiaGuard app's cloud KB snapshot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import settings


def write_atomic(path, text):
    staged = path.with_suffix(path.suffix + ".tmp")
    staged.write_text(text, encoding="utf-8")
    staged.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?")
    parser.add_argument("--prepare-only", action="store_true", help="Build locally for inspection")
    args = parser.parse_args()
    url = (args.url or input("Dan URL bai viet: ")).strip()
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        parser.error("Nhap URL HTTPS cong khai, khong kem thong tin dang nhap hoac #fragment.")
    host = parsed.hostname.removeprefix("www.")
    key = "web_" + re.sub(r"[^a-z0-9]+", "_", host) + "_" + hashlib.sha256(url.encode()).hexdigest()[:12]

    if os.environ.get("HYBRID_VECTOR_BACKEND") != "qdrant":
        parser.error("Can cau hinh HYBRID_VECTOR_BACKEND=qdrant trong .env.")
    config = ROOT / ".env"
    sources_path = ROOT / "knowledge/web_sources.json"
    sources = json.loads(sources_path.read_text(encoding="utf-8-sig"))
    source = next((item for item in sources if item["url"] == url), None)
    if source is None:
        source = {"id": key, "title": unquote(parsed.path.rstrip("/").split("/")[-1]).replace("-", " ") or host,
                  "organization": host.split(".")[0], "url": url,
                  "language": "vi" if "/vie/" in parsed.path else "und"}
        sources.append(source)

    output = ROOT / "tmp" / "web-import" / key
    output.mkdir(parents=True, exist_ok=True)
    pending = output / "web_sources.json"
    source_json = json.dumps(sources, ensure_ascii=False, indent=2) + "\n"
    write_atomic(pending, source_json)
    old_version = os.environ.get("HYBRID_KB_SNAPSHOT")
    candidates = [ROOT / "tmp/kb-upgrade-e5/kb_bundle.json", *(ROOT / "tmp/web-import").glob("*/kb_bundle.json")]
    previous = output / "kb_bundle.json"
    if not previous.is_file():
        previous = next((path for path in candidates if path.is_file()
                         and json.loads(path.read_text(encoding="utf-8"))["version"] == old_version), None)
    build = [sys.executable, str(ROOT / "tools/kb/build_hybrid_kb.py"), "--fetch-missing-web",
             "--web-sources", str(pending), "--semantic", "--output-dir", str(output)]
    if previous:
        build += ["--reuse-vectors", str(previous)]
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    os.environ.setdefault("MKL_NUM_THREADS", "4")
    subprocess.run(build, cwd=ROOT, check=True)
    bundle_path = output / "kb_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    ids = {d["id"] for d in bundle["documents"] if d["source_url"] == url and d["source_type"] == "web"}
    count = sum(c["document_id"] in ids for c in bundle["chunks"])
    if not count or bundle["errors"]:
        raise RuntimeError("Bản dựng thiếu nội dung web, chưa chuyển snapshot.")
    print(f"Web chunks: {count}\nBundle: {bundle_path}", flush=True)
    if args.prepare_only:
        return
    subprocess.run([sys.executable, str(ROOT / "tools/kb/stage_kb_snapshot.py"), str(bundle_path)],
                   cwd=ROOT, check=True)
    lines = config.read_text(encoding="utf-8-sig").splitlines() if config.exists() else []
    lines = [line for line in lines if not re.match(r"^\s*HYBRID_KB_SNAPSHOT\s*=", line)]
    write_atomic(sources_path, source_json)
    write_atomic(config, "\n".join(lines + [f"HYBRID_KB_SNAPSHOT={bundle['version']}"]) + "\n")
    print(f"Neo4j source_id: {source['id']}")
    print(f"Previous snapshot: {old_version or 'current'}")
    print("Da nap KB. Khoi dong lai web de dung snapshot moi.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
