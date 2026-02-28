# Archipel - Lancement rapide

## 1) Installer la dependance

```bash
pip install cryptography
```

## 2) Ouvrir le reseau local

- Toutes les machines doivent etre sur le meme LAN.
- Autoriser UDP `6000` (multicast discovery) et TCP `5007` (messages).

## 3) Demarrer un noeud serveur

```bash
python main.py start --port 5007
```

Le processus reste actif. Arret avec `Ctrl+C`.

## 4) Tester sur une seule machine (2 terminaux)

Terminal A:

```bash
python main.py start --port 5007
```

Terminal B:

```bash
python main.py start --port 5008
```

## 5) Lister les pairs

Depuis un 3e terminal:

```bash
python main.py peers --port 5010 --wait 3
```

## 6) Envoyer un message

1. Recuperer un `peer_id` via la commande `peers`.
2. Envoyer:

```bash
python main.py msg <peer_id> "Hello Archipel!" --port 5010 --wait 3
```

## 7) Envoyer un fichier (prototype)

```bash
python main.py send <peer_id> <chemin_du_fichier> --port 5010 --wait 3
```
