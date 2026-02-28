"""
config.py
Configuration reseau et parametres globaux pour Archipel (Sprint 1).
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> dict[str, str]:
    env_path = Path(__file__).resolve().parent / ".env"
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_DOTENV = _load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, _DOTENV.get(name))
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, _DOTENV.get(name, default))


MULTICAST_GROUP = _get_str("ARCHIPEL_MULTICAST_GROUP", "239.255.42.99")
MULTICAST_PORT = _get_int("ARCHIPEL_MULTICAST_PORT", 6000)
TCP_PORT = _get_int("ARCHIPEL_TCP_PORT", 7777)
ANNOUNCE_INTERVAL = _get_int("ARCHIPEL_ANNOUNCE_INTERVAL", 30)
PEER_TIMEOUT = _get_int("ARCHIPEL_PEER_TIMEOUT", 90)
DISCOVERY_WAIT_SECONDS = _get_int("ARCHIPEL_DISCOVERY_WAIT", 3)
KEEPALIVE_INTERVAL = _get_int("ARCHIPEL_KEEPALIVE_INTERVAL", 15)
KEEPALIVE_TIMEOUT = _get_int("ARCHIPEL_KEEPALIVE_TIMEOUT", 45)
TCP_MAX_CONNECTIONS = _get_int("ARCHIPEL_TCP_MAX_CONNECTIONS", 10)
PEER_TABLE_PATH = _get_str("ARCHIPEL_PEER_TABLE_PATH", "peer_table.json")
TRUST_STORE_PATH = _get_str("ARCHIPEL_TRUST_STORE_PATH", "trust_store.json")
