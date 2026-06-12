"""
End-to-end backend tests for chat-server.py.

Boots the real server (in-process, on an ephemeral port, against a
temporary database) and drives it over real TCP sockets. Stdlib only:

    python3 tests/test_backend.py
"""
import base64
import importlib.util
import os
import secrets
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_server_module(db_path: str):
    spec = importlib.util.spec_from_file_location(
        "chat_server", os.path.join(REPO_ROOT, "chat-server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = db_path
    return mod


class TestClient:
    """Thin line-oriented client mirroring what the GUI client sends."""

    def __init__(self, port: int):
        self.sock = socket.create_connection(("localhost", port), timeout=5)
        self._buf = bytearray()

    def send(self, line: str) -> None:
        self.sock.sendall((line + "\n").encode("utf-8"))

    def read(self, timeout: float = 5.0) -> str | None:
        self.sock.settimeout(timeout)
        try:
            while b"\n" not in self._buf:
                chunk = self.sock.recv(65536)
                if not chunk:
                    return None
                self._buf.extend(chunk)
        except OSError:
            return None
        idx = self._buf.index(b"\n")
        line = bytes(self._buf[:idx]).decode("utf-8").strip()
        del self._buf[: idx + 1]
        return line

    def read_until(self, prefix: str, timeout: float = 5.0) -> str | None:
        """Read lines, skipping broadcasts, until one starts with `prefix`."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.read(timeout=max(0.1, deadline - time.monotonic()))
            if line is None:
                return None
            if line.startswith(prefix):
                return line
        return None

    def handshake(self) -> None:
        self.send("HELLO")
        assert self.read() == "HELLO"

    def login(self, user: str, pwd: str) -> str:
        self.handshake()
        self.send(f"AUTH:{user}:{pwd}")
        return self.read() or ""

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class BackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="lol-test-")
        cls.db_path = os.path.join(cls.tmpdir, "test.db")
        cls.mod = load_server_module(cls.db_path)
        cls.mod.db = cls.mod.init_db()

        cls.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        cls.server_sock.bind(("localhost", 0))
        cls.port = cls.server_sock.getsockname()[1]
        cls.server_sock.listen(10)

        def accept_loop():
            while True:
                try:
                    conn, addr = cls.server_sock.accept()
                except OSError:
                    return
                threading.Thread(target=cls.mod.handle_client,
                                 args=(conn, addr), daemon=True).start()

        threading.Thread(target=accept_loop, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server_sock.close()

    # ── handshake & auth ─────────────────────────────────────────────────────

    def test_handshake(self):
        c = TestClient(self.port)
        c.send("HELLO")
        self.assertEqual(c.read(), "HELLO")
        c.close()

    def test_bad_handshake_closes_connection(self):
        c = TestClient(self.port)
        c.send("EHLO")
        self.assertIsNone(c.read())
        c.close()

    def test_seed_account_auth(self):
        c = TestClient(self.port)
        self.assertEqual(c.login("test1", "p000"), "AUTHYES")
        c.send("BYE")
        c.close()

    def test_wrong_password_rejected(self):
        c = TestClient(self.port)
        self.assertEqual(c.login("test1", "nope"), "AUTHNO:invalid")
        c.close()

    def test_three_failures_disconnect(self):
        c = TestClient(self.port)
        c.handshake()
        for _ in range(3):
            c.send("AUTH:test1:wrong")
            self.assertEqual(c.read(), "AUTHNO:invalid")
        self.assertIsNone(c.read(timeout=2))
        c.close()

    # ── registration ─────────────────────────────────────────────────────────

    def test_register_then_login(self):
        c = TestClient(self.port)
        c.handshake()
        c.send("REGISTER:newdog:woofwoof")
        self.assertEqual(c.read(), "REGYES")
        c.send("AUTH:newdog:woofwoof")
        self.assertEqual(c.read(), "AUTHYES")
        c.send("BYE")
        c.close()

    def test_register_duplicate_rejected(self):
        c = TestClient(self.port)
        c.handshake()
        c.send("REGISTER:dupuser:pass1")
        self.assertEqual(c.read(), "REGYES")
        c.send("REGISTER:dupuser:pass2")
        self.assertEqual(c.read(), "REGNO:username already taken")
        c.close()

    def test_register_bad_username_rejected(self):
        c = TestClient(self.port)
        c.handshake()
        c.send("REGISTER:bad name!:password")
        resp = c.read() or ""
        self.assertTrue(resp.startswith("REGNO:"))
        c.close()

    def test_register_short_password_rejected(self):
        c = TestClient(self.port)
        c.handshake()
        c.send("REGISTER:shortpw:ab")
        self.assertEqual(c.read(), "REGNO:password too short")
        c.close()

    # ── messaging ────────────────────────────────────────────────────────────

    def test_text_dm_roundtrip(self):
        a = TestClient(self.port)
        b = TestClient(self.port)
        self.assertEqual(a.login("test1", "p000"), "AUTHYES")
        self.assertEqual(b.login("test2", "p000"), "AUTHYES")
        a.send("TO:test2:hello there 🌭")
        line = b.read_until("FROM:")
        self.assertEqual(line, "FROM:test1:hello there 🌭")
        for c in (a, b):
            c.send("BYE")
            c.close()

    def test_message_to_offline_user(self):
        a = TestClient(self.port)
        self.assertEqual(a.login("test3", "p000"), "AUTHYES")
        a.send("TO:ghost:anyone home?")
        line = a.read_until("SYSMSG:")
        self.assertEqual(line, "SYSMSG:ghost is not online")
        a.send("BYE")
        a.close()

    def test_media_roundtrip(self):
        a = TestClient(self.port)
        b = TestClient(self.port)
        self.assertEqual(a.login("test1", "p000"), "AUTHYES")
        self.assertEqual(b.login("test2", "p000"), "AUTHYES")
        payload = base64.b64encode(secrets.token_bytes(200_000)).decode()
        a.send(f"TOMEDIA:test2:image:pup.png:{payload}")
        line = b.read_until("FROMMEDIA:", timeout=10)
        self.assertIsNotNone(line)
        _, sender, kind, fname, b64 = line.split(":", 4)
        self.assertEqual((sender, kind, fname), ("test1", "image", "pup.png"))
        self.assertEqual(b64, payload)
        for c in (a, b):
            c.send("BYE")
            c.close()

    def test_media_bad_kind_rejected(self):
        a = TestClient(self.port)
        self.assertEqual(a.login("test1", "p000"), "AUTHYES")
        a.send("TOMEDIA:test2:exe:virus.exe:AAAA")
        line = a.read_until("SYSMSG:")
        self.assertEqual(line, "SYSMSG:unsupported media type")
        a.send("BYE")
        a.close()

    # ── presence ─────────────────────────────────────────────────────────────

    def test_signin_signoff_broadcast_and_list(self):
        a = TestClient(self.port)
        self.assertEqual(a.login("test1", "p000"), "AUTHYES")

        b = TestClient(self.port)
        self.assertEqual(b.login("test2", "p000"), "AUTHYES")
        self.assertEqual(a.read_until("SIGNIN:test2"), "SIGNIN:test2")

        a.send("LIST")
        listing = a.read_until("test1")
        self.assertIn("test2", listing)

        b.send("BYE")
        b.close()
        self.assertEqual(a.read_until("SIGNOFF:test2"), "SIGNOFF:test2")
        a.send("BYE")
        a.close()

    # ── persistence ──────────────────────────────────────────────────────────

    def test_message_log_persisted(self):
        a = TestClient(self.port)
        b = TestClient(self.port)
        self.assertEqual(a.login("test1", "p000"), "AUTHYES")
        self.assertEqual(b.login("test3", "p000"), "AUTHYES")
        a.send("TO:test3:logged message")
        self.assertEqual(b.read_until("FROM:test1"), "FROM:test1:logged message")
        for c in (a, b):
            c.send("BYE")
            c.close()

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT COUNT(*) FROM message_log "
            "WHERE sender='test1' AND recipient='test3' AND kind='text'"
        ).fetchone()
        conn.close()
        self.assertGreaterEqual(rows[0], 1)

    def test_passwords_not_stored_in_plaintext(self):
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT salt, pwd_hash FROM users WHERE username='test1'"
        ).fetchone()
        conn.close()
        self.assertNotIn("p000", row[0])
        self.assertNotIn("p000", row[1])
        self.assertEqual(len(bytes.fromhex(row[0])), 16)
        self.assertEqual(len(bytes.fromhex(row[1])), 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
