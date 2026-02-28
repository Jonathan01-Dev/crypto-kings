"""
network/tcp_server.py
Serveur TCP basique pour recevoir des paquets.
"""
import socket
import threading

class TCPServer:
    def __init__(self, host, port, handler):
        self.host = host
        self.port = port
        self.handler = handler  # fonction à appeler pour chaque paquet reçu
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen()
            while self.running:
                try:
                    conn, addr = server.accept()
                    threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
                except Exception:
                    continue

    def _handle_client(self, conn, addr):
        with conn:
            data = conn.recv(4096)
            if data:
                self.handler(data, addr)

    def stop(self):
        self.running = False
