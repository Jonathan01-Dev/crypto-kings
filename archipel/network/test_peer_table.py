import unittest
from network.peer_table import PeerTable

class TestPeerTable(unittest.TestCase):
    def test_add_and_get_peer(self):
        table = PeerTable()
        table.add_peer('id1', '192.168.1.2', 6000)
        peer = table.get_peer('id1')
        self.assertEqual(peer['ip'], '192.168.1.2')
        self.assertEqual(peer['port'], 6000)

    def test_remove_peer(self):
        table = PeerTable()
        table.add_peer('id2', '192.168.1.3', 6001)
        table.remove_peer('id2')
        self.assertIsNone(table.get_peer('id2'))

if __name__ == '__main__':
    unittest.main()
