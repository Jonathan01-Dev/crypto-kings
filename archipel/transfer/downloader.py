"""
transfer/downloader.py
Réception des chunks et reconstruction des fichiers.
"""
import os

class Downloader:
    def __init__(self, output_path):
        self.output_path = output_path
        self.chunks = []

    def add_chunk(self, chunk):
        """Ajoute un chunk reçu."""
        self.chunks.append(chunk)

    def save_file(self):
        """Reconstruit le fichier à partir des chunks."""
        with open(self.output_path, 'wb') as f:
            for chunk in self.chunks:
                f.write(chunk)
