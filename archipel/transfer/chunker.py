"""
transfer/chunker.py
Generation de manifest et lecture de chunks.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


CHUNK_SIZE = 512 * 1024  # 512 KB


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


class Chunker:
    def __init__(self, chunk_size: int = CHUNK_SIZE):
        self.chunk_size = chunk_size

    def iter_chunks(self, file_path: str):
        with open(file_path, "rb") as f:
            idx = 0
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                yield idx, chunk
                idx += 1

    def read_chunk(self, file_path: str, index: int) -> bytes:
        with open(file_path, "rb") as f:
            f.seek(index * self.chunk_size)
            return f.read(self.chunk_size)

    def build_manifest(self, file_path: str, sender_id: str) -> dict:
        path = Path(file_path)
        size = path.stat().st_size
        chunks = []
        for index, chunk in self.iter_chunks(str(path)):
            chunks.append({"index": index, "hash": sha256_bytes(chunk), "size": len(chunk)})
        manifest = {
            "file_id": file_sha256(str(path)),
            "filename": path.name,
            "size": size,
            "chunk_size": self.chunk_size,
            "nb_chunks": len(chunks),
            "chunks": chunks,
            "sender_id": sender_id,
        }
        return manifest
