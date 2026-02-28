# Archipel - Sprint 1

Objectif Sprint 1: discovery mesh en LAN (HELLO multicast + PEER_LIST unicast TCP).

## Setup

```bash
pip install cryptography
```

Optionnel: fichier `.env` a cote de `main.py`.

```env
ARCHIPEL_TCP_PORT=7777
ARCHIPEL_MULTICAST_GROUP=239.255.42.99
ARCHIPEL_MULTICAST_PORT=6000
ARCHIPEL_ANNOUNCE_INTERVAL=30
ARCHIPEL_PEER_TIMEOUT=90
```

## Lancer 3 noeuds (meme machine)

Terminal 1:

```bash
python main.py start --port 7777
```

Terminal 2:

```bash
python main.py start --port 7778
```

Terminal 3:

```bash
python main.py start --port 7779
```

## Verifier la peer table

Dans un 4e terminal:

```bash
python main.py peers --port 7780 --wait 35
```

Attendu: les 3 noeuds se voient en moins de 60 secondes.
