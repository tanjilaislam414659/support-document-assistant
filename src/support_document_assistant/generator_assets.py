"""Pinned Qwen-only assets and runtime checks. Never imports dense model code."""
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request

from .assets import git_blob, json_bytes, safe_path, save_once, sha256


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def memory_available():
    class Status(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in
            ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "extended")]
    if os.name != "nt":
        return {"available_ram_bytes": None, "available_commit_bytes": None}
    status = Status()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    return {"system_ram_bytes": status.total_phys, "available_ram_bytes": status.avail_phys,
            "available_commit_bytes": status.avail_page}


def settings(root):
    root = Path(root)
    config = json.loads((root / "config/generation.json").read_bytes())
    for path, digest in config["frozen_runtime_files"].items():
        if file_sha256(safe_path(root, path)) != digest:
            raise ValueError(f"Frozen generator runtime input changed: {path}")
    deps = json.loads((root / "config/generator-dependencies.json").read_bytes())
    for name, version in deps["packages"].items():
        if importlib.metadata.version(name) != version:
            raise ValueError(f"Generator dependency version changed: {name}")
    return config


def verify_preserved(root):
    root = Path(root)
    saved = json.loads((root / "evaluation/milestone4-preserved-inputs.json").read_bytes())
    for path, digest in saved["files"].items():
        if file_sha256(safe_path(root, path)) != digest:
            raise ValueError(f"Previous milestone artifact changed: {path}")
    return len(saved["files"])


def model_directory(root, *, weights=True):
    root = Path(root)
    inventory = json.loads((root / "config/generator-model.json").read_bytes())
    directory = safe_path(root, inventory["local_directory"])
    for record in inventory["files"]:
        if not weights and record["path"] == "model.safetensors":
            continue
        path = safe_path(directory, record["path"])
        if not path.is_file() or path.stat().st_size != record["bytes"] or file_sha256(path) != record["sha256"]:
            raise ValueError(f"Qwen artifact unavailable or corrupt: {record['path']}")
    return directory


def acquire(root):
    root = Path(root)
    config = settings(root)
    inventory = json.loads((root / config["model_inventory"]).read_bytes())
    directory = safe_path(root, inventory["local_directory"])
    directory.mkdir(parents=True, exist_ok=True)
    record_path = root / "reports/model-acquisition/qwen25-15b-v1.json"
    if record_path.exists():
        model_directory(root)
        return json.loads(record_path.read_bytes())
    required = sum(r["bytes"] for r in inventory["files"] if not (directory / r["path"]).exists())
    free = shutil.disk_usage(root).free
    if free < required + 512 * 1024 * 1024:
        raise OSError(f"Insufficient project disk: need {required} bytes plus 512 MiB, free {free}")
    start = time.perf_counter()
    resources = memory_available()
    downloaded = []
    for record in inventory["files"]:
        path = safe_path(directory, record["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.stat().st_size != record["bytes"] or file_sha256(path) != record["sha256"]:
                raise ValueError(f"Conflicting Qwen artifact: {record['path']}")
            continue
        partial = path.with_name(path.name + ".part")
        digest, count, last_notice = hashlib.sha256(), 0, 0
        with partial.open("xb") as stream:
            with urllib.request.urlopen(record["url"], timeout=60) as response:
                if not response.geturl().startswith("https://"):
                    raise ValueError("Acquisition left HTTPS")
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > record["bytes"]:
                        raise ValueError("Download exceeds audited byte count")
                    digest.update(block)
                    stream.write(block)
                    if count - last_notice >= 256 * 1024 * 1024:
                        print(f"Acquiring {record['path']}: {count}/{record['bytes']} bytes", flush=True)
                        last_notice = count
        if count != record["bytes"] or digest.hexdigest() != record["sha256"]:
            raise ValueError("Qwen download checksum mismatch; partial preserved")
        if "lfs" not in record and git_blob(partial.read_bytes()) != record["git_blob_sha1"]:
            raise ValueError("Qwen Git blob identity mismatch")
        os.replace(partial, path)
        downloaded.append({"path": record["path"], "bytes": count, "sha256": digest.hexdigest()})
    model_directory(root)
    result = {"model_id": config["model_id"], "revision": config["model_revision"],
              "acquired_utc": datetime.now(timezone.utc).isoformat(), "downloaded": downloaded,
              "selected_file_count": len(inventory["files"]), "selected_total_bytes": inventory["selected_total_bytes"],
              "weight_format": "safetensors only", "license": inventory["license"],
              "acquisition_seconds": time.perf_counter() - start,
              "resources_before": resources, "project_disk_free_before_bytes": free,
              "project_disk_free_after_bytes": shutil.disk_usage(root).free}
    save_once(record_path, json_bytes(result))
    return result
