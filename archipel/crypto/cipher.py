"""
crypto/cipher.py
Chiffrement et déchiffrement AES pour les messages.
"""
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import os

AES_KEY_SIZE = 32  # 256 bits
BLOCK_SIZE = 128

class AESCipher:
    def __init__(self, key=None):
        self.key = key or os.urandom(AES_KEY_SIZE)

    def encrypt(self, plaintext):
        """Chiffre le texte en AES CBC."""
        iv = os.urandom(16)
        padder = padding.PKCS7(BLOCK_SIZE).padder()
        padded_data = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded_data) + encryptor.finalize()
        return iv + ct  # IV préfixé

    def decrypt(self, ciphertext):
        """Déchiffre le texte AES CBC."""
        iv = ciphertext[:16]
        ct = ciphertext[16:]
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ct) + decryptor.finalize()
        unpadder = padding.PKCS7(BLOCK_SIZE).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        return data.decode()
