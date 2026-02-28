"""
crypto/keys.py
Génération et chargement de paires de clés RSA.
"""
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os

KEY_SIZE = 2048

class KeyManager:
    def __init__(self, priv_path='private.pem', pub_path='public.pem'):
        self.priv_path = priv_path
        self.pub_path = pub_path
        self.private_key = None
        self.public_key = None

    def generate_keys(self):
        """Génère une nouvelle paire de clés RSA."""
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=KEY_SIZE,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        self.save_keys()

    def save_keys(self):
        """Sauvegarde les clés sur disque."""
        with open(self.priv_path, 'wb') as f:
            f.write(self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        with open(self.pub_path, 'wb') as f:
            f.write(self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

    def load_keys(self):
        """Charge les clés depuis le disque."""
        if os.path.exists(self.priv_path):
            with open(self.priv_path, 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
        if os.path.exists(self.pub_path):
            with open(self.pub_path, 'rb') as f:
                self.public_key = serialization.load_pem_public_key(
                    f.read(), backend=default_backend()
                )
