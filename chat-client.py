"""
LOL Retro Chatroom - CLI Client
Minimal terminal client, handy for testing the server without tkinter.
Supports sign-in, registration, listing users, and text DMs (no media).

Originally created by Nicholas Vaughn for ECPE 177, 10/12/2017; rewritten
when the server moved to a strictly newline-terminated protocol.
"""
import socket
import sys
import threading

SERVER_HOST = "localhost"
SERVER_PORT = 12000
RECV_CHUNK = 8192


class LineSocket:
    """Line-buffered reader/sender; the server only parses complete lines."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buf = bytearray()

    def send_line(self, line: str) -> None:
        self.sock.sendall((line + "\n").encode("utf-8"))

    def read_line(self) -> str | None:
        try:
            while b"\n" not in self._buf:
                chunk = self.sock.recv(RECV_CHUNK)
                if not chunk:
                    return None
                self._buf.extend(chunk)
        except OSError:
            return None
        idx = self._buf.index(b"\n")
        line = bytes(self._buf[:idx]).decode("utf-8", errors="replace").strip()
        del self._buf[: idx + 1]
        return line


def connect() -> LineSocket:
    host = input(f"Server host [{SERVER_HOST}]: ").strip() or SERVER_HOST
    port_s = input(f"Server port [{SERVER_PORT}]: ").strip() or str(SERVER_PORT)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port_s)))
    except (OSError, ValueError) as exc:
        print(f"ERROR: could not connect: {exc}")
        sys.exit(1)

    ls = LineSocket(sock)
    ls.send_line("HELLO")
    if ls.read_line() != "HELLO":
        print("ERROR: server did not answer the handshake")
        sys.exit(1)
    return ls


def sign_in(ls: LineSocket) -> str:
    while True:
        choice = input("1. Sign in  2. Create account — choose: ").strip()
        username = input("Screen name: ").strip()
        password = input("Password: ").strip()

        if choice == "2":
            ls.send_line(f"REGISTER:{username}:{password}")
            resp = ls.read_line() or ""
            if resp != "REGYES":
                reason = resp.split(":", 1)[1] if ":" in resp else resp
                print(f"Registration failed: {reason}")
                continue
            print("Account created!")

        ls.send_line(f"AUTH:{username}:{password}")
        resp = ls.read_line() or ""
        if resp.startswith("AUTHYES"):
            print(f"Signed in as {username}")
            return username
        reason = resp.split(":", 1)[1] if ":" in resp else "invalid credentials"
        print(f"Sign-in failed: {reason}")


def receiver(ls: LineSocket, stop: threading.Event) -> None:
    while not stop.is_set():
        line = ls.read_line()
        if line is None:
            if not stop.is_set():
                print("\n[disconnected from server]")
            break
        if line.startswith("FROM:"):
            _, sender, msg = line.split(":", 2)
            print(f"\n[{sender}] {msg}")
        elif line.startswith("FROMMEDIA:"):
            parts = line.split(":", 4)
            if len(parts) == 5:
                print(f"\n[{parts[1]}] sent a {parts[2]} ({parts[3]}) — "
                      f"use the GUI client to view it")
        elif line.startswith("SIGNIN:"):
            print(f"\n* {line.split(':', 1)[1]} signed on")
        elif line.startswith("SIGNOFF:"):
            print(f"\n* {line.split(':', 1)[1]} signed off")
        elif line.startswith("SYSMSG:"):
            print(f"\n* {line.split(':', 1)[1]}")
        else:
            print(f"\nOnline now: {line}")


def menu_loop(ls: LineSocket) -> None:
    while True:
        print("\n1. List online users\n2. Send a message\n3. Sign off")
        opt = input("Choose an option: ").strip()
        if opt == "1":
            ls.send_line("LIST")
        elif opt == "2":
            user = input("Send to: ").strip()
            msg = input("Message: ").strip()
            if user and msg:
                ls.send_line(f"TO:{user}:{msg}")
                print("Message sent!")
        elif opt == "3":
            ls.send_line("BYE")
            break
        else:
            print("Invalid option, try again")


def main() -> None:
    ls = connect()
    sign_in(ls)

    stop = threading.Event()
    t = threading.Thread(target=receiver, args=(ls, stop), daemon=True)
    t.start()

    try:
        menu_loop(ls)
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        stop.set()
        try:
            ls.sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()
