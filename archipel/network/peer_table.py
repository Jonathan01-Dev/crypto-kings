"""
network/peer_table.py
Table de pairs en memoire + persistance disque.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict

from config import PEER_TABLE_PATH


class PeerTable:
    def __init__(self, storage_path: str = PEER_TABLE_PATH):
        self._path = Path(storage_path)
        self._lock = threading.Lock()
        self._peers: Dict[str, Dict[str, Any]] = {}
        self._load()

    def upsert_peer(
        self,
        node_id: str,
        ip: str,
        tcp_port: int,
        last_seen: float | None = None,
        shared_files: list[str] | None = None,
        reputation: float = 1.0,
    ) -> None:
        with self._lock:
            self._peers[node_id] = {
                "node_id": node_id,
                "ip": ip,
                "tcp_port": int(tcp_port),
                "port": int(tcp_port),
                "last_seen": float(last_seen if last_seen is not None else time.time()),
                "shared_files": list(shared_files or []),
                "reputation": float(reputation),
            }
            self._save_locked()

    # Compatibilite avec l'ancien code/tests.
    def add_peer(self, peer_id: str, ip: str, port: int) -> None:
        self.upsert_peer(peer_id, ip, port)

    def mark_seen(self, node_id: str, ip: str | None = None, tcp_port: int | None = None) -> None:
        with self._lock:
            peer = self._peers.get(node_id)
            if not peer:
                return
            if ip is not None:
                peer["ip"] = ip
            if tcp_port is not None:
                peer["tcp_port"] = int(tcp_port)
                peer["port"] = int(tcp_port)
            peer["last_seen"] = time.time()
            self._save_locked()

    def remove_peer(self, node_id: str) -> None:
        with self._lock:
            if node_id in self._peers:
                del self._peers[node_id]
                self._save_locked()

    def prune_stale(self, timeout_seconds: int) -> list[str]:
        now = time.time()
        removed: list[str] = []
        with self._lock:
            for node_id, peer in list(self._peers.items()):
                if now - float(peer.get("last_seen", now)) > timeout_seconds:
                    removed.append(node_id)
                    del self._peers[node_id]
            if removed:
                self._save_locked()
        return removed

    def get_peer(self, node_id: str) -> Dict[str, Any] | None:
        with self._lock:
            peer = self._peers.get(node_id)
            return dict(peer) if peer else None

    def get_peers(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {node_id: dict(info) for node_id, info in self._peers.items()}

    def as_list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(info) for info in self._peers.values()]

    def merge_peers(self, peers: list[dict[str, Any]], skip_node_id: str | None = None) -> None:
        for peer in peers:
            node_id = peer.get("node_id")
            if not node_id or node_id == skip_node_id:
                continue
            self.upsert_peer(
                node_id=node_id,
                ip=peer.get("ip", "0.0.0.0"),
                tcp_port=int(peer.get("tcp_port", peer.get("port", 0))),
                last_seen=float(peer.get("last_seen", time.time())),
                shared_files=peer.get("shared_files", []),
                reputation=float(peer.get("reputation", 1.0)),
            )

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for node_id, peer in data.items():
                    self._peers[node_id] = dict(peer)
        except Exception:
            self._peers = {}

    def _save_locked(self) -> None:
        self._path.write_text(
            json.dumps(self._peers, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
