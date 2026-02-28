"""
cli/commands.py
Commandes CLI de base pour Archipel.
"""

import argparse

from config import DISCOVERY_WAIT_SECONDS, TCP_PORT


class CLI:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Archipel P2P CLI")
        subparsers = self.parser.add_subparsers(dest="command")

        start_parser = subparsers.add_parser("start", help="Demarrer le noeud")
        self._add_common_args(start_parser)

        peers_parser = subparsers.add_parser("peers", help="Lister les pairs connus")
        self._add_common_args(peers_parser)

        msg_parser = subparsers.add_parser("msg", help="Envoyer un message")
        self._add_common_args(msg_parser)
        msg_parser.add_argument("peer_id", help="ID du pair destinataire")
        msg_parser.add_argument("message", help="Message a envoyer")

        send_parser = subparsers.add_parser("send", help="Envoyer un fichier")
        self._add_common_args(send_parser)
        send_parser.add_argument("peer_id", help="ID du pair destinataire")
        send_parser.add_argument("file", help="Chemin du fichier a envoyer")

        download_parser = subparsers.add_parser("download", help="Telecharger un fichier")
        self._add_common_args(download_parser)
        download_parser.add_argument("file_id", help="ID du fichier a telecharger")

    @staticmethod
    def _add_common_args(parser):
        parser.add_argument(
            "--port",
            type=int,
            default=TCP_PORT,
            help=f"Port TCP du noeud (defaut: {TCP_PORT})",
        )
        parser.add_argument(
            "--wait",
            type=int,
            default=DISCOVERY_WAIT_SECONDS,
            help=f"Delai de decouverte avant action (defaut: {DISCOVERY_WAIT_SECONDS}s)",
        )

    def parse(self, args=None):
        """Analyse les arguments de la ligne de commande."""
        return self.parser.parse_args(args)
