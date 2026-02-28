import tempfile
import unittest
from pathlib import Path

from crypto.secure_channel import (
    Identity,
    TrustStore,
    canonical_json,
    compute_hmac,
    decrypt_message,
    encrypt_message,
    hkdf_session_keys,
    sha256,
    sign_dict,
    verify_hmac,
    verify_signature,
)


class TestSecureChannel(unittest.TestCase):
    def test_sign_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            identity = Identity(
                private_path=str(Path(td) / "id.pem"),
                public_path=str(Path(td) / "id.pub.pem"),
            )
            identity.load_or_create()
            packet = {"type": "X", "value": "abc"}
            packet["signature"] = sign_dict(identity, packet)
            self.assertTrue(verify_signature(packet, identity.public_key_raw()))

    def test_encrypt_decrypt_and_hmac(self):
        shared = sha256(b"shared-secret")
        session = hkdf_session_keys(shared)
        aad = canonical_json({"k": "v"})
        enc = encrypt_message(session, "hello", aad=aad)
        msg = decrypt_message(session, enc["nonce"], enc["ciphertext"], enc["auth_tag"], aad=aad)
        self.assertEqual(msg, "hello")

        payload = {"a": 1, "b": 2}
        mac = compute_hmac(session, payload)
        self.assertTrue(verify_hmac(session, payload, mac))

    def test_tofu(self):
        with tempfile.TemporaryDirectory() as td:
            trust = TrustStore(str(Path(td) / "trust.json"))
            pub = b"x" * 32
            self.assertTrue(trust.check_or_trust("node1", pub))
            self.assertTrue(trust.check_or_trust("node1", pub))
            self.assertFalse(trust.check_or_trust("node1", b"y" * 32))


if __name__ == "__main__":
    unittest.main()
