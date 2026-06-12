"""
Regenerate the README screenshots against a live server.

    xvfb-run -a -s "-screen 0 1280x800x24" python3 tests/capture_screenshots.py

Needs an X display plus `xwd` and ImageMagick's `convert` on PATH.
Writes PNGs into screenshots/.
"""
import base64
import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO_ROOT, "screenshots")

import tkinter as tk


def load_client_module():
    spec = importlib.util.spec_from_file_location(
        "chat_client_gui", os.path.join(REPO_ROOT, "chat-client-gui.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def snap(name: str) -> None:
    path = os.path.join(OUT_DIR, name)
    xwd = subprocess.run(["xwd", "-root", "-silent"], capture_output=True, check=True)
    subprocess.run(["convert", "xwd:-", path], input=xwd.stdout, check=True)
    print(f"wrote {path}")


def pump(widget, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        widget.update()
        time.sleep(0.02)


def start_server() -> subprocess.Popen:
    tmpdir = tempfile.mkdtemp(prefix="lol-shot-")
    server_copy = os.path.join(tmpdir, "chat-server.py")
    with open(os.path.join(REPO_ROOT, "chat-server.py")) as f:
        src = f.read()
    with open(server_copy, "w") as f:
        f.write(src)
    proc = subprocess.Popen([sys.executable, server_copy],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("localhost", 12000), timeout=0.5).close()
            return proc
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("server did not start")


class Peer:
    def __init__(self, user: str, pwd: str):
        self.sock = socket.create_connection(("localhost", 12000), timeout=5)
        self.send("HELLO"); self._drain()
        self.send(f"AUTH:{user}:{pwd}"); self._drain()

    def send(self, line: str) -> None:
        self.sock.sendall((line + "\n").encode("utf-8"))

    def _drain(self) -> None:
        self.sock.settimeout(2)
        try:
            self.sock.recv(65536)
        except OSError:
            pass


def main() -> None:
    gui = load_client_module()
    server = start_server()

    class ShotBuddyList(gui.BuddyList):
        def _show_login(self):
            pass

    app = ShotBuddyList()
    app.sfx.enabled = False
    app.geometry("+30+60")

    # 1 — sign-in dialog
    dlg = gui.LoginDialog(app)
    dlg.username_var.set("engineerNV")
    dlg.password_var.set("•••••")
    dlg.geometry("+340+120")
    pump(app, 0.8)
    snap("01-sign-in.png")
    dlg.destroy()

    # 2 — buddy list with two users online
    app._connect("localhost", 12000, "engineerNV", "p591")
    pump(app, 0.5)
    peer = Peer("test1", "p000")
    pump(app, 1.0)
    app._request_list()
    pump(app, 0.8)
    snap("02-buddy-list.png")

    # 3 — a conversation with emojis and an inline image
    peer.send("TO:engineerNV:hey!! is this the new LOL messenger?? 🌭")
    pump(app, 1.0)
    win = app.chat_windows["test1"]
    win.geometry("+330+90")
    win.append_text("engineerNV", "sure is — lots of love! ✨📼🐕", is_self=True)
    win.append_text("engineerNV", "check out this pixel art 🎨", is_self=True)

    art = tk.PhotoImage(width=120, height=72)
    for x in range(120):
        for y in range(72):
            if (x // 12 + y // 12) % 2 == 0:
                art.put("#FF2E9A", (x, y))
            else:
                art.put("#00F0FF", (x, y))
    png_path = os.path.join(tempfile.gettempdir(), "lol-art.png")
    art.write(png_path, format="png")
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    win.append_media("test1", "image", "pixel-art.png", b64)
    win.append_text("test1", "neon dachshund approved 🐕💾", is_self=False)
    pump(app, 1.0)
    snap("03-conversation.png")

    # 4 — emoji picker
    picker = gui.EmojiPicker(win, on_pick=lambda ch: None)
    picker.geometry("+420+200")
    pump(app, 0.8)
    snap("04-emoji-picker.png")
    picker.destroy()

    app.destroy()
    server.terminate()
    server.wait(timeout=5)


if __name__ == "__main__":
    main()
