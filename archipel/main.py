"""
main.py
Sprint 3: transfert de fichiers multi-noeuds (manifest + chunks).
"""

from __future__ import annotations

import base64
import hashlib
import json
import queue
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
    TYPE_ACK,
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_CHUNK_DATA,
    TYPE_CHUNK_REQ,
    TYPE_HELLO,
    TYPE_HELLO_REPLY,
    TYPE_MANIFEST,
    TYPE_MSG,
    TYPE_PEER_LIST,
    recv_tlv,
    send_tlv,
)
from network.tcp_server import TCPServer
from transfer.chunker import Chunker, file_sha256, sha256_bytes
from transfer.downloader import ChunkStore, LocalIndex


ACK_OK = 0
ACK_HASH_MISMATCH = 1
ACK_NOT_FOUND = 2


def _handshake_context_hash(a_node: str, b_node: str, a_eph_pub: bytes, b_eph_pub: bytes) -> bytes:
    ctx = {"a_node": a_node, "b_node": b_node, "a_eph": b64e(a_eph_pub), "b_eph": b64e(b_eph_pub)}
    return sha256(canonical_json(ctx))


def _init_identity(port: int) -> Identity:
    identity = Identity(
        private_path=f"identity_ed25519_{port}.pem",
        public_path=f"identity_ed25519_{port}.pub.pem",
    )
    identity.load_or_create()
    return identity


def _sign_manifest(identity: Identity, manifest: dict) -> dict:
    payload = dict(manifest)
    payload["signature"] = sign_dict(identity, payload)
    return payload


def _verify_manifest(manifest: dict, trust_store: TrustStore) -> bool:
    try:
        sender_id = manifest["sender_id"]
        sender_pub = bytes.fromhex(sender_id)
        if not trust_store.check_or_trust(sender_id, sender_pub):
            return False
        return verify_signature(manifest, sender_pub)
    except Exception:
        return False


def _make_secure_packet(identity: Identity, session, inner_type: str, body: dict) -> dict:
    ts = int(time.time() * 1000)
    aad_dict = {"sender_id": identity.node_id, "timestamp": ts, "inner_type": inner_type}
    aad = canonical_json(aad_dict)
    plaintext = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    encrypted = encrypt_message(session, plaintext, aad)
    packet = {
        "sender_id": identity.node_id,
        "sender_pub": b64e(identity.public_key_raw()),
        "timestamp": ts,
        "inner_type": inner_type,
        "nonce": encrypted["nonce"],
        "ciphertext": encrypted["ciphertext"],
        "auth_tag": encrypted["auth_tag"],
    }
    mac_payload = {
        "sender_id": packet["sender_id"],
        "sender_pub": packet["sender_pub"],
        "timestamp": packet["timestamp"],
        "inner_type": packet["inner_type"],
        "nonce": packet["nonce"],
        "ciphertext": packet["ciphertext"],
        "auth_tag": packet["auth_tag"],
    }
    packet["hmac"] = compute_hmac(session, mac_payload)
    packet["signature"] = sign_dict(identity, packet)
    return packet


def _parse_secure_packet(packet: dict, session, trust_store: TrustStore) -> dict:
    sender_id = packet["sender_id"]
    sender_pub = b64d(packet["sender_pub"])
    if sender_id != sender_pub.hex():
        raise RuntimeError("sender mismatch")
    if not trust_store.check_or_trust(sender_id, sender_pub):
        raise RuntimeError("trust mismatch")
    if not verify_signature(packet, sender_pub):
        raise RuntimeError("bad signature")
    mac_payload = {
        "sender_id": packet["sender_id"],
        "sender_pub": packet["sender_pub"],
        "timestamp": packet["timestamp"],
        "inner_type": packet["inner_type"],
        "nonce": packet["nonce"],
        "ciphertext": packet["ciphertext"],
        "auth_tag": packet["auth_tag"],
    }
    if not verify_hmac(session, mac_payload, packet["hmac"]):
        raise RuntimeError("bad hmac")
    aad = canonical_json(
        {
            "sender_id": packet["sender_id"],
            "timestamp": packet["timestamp"],
            "inner_type": packet["inner_type"],
        }
    )
    plaintext = decrypt_message(session, packet["nonce"], packet["ciphertext"], packet["auth_tag"], aad)
    return {"sender_id": sender_id, "inner_type": packet["inner_type"], "body": json.loads(plaintext)}


def _connect_with_handshake(identity: Identity, trust_store: TrustStore, peer: dict):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(8.0)
    sock.connect((peer["ip"], int(peer["tcp_port"])))

    a_priv, a_pub = generate_ephemeral_x25519()
    hello = {
        "type": "HELLO",
        "node_id": identity.node_id,
        "identity_pub": b64e(identity.public_key_raw()),
        "e_pub": b64e(a_pub),
        "timestamp": int(time.time() * 1000),
    }
    send_tlv(sock, TYPE_HELLO, json.dumps(hello).encode("utf-8"))
    incoming = recv_tlv(sock)
    if not incoming or incoming[0] != TYPE_HELLO_REPLY:
        sock.close()
        raise RuntimeError("HELLO_REPLY missing")
    hello_reply = json.loads(incoming[1].decode("utf-8"))
    peer_pub = b64d(hello_reply["identity_pub"])
    if hello_reply["node_id"] != peer_pub.hex():
        sock.close()
        raise RuntimeError("peer identity mismatch")
    if peer.get("node_id") and peer["node_id"] != hello_reply["node_id"]:
        sock.close()
        raise RuntimeError("node mismatch")
    if not trust_store.check_or_trust(hello_reply["node_id"], peer_pub):
        sock.close()
        raise RuntimeError("TOFU mismatch")
    if not verify_signature(hello_reply, peer_pub):
        sock.close()
        raise RuntimeError("invalid hello signature")
    b_pub = b64d(hello_reply["e_pub"])
    shared = a_priv.exchange(x25519.X25519PublicKey.from_public_bytes(b_pub))
    shared_hash = _handshake_context_hash(identity.node_id, hello_reply["node_id"], a_pub, b_pub)
    if hello_reply.get("hello_hash") != b64e(shared_hash):
        sock.close()
        raise RuntimeError("shared hash mismatch")
    auth = {"type": "AUTH", "node_id": identity.node_id, "shared_hash": b64e(shared_hash), "timestamp": int(time.time() * 1000)}
    auth["signature"] = sign_dict(identity, auth)
    send_tlv(sock, TYPE_AUTH, json.dumps(auth).encode("utf-8"))
    incoming = recv_tlv(sock)
    if not incoming or incoming[0] != TYPE_AUTH_OK:
        sock.close()
        raise RuntimeError("AUTH_OK missing")
    auth_ok = json.loads(incoming[1].decode("utf-8"))
    if not verify_signature(auth_ok, peer_pub):
        sock.close()
        raise RuntimeError("AUTH_OK invalid")
    return sock, hkdf_session_keys(shared), hello_reply["node_id"]


def main() -> None:
    args = CLI().parse()
    if not args.command:
        print("Aucune commande donnee. Utilise: start | peers | msg | send | download")
        return

    identity = _init_identity(args.port)
    node_id = identity.node_id
    peer_table = PeerTable(storage_path=f"peer_table_{args.port}.json")
    trust_store = TrustStore(path=f"{Path(TRUST_STORE_PATH).stem}_{args.port}.json")
    chunker = Chunker()
    node_data_dir = f".archipel/{args.port}"
    index = LocalIndex(base_dir=node_data_dir)
    chunk_store = ChunkStore(base_dir=f"{node_data_dir}/chunks")
    local_seed_files: dict[str, str] = {}
    lock = threading.Lock()
    pending_handshakes: dict[int, dict] = {}
    sessions_by_conn: dict[int, dict] = {}

    def _send_secure(conn: socket.socket, session, packet_type: int, inner_type: str, body: dict) -> None:
        packet = _make_secure_packet(identity, session, inner_type, body)
        send_tlv(conn, packet_type, json.dumps(packet).encode("utf-8"))

    def _send_ack(conn: socket.socket, session, chunk_idx: int, status: int, msg: str = "") -> None:
        _send_secure(conn, session, TYPE_ACK, "ACK", {"chunk_idx": chunk_idx, "status": status, "message": msg})

    def _serve_chunk(file_id: str, chunk_idx: int) -> bytes | None:
        path = local_seed_files.get(file_id)
        if path:
            return chunker.read_chunk(path, chunk_idx)
        return chunk_store.read_chunk(file_id, chunk_idx)

    def handle_packet(packet_type: int, payload: bytes, addr: tuple[str, int], conn: socket.socket) -> None:
        conn_id = conn.fileno()

        if packet_type == TYPE_PEER_LIST:
            try:
                pkt = json.loads(payload.decode("utf-8"))
                peer_table.merge_peers(pkt.get("peers", []), skip_node_id=node_id)
                print(f"[TCP] PEER_LIST recu de {addr[0]}:{addr[1]}")
            except Exception as exc:
                print(f"[TCP] PEER_LIST invalide: {exc}")
            return

        if packet_type == TYPE_HELLO:
            try:
                hello = json.loads(payload.decode("utf-8"))
                peer_node_id = hello["node_id"]
                peer_pub = b64d(hello["identity_pub"])
                peer_eph = b64d(hello["e_pub"])
                if peer_node_id != peer_pub.hex() or not trust_store.check_or_trust(peer_node_id, peer_pub):
                    return
                b_priv, b_pub = generate_ephemeral_x25519()
                shared = b_priv.exchange(x25519.X25519PublicKey.from_public_bytes(peer_eph))
                shared_hash = _handshake_context_hash(peer_node_id, node_id, peer_eph, b_pub)
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
                        "peer_pub": peer_pub,
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
                if not verify_signature(auth, pending["peer_pub"]):
                    return
                if auth.get("shared_hash") != b64e(pending["shared_hash"]):
                    return
                session = hkdf_session_keys(pending["shared"])
                with lock:
                    sessions_by_conn[conn_id] = {"session": session, "peer_node_id": pending["peer_node_id"]}
                    pending_handshakes.pop(conn_id, None)
                auth_ok = {"type": "AUTH_OK", "node_id": node_id, "timestamp": int(time.time() * 1000)}
                auth_ok["signature"] = sign_dict(identity, auth_ok)
                send_tlv(conn, TYPE_AUTH_OK, json.dumps(auth_ok).encode("utf-8"))
                print(f"[SEC] Session etablie avec {auth.get('node_id')[:16]}...")
            except Exception as exc:
                print(f"[SEC] AUTH error: {exc}")
            return

        if packet_type in (TYPE_MSG, TYPE_MANIFEST, TYPE_CHUNK_REQ, TYPE_CHUNK_DATA, TYPE_ACK):
            with lock:
                session_info = sessions_by_conn.get(conn_id)
            if not session_info:
                return
            try:
                secure_pkt = json.loads(payload.decode("utf-8"))
                decoded = _parse_secure_packet(secure_pkt, session_info["session"], trust_store)
                body = decoded["body"]
                sender = decoded["sender_id"]
            except Exception as exc:
                print(f"[SEC] secure packet error: {exc}")
                return

            if packet_type == TYPE_MSG:
                print(f"[MSG] {sender[:16]}... -> {body.get('text','')}")
                return

            if packet_type == TYPE_MANIFEST:
                manifest = body.get("manifest", {})
                if not _verify_manifest(manifest, trust_store):
                    print("[TRANSFER] Manifest signature invalide")
                    return
                index.upsert_manifest(manifest, source_node_id=sender)
                peer = peer_table.get_peer(sender)
                if peer:
                    files = set(peer.get("shared_files", []))
                    files.add(manifest["file_id"])
                    peer_table.upsert_peer(sender, peer["ip"], peer["tcp_port"], shared_files=list(files))
                else:
                    sender_tcp_port = int(manifest.get("sender_tcp_port", 0))
                    if sender_tcp_port > 0:
                        peer_table.upsert_peer(sender, addr[0], sender_tcp_port, shared_files=[manifest["file_id"]])
                print(f"[TRANSFER] Manifest recu file_id={manifest['file_id'][:16]}... nb_chunks={manifest['nb_chunks']}")
                return

            if packet_type == TYPE_CHUNK_REQ:
                file_id = body["file_id"]
                chunk_idx = int(body["chunk_idx"])
                data = _serve_chunk(file_id, chunk_idx)
                if data is None:
                    _send_ack(conn, session_info["session"], chunk_idx, ACK_NOT_FOUND, "chunk not found")
                    return
                chunk_hash = sha256_bytes(data)
                sig_material = sha256(canonical_json({"file_id": file_id, "chunk_idx": chunk_idx, "chunk_hash": chunk_hash}.copy()))
                chunk_sig = b64e(identity.sign(sig_material))
                _send_secure(
                    conn,
                    session_info["session"],
                    TYPE_CHUNK_DATA,
                    "CHUNK_DATA",
                    {
                        "file_id": file_id,
                        "chunk_idx": chunk_idx,
                        "data": base64.b64encode(data).decode("ascii"),
                        "chunk_hash": chunk_hash,
                        "signature": chunk_sig,
                    },
                )
                return

            if packet_type == TYPE_CHUNK_DATA:
                return

            if packet_type == TYPE_ACK:
                return

    server = TCPServer("0.0.0.0", args.port, handle_packet)
    discovery = PeerDiscovery(node_id=node_id, tcp_port=args.port, peer_table=peer_table)
    discovery.start()
    server.start()

    def _broadcast_manifest(manifest: dict) -> None:
        peers = peer_table.get_peers()
        for pid, peer in peers.items():
            if pid == node_id:
                continue
            try:
                sock, session, _ = _connect_with_handshake(identity, trust_store, peer)
                _send_secure(sock, session, TYPE_MANIFEST, "MANIFEST", {"manifest": manifest})
                sock.close()
                index.add_provider(manifest["file_id"], pid)
            except Exception as exc:
                print(f"[TRANSFER] Manifest send to {pid[:12]} failed: {exc}")

    def _request_chunk(peer: dict, file_id: str, idx: int) -> tuple[int, bytes | None]:
        try:
            sock, session, _ = _connect_with_handshake(identity, trust_store, peer)
            _send_secure(sock, session, TYPE_CHUNK_REQ, "CHUNK_REQ", {"file_id": file_id, "chunk_idx": idx, "requester": node_id})
            packet = recv_tlv(sock)
            sock.close()
            if not packet:
                return ACK_NOT_FOUND, None
            ptype, pdata = packet
            if ptype == TYPE_ACK:
                ack = _parse_secure_packet(json.loads(pdata.decode("utf-8")), session, trust_store)["body"]
                return int(ack.get("status", ACK_NOT_FOUND)), None
            if ptype != TYPE_CHUNK_DATA:
                return ACK_NOT_FOUND, None
            data_pkt = _parse_secure_packet(json.loads(pdata.decode("utf-8")), session, trust_store)["body"]
            data = base64.b64decode(data_pkt["data"].encode("ascii"))
            if sha256_bytes(data) != data_pkt["chunk_hash"]:
                return ACK_HASH_MISMATCH, None
            return ACK_OK, data
        except Exception:
            return ACK_NOT_FOUND, None

    def _download_file(file_id: str) -> None:
        manifest = index.get_manifest(file_id)
        if not manifest:
            print("Manifest inconnu. Recois d'abord un MANIFEST via send.")
            return
        providers = index.get_providers(file_id)
        if not providers:
            providers = [pid for pid in peer_table.get_peers().keys() if pid != node_id]
        peers = []
        for pid in providers:
            p = peer_table.get_peer(pid)
            if p:
                peers.append(p)
        if not peers:
            print("Aucun provider disponible.")
            return

        existing = set(chunk_store.available_chunks(file_id))
        chunk_entries = manifest["chunks"]
        missing = [c["index"] for c in chunk_entries if c["index"] not in existing]
        if not missing:
            output = chunk_store.assemble(file_id, manifest, output_dir="downloads")
            if file_sha256(output) == file_id:
                index.mark_complete(file_id, output)
                print(f"[TRANSFER] Deja complet: {output}")
            return

        rarity = {idx: 1 for idx in missing}
        missing_sorted = sorted(missing, key=lambda i: rarity[i])
        q: queue.Queue[int] = queue.Queue()
        for idx in missing_sorted:
            q.put(idx)
        retries: dict[int, int] = {idx: 0 for idx in missing_sorted}
        max_retries = 6
        done = set(existing)
        done_lock = threading.Lock()

        def worker(worker_id: int):
            while True:
                try:
                    idx = q.get_nowait()
                except queue.Empty:
                    return
                ok = False
                for peer in peers:
                    status, data = _request_chunk(peer, file_id, idx)
                    if status == ACK_OK and data is not None:
                        expected = next(c["hash"] for c in chunk_entries if c["index"] == idx)
                        if sha256_bytes(data) != expected:
                            status = ACK_HASH_MISMATCH
                        else:
                            chunk_store.write_chunk(file_id, idx, data)
                            index.mark_chunk(file_id, idx)
                            with done_lock:
                                done.add(idx)
                                print(f"[TRANSFER] worker={worker_id} chunk={idx} OK ({len(done)}/{manifest['nb_chunks']})")
                            ok = True
                            break
                    if status == ACK_HASH_MISMATCH:
                        print(f"[TRANSFER] worker={worker_id} chunk={idx} HASH_MISMATCH, retry...")
                        continue
                if not ok:
                    retries[idx] += 1
                    if retries[idx] < max_retries:
                        q.put(idx)
                    else:
                        print(f"[TRANSFER] chunk={idx} echec apres {max_retries} retries")
                q.task_done()

        workers = []
        worker_count = max(3, min(6, len(missing_sorted)))
        for i in range(worker_count):
            t = threading.Thread(target=worker, args=(i + 1,), daemon=True)
            workers.append(t)
            t.start()
        for t in workers:
            t.join()

        remaining = [c["index"] for c in chunk_entries if c["index"] not in set(chunk_store.available_chunks(file_id))]
        if remaining:
            print(f"[TRANSFER] Incomplet, chunks manquants: {remaining[:10]}")
            return
        output = chunk_store.assemble(file_id, manifest, output_dir="downloads")
        final_hash = file_sha256(output)
        print(f"[TRANSFER] SHA256 final={final_hash}")
        if final_hash == file_id:
            index.mark_complete(file_id, output)
            print(f"[TRANSFER] Download OK -> {output}")
        else:
            print("[TRANSFER] HASH FINAL MISMATCH")

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
                print(f"- node_id={peer_id[:16]}... ip={peer['ip']} tcp_port={peer['tcp_port']} shared_files={len(peer.get('shared_files', []))}")

    elif args.command == "msg":
        peer = peer_table.get_peer(args.peer_id)
        if not peer:
            print("Pair inconnu. Utilise d'abord: python main.py peers --wait 35")
        else:
            try:
                sock, session, peer_id = _connect_with_handshake(identity, trust_store, peer)
                _send_secure(sock, session, TYPE_MSG, "MSG", {"text": args.message})
                sock.close()
                print(f"[MSG] Message chiffre envoye vers {peer_id[:16]}...")
            except Exception as exc:
                print(f"[MSG] Echec envoi: {exc}")

    elif args.command == "send":
        peer = peer_table.get_peer(args.peer_id)
        if not peer:
            print("Pair inconnu. Utilise d'abord: python main.py peers --wait 35")
        else:
            manifest = chunker.build_manifest(args.file, sender_id=node_id)
            manifest["sender_tcp_port"] = args.port
            manifest = _sign_manifest(identity, manifest)
            local_seed_files[manifest["file_id"]] = args.file
            index.upsert_manifest(manifest, source_node_id=node_id)
            index.mark_complete(manifest["file_id"], args.file)
            index.set_available_chunks(manifest["file_id"], list(range(manifest["nb_chunks"])))
            for idx, chunk in chunker.iter_chunks(args.file):
                chunk_store.write_chunk(manifest["file_id"], idx, chunk)
            peer_data = peer_table.get_peer(args.peer_id)
            if peer_data:
                files = set(peer_data.get("shared_files", []))
                files.add(manifest["file_id"])
                peer_table.upsert_peer(args.peer_id, peer_data["ip"], peer_data["tcp_port"], shared_files=list(files))
            print(f"[TRANSFER] Manifest file_id={manifest['file_id']} chunks={manifest['nb_chunks']}")
            _broadcast_manifest(manifest)


    elif args.command == "download":
        _download_file(args.file_id)

    elif args.command == "receive":
        files = index.db.get("files", {})
        if not files:
            print("Aucun fichier disponible.")
        else:
            print("Fichiers disponibles:")
            for fid, meta in files.items():
                status = "complet" if meta.get("completed") else "incomplet"
                print(f"- file_id={fid[:16]}... status={status} chunks={len(meta.get('available_chunks', []))}")

    elif args.command == "status":
        print(f"Noeud: {node_id[:16]}... port={args.port}")
        peers = peer_table.get_peers()
        print(f"Pairs connus: {len(peers)}")
        files = index.db.get("files", {})
        print(f"Fichiers: {len(files)}")
        for fid, meta in files.items():
            print(f"- file_id={fid[:16]}... completed={meta.get('completed', False)} chunks={len(meta.get('available_chunks', []))}")

    elif args.command == "trust":
        peer = peer_table.get_peer(args.peer_id)
        if not peer:
            print("Pair inconnu.")
        else:
            pub_hex = peer["node_id"]
            pub_bytes = bytes.fromhex(pub_hex)
            trust_store.trust(pub_hex, pub_bytes)
            print(f"Pair {args.peer_id[:16]}... approuve dans le Web of Trust.")

    discovery.stop()
    server.stop()


if __name__ == "__main__":
    main()
