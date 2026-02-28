"""
network/protocol.py
Helpers TLV (Type-Length-Value) pour le transport TCP.
"""

from __future__ import annotations

import socket
import struct
from typing import Optional, Tuple


TYPE_PEER_LIST = 2
TYPE_CHAT_MESSAGE = 3
TYPE_PING = 4
TYPE_PONG = 5

_HEADER_STRUCT = struct.Struct("!BI")  # type:uint8, length:uint32


def encode_tlv(packet_type: int, payload: bytes) -> bytes:
    return _HEADER_STRUCT.pack(packet_type, len(payload)) + payload


def send_tlv(sock: socket.socket, packet_type: int, payload: bytes) -> None:
    sock.sendall(encode_tlv(packet_type, payload))


def _recv_exact(sock: socket.socket, length: int) -> Optional[bytes]:
    chunks = []
    remaining = length
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def recv_tlv(sock: socket.socket) -> Optional[Tuple[int, bytes]]:
    header = _recv_exact(sock, _HEADER_STRUCT.size)
    if header is None:
        return None
    packet_type, payload_length = _HEADER_STRUCT.unpack(header)
    payload = _recv_exact(sock, payload_length)
    if payload is None:
        return None
    return packet_type, payload
