"""
network/discovery.py
Découverte des pairs sur le réseau local via UDP multicast.
"""
import socket
import struct
import threading
import time
from config import MULTICAST_GROUP, MULTICAST_PORT, ANNOUNCE_INTERVAL
import json

class PeerDiscovery:
    def __init__(self, peer_id, port, on_peer=None):
        self.peer_id = peer_id
        self.port = port
        self.running = False
        self.peers = set()
        self.on_peer = on_peer  # callback pour ajout auto dans PeerTable

    def start(self):
        self.running = True
        threading.Thread(target=self._announce, daemon=True).start()
        threading.Thread(target=self._listen, daemon=True).start()

    def _announce(self):
        """Annonce périodique de la présence du nœud sur le réseau."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            ttl = struct.pack('b', 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
            while self.running:
                msg = f"ARCHIPEL:{self.peer_id}:{self.port}".encode()
                try:
                    sock.sendto(msg, (MULTICAST_GROUP, MULTICAST_PORT))
                    print(f"[DISCOVERY] Annonce envoyée: {msg}")
                except Exception as e:
                    print(f"[DISCOVERY] Erreur lors de l'envoi: {e}")
                time.sleep(ANNOUNCE_INTERVAL)
        except Exception as e:
            print(f"[DISCOVERY] Erreur thread annonce: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _listen(self):
        """Écoute les annonces des autres pairs."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', MULTICAST_PORT))
            mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton('0.0.0.0')
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(2.0)
            while self.running:
                try:
                    data, addr = sock.recvfrom(1024)
                    msg = data.decode()
                    if msg.startswith("ARCHIPEL:"):
                        parts = msg.split(":")
                        if len(parts) == 3:
                            _, peer_id, port = parts
                            if peer_id != self.peer_id:
                                print(f"[DISCOVERY] Pair découvert: {peer_id} @ {addr[0]}:{port}")
                                self.peers.add((peer_id, addr[0], int(port)))
                                if self.on_peer:
                                    self.on_peer(peer_id, addr[0], int(port))
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[DISCOVERY] Erreur réception: {e}")
                    continue
        except Exception as e:
            print(f"[DISCOVERY] Erreur thread écoute: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def _timeout_check(self):
        """Retire les pairs non vus depuis 90s."""
        TIMEOUT = 90
        while self.running:
            now = time.time()
            to_remove = []
            if isinstance(self.peers, dict):
                to_remove = [pid for pid, info in self.peers.items() if now - info.get('last_seen', now) > TIMEOUT]
                for pid in to_remove:
                    print(f"[DISCOVERY] Pair expiré: {pid}")
                    self.peers.pop(pid)
                    if self.peer_table:
                        self.peer_table.remove_peer(pid)
            time.sleep(10)

    def _reply_with_peer_list(self, ip, port):
        """Envoie la liste des pairs connus en TCP (PEER_LIST)."""
        try:
            peer_list = []
            if isinstance(self.peers, dict):
                peer_list = [{'node_id': pid, 'ip': info['ip'], 'port': info['port']} for pid, info in self.peers.items()]
            pkt = json.dumps({'type': 'PEER_LIST', 'peers': peer_list}).encode()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                s.sendall(pkt)
            print(f"[DISCOVERY] PEER_LIST envoyé à {ip}:{port}")
        except Exception as e:
            print(f"[DISCOVERY] Erreur envoi PEER_LIST: {e}")
