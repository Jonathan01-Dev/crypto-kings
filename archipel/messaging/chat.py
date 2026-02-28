"""
messaging/chat.py
Envoi et réception de messages texte chiffrés.
"""
import socket
from crypto.cipher import AESCipher

class Chat:
    def __init__(self, key):
        self.cipher = AESCipher(key)

    def send_message(self, msg, ip, port):
        """Chiffre et envoie un message à un pair."""
        ciphertext = self.cipher.encrypt(msg)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((ip, port))
            s.sendall(ciphertext)

    def receive_message(self, data):
        """Déchiffre un message reçu."""
        return self.cipher.decrypt(data)
