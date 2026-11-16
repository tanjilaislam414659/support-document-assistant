"""Read-only loading of the pinned serving corpus. Never loads reference questions."""
import json
from pathlib import Path

from .assets import git_blob, json_bytes, registry_assets, safe_path, sha256
from .ingestion import load_json, validate_existing_build
from .retrieval import BM25Retriever


SPEC_SHA256 = "1adf214bea9290dd789e030fa62d381683d55c3e7dd58f42cd8f9c449a19ed2d"


def load_bm25(root: Path) -> BM25Retriever:
    root = Path(root).resolve()
    spec_bytes = safe_path(root, "config/retrieval.json").read_bytes()
    if sha256(spec_bytes) != SPEC_SHA256:
        raise ValueError("Fixed retrieval specification changed; no runtime parameter override")
    spec = json.loads(spec_bytes)
    expected = spec["corpus"]
    pointer = load_json(safe_path(root, "data/processed/current.json"))
    if (pointer.get("build_id") != expected["build_id"] or
            pointer.get("manifest_sha256") != expected["manifest_sha256"]):
        raise ValueError("Serving pointer does not match the pinned retrieval corpus")
    folder = validate_existing_build(root, pointer)
    build = load_json(folder / "manifest.json")
    if set(build["artifacts"]) != {"chunks.jsonl", "exclusions.json", "report.json"}:
        raise ValueError("Incomplete serving build")
    if sha256(json_bytes(build["inputs"])) != expected["build_id"]:
        raise ValueError("Serving build identity mismatch")
    if build["artifacts"]["chunks.jsonl"] != expected["chunks_sha256"]:
        raise ValueError("Serving chunk identity mismatch")
    registry_bytes = safe_path(root, "config/sources.json").read_bytes()
    if sha256(registry_bytes) != build["inputs"]["registry_sha256"]:
        raise ValueError("Source registry changed")
    registry = json.loads(registry_bytes)
    chunking = load_json(safe_path(root, "config/chunking.json"))
    exclusions = load_json(safe_path(root, "config/source-exclusions.json"))
    if sha256(json_bytes({"policy": chunking, "exclusions": exclusions})) != build["inputs"]["policy_sha256"]:
        raise ValueError("Chunking/exclusion policy changed")
    assets = registry_assets(registry)
    asset_manifest = load_json(safe_path(root, "data/assets.json"))
    records = {a["asset_id"]: a for a in asset_manifest["assets"]}
    if (len(records) != len(asset_manifest["assets"]) or set(records) != {a["asset_id"] for a in assets} or
            asset_manifest["commit"] != registry["commit"] or set(records) != set(build["inputs"]["assets"])):
        raise ValueError("Asset manifest identity mismatch")
    raw_text = {}
    for asset in assets:
        record = records[asset["asset_id"]]
        for key in ("role", "local_path", "path", "download_url", "immutable_url", "git_blob_sha1"):
            if record[key] != asset[key]:
                raise ValueError("Asset provenance changed")
        path = safe_path(root, asset["local_path"])
        if path.stat().st_size > chunking["max_asset_bytes"]:
            raise ValueError("Cached asset exceeds byte limit")
        raw = path.read_bytes()
        digest = sha256(raw)
        if (git_blob(raw) != asset["git_blob_sha1"] or digest != record["sha256"] or
                digest != build["inputs"]["assets"][asset["asset_id"]] or len(raw) != record["byte_count"]):
            raise ValueError(f"Cached asset integrity failed: {asset['asset_id']}")
        if asset["role"] == "corpus":
            raw_text[asset["asset_id"]] = raw.decode("utf-8")
    sources = {s["source_id"]: s for s in registry["sources"]}
    if len(sources) != expected["source_count"] or len(raw_text) != expected["source_count"]:
        raise ValueError("Retrieval source count changed")
    chunk_bytes = (folder / "chunks.jsonl").read_bytes()
    if sha256(chunk_bytes) != expected["chunks_sha256"]:
        raise ValueError("Serving chunks changed during loading")
    chunks = [json.loads(line) for line in chunk_bytes.decode("utf-8").splitlines()]
    if len(chunks) != expected["chunk_count"]:
        raise ValueError("Retrieval chunk count changed")
    for chunk in chunks:
        source_id = chunk.get("source_id")
        if source_id not in sources:
            raise ValueError("Chunk is not from an approved corpus source")
        source = sources[source_id]
        fields = {"commit": registry["commit"], "product_version": source["product_version"],
                  "immutable_url": source["immutable_url"], "source_path": source["path"],
                  "source_git_blob_sha1": source["git_blob_sha1"],
                  "source_sha256": records[source_id]["sha256"],
                  "policy_sha256": build["inputs"]["policy_sha256"],
                  "parser_version": chunking["parser_version"], "eligible_for_answer_support": True}
        if any(chunk.get(key) != value for key, value in fields.items()):
            raise ValueError("Chunk source/version/eligibility metadata mismatch")
        identity = {key: chunk[key] for key in ("source_id", "source_sha256", "policy_sha256",
                    "parser_version", "section_titles", "segments", "text_sha256")}
        if chunk["chunk_id"] != "chunk-" + sha256(json_bytes(identity)):
            raise ValueError("Stable chunk ID does not match its content identity")
        if not isinstance(chunk["text"], str) or chunk["character_count"] != len(chunk["text"]):
            raise ValueError("Invalid full chunk text")
        segments = chunk["segments"]
        if not segments:
            raise ValueError("Chunk has no source mappings")
        pieces = []
        for segment in segments:
            a, b = segment["source_char_range"]
            x, y = segment["chunk_char_range"]
            if not 0 <= a < b <= len(raw_text[source_id]) or not 0 <= x < y <= len(chunk["text"]):
                raise ValueError("Source segment outside text")
            piece = raw_text[source_id][a:b]
            if piece != chunk["text"][x:y]:
                raise ValueError("Chunk/source text mapping mismatch")
            pieces.append(piece)
            start, end = segment["source_lines"]
            for issue in exclusions["issues"]:
                if issue["source_id"] == source_id:
                    first, last = issue["lines"]
                    if max(start, first) <= min(end, last):
                        raise ValueError("Ineligible source lines cannot be searched")
        if "\n\n".join(pieces) != chunk["text"]:
            raise ValueError("Not all chunk text is accounted for by source mappings")
    return BM25Retriever(chunks, corpus_build_id=expected["build_id"])
