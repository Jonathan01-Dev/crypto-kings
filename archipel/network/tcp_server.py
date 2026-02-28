"""
network/tcp_server.py
Serveur TCP avec TLV + keep-alive ping/pong.
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable

from config import KEEPALIVE_INTERVAL, KEEPALIVE_TIMEOUT, TCP_MAX_CONNECTIONS
from network.protocol import TYPE_PING, TYPE_PONG, recv_tlv, send_tlv


PacketHandler = Callable[[int, bytes, tuple[str, int], socket.socket], None]


class TCPServer:
    def __init__(self, host: str, port: int, handler: PacketHandler):
        self.host = host
        self.port = port
        self.handler = handler
        self.running = False
        self._server_socket: socket.socket | None = None

    def start(self) -> None:
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self.running = False
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except Exception:
                pass

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            self._server_socket = server
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(TCP_MAX_CONNECTIONS)
            server.settimeout(1.0)

            while self.running:
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        with conn:
            conn.settimeout(1.0)
            last_ping = time.time()
            last_pong = time.time()

            while self.running:
                now = time.time()
                if now - last_ping >= KEEPALIVE_INTERVAL:
                    try:
                        send_tlv(conn, TYPE_PING, b"")
                        last_ping = now
                    except Exception:
                        return

                if now - last_pong > KEEPALIVE_TIMEOUT:
                    return

                try:
                    packet = recv_tlv(conn)
                except socket.timeout:
                    continue
                except Exception:
                    return

                if packet is None:
                    return

                packet_type, payload = packet
                if packet_type == TYPE_PING:
                    try:
                        send_tlv(conn, TYPE_PONG, b"")
                    except Exception:
                        return
                    continue
                if packet_type == TYPE_PONG:
                    last_pong = time.time()
                    continue

                print(f"[TCP] packet type={packet_type} from {addr[0]}:{addr[1]}")
                self.handler(packet_type, payload, addr, conn)
