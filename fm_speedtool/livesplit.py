"""Client du serveur TCP de LiveSplit (Controle > Start TCP Server, port 16834)."""

import socket


class LiveSplitClient:
    def __init__(self, host="localhost", port=16834):
        self.host = host
        self.port = port
        self.sock = None

    @property
    def connected(self):
        return self.sock is not None

    def connect(self):
        self.close()
        sock = socket.create_connection((self.host, self.port), timeout=1.0)
        sock.settimeout(1.0)
        self.sock = sock

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def send(self, command):
        """Envoie une commande ; reconnecte une fois si la connexion est tombee."""
        for attempt in range(2):
            try:
                if not self.sock:
                    self.connect()
                self.sock.sendall((command + "\r\n").encode("utf-8"))
                return True
            except OSError:
                self.close()
                if attempt:
                    raise
        return False

    def query(self, command):
        self.send(command)
        try:
            return self.sock.recv(1024).decode("utf-8", "replace").strip()
        except OSError:
            self.close()
            raise

    def split(self):
        self.send("split")

    def reset(self):
        self.send("reset")

    def start(self):
        self.send("starttimer")

    def timer_phase(self):
        """'NotRunning', 'Running', 'Ended', 'Paused' ou None si inconnu."""
        try:
            return self.query("getcurrenttimerphase")
        except OSError:
            return None
