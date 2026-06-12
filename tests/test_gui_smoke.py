"""
Headless smoke test for chat-client-gui.py.

Requires tkinter and an X display (real or virtual):

    xvfb-run -a python3 tests/test_gui_smoke.py

Boots the real server as a subprocess, drives a real BuddyList window
(login dialog suppressed), and exercises text messaging, media rendering,
and the GIF-animation plumbing end to end.
"""
import base64
import importlib.util
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import tkinter as tk
    _probe = tk.Tk()
    _probe.destroy()
    HAVE_DISPLAY = True
except Exception:
    HAVE_DISPLAY = False


def load_client_module():
    spec = importlib.util.spec_from_file_location(
        "chat_client_gui", os.path.join(REPO_ROOT, "chat-client-gui.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class RawPeer:
    """Second chat participant implemented as a bare socket."""

    def __init__(self, port: int, user: str, pwd: str):
        self.sock = socket.create_connection(("localhost", port), timeout=5)
        self._buf = bytearray()
        self.send("HELLO")
        resp = self.read()
        if resp != "HELLO":
            raise RuntimeError(f"handshake failed: expected 'HELLO', got {resp!r}")
        self.send(f"AUTH:{user}:{pwd}")
        resp = self.read()
        if resp != "AUTHYES":
            raise RuntimeError(f"auth failed: expected 'AUTHYES', got {resp!r}")

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
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.read(timeout=max(0.1, deadline - time.monotonic()))
            if line is None:
                return None
            if line.startswith(prefix):
                return line
        return None

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


@unittest.skipUnless(HAVE_DISPLAY, "tkinter or X display unavailable")
class GuiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The server writes chat-data.db next to chat-server.py, so run it
        # from a copy in a temp dir to keep the repo clean.
        cls.tmpdir = tempfile.mkdtemp(prefix="lol-gui-test-")
        server_copy = os.path.join(cls.tmpdir, "chat-server.py")
        with open(os.path.join(REPO_ROOT, "chat-server.py")) as f:
            src = f.read()
        # Pick an ephemeral free port and patch the copied server to use it.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("localhost", 0))
            cls.port = probe.getsockname()[1]
        src = src.replace("SERVER_PORT = 12000", f"SERVER_PORT = {cls.port}", 1)
        with open(server_copy, "w") as f:
            f.write(src)
        cls.server = subprocess.Popen(
            [sys.executable, server_copy],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                socket.create_connection(("localhost", cls.port),
                                         timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("server did not start")

        cls.gui = load_client_module()

        # Suppress the modal login dialog; tests sign in programmatically.
        class TestableBuddyList(cls.gui.BuddyList):
            def _show_login(self):
                pass

        cls.app = TestableBuddyList()
        cls.app._connect("localhost", cls.port, "test1", "p000")
        cls.pump()
        if not cls.app.running:
            raise RuntimeError("GUI failed to sign in")

        cls.peer = RawPeer(cls.port, "test2", "p000")
        cls.pump()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.peer.close()
            cls.app.destroy()
        except Exception:
            pass
        cls.server.terminate()
        cls.server.wait(timeout=5)

    @classmethod
    def pump(cls, seconds: float = 0.5):
        """Run the Tk event loop briefly so after() callbacks fire."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            cls.app.update()
            time.sleep(0.02)

    # ── tests ────────────────────────────────────────────────────────────────

    def test_01_signed_in_state(self):
        self.assertEqual(self.app.my_name, "test1")
        self.assertIn("test1", self.app.screen_name_lbl.cget("text"))

    def test_02_buddy_list_shows_peer(self):
        self.app._request_list()
        self.pump()
        buddies = list(self.app.buddy_listbox.get(0, "end"))
        self.assertTrue(any("test2" in b for b in buddies), buddies)

    def test_03_incoming_text_opens_chat_window(self):
        self.peer.send("TO:test1:hello from the wire 🌭")
        self.pump(1.0)
        self.assertIn("test2", self.app.chat_windows)
        win = self.app.chat_windows["test2"]
        content = win.log.get("1.0", "end")
        self.assertIn("hello from the wire", content)

    def test_04_outgoing_text_reaches_peer(self):
        self.app._send_text("test2", "right back at you")
        line = self.peer.read_until("FROM:test1")
        self.assertEqual(line, "FROM:test1:right back at you")

    def test_05_incoming_png_renders_inline(self):
        img = tk.PhotoImage(width=8, height=8)
        img.put("#FF2E9A", to=(0, 0, 8, 8))
        png_path = os.path.join(self.tmpdir, "pix.png")
        img.write(png_path, format="png")
        with open(png_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")

        win = self.app.chat_windows["test2"]
        before = len(win._image_refs)
        self.peer.send(f"FROMMEDIA:test1:image:pix.png:{b64}".replace(
            "FROMMEDIA:test1", "TOMEDIA:test1"))
        self.pump(1.5)
        self.assertEqual(len(win._image_refs), before + 1)
        self.assertIn("sent a image: pix.png", win.log.get("1.0", "end"))

    def test_06_gif_anim_uses_stable_image_name(self):
        # Regression test: image_configure must address the embedded image
        # by the name image_create returned, not by a positional text index.
        img = tk.PhotoImage(width=4, height=4)
        img.put("#00F0FF", to=(0, 0, 4, 4))
        gif_path = os.path.join(self.tmpdir, "anim.gif")
        img.write(gif_path, format="gif")

        win = self.app.chat_windows["test2"]
        win.log.configure(state="normal")
        keep = tk.PhotoImage(file=gif_path)
        name = win.log.image_create("end", image=keep)
        win.log.insert("end", "\ntrailing text moves any numeric index\n")
        win.log.configure(state="disabled")

        anim = self.gui.GifAnim(win.log, gif_path)
        self.assertEqual(len(anim.frames), 1)
        win.log.image_configure(name, image=anim.frames[0])  # must not raise
        self._keep = (keep, anim)

    def test_07_sound_fx_generated(self):
        expected = {"msg_in", "msg_send", "signin", "signoff",
                    "error", "media_in"}
        self.assertEqual(set(self.app.sfx.paths), expected)
        for path in self.app.sfx.paths.values():
            self.assertGreater(os.path.getsize(path), 100)
        self.app.sfx.play("msg_in")  # must not raise even with no audio out

    def test_08_offline_recipient_systmsg(self):
        self.app._send_text("nobody-home", "echo?")
        self.pump(1.0)
        self.assertIsNotNone(self.app.system_win)
        notices = self.app.system_win.log.get("1.0", "end")
        self.assertIn("nobody-home is not online", notices)


if __name__ == "__main__":
    unittest.main(verbosity=2)
