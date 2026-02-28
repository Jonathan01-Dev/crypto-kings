"""
main.py
Point d'entree Archipel (Sprint 1: discovery + mesh networking).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from cli.commands import CLI
from config import DISCOVERY_WAIT_SECONDS
from network.discovery import PeerDiscovery
from network.peer_table import PeerTable
from network.protocol import TYPE_CHAT_MESSAGE, TYPE_PEER_LIST
from network.tcp_server import TCPServer


def _build_node_id(port: int) -> str:
    node_id_path = Path(f"node_id_{port}.txt")
    if node_id_path.exists():
        return node_id_path.read_text(encoding="utf-8").strip()
    node_id = hashlib.sha256(os.urandom(32)).hexdigest()
    node_id_path.write_text(node_id, encoding="utf-8")
    return node_id


def main() -> None:
    args = CLI().parse()
    if not args.command:
        print("Aucune commande donnee. Utilise: start | peers | msg | send | download")
        return

    node_id = _build_node_id(args.port)
    peer_table = PeerTable(storage_path=f"peer_table_{args.port}.json")

    def handle_packet(packet_type: int, payload: bytes, addr: tuple[str, int]) -> None:
        if packet_type == TYPE_PEER_LIST:
            try:
                packet = json.loads(payload.decode("utf-8"))
                peers = packet.get("peers", [])
                peer_table.merge_peers(peers, skip_node_id=node_id)
                print(f"[TCP] PEER_LIST recu de {addr[0]}:{addr[1]} ({len(peers)} peers)")
            except Exception as exc:
                print(f"[TCP] PEER_LIST invalide: {exc}")
            return

        if packet_type == TYPE_CHAT_MESSAGE:
            try:
                msg = payload.decode("utf-8")
                print(f"[TCP] Message recu de {addr[0]}:{addr[1]}: {msg}")
            except Exception:
                print(f"[TCP] Message non decode de {addr[0]}:{addr[1]}")
            return

        print(f"[TCP] Packet type inconnu={packet_type} depuis {addr[0]}:{addr[1]}")

    server = TCPServer("0.0.0.0", args.port, handle_packet)
    discovery = PeerDiscovery(node_id=node_id, tcp_port=args.port, peer_table=peer_table)

    discovery.start()
    server.start()

    if args.command == "start":
        print(f"Noeud demarre: node_id={node_id[:16]}... tcp_port={args.port}")
        print("Ctrl+C pour arreter.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nArret du noeud...")
        finally:
            discovery.stop()
            server.stop()
        return

    wait_seconds = max(0, getattr(args, "wait", DISCOVERY_WAIT_SECONDS))
    if wait_seconds:
        time.sleep(wait_seconds)

    if args.command == "peers":
        peers = peer_table.get_peers()
        if not peers:
            print("Aucun pair detecte.")
        else:
            print("Peer table:")
            for peer_id, peer in peers.items():
                print(
                    f"- node_id={peer_id[:16]}... ip={peer['ip']} tcp_port={peer['tcp_port']} "
                    f"last_seen={int(peer['last_seen'])}"
                )

    elif args.command == "msg":
        print("Sprint 1: commande msg non activee (transport chat finalise au Sprint 2).")

    elif args.command == "send":
        print("Sprint 1: commande send non activee (transfer finalise au Sprint 3).")

    elif args.command == "download":
        print("Sprint 1: commande download non activee.")

    discovery.stop()
    server.stop()


if __name__ == "__main__":
    main()
