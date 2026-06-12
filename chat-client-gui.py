"""
LOL Retro Chatroom - GUI Client
Tkinter client with a synthwave/vaporwave aesthetic, sound effects,
dachshund + retro emoji picker, image/GIF sharing, and self-service
account creation.
"""
import socket
import base64
import math
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import wave
from tkinter import messagebox, simpledialog, scrolledtext, filedialog

# ── Server config ────────────────────────────────────────────────────────────
SERVER_HOST = "localhost"
SERVER_PORT = 12000
RECV_CHUNK = 8192
MAX_MEDIA_BYTES = 4 * 1024 * 1024   # 4 MB cap for outgoing image/gif
SUPPORTED_MEDIA_EXTS = (".png", ".gif", ".pgm", ".ppm")

# ── LOL Synthwave / Vaporwave palette ────────────────────────────────────────
NEON_PINK     = "#FF2E9A"
NEON_CYAN     = "#00F0FF"
NEON_PURPLE   = "#A445FF"
NEON_YELLOW   = "#F9F871"
NEON_GREEN    = "#3DFFB0"
DEEP_NAVY     = "#0D0221"
DEEP_PURPLE   = "#241734"
PANEL_BG      = "#1B0A2E"
CHAT_BG       = "#120524"
GRID_LINE     = "#3A1A5E"
TEXT_FG       = "#F4E9FF"
DIM_TEXT      = "#9B7FBF"
SELF_MSG      = "#FFD23F"      # warm gold for own messages
OTHER_MSG     = "#00F0FF"      # cyan for incoming
SYSTEM_MSG    = "#FF8AD8"      # soft pink for system
ERROR_FG      = "#FF4D6D"
BTN_BG        = "#2D124D"
BTN_ACTIVE    = "#4A1F7A"
BORDER_GLOW   = "#FF2E9A"

# ── Fonts ────────────────────────────────────────────────────────────────────
FONT_TITLE    = ("Courier New", 14, "bold")
FONT_HEADER   = ("Courier New", 10, "bold")
FONT_BODY     = ("Courier New", 11)
FONT_CHAT     = ("Courier New", 11)
FONT_SYSTEM   = ("Courier New", 9, "italic")
FONT_BUDDY    = ("Courier New", 10, "bold")
FONT_MONO_SM  = ("Courier New", 8)
FONT_EMOJI    = ("Segoe UI Emoji", 14) if sys.platform == "win32" else ("Courier New", 14)

# ── ASCII art banner ─────────────────────────────────────────────────────────
LOL_BANNER = (
    "  ██╗      ██████╗ ██╗     \n"
    "  ██║     ██╔═══██╗██║     \n"
    "  ██║     ██║   ██║██║     \n"
    "  ██║     ██║   ██║██║     \n"
    "  ███████╗╚██████╔╝███████╗\n"
    "  ╚══════╝ ╚═════╝ ╚══════╝\n"
    "  >> Lots Of Love Messenger\n"
)

# ── Emoji palettes ───────────────────────────────────────────────────────────
# Dachshunds first (the 🌭 hot dog is the universal wiener-dog stand-in).
DACHSHUND_EMOJIS = ["🐕", "🌭", "🐶", "🦴", "🐾", "❤️‍🐕", "🐩", "🐺"]
RETRO_EMOJIS = [
    "📼", "💾", "💿", "📀", "📟", "📺", "📻", "☎️", "📞", "📠",
    "🕹️", "👾", "🎮", "🎞️", "📷", "📸", "💽", "🖥️", "⌨️", "🖱️",
    "💌", "📬", "🪩", "🎀", "🌈", "✨", "⭐", "🌟", "💫", "🔮",
    "🛼", "🎧", "🎤", "🪀", "🧃", "🍭", "🍓", "🌸",
]
EMOJI_PALETTE = DACHSHUND_EMOJIS + RETRO_EMOJIS


# ─────────────────────────────────────────────────────────────────────────────
#  Sound effects: generate WAVs at startup, play via platform tools
# ─────────────────────────────────────────────────────────────────────────────
class SoundFX:
    """Generates a few short WAV files on disk and plays them on demand.

    Synthesizing tones at startup keeps the project zero-dependency (no
    bundled audio assets, no pip packages). Playback is delegated to the
    OS's audio CLI so we don't need to link an audio library into Python.
    """

    SAMPLE_RATE = 22050

    def __init__(self):
        self.enabled = True
        self.dir = tempfile.mkdtemp(prefix="lol-chat-sfx-")
        self.paths: dict[str, str] = {}
        self._player = self._detect_player()
        self._build_all()

    # ── platform-specific player detection ───────────────────────────────────
    @staticmethod
    def _detect_player() -> list[str] | None:
        if sys.platform == "win32":
            return ["__winsound__"]
        if sys.platform == "darwin":
            return ["afplay"]
        for cmd in (["paplay"], ["aplay", "-q"], ["play", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
            try:
                subprocess.run([cmd[0], "--version"], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=1)
                return cmd
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        return None

    # ── tone synthesis ───────────────────────────────────────────────────────
    def _write_wav(self, name: str, samples: list[float]) -> str:
        path = os.path.join(self.dir, f"{name}.wav")
        frames = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s))
            frames.extend(struct.pack("<h", int(v * 30000)))
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(bytes(frames))
        self.paths[name] = path
        return path

    def _tone(self, freq: float, duration: float, *, attack: float = 0.01,
              decay: float = 0.05, harmonics: tuple[float, ...] = (1.0,)) -> list[float]:
        n = int(self.SAMPLE_RATE * duration)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            sample = 0.0
            for k, amp in enumerate(harmonics, start=1):
                sample += amp * math.sin(2 * math.pi * freq * k * t)
            env = 1.0
            if t < attack:
                env = t / attack
            elif t > duration - decay:
                env = max(0.0, (duration - t) / decay)
            out.append(0.4 * env * sample / max(1.0, sum(harmonics)))
        return out

    def _silence(self, duration: float) -> list[float]:
        return [0.0] * int(self.SAMPLE_RATE * duration)

    def _build_all(self):
        # Incoming message: classic two-tone "ding" (high then higher)
        self._write_wav("msg_in",
                        self._tone(880, 0.08) + self._tone(1320, 0.12))
        # Outgoing message: short upward blip
        self._write_wav("msg_send",
                        self._tone(660, 0.04) + self._tone(990, 0.05))
        # Sign-in: ascending arpeggio
        self._write_wav("signin",
                        self._tone(523, 0.08) + self._tone(659, 0.08) +
                        self._tone(784, 0.10) + self._tone(1046, 0.18))
        # Sign-off: descending arpeggio
        self._write_wav("signoff",
                        self._tone(784, 0.10) + self._tone(587, 0.10) +
                        self._tone(392, 0.18))
        # Error: low buzzy square-ish blip
        self._write_wav("error",
                        self._tone(196, 0.18, harmonics=(1.0, 0.6, 0.3)))
        # Image/gif arrival: shimmery high-low ping
        self._write_wav("media_in",
                        self._tone(1568, 0.06) + self._silence(0.02) +
                        self._tone(1175, 0.08) + self._tone(1760, 0.10))

    # ── playback ─────────────────────────────────────────────────────────────
    def play(self, name: str) -> None:
        if not self.enabled:
            return
        path = self.paths.get(name)
        if not path:
            return
        # Off-thread so audio playback never blocks the Tk event loop, even
        # if the chosen player takes a moment to spawn.
        threading.Thread(target=self._play_blocking, args=(path,), daemon=True).start()

    def _play_blocking(self, path: str) -> None:
        try:
            if not self._player:
                return
            if self._player == ["__winsound__"]:
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            subprocess.run(self._player + [path],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           timeout=5)
        except Exception:
            pass

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled


# ─────────────────────────────────────────────────────────────────────────────
#  Networking helpers (line-buffered reader, line sender)
# ─────────────────────────────────────────────────────────────────────────────
class LineSocket:
    """Wraps a socket with a line-buffered reader and line-aware sender."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self._buf = bytearray()

    def send_line(self, line: str) -> None:
        if not line.endswith("\n"):
            line += "\n"
        self.sock.sendall(line.encode("utf-8"))

    def read_line(self, timeout: float | None = None) -> str | None:
        if timeout is not None:
            self.sock.settimeout(timeout)
        try:
            while b"\n" not in self._buf:
                chunk = self.sock.recv(RECV_CHUNK)
                if not chunk:
                    return None
                self._buf.extend(chunk)
            idx = self._buf.index(b"\n")
            line = bytes(self._buf[:idx]).decode("utf-8", errors="replace").strip()
            del self._buf[: idx + 1]
            return line
        except OSError:
            return None
        finally:
            if timeout is not None:
                try:
                    self.sock.settimeout(None)
                except OSError:
                    pass

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Tiny neon-button helper
# ─────────────────────────────────────────────────────────────────────────────
def neon_button(parent, text, command, *, primary=False, width=None):
    fg = NEON_YELLOW if primary else NEON_CYAN
    bg = BTN_BG
    btn = tk.Button(
        parent, text=text, command=command,
        font=FONT_HEADER, fg=fg, bg=bg,
        activebackground=BTN_ACTIVE, activeforeground=NEON_PINK,
        relief="raised", bd=2, padx=12, pady=4,
        highlightbackground=BORDER_GLOW, highlightthickness=1,
        cursor="hand2",
    )
    if width:
        btn.config(width=width)
    return btn


# ─────────────────────────────────────────────────────────────────────────────
#  Login Dialog (with Create-Account button)
# ─────────────────────────────────────────────────────────────────────────────
class LoginDialog(tk.Toplevel):
    """Returns: ('login'|'register', username, password, host, port) or None."""

    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.result: tuple | None = None

        self.title("LOL Messenger - Sign In")
        self.resizable(False, False)
        self.configure(bg=DEEP_NAVY)
        self.grab_set()

        self._build()
        self.update_idletasks()
        w, h = 400, 500
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        banner = tk.Frame(self, bg=DEEP_NAVY)
        banner.pack(fill="x", pady=(12, 0))

        tk.Label(banner, text="L O L", font=("Courier New", 36, "bold"),
                 fg=NEON_PINK, bg=DEEP_NAVY).pack()
        tk.Label(banner, text="Lots Of Love Messenger",
                 font=("Courier New", 11, "italic"),
                 fg=NEON_CYAN, bg=DEEP_NAVY).pack()
        tk.Label(banner, text="🌭  ✨  📼  🐕  💾  🌈",
                 font=("Courier New", 14), fg=NEON_YELLOW,
                 bg=DEEP_NAVY).pack(pady=(6, 0))

        tk.Label(self, text='"You\'ve got vibes!"',
                 font=("Courier New", 10, "italic"),
                 fg=NEON_PURPLE, bg=DEEP_NAVY).pack(pady=(8, 4))

        tk.Frame(self, bg=NEON_PINK, height=2).pack(fill="x", padx=24, pady=4)

        form = tk.Frame(self, bg=DEEP_NAVY, padx=32)
        form.pack(fill="x", pady=8)

        def label(parent, text):
            return tk.Label(parent, text=text, font=FONT_HEADER,
                            fg=NEON_CYAN, bg=DEEP_NAVY, anchor="w")

        def entry(parent, var, *, show=None):
            return tk.Entry(parent, textvariable=var, font=FONT_BODY, width=24,
                            bg=PANEL_BG, fg=TEXT_FG, insertbackground=NEON_PINK,
                            relief="flat", bd=0, show=show or "",
                            highlightbackground=NEON_PURPLE,
                            highlightcolor=NEON_PINK, highlightthickness=1)

        label(form, "▶ Screen Name").grid(row=0, column=0, sticky="w", pady=(4, 2))
        self.username_var = tk.StringVar()
        ue = entry(form, self.username_var)
        ue.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ue.focus_set()

        label(form, "▶ Password").grid(row=2, column=0, sticky="w", pady=(4, 2))
        self.password_var = tk.StringVar()
        entry(form, self.password_var, show="●").grid(row=3, column=0, sticky="ew", pady=(0, 8))

        form.columnconfigure(0, weight=1)

        host_row = tk.Frame(self, bg=DEEP_NAVY, padx=32)
        host_row.pack(fill="x", pady=(4, 4))
        tk.Label(host_row, text="HOST", font=FONT_MONO_SM,
                 fg=DIM_TEXT, bg=DEEP_NAVY).pack(side="left")
        self.host_var = tk.StringVar(value=SERVER_HOST)
        entry(host_row, self.host_var).pack(side="left", padx=(4, 8))
        tk.Label(host_row, text="PORT", font=FONT_MONO_SM,
                 fg=DIM_TEXT, bg=DEEP_NAVY).pack(side="left")
        self.port_var = tk.StringVar(value=str(SERVER_PORT))
        e = entry(host_row, self.port_var)
        e.config(width=6)
        e.pack(side="left", padx=4)

        btns = tk.Frame(self, bg=DEEP_NAVY)
        btns.pack(pady=18)

        neon_button(btns, "▶ SIGN IN", self._on_sign_in,
                    primary=True).pack(side="left", padx=6)
        neon_button(btns, "+ CREATE ACCOUNT",
                    self._on_register).pack(side="left", padx=6)
        neon_button(btns, "✕ CANCEL", self.destroy).pack(side="left", padx=6)

        self.bind("<Return>", lambda _e: self._on_sign_in())

        tk.Label(self, text="▼ no copyright dachshunds were harmed ▼",
                 font=FONT_MONO_SM, fg=DIM_TEXT,
                 bg=DEEP_NAVY).pack(side="bottom", pady=8)

    def _validate(self):
        u = self.username_var.get().strip()
        p = self.password_var.get()
        if not u or not p:
            messagebox.showwarning("LOL", "Please enter Screen Name and Password.",
                                   parent=self)
            return None
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showwarning("LOL", "Port must be a number.", parent=self)
            return None
        return u, p, self.host_var.get().strip(), port

    def _on_sign_in(self):
        v = self._validate()
        if v:
            self.result = ("login", *v)
            self.destroy()

    def _on_register(self):
        v = self._validate()
        if v:
            self.result = ("register", *v)
            self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Emoji picker (popup grid)
# ─────────────────────────────────────────────────────────────────────────────
class EmojiPicker(tk.Toplevel):
    def __init__(self, parent, on_pick):
        super().__init__(parent)
        self.on_pick = on_pick
        self.title("✦ Pick an emoji ✦")
        self.configure(bg=DEEP_NAVY)
        self.resizable(False, False)
        self.transient(parent)

        tk.Label(self, text="🐕  DACHSHUNDS  🌭",
                 font=FONT_HEADER, fg=NEON_PINK, bg=DEEP_NAVY).pack(pady=(8, 2))
        self._grid_section(DACHSHUND_EMOJIS, cols=8)

        tk.Label(self, text="📼  RETRO VIBES  ✨",
                 font=FONT_HEADER, fg=NEON_CYAN, bg=DEEP_NAVY).pack(pady=(6, 2))
        self._grid_section(RETRO_EMOJIS, cols=10)

    def _grid_section(self, items, cols):
        frame = tk.Frame(self, bg=DEEP_NAVY)
        frame.pack(padx=8, pady=2)
        for i, ch in enumerate(items):
            r, c = divmod(i, cols)
            btn = tk.Label(frame, text=ch, font=FONT_EMOJI,
                           bg=PANEL_BG, fg=TEXT_FG,
                           padx=6, pady=4, cursor="hand2",
                           highlightbackground=NEON_PURPLE,
                           highlightthickness=1)
            btn.grid(row=r, column=c, padx=2, pady=2)
            btn.bind("<Enter>", lambda e, b=btn: b.config(bg=BTN_ACTIVE))
            btn.bind("<Leave>", lambda e, b=btn: b.config(bg=PANEL_BG))
            btn.bind("<Button-1>", lambda e, ch=ch: self._pick(ch))

    def _pick(self, ch):
        self.on_pick(ch)
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Animated-GIF helper (manual frame cycling via PhotoImage)
# ─────────────────────────────────────────────────────────────────────────────
class GifAnim:
    """Loads all frames of a GIF from disk and cycles them in a Text widget.

    Tk's PhotoImage doesn't expose animated-GIF playback directly; the
    workaround is to load each frame by index and rotate the displayed
    image manually. We use a fixed ~10 fps tick rather than parsing per-
    frame delays — good enough for chat-window doodles, not for cinema.
    """

    def __init__(self, text_widget: tk.Text, path: str):
        self.text = text_widget
        self.frames: list[tk.PhotoImage] = []
        self._stopped = False
        # Probe frame indexes until PhotoImage refuses; that's how we
        # discover the frame count without a GIF parser.
        i = 0
        while True:
            try:
                frame = tk.PhotoImage(file=path, format=f"gif -index {i}")
            except tk.TclError:
                break
            self.frames.append(frame)
            i += 1

    def start(self, idx: int):
        """Begin cycling, replacing image at text index `idx`."""
        if not self.frames:
            return
        self._idx = idx
        self._frame_i = 0
        self._tick()

    def _tick(self):
        if self._stopped or not self.frames:
            return
        try:
            self.text.image_configure(self._idx, image=self.frames[self._frame_i])
        except tk.TclError:
            self._stopped = True
            return
        self._frame_i = (self._frame_i + 1) % len(self.frames)
        # Roughly 10 fps; many GIFs were authored for ~100ms/frame.
        self.text.after(100, self._tick)

    def stop(self):
        self._stopped = True


# ─────────────────────────────────────────────────────────────────────────────
#  Chat Window (per buddy)
# ─────────────────────────────────────────────────────────────────────────────
class ChatWindow(tk.Toplevel):
    def __init__(self, parent: "BuddyList", my_name: str, buddy: str,
                 send_text_cb, send_media_cb, sfx: SoundFX):
        super().__init__(parent)
        self.my_name = my_name
        self.buddy = buddy
        self.send_text_cb = send_text_cb
        self.send_media_cb = send_media_cb
        self.sfx = sfx

        # Tk doesn't hold strong refs to PhotoImages embedded in widgets;
        # if these lists go out of scope the images vanish from the chat log.
        self._image_refs: list[tk.PhotoImage] = []
        self._gif_anims: list[GifAnim] = []

        self.title(f"✦ IM with {buddy} ✦")
        self.configure(bg=DEEP_NAVY)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self.update_idletasks()
        w, h = 540, 480
        x = (self.winfo_screenwidth() - w) // 2 + 60
        y = (self.winfo_screenheight() - h) // 2 + 40
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.lift()

    def _build(self):
        bar = tk.Frame(self, bg=DEEP_PURPLE, height=30,
                       highlightbackground=NEON_PINK, highlightthickness=1)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text=f"  ▷ Chatting with  {self.buddy}  ◁",
                 font=FONT_HEADER, fg=NEON_YELLOW,
                 bg=DEEP_PURPLE).pack(side="left", fill="y")
        tk.Label(bar, text="🌭  ", font=FONT_EMOJI,
                 fg=NEON_PINK, bg=DEEP_PURPLE).pack(side="right")

        log_frame = tk.Frame(self, bg=DEEP_NAVY,
                             highlightbackground=NEON_PURPLE,
                             highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.log = scrolledtext.ScrolledText(
            log_frame, font=FONT_CHAT, bg=CHAT_BG, fg=TEXT_FG,
            relief="flat", state="disabled", wrap="word", cursor="arrow",
            insertbackground=NEON_PINK, padx=8, pady=8,
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("self_name", foreground=SELF_MSG,
                               font=(FONT_CHAT[0], FONT_CHAT[1], "bold"))
        self.log.tag_configure("self_msg", foreground=SELF_MSG)
        self.log.tag_configure("other_name", foreground=OTHER_MSG,
                               font=(FONT_CHAT[0], FONT_CHAT[1], "bold"))
        self.log.tag_configure("other_msg", foreground=TEXT_FG)
        self.log.tag_configure("system", foreground=SYSTEM_MSG, font=FONT_SYSTEM)
        self.log.tag_configure("ts", foreground=DIM_TEXT, font=FONT_MONO_SM)

        input_frame = tk.Frame(self, bg=DEEP_NAVY)
        input_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.input_var = tk.StringVar()
        entry = tk.Entry(
            input_frame, textvariable=self.input_var, font=FONT_BODY,
            bg=PANEL_BG, fg=TEXT_FG, insertbackground=NEON_PINK,
            relief="flat", bd=0,
            highlightbackground=NEON_PURPLE,
            highlightcolor=NEON_PINK, highlightthickness=1,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=4)
        entry.bind("<Return>", lambda _e: self._send_text())
        entry.focus_set()

        neon_button(input_frame, "😀", self._open_emoji).pack(side="left", padx=2)
        neon_button(input_frame, "🖼", self._send_image_dialog).pack(side="left", padx=2)
        neon_button(input_frame, "▶ SEND", self._send_text,
                    primary=True).pack(side="left", padx=2)

    # ── send paths ───────────────────────────────────────────────────────────
    def _send_text(self):
        msg = self.input_var.get().strip()
        if not msg:
            return
        self.input_var.set("")
        self.send_text_cb(self.buddy, msg)
        self.append_text(self.my_name, msg, is_self=True)
        self.sfx.play("msg_send")

    def _open_emoji(self):
        EmojiPicker(self, on_pick=lambda ch: self.input_var.set(self.input_var.get() + ch))

    def _send_image_dialog(self):
        path = filedialog.askopenfilename(
            parent=self, title="Pick an image / GIF",
            filetypes=[("Images", "*.png *.gif *.pgm *.ppm"),
                       ("PNG", "*.png"), ("GIF", "*.gif"), ("All", "*.*")],
        )
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_MEDIA_EXTS:
            messagebox.showwarning(
                "LOL", "Tkinter only supports PNG and GIF inline.\n"
                       "Convert your file first.", parent=self)
            self.sfx.play("error")
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as exc:
            messagebox.showerror("LOL", f"Could not read file:\n{exc}", parent=self)
            self.sfx.play("error")
            return
        if len(raw) > MAX_MEDIA_BYTES:
            messagebox.showwarning(
                "LOL", f"File too big ({len(raw)//1024} KB).\n"
                       f"Max is {MAX_MEDIA_BYTES//1024} KB.", parent=self)
            self.sfx.play("error")
            return
        kind = "gif" if ext == ".gif" else "image"
        b64 = base64.b64encode(raw).decode("ascii")
        filename = os.path.basename(path)
        self.send_media_cb(self.buddy, kind, filename, b64)
        self._render_media(self.my_name, kind, filename, raw, is_self=True)
        self.sfx.play("msg_send")

    # ── render helpers ───────────────────────────────────────────────────────
    def _stamp(self) -> str:
        return time.strftime("[%H:%M] ")

    def append_text(self, sender: str, msg: str, is_self: bool = False):
        self.log.configure(state="normal")
        self.log.insert("end", self._stamp(), "ts")
        self.log.insert("end", f"{sender}: ",
                        "self_name" if is_self else "other_name")
        self.log.insert("end", msg + "\n",
                        "self_msg" if is_self else "other_msg")
        self.log.see("end")
        self.log.configure(state="disabled")

    def append_system(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", f"  ✦ {msg} ✦\n", "system")
        self.log.see("end")
        self.log.configure(state="disabled")

    def append_media(self, sender: str, kind: str, filename: str, b64: str):
        try:
            raw = base64.b64decode(b64.encode("ascii"))
        except Exception:
            self.append_system(f"{sender} sent a corrupt {kind}.")
            return
        self._render_media(sender, kind, filename, raw, is_self=False)

    def _render_media(self, sender: str, kind: str, filename: str,
                      raw: bytes, is_self: bool):
        self.log.configure(state="normal")
        self.log.insert("end", self._stamp(), "ts")
        self.log.insert("end", f"{sender} ",
                        "self_name" if is_self else "other_name")
        self.log.insert("end", f"sent a {kind}: {filename}\n",
                        "self_msg" if is_self else "other_msg")

        # PhotoImage(data=…) handles base64 PNGs fine, but the `gif -index N`
        # frame trick only accepts a file path — so we round-trip via a
        # short-lived temp file even for static images, for consistency.
        tmp = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".gif" if kind == "gif" else ".png",
            prefix="lol-media-",
        )
        tmp.write(raw)
        tmp.close()

        try:
            img = tk.PhotoImage(file=tmp.name)
        except tk.TclError as exc:
            self.append_system(f"Could not display image: {exc}")
            self.log.configure(state="disabled")
            return

        self._image_refs.append(img)
        self.log.image_create("end", image=img)
        idx = self.log.index("end-1c")  # location of the image we just inserted
        self.log.insert("end", "\n")

        if kind == "gif":
            anim = GifAnim(self.log, tmp.name)
            if len(anim.frames) > 1:
                self._gif_anims.append(anim)
                anim.start(idx)

        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self):
        for a in self._gif_anims:
            a.stop()
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Buddy List (main window)
# ─────────────────────────────────────────────────────────────────────────────
class BuddyList(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LOL Messenger")
        self.configure(bg=DEEP_NAVY)
        self.resizable(False, True)

        self.my_name: str = ""
        self.line_sock: LineSocket | None = None
        self.rec_thread: threading.Thread | None = None
        self.running = False

        self.sfx = SoundFX()

        # buddy name -> ChatWindow
        self.chat_windows: dict[str, ChatWindow] = {}
        self.system_win: ChatWindow | None = None

        self._build_menu()
        self._build()
        self.update_idletasks()
        w, h = 260, 520
        x = (self.winfo_screenwidth() - w) // 2 - 240
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.after(100, self._show_login)

    # ── Menu ──────────────────────────────────────────────────────────────────
    def _build_menu(self):
        menu = tk.Menu(self, bg=DEEP_PURPLE, fg=NEON_CYAN,
                       activebackground=BTN_ACTIVE,
                       activeforeground=NEON_PINK, tearoff=0)

        file_m = tk.Menu(menu, tearoff=0, bg=DEEP_PURPLE, fg=NEON_CYAN,
                         activebackground=BTN_ACTIVE,
                         activeforeground=NEON_PINK)
        file_m.add_command(label="Refresh buddy list", command=self._request_list)
        file_m.add_separator()
        file_m.add_command(label="Sign Off", command=self._sign_off)
        file_m.add_command(label="Quit", command=self._on_quit)
        menu.add_cascade(label="File", menu=file_m)

        acct_m = tk.Menu(menu, tearoff=0, bg=DEEP_PURPLE, fg=NEON_CYAN,
                         activebackground=BTN_ACTIVE,
                         activeforeground=NEON_PINK)
        acct_m.add_command(label="Create new account…",
                           command=self._create_account_inline)
        acct_m.add_command(label="Switch account",
                           command=self._switch_account)
        menu.add_cascade(label="Account", menu=acct_m)

        chat_m = tk.Menu(menu, tearoff=0, bg=DEEP_PURPLE, fg=NEON_CYAN,
                         activebackground=BTN_ACTIVE,
                         activeforeground=NEON_PINK)
        chat_m.add_command(label="New IM…", command=self._open_im_prompt)
        chat_m.add_command(label="Send image / GIF…",
                           command=self._send_media_prompt)
        menu.add_cascade(label="Chat", menu=chat_m)

        opts_m = tk.Menu(menu, tearoff=0, bg=DEEP_PURPLE, fg=NEON_CYAN,
                         activebackground=BTN_ACTIVE,
                         activeforeground=NEON_PINK)
        opts_m.add_command(label="Toggle sound", command=self._toggle_sound)
        menu.add_cascade(label="Options", menu=opts_m)

        help_m = tk.Menu(menu, tearoff=0, bg=DEEP_PURPLE, fg=NEON_CYAN,
                         activebackground=BTN_ACTIVE,
                         activeforeground=NEON_PINK)
        help_m.add_command(label="About", command=self._show_about)
        menu.add_cascade(label="Help", menu=help_m)

        self.config(menu=menu)

    def _show_about(self):
        messagebox.showinfo(
            "About LOL Messenger",
            "LOL Messenger — Lots Of Love\n"
            "Retro-vibe TCP chat with dachshunds, sound FX,\n"
            "and image/GIF sharing.\n\n"
            "🐕 🌭 ✨ 📼 💾 🌈",
            parent=self,
        )

    def _toggle_sound(self):
        on = self.sfx.toggle()
        self._set_status("🔊 Sound ON" if on else "🔇 Sound OFF")

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        header = tk.Frame(self, bg=DEEP_NAVY, height=84,
                          highlightbackground=NEON_PINK, highlightthickness=1)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="LOL", font=("Courier New", 28, "bold"),
                 fg=NEON_PINK, bg=DEEP_NAVY).pack(side="left", padx=10)
        tk.Label(header, text="Lots Of Love\nMessenger",
                 font=("Courier New", 9, "bold"),
                 fg=NEON_CYAN, bg=DEEP_NAVY,
                 justify="left").pack(side="left")
        tk.Label(header, text="🌭", font=("Courier New", 28),
                 fg=NEON_YELLOW, bg=DEEP_NAVY).pack(side="right", padx=8)

        self.name_bar = tk.Frame(self, bg=DEEP_PURPLE, height=24)
        self.name_bar.pack(fill="x")
        self.name_bar.pack_propagate(False)
        self.screen_name_lbl = tk.Label(
            self.name_bar, text="✦ Not Signed In ✦",
            font=FONT_HEADER, fg=NEON_YELLOW, bg=DEEP_PURPLE,
        )
        self.screen_name_lbl.pack(side="left", padx=8)

        bl_header = tk.Frame(self, bg=PANEL_BG, height=22)
        bl_header.pack(fill="x")
        bl_header.pack_propagate(False)
        tk.Label(bl_header, text="▶ ONLINE BUDDIES",
                 font=FONT_HEADER, fg=NEON_PINK, bg=PANEL_BG).pack(side="left", padx=6)
        self.buddy_count_lbl = tk.Label(bl_header, text="(0)",
                                        font=FONT_MONO_SM, fg=NEON_CYAN,
                                        bg=PANEL_BG)
        self.buddy_count_lbl.pack(side="right", padx=6)

        list_frame = tk.Frame(self, bg=DEEP_NAVY,
                              highlightbackground=NEON_PURPLE,
                              highlightthickness=1)
        list_frame.pack(fill="both", expand=True, padx=6, pady=4)

        scrollbar = tk.Scrollbar(list_frame, bg=DEEP_PURPLE,
                                 troughcolor=PANEL_BG)
        scrollbar.pack(side="right", fill="y")

        self.buddy_listbox = tk.Listbox(
            list_frame, font=FONT_BUDDY,
            bg=CHAT_BG, fg=TEXT_FG,
            selectbackground=NEON_PINK, selectforeground=DEEP_NAVY,
            activestyle="none", relief="flat",
            yscrollcommand=scrollbar.set, height=14, bd=0,
            highlightthickness=0,
        )
        self.buddy_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.buddy_listbox.yview)
        self.buddy_listbox.bind("<Double-Button-1>", self._on_buddy_double_click)

        self.status_var = tk.StringVar(value="✦ Welcome to LOL ✦")
        status_bar = tk.Label(
            self, textvariable=self.status_var,
            font=FONT_MONO_SM, fg=NEON_CYAN, bg=DEEP_PURPLE,
            relief="flat", anchor="w", padx=6, pady=2,
        )
        status_bar.pack(fill="x", side="bottom")

        btn_row = tk.Frame(self, bg=DEEP_NAVY)
        btn_row.pack(fill="x", padx=4, pady=4, side="bottom")

        neon_button(btn_row, "IM", self._open_im_prompt,
                    primary=True).pack(side="left", padx=2, expand=True, fill="x")
        neon_button(btn_row, "🖼", self._send_media_prompt
                    ).pack(side="left", padx=2, expand=True, fill="x")
        neon_button(btn_row, "List", self._request_list
                    ).pack(side="left", padx=2, expand=True, fill="x")
        neon_button(btn_row, "Bye", self._sign_off
                    ).pack(side="left", padx=2, expand=True, fill="x")

    # ── Login / register flow ─────────────────────────────────────────────────
    def _show_login(self):
        dlg = LoginDialog(self)
        self.wait_window(dlg)
        if dlg.result is None:
            self.destroy()
            return
        action, username, password, host, port = dlg.result
        if action == "register":
            self._register_then_login(host, port, username, password)
        else:
            self._connect(host, port, username, password)

    def _open_socket(self, host: str, port: int) -> LineSocket | None:
        self._set_status(f"Connecting to {host}:{port}…")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(8)
            sock.connect((host, port))
            sock.settimeout(None)
        except OSError as exc:
            messagebox.showerror("LOL", f"Could not connect:\n{exc}")
            self.sfx.play("error")
            return None

        ls = LineSocket(sock)
        ls.send_line("HELLO")
        resp = ls.read_line(timeout=8)
        if resp != "HELLO":
            messagebox.showerror("LOL", "Server did not respond correctly.")
            ls.close()
            self.sfx.play("error")
            return None
        return ls

    def _register_then_login(self, host: str, port: int,
                             username: str, password: str):
        ls = self._open_socket(host, port)
        if not ls:
            self.after(100, self._show_login)
            return
        ls.send_line(f"REGISTER:{username}:{password}")
        resp = ls.read_line(timeout=8) or ""
        ls.close()
        if resp == "REGYES":
            self.sfx.play("signin")
            messagebox.showinfo("LOL", f"Account '{username}' created!\n"
                                       f"Signing you in…", parent=self)
            self._connect(host, port, username, password)
        else:
            reason = resp.split(":", 1)[1] if ":" in resp else "unknown error"
            self.sfx.play("error")
            messagebox.showerror("LOL", f"Could not create account:\n{reason}",
                                 parent=self)
            self.after(100, self._show_login)

    def _connect(self, host: str, port: int, username: str, password: str):
        ls = self._open_socket(host, port)
        if not ls:
            self.after(100, self._show_login)
            return

        ls.send_line(f"AUTH:{username}:{password}")
        resp = ls.read_line(timeout=8) or ""
        if not resp.startswith("AUTHYES"):
            reason = resp.split(":", 1)[1] if ":" in resp else "invalid credentials"
            messagebox.showerror("LOL", f"Sign-in failed:\n{reason}")
            ls.close()
            self.sfx.play("error")
            self.after(100, self._show_login)
            return

        self.line_sock = ls
        self.my_name = username
        self.running = True

        self.screen_name_lbl.config(text=f"  ✦ {username} ✦")
        self._set_status(f"Signed in as {username}")
        self.sfx.play("signin")
        self._add_buddy(username, is_self=True)

        self.rec_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.rec_thread.start()
        self._request_list()

    def _create_account_inline(self):
        # Re-use the LoginDialog since it already has username/password fields.
        if self.running:
            messagebox.showinfo(
                "LOL", "You're already signed in.\n"
                       "Sign off first to create a new account.",
                parent=self,
            )
            return
        self._show_login()

    def _switch_account(self):
        if self.running:
            self._do_sign_off()
        else:
            self._show_login()

    # ── Networking ────────────────────────────────────────────────────────────
    def _recv_loop(self):
        # Runs on a background thread; every UI mutation must be marshalled
        # back to the Tk thread via `after(0, …)` to stay thread-safe.
        while self.running:
            line = self.line_sock.read_line() if self.line_sock else None
            if line is None:
                break
            if line:
                self.after(0, self._handle_server_msg, line)
        self.after(0, self._on_disconnected)

    def _handle_server_msg(self, msg: str):
        if msg.startswith("SIGNIN:"):
            user = msg.split(":", 1)[1]
            self._add_buddy(user)
            self._set_status(f"{user} has signed on!")
            self._system_notice(f"{user} has signed on!")
            if user != self.my_name:
                self.sfx.play("signin")

        elif msg.startswith("SIGNOFF:"):
            user = msg.split(":", 1)[1]
            self._remove_buddy(user)
            self._set_status(f"{user} has signed off.")
            self._system_notice(f"{user} has signed off.")
            self.sfx.play("signoff")
            if user in self.chat_windows and self.chat_windows[user].winfo_exists():
                self.chat_windows[user].append_system(f"{user} has signed off.")

        elif msg.startswith("FROM:"):
            _, sender, text = msg.split(":", 2)
            win = self._get_or_open_chat(sender)
            win.append_text(sender, text, is_self=False)
            win.lift()
            self._set_status(f"New message from {sender}")
            self.sfx.play("msg_in")

        elif msg.startswith("FROMMEDIA:"):
            parts = msg.split(":", 4)
            if len(parts) != 5:
                return
            _, sender, kind, filename, b64 = parts
            win = self._get_or_open_chat(sender)
            win.append_media(sender, kind, filename, b64)
            win.lift()
            self._set_status(f"{sender} sent a {kind}!")
            self.sfx.play("media_in")

        elif msg.startswith("SYSMSG:"):
            notice = msg.split(":", 1)[1]
            self._system_notice(notice)
            self.sfx.play("error")

        else:
            users = [u.strip() for u in msg.split(",") if u.strip()]
            if users:
                self._sync_buddy_list(users)

    def _send_text(self, recipient: str, msg: str):
        if self.line_sock:
            try:
                self.line_sock.send_line(f"TO:{recipient}:{msg}")
            except OSError:
                pass

    def _send_media(self, recipient: str, kind: str, filename: str, b64: str):
        if self.line_sock:
            try:
                self.line_sock.send_line(
                    f"TOMEDIA:{recipient}:{kind}:{filename}:{b64}")
            except OSError:
                pass

    def _request_list(self):
        if self.line_sock:
            try:
                self.line_sock.send_line("LIST")
            except OSError:
                pass

    # ── Buddy list helpers ────────────────────────────────────────────────────
    def _add_buddy(self, username: str, is_self: bool = False):
        items = list(self.buddy_listbox.get(0, "end"))
        if any(f" {username}" in item for item in items):
            return
        label = f"● {username}" + ("  (you)" if is_self else "")
        self.buddy_listbox.insert("end", label)
        self._update_count()

    def _remove_buddy(self, username: str):
        items = list(self.buddy_listbox.get(0, "end"))
        for i, item in enumerate(items):
            if f"● {username}" in item:
                self.buddy_listbox.delete(i)
                break
        self._update_count()

    def _sync_buddy_list(self, users: list[str]):
        self.buddy_listbox.delete(0, "end")
        for u in users:
            label = f"● {u}" + ("  (you)" if u == self.my_name else "")
            self.buddy_listbox.insert("end", label)
        self._update_count()

    def _update_count(self):
        n = self.buddy_listbox.size()
        self.buddy_count_lbl.config(text=f"({n})")

    # ── Chat window helpers ───────────────────────────────────────────────────
    def _get_or_open_chat(self, buddy: str) -> ChatWindow:
        if (buddy not in self.chat_windows
                or not self.chat_windows[buddy].winfo_exists()):
            win = ChatWindow(self, self.my_name, buddy,
                             self._send_text, self._send_media, self.sfx)
            self.chat_windows[buddy] = win
        return self.chat_windows[buddy]

    def _system_notice(self, msg: str):
        if self.system_win is None or not self.system_win.winfo_exists():
            self.system_win = ChatWindow(
                self, "LOL", "★ System Notices ★",
                lambda *_: None, lambda *_: None, self.sfx,
            )
            self.system_win.title("LOL System Notices")
        self.system_win.append_system(msg)

    # ── Button handlers ───────────────────────────────────────────────────────
    def _on_buddy_double_click(self, _event):
        sel = self.buddy_listbox.curselection()
        if not sel:
            return
        item = self.buddy_listbox.get(sel[0])
        buddy = item.replace("●", "").replace("(you)", "").strip()
        if buddy == self.my_name:
            return
        win = self._get_or_open_chat(buddy)
        win.lift()

    def _open_im_prompt(self):
        buddy = simpledialog.askstring("Send IM", "Enter Screen Name:",
                                       parent=self)
        if buddy:
            buddy = buddy.strip()
            if not buddy:
                return
            win = self._get_or_open_chat(buddy)
            win.lift()

    def _send_media_prompt(self):
        if not self.running:
            messagebox.showinfo("LOL", "Sign in first.", parent=self)
            return
        buddy = simpledialog.askstring("Send Media",
                                       "Send an image / GIF to which buddy?",
                                       parent=self)
        if not buddy:
            return
        buddy = buddy.strip()
        if not buddy:
            return
        win = self._get_or_open_chat(buddy)
        win.lift()
        win._send_image_dialog()

    def _sign_off(self):
        if not self.running:
            return
        if messagebox.askyesno("LOL", "Are you sure you want to sign off?"):
            self._do_sign_off()

    def _do_sign_off(self):
        self.running = False
        if self.line_sock:
            try:
                self.line_sock.send_line("BYE")
            except OSError:
                pass
            self.line_sock.close()
            self.line_sock = None
        self.screen_name_lbl.config(text="✦ Not Signed In ✦")
        self.buddy_listbox.delete(0, "end")
        self._update_count()
        self._set_status("Signed off. Bye! 🌭")
        self.sfx.play("signoff")
        self.after(1500, self._show_login)

    def _on_disconnected(self):
        if not self.running:
            return
        self.running = False
        messagebox.showwarning("LOL", "You have been disconnected.")
        self._set_status("Disconnected.")
        self.sfx.play("error")
        self.after(100, self._show_login)

    def _on_quit(self):
        if self.running:
            self._do_sign_off()
            self.after(400, self.destroy)
        else:
            self.destroy()

    def _set_status(self, msg: str):
        self.status_var.set(msg)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    app = BuddyList()
    app.mainloop()


if __name__ == "__main__":
    main()

