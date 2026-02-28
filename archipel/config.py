"""
config.py
Configuration reseau et parametres globaux pour Archipel.
"""

MULTICAST_GROUP = "239.255.42.99"
MULTICAST_PORT = 6000
TCP_PORT = 5007
ANNOUNCE_INTERVAL = 5  # secondes
DISCOVERY_WAIT_SECONDS = 3

# Cle AES partagee pour le prototype (32 octets / 256 bits).
# Cette cle n'est pas securisee pour la production.
SHARED_AES_KEY = bytes.fromhex(
    "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
)
