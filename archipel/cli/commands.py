"""
cli/commands.py
Commandes CLI de base pour Archipel.
"""
import argparse

class CLI:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='Archipel P2P CLI')
        subparsers = self.parser.add_subparsers(dest='command')

        subparsers.add_parser('start', help='Démarrer le nœud')
        subparsers.add_parser('peers', help='Lister les pairs connus')

        msg_parser = subparsers.add_parser('msg', help='Envoyer un message')
        msg_parser.add_argument('peer_id', help='ID du pair destinataire')
        msg_parser.add_argument('message', help='Message à envoyer')

        send_parser = subparsers.add_parser('send', help='Envoyer un fichier')
        send_parser.add_argument('peer_id', help='ID du pair destinataire')
        send_parser.add_argument('file', help='Chemin du fichier à envoyer')

        download_parser = subparsers.add_parser('download', help='Télécharger un fichier')
        download_parser.add_argument('file_id', help='ID du fichier à télécharger')

    def parse(self, args=None):
        """Analyse les arguments de la ligne de commande."""
        return self.parser.parse_args(args)
