"""
transfer/downloader.py
Index local + ecriture/reassemblage des chunks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class LocalIndex:
    def __init__(self, base_dir: str = ".archipel"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / "index.json"
        self.db = {"files": {}}
        if self.path.exists():
            try:
                self.db = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.db = {"files": {}}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.db, indent=2), encoding="utf-8")

    def upsert_manifest(self, manifest: dict, source_node_id: str | None = None) -> None:
        file_id = manifest["file_id"]
        meta = self.db["files"].setdefault(
            file_id,
            {
                "manifest": manifest,
                "providers": [],
                "available_chunks": [],
                "completed": False,
                "output_path": "",
            },
        )
        meta["manifest"] = manifest
        if source_node_id and source_node_id not in meta["providers"]:
            meta["providers"].append(source_node_id)
        self.save()

    def set_available_chunks(self, file_id: str, chunks: list[int]) -> None:
        if file_id in self.db["files"]:
            self.db["files"][file_id]["available_chunks"] = sorted(set(chunks))
            self.save()

    def mark_chunk(self, file_id: str, idx: int) -> None:
        if file_id not in self.db["files"]:
            return
        arr = set(self.db["files"][file_id].get("available_chunks", []))
        arr.add(idx)
        self.db["files"][file_id]["available_chunks"] = sorted(arr)
        self.save()

    def mark_complete(self, file_id: str, output_path: str) -> None:
        if file_id not in self.db["files"]:
            return
        self.db["files"][file_id]["completed"] = True
        self.db["files"][file_id]["output_path"] = output_path
        self.save()

    def get_manifest(self, file_id: str) -> dict | None:
        node = self.db["files"].get(file_id)
        if not node:
            return None
        return node.get("manifest")

    def add_provider(self, file_id: str, node_id: str) -> None:
        if file_id not in self.db["files"]:
            return
        providers = self.db["files"][file_id].setdefault("providers", [])
        if node_id not in providers:
            providers.append(node_id)
            self.save()

    def get_providers(self, file_id: str) -> list[str]:
        if file_id not in self.db["files"]:
            return []
        return list(self.db["files"][file_id].get("providers", []))

    def has_file(self, file_id: str) -> bool:
        entry = self.db["files"].get(file_id)
        return bool(entry and entry.get("completed"))


class ChunkStore:
    def __init__(self, base_dir: str = ".archipel/chunks"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _file_dir(self, file_id: str) -> Path:
        d = self.base_dir / file_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_chunk(self, file_id: str, index: int, data: bytes) -> None:
        path = self._file_dir(file_id) / f"{index:08d}.part"
        path.write_bytes(data)

    def read_chunk(self, file_id: str, index: int) -> bytes | None:
        path = self._file_dir(file_id) / f"{index:08d}.part"
        if not path.exists():
            return None
        return path.read_bytes()

    def available_chunks(self, file_id: str) -> list[int]:
        d = self._file_dir(file_id)
        out: list[int] = []
        for p in d.glob("*.part"):
            try:
                out.append(int(p.stem))
            except ValueError:
                continue
        return sorted(out)

    def assemble(self, file_id: str, manifest: dict, output_dir: str = "downloads") -> str:
        os.makedirs(output_dir, exist_ok=True)
        output_path = Path(output_dir) / manifest["filename"]
        with open(output_path, "wb") as out:
            for i in range(manifest["nb_chunks"]):
                chunk = self.read_chunk(file_id, i)
                if chunk is None:
                    raise RuntimeError(f"Chunk missing: {i}")
                out.write(chunk)
        return str(output_path)
