"""
network/discovery.py
Decouverte de pairs via UDP multicast + reponse PEER_LIST en TCP unicast.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
import time

from config import ANNOUNCE_INTERVAL, MULTICAST_GROUP, MULTICAST_PORT, PEER_TIMEOUT
from network.peer_table import PeerTable
from network.protocol import TYPE_PEER_LIST, send_tlv


class PeerDiscovery:
    def __init__(self, node_id: str, tcp_port: int, peer_table: PeerTable):
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.peer_table = peer_table
        self.running = False

    def start(self) -> None:
        self.running = True
        threading.Thread(target=self._announce_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        threading.Thread(target=self._timeout_loop, daemon=True).start()

    def stop(self) -> None:
        self.running = False

    def _announce_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        ttl = struct.pack("b", 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        try:
            while self.running:
                pkt = {
                    "type": "HELLO",
                    "node_id": self.node_id,
                    "tcp_port": self.tcp_port,
                    "timestamp": int(time.time() * 1000),
                }
                payload = json.dumps(pkt).encode("utf-8")
                try:
                    sock.sendto(payload, (MULTICAST_GROUP, MULTICAST_PORT))
                    print(f"[DISCOVERY] HELLO sent node={self.node_id[:12]} tcp={self.tcp_port}")
                except Exception as exc:
                    print(f"[DISCOVERY] HELLO send error: {exc}")
                time.sleep(ANNOUNCE_INTERVAL)
        finally:
            sock.close()

    def _listen_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", MULTICAST_PORT))
        membership = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sock.settimeout(2.0)
        try:
            while self.running:
                try:
                    data, addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except Exception as exc:
                    print(f"[DISCOVERY] recv error: {exc}")
                    continue

                try:
                    pkt = json.loads(data.decode("utf-8"))
                except Exception:
                    continue

                if pkt.get("type") != "HELLO":
                    continue

                node_id = pkt.get("node_id")
                peer_tcp_port = int(pkt.get("tcp_port", 0))
                if not node_id or node_id == self.node_id or peer_tcp_port <= 0:
                    continue

                peer_ip = addr[0]
                self.peer_table.upsert_peer(node_id=node_id, ip=peer_ip, tcp_port=peer_tcp_port)
                print(f"[DISCOVERY] Peer seen {node_id[:12]} @ {peer_ip}:{peer_tcp_port}")
                self._reply_with_peer_list(peer_ip, peer_tcp_port)
        finally:
            sock.close()

    def _reply_with_peer_list(self, ip: str, port: int) -> None:
        packet = {
            "type": "PEER_LIST",
            "node_id": self.node_id,
            "peers": self.peer_table.as_list(),
            "timestamp": int(time.time() * 1000),
        }
        payload = json.dumps(packet).encode("utf-8")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                sock.connect((ip, port))
                send_tlv(sock, TYPE_PEER_LIST, payload)
        except Exception as exc:
            print(f"[DISCOVERY] PEER_LIST send error to {ip}:{port}: {exc}")

    def _timeout_loop(self) -> None:
        while self.running:
            removed = self.peer_table.prune_stale(PEER_TIMEOUT)
            for node_id in removed:
                print(f"[DISCOVERY] Peer timeout {node_id[:12]}")
            time.sleep(5)
