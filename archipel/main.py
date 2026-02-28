"""
main.py
Sprint 2: chiffrement E2E et authentification sans CA.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

from cli.commands import CLI
from config import DISCOVERY_WAIT_SECONDS, TRUST_STORE_PATH
from cryptography.hazmat.primitives.asymmetric import x25519
from crypto.secure_channel import (
    Identity,
    TrustStore,
    b64d,
    b64e,
    canonical_json,
    compute_hmac,
    decrypt_message,
    encrypt_message,
    generate_ephemeral_x25519,
    hkdf_session_keys,
    sha256,
    sign_dict,
    verify_hmac,
    verify_signature,
)
from network.discovery import PeerDiscovery
from network.peer_table import PeerTable
from network.protocol import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_HELLO,
    TYPE_HELLO_REPLY,
    TYPE_MSG,
    TYPE_PEER_LIST,
    recv_tlv,
    send_tlv,
)
from network.tcp_server import TCPServer


def _handshake_context_hash(a_node: str, b_node: str, a_eph_pub: bytes, b_eph_pub: bytes) -> bytes:
    context = {
        "a_node": a_node,
        "b_node": b_node,
        "a_eph": b64e(a_eph_pub),
        "b_eph": b64e(b_eph_pub),
    }
    return sha256(canonical_json(context))


def _init_identity(port: int) -> Identity:
    identity = Identity(
        private_path=f"identity_ed25519_{port}.pem",
        public_path=f"identity_ed25519_{port}.pub.pem",
    )
    identity.load_or_create()
    return identity


def main() -> None:
    args = CLI().parse()
    if not args.command:
        print("Aucune commande donnee. Utilise: start | peers | msg | send | download")
        return

    identity = _init_identity(args.port)
    node_id = identity.node_id
    peer_table = PeerTable(storage_path=f"peer_table_{args.port}.json")
    trust_store = TrustStore(path=f"{Path(TRUST_STORE_PATH).stem}_{args.port}.json")

    lock = threading.Lock()
    pending_handshakes: dict[int, dict] = {}
    sessions_by_conn: dict[int, dict] = {}

    def handle_packet(packet_type: int, payload: bytes, addr: tuple[str, int], conn: socket.socket) -> None:
        conn_id = conn.fileno()

        if packet_type == TYPE_PEER_LIST:
            try:
                packet = json.loads(payload.decode("utf-8"))
                peers = packet.get("peers", [])
                peer_table.merge_peers(peers, skip_node_id=node_id)
                print(f"[TCP] PEER_LIST recu de {addr[0]}:{addr[1]} ({len(peers)} peers)")
            except Exception as exc:
                print(f"[TCP] PEER_LIST invalide: {exc}")
            return

        if packet_type == TYPE_HELLO:
            try:
                hello = json.loads(payload.decode("utf-8"))
                peer_node_id = hello["node_id"]
                peer_identity_pub = b64d(hello["identity_pub"])
                peer_eph_pub = b64d(hello["e_pub"])

                if peer_node_id != peer_identity_pub.hex():
                    return
                if not trust_store.check_or_trust(peer_node_id, peer_identity_pub):
                    print(f"[SEC] TOFU mismatch from {addr[0]}:{addr[1]}")
                    return

                b_priv, b_pub = generate_ephemeral_x25519()
                shared = b_priv.exchange(x25519.X25519PublicKey.from_public_bytes(peer_eph_pub))
                shared_hash = _handshake_context_hash(peer_node_id, node_id, peer_eph_pub, b_pub)

                hello_reply = {
                    "type": "HELLO_REPLY",
                    "node_id": node_id,
                    "identity_pub": b64e(identity.public_key_raw()),
                    "e_pub": b64e(b_pub),
                    "timestamp": int(time.time() * 1000),
                    "hello_hash": b64e(shared_hash),
                }
                hello_reply["signature"] = sign_dict(identity, hello_reply)

                with lock:
                    pending_handshakes[conn_id] = {
                        "peer_node_id": peer_node_id,
                        "peer_identity_pub": peer_identity_pub,
                        "shared": shared,
                        "shared_hash": shared_hash,
                    }
                send_tlv(conn, TYPE_HELLO_REPLY, json.dumps(hello_reply).encode("utf-8"))
            except Exception as exc:
                print(f"[SEC] HELLO error: {exc}")
            return

        if packet_type == TYPE_AUTH:
            try:
                auth = json.loads(payload.decode("utf-8"))
                with lock:
                    pending = pending_handshakes.get(conn_id)
                if not pending:
                    return
                if auth.get("node_id") != pending["peer_node_id"]:
                    return

                if not verify_signature(auth, pending["peer_identity_pub"]):
                    print("[SEC] AUTH signature invalide")
                    return

                if auth.get("shared_hash") != b64e(pending["shared_hash"]):
                    print("[SEC] AUTH shared hash mismatch")
                    return

                session = hkdf_session_keys(pending["shared"])
                with lock:
                    sessions_by_conn[conn_id] = {
                        "session": session,
                        "peer_node_id": pending["peer_node_id"],
                        "peer_identity_pub": pending["peer_identity_pub"],
                    }
                    pending_handshakes.pop(conn_id, None)

                auth_ok = {
                    "type": "AUTH_OK",
                    "node_id": node_id,
                    "timestamp": int(time.time() * 1000),
                }
                auth_ok["signature"] = sign_dict(identity, auth_ok)
                send_tlv(conn, TYPE_AUTH_OK, json.dumps(auth_ok).encode("utf-8"))
                print(f"[SEC] Session etablie avec {sessions_by_conn[conn_id]['peer_node_id'][:16]}...")
            except Exception as exc:
                print(f"[SEC] AUTH error: {exc}")
            return

        if packet_type == TYPE_MSG:
            try:
                msg_packet = json.loads(payload.decode("utf-8"))
                with lock:
                    session_info = sessions_by_conn.get(conn_id)
                if not session_info:
                    print("[SEC] MSG refuse: session absente")
                    return

                payload_for_hmac = {
                    "sender_id": msg_packet["sender_id"],
                    "sender_pub": msg_packet["sender_pub"],
                    "timestamp": msg_packet["timestamp"],
                    "nonce": msg_packet["nonce"],
                    "ciphertext": msg_packet["ciphertext"],
                    "auth_tag": msg_packet["auth_tag"],
                }
                if not verify_hmac(session_info["session"], payload_for_hmac, msg_packet["hmac"]):
                    print("[SEC] HMAC invalide")
                    return

                if msg_packet["sender_id"] != b64d(msg_packet["sender_pub"]).hex():
                    print("[SEC] sender_id/public key mismatch")
                    return
                if not trust_store.check_or_trust(msg_packet["sender_id"], b64d(msg_packet["sender_pub"])):
                    print("[SEC] sender key mismatch")
                    return
                if not verify_signature(msg_packet, b64d(msg_packet["sender_pub"])):
                    print("[SEC] signature invalide")
                    return

                aad = canonical_json(
                    {
                        "sender_id": msg_packet["sender_id"],
                        "timestamp": msg_packet["timestamp"],
                    }
                )
                plaintext = decrypt_message(
                    session=session_info["session"],
                    nonce_b64=msg_packet["nonce"],
                    ciphertext_b64=msg_packet["ciphertext"],
                    tag_b64=msg_packet["auth_tag"],
                    aad=aad,
                )
                print(f"[MSG] {msg_packet['sender_id'][:16]}... -> {plaintext}")
            except Exception as exc:
                print(f"[SEC] MSG error: {exc}")
            return

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
        peer = peer_table.get_peer(args.peer_id)
        if not peer:
            print("Pair inconnu. Utilise d'abord: python main.py peers --wait 35")
        else:
            _send_secure_message(identity, trust_store, peer, args.message)

    elif args.command == "send":
        print("Sprint 2: send sera finalise au Sprint 3.")
    elif args.command == "download":
        print("Sprint 2: download sera finalise au Sprint 3.")

    discovery.stop()
    server.stop()


def _send_secure_message(identity: Identity, trust_store: TrustStore, peer: dict, message: str) -> None:
    peer_ip = peer["ip"]
    peer_port = int(peer["tcp_port"])
    peer_node_id = peer["node_id"]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(5.0)
        sock.connect((peer_ip, peer_port))

        a_priv, a_pub = generate_ephemeral_x25519()
        hello = {
            "type": "HELLO",
            "node_id": identity.node_id,
            "identity_pub": b64e(identity.public_key_raw()),
            "e_pub": b64e(a_pub),
            "timestamp": int(time.time() * 1000),
        }
        send_tlv(sock, TYPE_HELLO, json.dumps(hello).encode("utf-8"))

        packet = recv_tlv(sock)
        if not packet or packet[0] != TYPE_HELLO_REPLY:
            print("[SEC] handshake failed: missing HELLO_REPLY")
            return
        hello_reply = json.loads(packet[1].decode("utf-8"))

        peer_identity_pub = b64d(hello_reply["identity_pub"])
        if hello_reply["node_id"] != peer_identity_pub.hex():
            print("[SEC] handshake failed: peer identity mismatch")
            return
        if peer_node_id and hello_reply["node_id"] != peer_node_id:
            print("[SEC] handshake failed: node_id mismatch with peer table")
            return
        if not trust_store.check_or_trust(hello_reply["node_id"], peer_identity_pub):
            print("[SEC] handshake failed: TOFU mismatch")
            return
        if not verify_signature(hello_reply, peer_identity_pub):
            print("[SEC] handshake failed: invalid HELLO_REPLY signature")
            return

        b_pub = b64d(hello_reply["e_pub"])
        shared = a_priv.exchange(x25519.X25519PublicKey.from_public_bytes(b_pub))
        shared_hash = _handshake_context_hash(identity.node_id, hello_reply["node_id"], a_pub, b_pub)
        if hello_reply.get("hello_hash") != b64e(shared_hash):
            print("[SEC] handshake failed: shared hash mismatch")
            return

        auth = {
            "type": "AUTH",
            "node_id": identity.node_id,
            "shared_hash": b64e(shared_hash),
            "timestamp": int(time.time() * 1000),
        }
        auth["signature"] = sign_dict(identity, auth)
        send_tlv(sock, TYPE_AUTH, json.dumps(auth).encode("utf-8"))

        packet = recv_tlv(sock)
        if not packet or packet[0] != TYPE_AUTH_OK:
            print("[SEC] handshake failed: AUTH_OK not received")
            return
        auth_ok = json.loads(packet[1].decode("utf-8"))
        if not verify_signature(auth_ok, peer_identity_pub):
            print("[SEC] handshake failed: AUTH_OK invalid signature")
            return

        session = hkdf_session_keys(shared)
        aad_dict = {"sender_id": identity.node_id, "timestamp": int(time.time() * 1000)}
        aad = canonical_json(aad_dict)
        encrypted = encrypt_message(session, message, aad=aad)
        msg_packet = {
            "type": "MSG",
            "sender_id": identity.node_id,
            "sender_pub": b64e(identity.public_key_raw()),
            "timestamp": aad_dict["timestamp"],
            "nonce": encrypted["nonce"],
            "ciphertext": encrypted["ciphertext"],
            "auth_tag": encrypted["auth_tag"],
        }
        payload_for_hmac = {
            "sender_id": msg_packet["sender_id"],
            "sender_pub": msg_packet["sender_pub"],
            "timestamp": msg_packet["timestamp"],
            "nonce": msg_packet["nonce"],
            "ciphertext": msg_packet["ciphertext"],
            "auth_tag": msg_packet["auth_tag"],
        }
        msg_packet["hmac"] = compute_hmac(session, payload_for_hmac)
        msg_packet["signature"] = sign_dict(identity, msg_packet)
        send_tlv(sock, TYPE_MSG, json.dumps(msg_packet).encode("utf-8"))
        print(f"[MSG] Message chiffre envoye vers {peer_node_id[:16]}...")


if __name__ == "__main__":
    main()
