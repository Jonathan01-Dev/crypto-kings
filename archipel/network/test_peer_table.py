import tempfile
import unittest
from pathlib import Path

from network.peer_table import PeerTable


class TestPeerTable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = str(Path(self.tmp.name) / "peer_table.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_and_get_peer(self):
        table = PeerTable(storage_path=self.storage)
        table.add_peer("id1", "192.168.1.2", 6000)
        peer = table.get_peer("id1")
        self.assertEqual(peer["ip"], "192.168.1.2")
        self.assertEqual(peer["tcp_port"], 6000)

    def test_remove_peer(self):
        table = PeerTable(storage_path=self.storage)
        table.add_peer("id2", "192.168.1.3", 6001)
        table.remove_peer("id2")
        self.assertIsNone(table.get_peer("id2"))

    def test_persistence(self):
        table = PeerTable(storage_path=self.storage)
        table.add_peer("id3", "192.168.1.4", 7000)
        restored = PeerTable(storage_path=self.storage)
        peer = restored.get_peer("id3")
        self.assertIsNotNone(peer)
        self.assertEqual(peer["tcp_port"], 7000)


if __name__ == "__main__":
    unittest.main()
