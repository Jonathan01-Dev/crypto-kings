"""
main.py
Point d'entree du programme Archipel.
"""

import os
import time
import uuid

from cli.commands import CLI
from config import SHARED_AES_KEY
from crypto.keys import KeyManager
from messaging.chat import Chat
from network.discovery import PeerDiscovery
from network.peer_table import PeerTable
from network.tcp_server import TCPServer
from transfer.chunker import Chunker
from transfer.downloader import Downloader


def main():
    args = CLI().parse()
    if not args.command:
        print("Aucune commande donnee. Utilise: start | peers | msg | send | download")
        return

    peer_id = str(uuid.uuid4())
    peer_table = PeerTable()

    def add_peer_to_table(discovered_peer_id, ip, port):
        peer_table.add_peer(discovered_peer_id, ip, port)

    discovery = PeerDiscovery(peer_id, args.port, on_peer=add_peer_to_table)
    chat = Chat(SHARED_AES_KEY)
    chunker = Chunker()
    downloader = Downloader("received_file")

    key_manager = KeyManager()
    if os.path.exists(key_manager.priv_path) and os.path.exists(key_manager.pub_path):
        key_manager.load_keys()
    else:
        key_manager.generate_keys()

    def handle_packet(data, addr):
        try:
            msg = chat.receive_message(data)
            print(f"Message recu de {addr}: {msg}")
        except Exception:
            print(f"Paquet non reconnu de {addr}")

    server = TCPServer("0.0.0.0", args.port, handle_packet)

    discovery.start()
    server.start()

    if args.command == "start":
        print(f"Noeud demarre sur le port {args.port} avec ID: {peer_id}")
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

    wait_seconds = max(0, args.wait)
    if wait_seconds:
        time.sleep(wait_seconds)

    if args.command == "peers":
        peers = peer_table.get_peers()
        if not peers:
            print("Aucun pair detecte.")
        else:
            print("Pairs connus:")
            for known_peer_id, info in peers.items():
                print(f"- {known_peer_id} @ {info['ip']}:{info['port']}")

    elif args.command == "msg":
        peer = peer_table.get_peer(args.peer_id)
        if peer:
            chat.send_message(args.message, peer["ip"], peer["port"])
            print(f"Message envoye a {args.peer_id}")
        else:
            print("Pair inconnu. Lance d'abord: python main.py peers")

    elif args.command == "send":
        peer = peer_table.get_peer(args.peer_id)
        if peer:
            for chunk in chunker.chunk_file(args.file):
                chat.send_message(chunk.hex(), peer["ip"], peer["port"])
            print(f"Fichier envoye a {args.peer_id}")
        else:
            print("Pair inconnu. Lance d'abord: python main.py peers")

    elif args.command == "download":
        print("Telechargement non implemente (prototype)")
        _ = downloader

    discovery.stop()
    server.stop()


if __name__ == "__main__":
    main()
