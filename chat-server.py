"""
LOL Retro Chatroom - Server
Multi-threaded TCP chat server with SQLite-backed accounts, account
self-registration, and image/GIF transfer (base64-framed over the existing
line-based protocol).

Listens on localhost:12000 by default.
"""
import socket
import hashlib
import logging
import os
import secrets
import sqlite3
import sys
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("lol-server")

SERVER_HOST = "localhost"
SERVER_PORT = 12000
MAX_PENDING = 10
RECV_CHUNK = 8192
MAX_LINE_BYTES = 8 * 1024 * 1024  # 8 MB max single message (base64 image)
MAX_AUTH_TRIES = 3
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat-data.db")

# Seed accounts created on first run if the DB doesn't exist yet.
SEED_USERS = {
    "test1":      "p000",
    "test2":      "p000",
    "test3":      "p000",
    "engineerNV": "p591",
}

# ── Thread-safe shared state ─────────────────────────────────────────────────
_lock = threading.Lock()
socket_list: list[tuple[str, socket.socket]] = []   # [(username, conn), ...]
online: list[str] = []
# Separate from `_lock` so a slow disk write can't stall message routing.
_db_lock = threading.Lock()


# ── Password hashing (PBKDF2-SHA256, stdlib only) ────────────────────────────
def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Return (salt_hex, hash_hex)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    # 120k iterations: comfortably above OWASP-recommended floor for SHA256
    # while still cheap enough not to stall the auth handshake on a laptop.
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), h.hex()


def _verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    _, candidate = _hash_password(password, salt)
    return secrets.compare_digest(candidate, hash_hex)


# ── DB helpers ───────────────────────────────────────────────────────────────
def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> sqlite3.Connection:
    # Seed accounts only land on a brand-new DB; once chat-data.db exists,
    # editing SEED_USERS has no effect (delete the file to re-seed).
    fresh = not os.path.exists(DB_PATH)
    conn = _connect_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            username   TEXT PRIMARY KEY,
            salt       TEXT NOT NULL,
            pwd_hash   TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS message_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            sender     TEXT NOT NULL,
            recipient  TEXT NOT NULL,
            kind       TEXT NOT NULL,    -- 'text' | 'image' | 'gif'
            ts         INTEGER NOT NULL
        );
        """
    )
    if fresh:
        now = int(time.time())
        for u, p in SEED_USERS.items():
            salt, h = _hash_password(p)
            conn.execute(
                "INSERT INTO users (username, salt, pwd_hash, created_at) VALUES (?,?,?,?)",
                (u, salt, h, now),
            )
        conn.commit()
        log.info("Initialized new SQLite DB with %d seed accounts.", len(SEED_USERS))
    else:
        log.info("Loaded existing SQLite DB at %s.", DB_PATH)
    return conn


db: sqlite3.Connection = None  # type: ignore


def db_user_exists(username: str) -> bool:
    with _db_lock:
        cur = db.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cur.fetchone() is not None


def db_register(username: str, password: str) -> tuple[bool, str]:
    if not username or not password:
        return False, "missing fields"
    if len(username) < 2 or len(username) > 24:
        return False, "username must be 2-24 chars"
    if not all(c.isalnum() or c in "_-." for c in username):
        return False, "username may only contain letters, digits, _ - ."
    if len(password) < 3:
        return False, "password too short"
    if len(password) > 128:
        return False, "password too long"
    salt, h = _hash_password(password)
    with _db_lock:
        try:
            db.execute(
                "INSERT INTO users (username, salt, pwd_hash, created_at) VALUES (?,?,?,?)",
                (username, salt, h, int(time.time())),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return False, "username already taken"
    return True, "ok"


def db_authenticate(username: str, password: str) -> bool:
    with _db_lock:
        row = db.execute(
            "SELECT salt, pwd_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return False
    return _verify_password(password, row["salt"], row["pwd_hash"])


def db_log_message(sender: str, recipient: str, kind: str) -> None:
    with _db_lock:
        db.execute(
            "INSERT INTO message_log (sender, recipient, kind, ts) VALUES (?,?,?,?)",
            (sender, recipient, kind, int(time.time())),
        )
        db.commit()


# ── Networking helpers ───────────────────────────────────────────────────────
class LineReader:
    """Buffered line reader so we can handle large base64 media payloads.

    A naive `recv(BUFFER)` would split a multi-megabyte TOMEDIA line across
    multiple reads and corrupt the protocol; this accumulates until a real
    `\\n` arrives.
    """

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buf = bytearray()

    def readline(self) -> str | None:
        while b"\n" not in self.buf:
            try:
                chunk = self.sock.recv(RECV_CHUNK)
            except OSError:
                return None
            if not chunk:
                return None
            self.buf.extend(chunk)
            # Cap per-line memory so a malicious peer can't OOM the server
            # by streaming bytes without ever sending a newline.
            if len(self.buf) > MAX_LINE_BYTES:
                return None
        idx = self.buf.index(b"\n")
        line = bytes(self.buf[:idx]).decode("utf-8", errors="replace").strip()
        del self.buf[: idx + 1]
        return line


def _send(sock: socket.socket, message: str) -> None:
    if not message.endswith("\n"):
        message += "\n"
    try:
        sock.sendall(message.encode("utf-8"))
    except OSError:
        pass


def _broadcast(message: str, exclude: socket.socket | None = None) -> None:
    encoded = (message if message.endswith("\n") else message + "\n").encode("utf-8")
    with _lock:
        targets = list(socket_list)
    for _user, sock in targets:
        if sock is not exclude:
            try:
                sock.sendall(encoded)
            except OSError:
                pass


def _send_to_user(recipient: str, payload: str) -> int:
    """Send `payload` to every connection for `recipient`; returns count."""
    encoded = (payload if payload.endswith("\n") else payload + "\n").encode("utf-8")
    with _lock:
        targets = [s for u, s in socket_list if u == recipient]
    for sock in targets:
        try:
            sock.sendall(encoded)
        except OSError:
            pass
    return len(targets)


# ── Per-client handler ───────────────────────────────────────────────────────
def handle_client(conn: socket.socket, addr: tuple) -> None:
    log.info("Connection from %s:%s", *addr)
    reader = LineReader(conn)

    line = reader.readline()
    if line != "HELLO":
        conn.close()
        return
    _send(conn, "HELLO")

    auth_user = ""
    auth_attempts = 0
    while auth_user == "":
        line = reader.readline()
        if line is None:
            conn.close()
            return

        if line.startswith("REGISTER:"):
            parts = line.split(":", 2)
            if len(parts) != 3:
                _send(conn, "REGNO:malformed")
                continue
            _, usr, pwd = parts
            ok, reason = db_register(usr.strip(), pwd)
            if ok:
                _send(conn, "REGYES")
                log.info("New account registered: %s", usr)
            else:
                _send(conn, f"REGNO:{reason}")
            continue

        if line.startswith("AUTH:"):
            parts = line.split(":", 2)
            if len(parts) != 3:
                _send(conn, "AUTHNO:malformed")
                auth_attempts += 1
            else:
                _, usr, pwd = parts
                if db_authenticate(usr, pwd):
                    auth_user = usr
                    with _lock:
                        socket_list.append((usr, conn))
                        already_online = usr in online
                        if not already_online:
                            online.append(usr)
                    _send(conn, "AUTHYES")
                    if not already_online:
                        _broadcast(f"SIGNIN:{usr}")
                        log.info("%s signed in", usr)
                    break
                _send(conn, "AUTHNO:invalid")
                auth_attempts += 1

            if auth_attempts >= MAX_AUTH_TRIES:
                log.warning("Too many failed auth attempts from %s:%s", *addr)
                conn.close()
                return
            continue

        if line == "BYE" or line == "":
            conn.close()
            return

        _send(conn, "AUTHNO:not_authenticated")

    try:
        while True:
            line = reader.readline()
            if line is None or line == "":
                break

            if line == "LIST":
                with _lock:
                    user_list = ", ".join(online)
                _send(conn, user_list)

            elif line == "BYE":
                break

            elif line.startswith("TO:"):
                parts = line.split(":", 2)
                if len(parts) != 3:
                    continue
                _, recipient, msg = parts
                payload = f"FROM:{auth_user}:{msg}"
                delivered = _send_to_user(recipient, payload)
                if delivered == 0:
                    _send(conn, f"SYSMSG:{recipient} is not online")
                else:
                    db_log_message(auth_user, recipient, "text")
                    log.info("%s -> %s [text]", auth_user, recipient)

            elif line.startswith("TOMEDIA:"):
                parts = line.split(":", 4)
                if len(parts) != 5:
                    _send(conn, "SYSMSG:malformed media payload")
                    continue
                _, recipient, kind, filename, b64 = parts
                kind = kind.strip().lower()
                if kind not in ("image", "gif"):
                    _send(conn, "SYSMSG:unsupported media type")
                    continue
                payload = f"FROMMEDIA:{auth_user}:{kind}:{filename}:{b64}"
                delivered = _send_to_user(recipient, payload)
                if delivered == 0:
                    _send(conn, f"SYSMSG:{recipient} is not online")
                else:
                    db_log_message(auth_user, recipient, kind)
                    log.info("%s -> %s [%s, %d bytes b64]",
                             auth_user, recipient, kind, len(b64))

            else:
                log.warning("Unknown command from %s: %r", auth_user,
                            line[:80] + ("..." if len(line) > 80 else ""))

    finally:
        with _lock:
            try:
                socket_list.remove((auth_user, conn))
            except ValueError:
                pass
            remaining = sum(1 for u, _ in socket_list if u == auth_user)
            do_broadcast = remaining == 0 and auth_user in online
            if do_broadcast:
                online.remove(auth_user)

        if do_broadcast:
            _broadcast(f"SIGNOFF:{auth_user}")
            log.info("%s signed off", auth_user)

        try:
            conn.close()
        except OSError:
            pass


def main() -> None:
    global db
    db = init_db()

    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((SERVER_HOST, SERVER_PORT))
        server_sock.listen(MAX_PENDING)
        log.info("LOL Retro Chat Server ready on %s:%s", SERVER_HOST, SERVER_PORT)
    except OSError as exc:
        log.error("Cannot start server: %s", exc)
        sys.exit(1)

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log.info("Server shutting down.")
    finally:
        server_sock.close()
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
