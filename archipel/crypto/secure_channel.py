"""
crypto/secure_channel.py
Primitives Sprint 2: Ed25519, X25519, HKDF, AES-256-GCM, HMAC-SHA256.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def canonical_json(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


@dataclass
class SessionKeys:
    aes_key: bytes
    hmac_key: bytes


class Identity:
    def __init__(self, private_path: str, public_path: str):
        self.private_path = Path(private_path)
        self.public_path = Path(public_path)
        self.private_key: ed25519.Ed25519PrivateKey | None = None
        self.public_key: ed25519.Ed25519PublicKey | None = None

    def load_or_create(self) -> None:
        if self.private_path.exists() and self.public_path.exists():
            self.private_key = serialization.load_pem_private_key(
                self.private_path.read_bytes(), password=None
            )
            self.public_key = serialization.load_pem_public_key(self.public_path.read_bytes())
            return
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()
        self.private_path.write_bytes(
            self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        self.public_path.write_bytes(
            self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    @property
    def node_id(self) -> str:
        return self.public_key_raw().hex()

    def public_key_raw(self) -> bytes:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def sign(self, data: bytes) -> bytes:
        return self.private_key.sign(data)


class TrustStore:
    def __init__(self, path: str):
        self.path = Path(path)
        self.db = {"keys": {}, "revoked": {}}
        if self.path.exists():
            try:
                self.db = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.db = {"keys": {}, "revoked": {}}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.db, indent=2), encoding="utf-8")

    def check_or_trust(self, node_id: str, public_key_raw: bytes) -> bool:
        if self.db.get("revoked", {}).get(node_id):
            return False
        fingerprint = sha256(public_key_raw).hex()
        known = self.db.setdefault("keys", {}).get(node_id)
        if known is None:
            self.db["keys"][node_id] = fingerprint  # TOFU
            self.save()
            return True
        return known == fingerprint

    def revoke(self, node_id: str, reason: str) -> None:
        self.db.setdefault("revoked", {})[node_id] = {"reason": reason}
        self.save()


def hkdf_session_keys(shared_secret: bytes) -> SessionKeys:
    keymat = HKDF(
        algorithm=hashes.SHA256(),
        length=64,
        salt=None,
        info=b"archipel-v1",
    ).derive(shared_secret)
    return SessionKeys(aes_key=keymat[:32], hmac_key=keymat[32:])


def sign_dict(identity: Identity, packet: dict) -> str:
    content = dict(packet)
    content.pop("signature", None)
    digest = sha256(canonical_json(content))
    return b64e(identity.sign(digest))


def verify_signature(packet: dict, public_key_raw: bytes) -> bool:
    try:
        content = dict(packet)
        signature = b64d(content.pop("signature"))
        digest = sha256(canonical_json(content))
        pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key_raw)
        pub.verify(signature, digest)
        return True
    except Exception:
        return False


def encrypt_message(session: SessionKeys, plaintext: str, aad: bytes) -> dict:
    nonce = os.urandom(12)
    aesgcm = AESGCM(session.aes_key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)
    # cryptography returns ciphertext||tag
    ciphertext, tag = ct[:-16], ct[-16:]
    return {"nonce": b64e(nonce), "ciphertext": b64e(ciphertext), "auth_tag": b64e(tag)}


def decrypt_message(session: SessionKeys, nonce_b64: str, ciphertext_b64: str, tag_b64: str, aad: bytes) -> str:
    nonce = b64d(nonce_b64)
    ciphertext = b64d(ciphertext_b64)
    tag = b64d(tag_b64)
    aesgcm = AESGCM(session.aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext + tag, aad)
    return plaintext.decode("utf-8")


def compute_hmac(session: SessionKeys, payload: dict) -> str:
    data = canonical_json(payload)
    mac = hmac.new(session.hmac_key, data, hashlib.sha256).digest()
    return b64e(mac)


def verify_hmac(session: SessionKeys, payload: dict, mac_b64: str) -> bool:
    expected = compute_hmac(session, payload)
    return hmac.compare_digest(expected, mac_b64)


def generate_ephemeral_x25519() -> tuple[x25519.X25519PrivateKey, bytes]:
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv, pub
