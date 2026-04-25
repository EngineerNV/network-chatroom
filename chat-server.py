"""
AOL Retro Chatroom - Server
Multi-threaded TCP chat server on localhost:12000
"""
from socket import *
import sys
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("chat-server")

SERVER_HOST = "localhost"
SERVER_PORT = 12000
MAX_PENDING = 10
BUFFER = 4096
MAX_AUTH_TRIES = 3

# username -> password  (extend here to add accounts)
USERS = {
    "test1":      "p000",
    "test2":      "p000",
    "test3":      "p000",
    "engineerNV": "p591",
}

# Thread-safe shared state
_lock = threading.Lock()
socket_list: list[tuple[str, socket]] = []   # [(username, conn), ...]
online: list[str] = []


def _broadcast(message: str, exclude: socket | None = None) -> None:
    """Send a message to every connected client (optionally skip one)."""
    encoded = message.encode()
    with _lock:
        targets = list(socket_list)
    for _user, sock in targets:
        if sock is not exclude:
            try:
                sock.send(encoded)
            except OSError:
                pass


def _send(sock: socket, message: str) -> None:
    try:
        sock.send(message.encode())
    except OSError:
        pass


def _recv(sock: socket) -> str:
    try:
        return sock.recv(BUFFER).decode().strip()
    except OSError:
        return ""


def handle_client(conn: socket, addr: tuple) -> None:
    log.info("Connection from %s:%s", *addr)

    # --- Handshake ---
    data = _recv(conn)
    if data != "HELLO":
        conn.close()
        return
    _send(conn, "HELLO\n")

    # --- Authentication ---
    auth_user = ""
    for attempt in range(MAX_AUTH_TRIES):
        data = _recv(conn)
        parts = data.split(":")
        if len(parts) != 3 or parts[0] != "AUTH":
            _send(conn, "AUTHNO\n")
            continue
        _, usr, pwd = parts
        if USERS.get(usr) == pwd:
            auth_user = usr
            with _lock:
                socket_list.append((usr, conn))
                already_online = usr in online
                if not already_online:
                    online.append(usr)
            _send(conn, "AUTHYES\n")
            if not already_online:
                _broadcast(f"SIGNIN:{usr}\n")
                log.info("%s signed in", usr)
            break
        _send(conn, "AUTHNO\n")
    else:
        log.warning("Too many failed auth attempts from %s:%s", *addr)
        conn.close()
        return

    # --- Main message loop ---
    while True:
        data = _recv(conn)
        if not data:
            break

        if data == "LIST":
            with _lock:
                user_list = ", ".join(online)
            _send(conn, user_list + "\n")

        elif data.startswith("TO:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, recipient, msg = parts
                payload = f"FROM:{auth_user}:{msg}\n"
                with _lock:
                    targets = [s for u, s in socket_list if u == recipient]
                for sock in targets:
                    _send(sock, payload)
                if not targets:
                    _send(conn, f"SYSMSG:{recipient} is not online\n")
            log.info("%s -> %s", auth_user, parts[1] if len(parts) > 1 else "?")

        elif data == "BYE" or data == "":
            break

        else:
            log.warning("Unknown command from %s: %r", auth_user, data)

    # --- Clean up ---
    with _lock:
        try:
            socket_list.remove((auth_user, conn))
        except ValueError:
            pass
        remaining = sum(1 for u, _ in socket_list if u == auth_user)
        if remaining == 0 and auth_user in online:
            online.remove(auth_user)
            do_broadcast = True
        else:
            do_broadcast = False

    if do_broadcast:
        _broadcast(f"SIGNOFF:{auth_user}\n")
        log.info("%s signed off", auth_user)

    conn.close()


def main() -> None:
    try:
        server_sock = socket(AF_INET, SOCK_STREAM)
        server_sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server_sock.bind((SERVER_HOST, SERVER_PORT))
        server_sock.listen(MAX_PENDING)
        log.info("AOL Retro Chat Server ready on %s:%s", SERVER_HOST, SERVER_PORT)
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


if __name__ == "__main__":
    main()
