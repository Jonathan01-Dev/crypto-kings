# Archipel - Sprint 2

Sprint 2 ajoute:
- Identite noeud Ed25519 (signature)
- Handshake ephemere X25519 + HKDF
- Tunnel message AES-256-GCM
- Integrite HMAC-SHA256
- TOFU (Trust On First Use) sans CA

## Setup

```bash
pip install cryptography
```

## Lancer Bob

```bash
python main.py start --port 7778
```

## Lancer Alice

```bash
python main.py start --port 7777
```

## Recuperer les peers (depuis Alice)

```bash
python main.py peers --port 7780 --wait 35
```

## Envoyer un message chiffre (Alice -> Bob)

```bash
python main.py msg <peer_id_de_bob> "Bonjour Bob (Sprint 2)" --port 7777 --wait 1
```

## Test 3 noeuds

```bash
python main.py start --port 7777
python main.py start --port 7778
python main.py start --port 7779
python main.py peers --port 7780 --wait 35
```

Attendu:
- Discovery en moins de 60 secondes
- Peer table affichee
- Message recu en clair uniquement sur le noeud destinataire
- Capture reseau: octets chiffrés (AES-GCM), jamais le plaintext
