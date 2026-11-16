"""Reproducible ingestion orchestration; this module never reads evaluation questions."""
import json
import os
from pathlib import Path
import re
import uuid

from .assets import acquire, json_bytes, safe_path, save_once, sha256
from .chunking import chunk_source


def load_json(path):
    return json.loads(path.read_bytes())


def validate_policy(policy):
    if policy["parser_version"] != "conservative-rst-v1" or policy["overlap_characters"] != 0:
        raise ValueError("Unsupported parser/overlap policy")
    if not 0 < policy["target_characters"] <= policy["max_atomic_characters"]:
        raise ValueError("Invalid chunk size policy")
    for name in ("max_corpus_bytes", "max_asset_bytes", "max_chunks"):
        if policy[name] <= 0:
            raise ValueError("Invalid resource limit")


def verify_quality_audit(root, registry, exclusions):
    assets = {a["asset_id"]: a for a in registry["supporting_assets"]}
    for issue in exclusions["issues"]:
        audit = assets[issue["audit_asset_id"]]
        if audit["role"] != "audit_only":
            raise ValueError("Source-quality audit must not become corpus evidence")
        a, b = issue["audit_lines"]
        text = safe_path(root, audit["local_path"]).read_text(encoding="utf-8").splitlines()
        if not 1 <= a <= b <= len(text):
            raise ValueError("Audit evidence outside source")
        if issue["issue_id"] == "stale-distutils":
            passage = "\n".join(text[a - 1:b])
            if "Remove the :py:mod:`!distutils` package" not in passage:
                raise ValueError("Pinned audit does not confirm distutils removal")


def validate_existing_build(root, pointer):
    if not re.fullmatch(r"[0-9a-f]{64}", pointer["build_id"]):
        raise ValueError("Invalid current build ID")
    folder = safe_path(root, f"data/processed/{pointer['build_id']}")
    manifest_bytes = (folder / "manifest.json").read_bytes()
    if sha256(manifest_bytes) != pointer["manifest_sha256"]:
        raise ValueError("Current build manifest was changed")
    manifest = json.loads(manifest_bytes)
    if manifest["build_id"] != pointer["build_id"]:
        raise ValueError("Current build identity mismatch")
    for name, digest in manifest["artifacts"].items():
        if name not in ("chunks.jsonl", "exclusions.json", "report.json"):
            raise ValueError("Unexpected build artifact")
        if sha256((folder / name).read_bytes()) != digest:
            raise ValueError(f"Current build artifact was changed: {name}")
    return folder


def ingest(root, fetch=False, fetcher=None):
    root = Path(root).resolve()
    data_dir = safe_path(root, "data")
    data_dir.mkdir(exist_ok=True)
    lock = data_dir / ".ingestion.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError("Ingestion lock exists; inspect concurrent/stale run before removing it") from exc
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()))
        return _ingest_locked(root, fetch, fetcher)
    finally:
        lock.unlink()


def _ingest_locked(root, fetch, fetcher):
    registry = load_json(root / "config/sources.json")
    policy = load_json(root / "config/chunking.json")
    exclusions = load_json(root / "config/source-exclusions.json")
    validate_policy(policy)
    pointer_path = safe_path(root, "data/processed/current.json")
    old_pointer = load_json(pointer_path) if pointer_path.exists() else None
    if old_pointer:
        validate_existing_build(root, old_pointer)
    manifest = acquire(root, registry, policy, fetch=fetch, fetcher=fetcher)
    verify_quality_audit(root, registry, exclusions)
    policy_hash = sha256(json_bytes({"policy": policy, "exclusions": exclusions}))
    implementation = {name: sha256(Path(__file__).with_name(name).read_bytes())
                      for name in ("assets.py", "chunking.py", "ingestion.py")}
    inputs = {"assets": {a["asset_id"]: a["sha256"] for a in manifest["assets"]},
              "registry_sha256": sha256((root / "config/sources.json").read_bytes()),
              "policy_sha256": policy_hash, "implementation_sha256": implementation}
    build_id = sha256(json_bytes(inputs))
    chunks, omitted, per_source = [], [], []
    for source in registry["sources"]:
        raw = safe_path(root, source["local_path"]).read_bytes()
        source_chunks, source_omissions = chunk_source(raw, source, policy, exclusions["issues"], policy_hash)
        for chunk in source_chunks:
            chunk["commit"] = registry["commit"]
            chunk["license"] = source["license"]
            chunk["notice_paths"] = [a["local_path"] for a in registry["supporting_assets"] if a["role"] == "notice"]
        chunks.extend(source_chunks)
        omitted.extend(source_omissions)
        per_source.append({"source_id": source["source_id"], "raw_bytes": len(raw),
                           "chunks": len(source_chunks), "exclusions": len(source_omissions)})
    if len(chunks) > policy["max_chunks"]:
        raise ValueError("Chunk count exceeds budget; no truncated output will be served")
    if len({c["chunk_id"] for c in chunks}) != len(chunks):
        raise ValueError("Chunk identity collision")
    report = {"schema_version": 1, "build_id": build_id, "corpus_documents": len(per_source),
              "corpus_bytes": sum(s["raw_bytes"] for s in per_source),
              "assets": len(manifest["assets"]), "chunks": len(chunks),
              "over_target_atomic_chunks": sum(c["over_target_atomic"] for c in chunks),
              "max_chunk_characters": max((c["character_count"] for c in chunks), default=0),
              "exclusions": len(omitted), "per_source": per_source,
              "unresolved_includes": [o for o in omitted if o["reason"] == "unresolved_include"],
              "audit_assets_served": 0, "overlap_characters": policy["overlap_characters"],
              "limitations": ["Conservative inert RST, not full Sphinx rendering.",
                              "Unresolved includes may omit platform-availability caveats.",
                              "No semantic correctness or human evidence approval inferred."]}
    artifacts = {"chunks.jsonl": b"".join(json_bytes(c).replace(b"\n", b"") + b"\n" for c in chunks),
                 "exclusions.json": json_bytes(omitted), "report.json": json_bytes(report)}
    folder = safe_path(root, f"data/processed/{build_id}")
    for name, content in artifacts.items():
        save_once(folder / name, content)
    build_manifest = {"schema_version": 1, "build_id": build_id, "inputs": inputs,
                      "artifacts": {name: sha256(content) for name, content in artifacts.items()}}
    manifest_bytes = json_bytes(build_manifest)
    save_once(folder / "manifest.json", manifest_bytes)
    pointer = {"build_id": build_id, "manifest_sha256": sha256(manifest_bytes)}
    validate_existing_build(root, pointer)
    if old_pointer != pointer:
        temp = pointer_path.with_name(f".current-{uuid.uuid4().hex}.tmp")
        save_once(temp, json_bytes(pointer))
        os.replace(temp, pointer_path)
    return report


def current_chunks(root):
    root = Path(root)
    pointer = load_json(root / "data/processed/current.json")
    folder = validate_existing_build(root, pointer)
    return [json.loads(line) for line in (folder / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
