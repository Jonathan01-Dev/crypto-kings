import tempfile
import unittest
from pathlib import Path

from transfer.chunker import Chunker, file_sha256
from transfer.downloader import ChunkStore, LocalIndex


class TestTransfer(unittest.TestCase):
    def test_manifest_and_chunk_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.bin"
            src.write_bytes(b"A" * 1400 + b"B" * 777 + b"C" * 999)

            chunker = Chunker(chunk_size=512)
            manifest = chunker.build_manifest(str(src), sender_id="ab" * 32)
            self.assertEqual(manifest["file_id"], file_sha256(str(src)))
            self.assertGreater(manifest["nb_chunks"], 1)

            index = LocalIndex(base_dir=str(Path(td) / ".archipel"))
            store = ChunkStore(base_dir=str(Path(td) / ".archipel/chunks"))
            index.upsert_manifest(manifest, source_node_id="ab" * 32)

            for idx, chunk in chunker.iter_chunks(str(src)):
                store.write_chunk(manifest["file_id"], idx, chunk)
                index.mark_chunk(manifest["file_id"], idx)

            out = store.assemble(manifest["file_id"], manifest, output_dir=str(Path(td) / "out"))
            self.assertEqual(file_sha256(out), manifest["file_id"])


if __name__ == "__main__":
    unittest.main()
