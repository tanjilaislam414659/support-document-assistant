"""Read-only portable serving bundle; no ingestion, network, models or references."""
from pathlib import Path
import hashlib,json
from ._frozen_core.retrieval import BM25Retriever
from .corpus import Corpus,digest

RESOURCES=Path(__file__).with_name("resources")

def load_bundle(directory=None):
    root=Path(directory) if directory is not None else RESOURCES/"corpus"
    root=root.resolve()
    manifest=root/"bundle.json"
    if digest(manifest)!=(RESOURCES/"bundle.sha256").read_text(encoding="ascii").strip():
        raise ValueError("Portable corpus manifest identity mismatch")
    m=json.loads(manifest.read_bytes());watched={manifest:digest(manifest)}
    for name,record in m["files"].items():
        path=(root/name).resolve()
        if not path.is_relative_to(root) or path.is_symlink():raise ValueError("Unsafe bundle path")
        if path.stat().st_size!=record["bytes"] or digest(path)!=record["sha256"]:
            raise ValueError("Portable corpus artifact identity mismatch")
        watched[path]=record["sha256"]
    registry=json.loads((root/"config/sources.json").read_bytes())
    source_records={};metadata={}
    for s in registry["sources"]:
        raw=(root/s["local_path"]).read_bytes()
        source_records[s["source_id"]]={"text":raw.decode("utf-8"),"source_id":s["source_id"],
            "source_path":s["path"],"product_version":s["product_version"],"commit":registry["commit"],
            "immutable_url":s["immutable_url"],"source_sha256":hashlib.sha256(raw).hexdigest()}
        metadata[s["source_id"]]=s
    chunks=[json.loads(line) for line in (root/"serving/chunks.jsonl").read_bytes().splitlines()]
    if len(chunks)!=m["chunk_count"] or len(source_records)!=m["source_count"]:
        raise ValueError("Portable corpus count mismatch")
    return Corpus(BM25Retriever(chunks,corpus_build_id=m["build_id"]),chunks,source_records,metadata,watched)
