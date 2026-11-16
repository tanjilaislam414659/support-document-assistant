"""Allowlisted acquisition and byte-level integrity. No crawling or directive execution."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import __version__


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def safe_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise ValueError(f"Path escapes project: {relative}")
    return path


def save_once(path, data):
    """Never overwrite a conflicting raw or content-addressed artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Integrity conflict: {path}")
        return
    with path.open("xb") as stream:
        stream.write(data)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Acquisition redirects are not allowed")


def download(url, max_bytes):
    request = Request(url, headers={"User-Agent": f"SupportDocumentAssistant/{__version__}"})
    with build_opener(NoRedirect).open(request, timeout=30) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Asset exceeds byte limit")
    return data


def registry_assets(registry):
    commit = registry["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid pinned commit")
    if registry["repository"] != "https://github.com/python/cpython":
        raise ValueError("Only the approved CPython repository is allowed")
    sources = registry["sources"]
    if len(sources) != 4:
        raise ValueError("The retrieval corpus must remain exactly four documents")
    assets = []
    for source in sources:
        assets.append({**source, "asset_id": source["source_id"]})
    assets.extend(registry["supporting_assets"])
    ids, paths = set(), set()
    for asset in assets:
        if asset["asset_id"] in ids or asset["local_path"] in paths:
            raise ValueError("Duplicate asset identity/path")
        ids.add(asset["asset_id"])
        paths.add(asset["local_path"])
        role = asset["role"]
        expected_prefix = {"corpus": "data/raw/", "notice": "data/notices/",
                           "audit_only": "data/audit/"}.get(role)
        if expected_prefix is None or not asset["local_path"].startswith(expected_prefix):
            raise ValueError("Asset path does not match its role")
        if not re.fullmatch(r"[0-9a-f]{40}", asset["git_blob_sha1"]):
            raise ValueError("Missing upstream Git blob identity")
        expected_url = f"https://raw.githubusercontent.com/python/cpython/{commit}/{asset['path']}"
        if asset["download_url"] != expected_url or ".." in asset["path"].split("/"):
            raise ValueError("Asset URL is outside the pinned allowlist")
        if asset["immutable_url"] != f"https://github.com/python/cpython/blob/{commit}/{asset['path']}":
            raise ValueError("Invalid immutable source URL")
    return assets


def acquire(root, registry, policy, fetch=False, fetcher=None):
    """Validate every cached byte; fetch missing allowlisted assets only on explicit opt-in."""
    assets = registry_assets(registry)
    manifest_path = safe_path(root, "data/assets.json")
    previous = json.loads(manifest_path.read_bytes()) if manifest_path.exists() else None
    old = {a["asset_id"]: a for a in previous["assets"]} if previous else {}
    if previous and (previous["commit"] != registry["commit"] or set(old) != {a["asset_id"] for a in assets}):
        raise ValueError("Asset manifest scope changed; inspect and use a new corpus snapshot")
    records = []
    corpus_size = 0
    for asset in assets:
        path = safe_path(root, asset["local_path"])
        downloaded = False
        if not path.exists():
            if previous:
                raise ValueError(f"Cached asset missing: {asset['asset_id']}; refusing silent repair")
            if not fetch:
                raise ValueError(f"Missing asset: {asset['asset_id']}; first acquisition needs --fetch")
            data = (fetcher or download)(asset["download_url"], policy["max_asset_bytes"])
            downloaded = True
        else:
            data = path.read_bytes()
        if len(data) > policy["max_asset_bytes"] or git_blob(data) != asset["git_blob_sha1"]:
            raise ValueError(f"Raw integrity check failed: {asset['asset_id']}")
        text = data.decode("utf-8", errors="strict")
        if asset["role"] == "corpus":
            corpus_size += len(data)
        record = {key: asset[key] for key in ("asset_id", "path", "local_path", "role",
                                               "download_url", "immutable_url", "git_blob_sha1")}
        record.update(commit=registry["commit"], byte_count=len(data),
                      line_count=len(text.splitlines()), sha256=sha256(data))
        if previous:
            for key, value in record.items():
                if old[asset["asset_id"]].get(key) != value:
                    raise ValueError(f"Asset manifest mismatch: {asset['asset_id']} / {key}")
            record = old[asset["asset_id"]]
        else:
            record["acquired_at_utc"] = datetime.now(timezone.utc).isoformat() if downloaded else None
            record["acquisition"] = "immutable_https" if downloaded else "preexisting_bytes_verified"
        if downloaded:
            save_once(path, data)
        records.append(record)
    if corpus_size > policy["max_corpus_bytes"]:
        raise ValueError("Corpus exceeds byte budget")
    manifest = {"schema_version": 1, "commit": registry["commit"], "assets": records}
    save_once(manifest_path, json_bytes(manifest))
    return manifest
