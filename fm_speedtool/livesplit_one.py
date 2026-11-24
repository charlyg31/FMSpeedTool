"""Liaison avec LiveSplit One (web one.livesplit.org ou version de bureau ; Windows, Linux, Mac).

LiveSplit One ne lit pas de script .asl, mais il peut se connecter a un serveur (menu
"Connect to Server") : il ouvre un WebSocket vers une adresse, execute les commandes JSON
qu'il recoit ({"command": "split"}) et renvoie une reponse ({"success": ...} ou
{"error": ...}) ; il envoie aussi des evenements ({"event": "Splitted"}), ignores ici.

Ce module est ce serveur : il ecoute sur ws://localhost:<port> (bibliotheque standard
seulement) et garde la derniere connexion de LiveSplit One. Meme interface que
LiveSplitClient (split, reset, start, unsplit, split_index, connected, close).
"""

import base64
import hashlib
import json
import queue
import socket
import struct
import threading

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DEFAULT_PORT = 16835


class LiveSplitOneServer:
    def __init__(self, port=DEFAULT_PORT, host="127.0.0.1"):
        self.host, self.port = host, port
        self.listener = None
        self.client = None
        self.lock = threading.Lock()          # une commande a la fois (envoi + reponse)
        self.replies = queue.Queue()
        self.running = False

    # --- serveur ---------------------------------------------------------------------

    def start_server(self):
        """Ouvre le port d'ecoute ; OSError si le port est deja pris."""
        self.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(2)
        self.listener = sock
        self.running = True
        threading.Thread(target=self._accept_loop, args=(sock,), daemon=True).start()

    @property
    def listening(self):
        return self.listener is not None

    @property
    def connected(self):
        return self.client is not None

    @property
    def url(self):
        return f"ws://localhost:{self.port}"

    def close(self):
        self.running = False
        for s in (self.listener, self.client):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
        self.listener = self.client = None

    def _accept_loop(self, listener):
        while self.running and self.listener is listener:
            try:
                conn, _addr = listener.accept()
            except OSError:
                return
            try:
                conn.settimeout(5.0)
                self._handshake(conn)
                conn.settimeout(None)
            except (OSError, ValueError):
                conn.close()
                continue
            old, self.client = self.client, conn      # la derniere connexion remplace l'ancienne
            if old is not None:
                try:
                    old.close()
                except OSError:
                    pass
            threading.Thread(target=self._read_loop, args=(conn,), daemon=True).start()

    @staticmethod
    def _handshake(conn):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk or len(data) > 16384:
                raise ValueError("handshake")
            data += chunk
        headers = {}
        for line in data.split(b"\r\n")[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower()] = v.strip()
        key = headers.get(b"sec-websocket-key")
        if key is None:
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
            raise ValueError("pas une connexion WebSocket")
        accept = base64.b64encode(hashlib.sha1(key + WS_GUID.encode()).digest())
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                     b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n")

    @staticmethod
    def _recv_exact(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise OSError("connexion fermee")
            buf += chunk
        return buf

    def _read_loop(self, conn):
        parts = []
        try:
            while True:
                b0, b1 = self._recv_exact(conn, 2)
                fin, opcode = b0 & 0x80, b0 & 0x0F
                length = b1 & 0x7F
                if length == 126:
                    length = struct.unpack(">H", self._recv_exact(conn, 2))[0]
                elif length == 127:
                    length = struct.unpack(">Q", self._recv_exact(conn, 8))[0]
                mask = self._recv_exact(conn, 4) if b1 & 0x80 else None
                payload = self._recv_exact(conn, length)
                if mask:
                    payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
                if opcode == 0x8:                                  # fermeture
                    break
                if opcode == 0x9:                                  # ping -> pong
                    self._send_frame(conn, 0xA, payload)
                    continue
                if opcode in (0x0, 0x1):
                    parts.append(payload)
                    if fin:
                        self._on_message(b"".join(parts).decode("utf-8", "replace"))
                        parts = []
        except OSError:
            pass
        finally:
            if self.client is conn:
                self.client = None
            try:
                conn.close()
            except OSError:
                pass

    def _on_message(self, text):
        try:
            msg = json.loads(text)
        except ValueError:
            return
        if isinstance(msg, dict) and ("success" in msg or "error" in msg):
            self.replies.put(msg)                 # les evenements ({"event": ...}) sont ignores

    @staticmethod
    def _send_frame(conn, opcode, payload):
        n = len(payload)
        if n < 126:
            head = struct.pack(">BB", 0x80 | opcode, n)
        elif n < 65536:
            head = struct.pack(">BBH", 0x80 | opcode, 126, n)
        else:
            head = struct.pack(">BBQ", 0x80 | opcode, 127, n)
        conn.sendall(head + payload)

    # --- commandes -------------------------------------------------------------------

    def command(self, name, **params):
        """Envoie une commande et attend sa reponse ; OSError si LiveSplit One n'est pas connecte."""
        conn = self.client
        if conn is None:
            raise OSError("LiveSplit One non connecte")
        with self.lock:
            while not self.replies.empty():
                self.replies.get_nowait()
            try:
                self._send_frame(conn, 0x1, json.dumps(dict(command=name, **params)).encode("utf-8"))
            except OSError:
                if self.client is conn:
                    self.client = None
                raise
            try:
                return self.replies.get(timeout=1.0)
            except queue.Empty:
                return None

    def split(self):
        self.command("split")

    def reset(self):
        # Sans saveAttempt, LiveSplit One demande "Enregistrer les meilleurs temps ?" et
        # attend le joueur : la nouvelle run ne demarrerait pas. Oui, comme par defaut.
        self.command("reset", saveAttempt=True)

    def start(self):
        self.command("start")

    def unsplit(self):
        self.command("undoSplit")

    def state(self):
        """{'state': 'Running', 'index': 3}, {'state': 'NotRunning'}... ou None."""
        try:
            reply = self.command("getCurrentState")
        except OSError:
            return None
        if isinstance(reply, dict) and isinstance(reply.get("success"), dict):
            return reply["success"]
        return None

    def split_index(self):
        """Index du split en cours (-1 hors run) ou None si inconnu."""
        st = self.state()
        if st is None:
            return None
        if st.get("state") == "NotRunning":
            return -1
        return st.get("index")
