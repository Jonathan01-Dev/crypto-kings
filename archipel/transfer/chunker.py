"""
transfer/chunker.py
Découpage de fichiers en blocs (chunks).
"""
import os

CHUNK_SIZE = 4096

class Chunker:
    def __init__(self, chunk_size=CHUNK_SIZE):
        self.chunk_size = chunk_size

    def chunk_file(self, file_path):
        """Découpe un fichier en chunks."""
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk
