# Archipel - Sprint 3 (Chunking & Transfert Multi-noeuds)

## Objectif
- Manifest signe Ed25519
- Chunks 512KB avec hash SHA-256
- Requetes `CHUNK_REQ` / reponses `CHUNK_DATA` (chiffrees)
- Telechargement parallele (>= 3 workers)
- Verification hash chunk + hash final fichier

## Lancer 3 noeuds (exemple local)

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

## Publier un fichier (noeud source)

1. Recuperer un peer_id via:
```bash
python main.py peers --port 7780 --wait 35
```
2. Envoyer le manifest:
```bash
python main.py send <peer_id> <chemin_fichier_50MB> --port 7777 --wait 1
```

## Telecharger (receveur)

1. Recupere `file_id` dans les logs `Manifest file_id=...`
2. Telecharge:
```bash
python main.py download <file_id> --port 7778 --wait 1
```

Le fichier final est dans `downloads/` et le hash final est affiche.

## Tests unitaires

```bash
python -m unittest network/test_peer_table.py
python -m unittest crypto/test_secure_channel.py
python -m unittest transfer/test_transfer.py
```
