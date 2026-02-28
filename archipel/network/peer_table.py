"""
network/peer_table.py
Stockage et gestion des pairs connus.
"""
import threading

class PeerTable:
    def __init__(self):
        self.peers = {}
        self.lock = threading.Lock()

    def add_peer(self, peer_id, ip, port):
        """Ajoute ou met à jour un pair."""
        with self.lock:
            self.peers[peer_id] = {'ip': ip, 'port': port}

    def remove_peer(self, peer_id):
        """Supprime un pair."""
        with self.lock:
            if peer_id in self.peers:
                del self.peers[peer_id]

    def get_peers(self):
        """Retourne la liste des pairs connus."""
        with self.lock:
            return self.peers.copy()

    def get_peer(self, peer_id):
        """Retourne les infos d'un pair."""
        with self.lock:
            return self.peers.get(peer_id)
