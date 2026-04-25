"""
AOL Retro Chatroom - GUI Client
Tkinter-based client with authentic 90s AOL Instant Messenger aesthetic.
"""
from socket import *
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, font as tkfont

# ── Server config ────────────────────────────────────────────────────────────
SERVER_HOST = "localhost"
SERVER_PORT = 12000
BUFFER = 4096

# ── AOL Color Palette ────────────────────────────────────────────────────────
AOL_BG        = "#C0C0C0"   # classic Windows 95 grey
AOL_DARK      = "#000080"   # deep navy (title bars)
AOL_ACCENT    = "#008080"   # teal (AOL buddy list header)
AOL_YELLOW    = "#FFFF00"   # AOL warning yellow
AOL_WHITE     = "#FFFFFF"
AOL_CHAT_BG   = "#FFFAF0"   # warm off-white chat area
AOL_MSG_SELF  = "#000080"   # navy for own messages
AOL_MSG_OTHER = "#8B0000"   # dark-red for incoming messages
AOL_SYSTEM    = "#006400"   # green for system notices
AOL_BORDER    = "#808080"
AOL_BTN_BG    = "#D4D0C8"
AOL_BTN_ACTIVE= "#ECE9D8"

# ── AOL Fonts ────────────────────────────────────────────────────────────────
FONT_TITLE  = ("Arial", 12, "bold")
FONT_BODY   = ("Times New Roman", 11)
FONT_CHAT   = ("Comic Sans MS", 10)   # Peak 90s
FONT_SYSTEM = ("Courier New", 9)
FONT_BUDDY  = ("Arial", 10)
FONT_HEADER = ("Arial", 9, "bold")

# ── ASCII art banner ─────────────────────────────────────────────────────────
AOL_BANNER = (
    "   ___   ___  _       \n"
    "  / _ | / _ \\| |      \n"
    " / __ |/ /_\\ \\ |      \n"
    "/_/ |_/\\____/_/  v2.0 \n"
    "  Instant Messenger   \n"
)


# ─────────────────────────────────────────────────────────────────────────────
#  Login Dialog
# ─────────────────────────────────────────────────────────────────────────────
class LoginDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk):
        super().__init__(parent)
        self.result: tuple[str, str] | None = None

        self.title("AOL Instant Messenger - Sign In")
        self.resizable(False, False)
        self.configure(bg=AOL_BG)
        self.grab_set()

        self._build()
        self.update_idletasks()
        # Center on screen
        w, h = 360, 440
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # ── Top banner ──
        banner_frame = tk.Frame(self, bg=AOL_DARK, height=90)
        banner_frame.pack(fill="x")
        banner_frame.pack_propagate(False)

        tk.Label(
            banner_frame,
            text="AOL",
            font=("Arial", 36, "bold"),
            fg=AOL_YELLOW,
            bg=AOL_DARK,
        ).pack(side="left", padx=16)

        tk.Label(
            banner_frame,
            text="Instant\nMessenger",
            font=("Arial", 14, "bold"),
            fg=AOL_WHITE,
            bg=AOL_DARK,
            justify="left",
        ).pack(side="left", pady=8)

        # Running man unicode substitute
        tk.Label(
            banner_frame,
            text="♟",
            font=("Arial", 42),
            fg=AOL_YELLOW,
            bg=AOL_DARK,
        ).pack(side="right", padx=16)

        # ── Tagline ──
        tk.Label(
            self,
            text='"You\'ve Got Mail!"',
            font=("Comic Sans MS", 10, "italic"),
            fg=AOL_DARK,
            bg=AOL_BG,
        ).pack(pady=(8, 2))

        # ── Form ──
        form = tk.Frame(self, bg=AOL_BG, padx=24)
        form.pack(fill="x", pady=8)

        tk.Label(form, text="Screen Name:", font=FONT_HEADER, bg=AOL_BG, anchor="w").grid(
            row=0, column=0, sticky="w", pady=4
        )
        self.username_var = tk.StringVar()
        uentry = tk.Entry(form, textvariable=self.username_var, font=FONT_BODY, width=22,
                          relief="sunken", bd=2)
        uentry.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        uentry.focus_set()

        tk.Label(form, text="Password:", font=FONT_HEADER, bg=AOL_BG, anchor="w").grid(
            row=2, column=0, sticky="w", pady=4
        )
        self.password_var = tk.StringVar()
        tk.Entry(form, textvariable=self.password_var, font=FONT_BODY, width=22,
                 show="*", relief="sunken", bd=2).grid(row=3, column=0, sticky="ew", pady=(0, 8))

        form.columnconfigure(0, weight=1)

        # Host row
        host_frame = tk.Frame(self, bg=AOL_BG, padx=24)
        host_frame.pack(fill="x")
        tk.Label(host_frame, text="Host:", font=FONT_HEADER, bg=AOL_BG).pack(side="left")
        self.host_var = tk.StringVar(value=SERVER_HOST)
        tk.Entry(host_frame, textvariable=self.host_var, font=FONT_SYSTEM, width=16,
                 relief="sunken", bd=2).pack(side="left", padx=4)
        tk.Label(host_frame, text="Port:", font=FONT_HEADER, bg=AOL_BG).pack(side="left")
        self.port_var = tk.StringVar(value=str(SERVER_PORT))
        tk.Entry(host_frame, textvariable=self.port_var, font=FONT_SYSTEM, width=6,
                 relief="sunken", bd=2).pack(side="left", padx=4)

        # ── Buttons ──
        btn_frame = tk.Frame(self, bg=AOL_BG)
        btn_frame.pack(pady=16)

        sign_in_btn = tk.Button(
            btn_frame, text="Sign In", font=FONT_TITLE,
            bg=AOL_DARK, fg=AOL_WHITE, activebackground="#0000AA", activeforeground=AOL_WHITE,
            relief="raised", bd=3, padx=20, pady=6,
            command=self._on_sign_in,
        )
        sign_in_btn.pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="Cancel", font=FONT_HEADER,
            bg=AOL_BTN_BG, fg="black", relief="raised", bd=2, padx=12, pady=6,
            command=self.destroy,
        ).pack(side="left", padx=8)

        self.bind("<Return>", lambda _e: self._on_sign_in())

        # ── Footer ──
        tk.Label(
            self,
            text="© 1998 America Online, Inc.  (fan tribute)",
            font=("Arial", 7),
            fg="#555555",
            bg=AOL_BG,
        ).pack(side="bottom", pady=4)

    def _on_sign_in(self):
        u = self.username_var.get().strip()
        p = self.password_var.get().strip()
        if not u or not p:
            messagebox.showwarning("AOL", "Please enter Screen Name and Password.", parent=self)
            return
        self.result = (u, p, self.host_var.get().strip(), int(self.port_var.get().strip()))
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Chat Window (opened per conversation)
# ─────────────────────────────────────────────────────────────────────────────
class ChatWindow(tk.Toplevel):
    def __init__(self, parent: "BuddyList", my_name: str, buddy: str, send_cb):
        super().__init__(parent)
        self.my_name = my_name
        self.buddy = buddy
        self.send_cb = send_cb

        self.title(f"IM with {buddy}")
        self.configure(bg=AOL_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self.update_idletasks()
        w, h = 480, 420
        x = (self.winfo_screenwidth() - w) // 2 + 60
        y = (self.winfo_screenheight() - h) // 2 + 40
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.lift()

    def _build(self):
        # Title bar replica
        title_bar = tk.Frame(self, bg=AOL_DARK, height=28)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        tk.Label(
            title_bar,
            text=f"  Instant Message — {self.buddy}",
            font=FONT_HEADER,
            fg=AOL_WHITE,
            bg=AOL_DARK,
            anchor="w",
        ).pack(side="left", fill="y")

        # Chat log
        log_frame = tk.Frame(self, bg=AOL_BG, bd=2, relief="sunken")
        log_frame.pack(fill="both", expand=True, padx=6, pady=4)

        self.log = scrolledtext.ScrolledText(
            log_frame,
            font=FONT_CHAT,
            bg=AOL_CHAT_BG,
            fg="black",
            relief="flat",
            state="disabled",
            wrap="word",
            cursor="arrow",
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_configure("self_name",  foreground=AOL_MSG_SELF,  font=(FONT_CHAT[0], FONT_CHAT[1], "bold"))
        self.log.tag_configure("self_msg",   foreground=AOL_MSG_SELF)
        self.log.tag_configure("other_name", foreground=AOL_MSG_OTHER, font=(FONT_CHAT[0], FONT_CHAT[1], "bold"))
        self.log.tag_configure("other_msg",  foreground=AOL_MSG_OTHER)
        self.log.tag_configure("system",     foreground=AOL_SYSTEM,    font=FONT_SYSTEM)

        # Input area
        input_frame = tk.Frame(self, bg=AOL_BG)
        input_frame.pack(fill="x", padx=6, pady=(0, 6))

        self.input_var = tk.StringVar()
        entry = tk.Entry(
            input_frame,
            textvariable=self.input_var,
            font=FONT_BODY,
            relief="sunken",
            bd=2,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        entry.bind("<Return>", lambda _e: self._send())
        entry.focus_set()

        tk.Button(
            input_frame,
            text="Send",
            font=FONT_HEADER,
            bg=AOL_DARK,
            fg=AOL_WHITE,
            activebackground="#0000AA",
            relief="raised",
            bd=2,
            padx=10,
            command=self._send,
        ).pack(side="right")

    def _send(self):
        msg = self.input_var.get().strip()
        if not msg:
            return
        self.input_var.set("")
        self.send_cb(self.buddy, msg)
        self.append_message(self.my_name, msg, is_self=True)

    def append_message(self, sender: str, msg: str, is_self: bool = False):
        self.log.configure(state="normal")
        name_tag = "self_name" if is_self else "other_name"
        msg_tag  = "self_msg"  if is_self else "other_msg"
        self.log.insert("end", f"{sender}: ", name_tag)
        self.log.insert("end", msg + "\n", msg_tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def append_system(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", f"*** {msg} ***\n", "system")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _on_close(self):
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
#  Buddy List (main window)
# ─────────────────────────────────────────────────────────────────────────────
class BuddyList(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AOL Instant Messenger")
        self.configure(bg=AOL_BG)
        self.resizable(False, True)

        self.my_name: str = ""
        self.client_socket: socket | None = None
        self.rec_thread: threading.Thread | None = None
        self.running = False

        # buddy name -> ChatWindow
        self.chat_windows: dict[str, ChatWindow] = {}
        # system chat log window
        self.system_win: ChatWindow | None = None

        self._build()
        self.update_idletasks()
        w, h = 220, 480
        x = (self.winfo_screenwidth() - w) // 2 - 200
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_quit)
        self.after(100, self._show_login)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        # ── Top gradient-like header ──
        header = tk.Frame(self, bg=AOL_DARK, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text="AOL", font=("Arial", 28, "bold"),
                 fg=AOL_YELLOW, bg=AOL_DARK).pack(side="left", padx=8)
        tk.Label(header, text="Instant\nMessenger", font=("Arial", 10, "bold"),
                 fg=AOL_WHITE, bg=AOL_DARK, justify="left").pack(side="left")
        tk.Label(header, text="♟", font=("Arial", 30), fg=AOL_YELLOW,
                 bg=AOL_DARK).pack(side="right", padx=8)

        # ── Screen name bar ──
        self.name_bar = tk.Frame(self, bg=AOL_ACCENT, height=22)
        self.name_bar.pack(fill="x")
        self.name_bar.pack_propagate(False)
        self.screen_name_lbl = tk.Label(
            self.name_bar, text="Not Signed In",
            font=FONT_HEADER, fg=AOL_WHITE, bg=AOL_ACCENT
        )
        self.screen_name_lbl.pack(side="left", padx=6)

        # ── Buddy list section ──
        bl_header = tk.Frame(self, bg="#003366", height=20)
        bl_header.pack(fill="x")
        bl_header.pack_propagate(False)
        tk.Label(bl_header, text="Buddies", font=FONT_HEADER,
                 fg=AOL_YELLOW, bg="#003366").pack(side="left", padx=6)
        self.buddy_count_lbl = tk.Label(bl_header, text="(0/0)",
                 font=("Arial", 8), fg=AOL_WHITE, bg="#003366")
        self.buddy_count_lbl.pack(side="right", padx=4)

        # Listbox
        list_frame = tk.Frame(self, bg=AOL_BG, bd=2, relief="sunken")
        list_frame.pack(fill="both", expand=True, padx=4, pady=2)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.buddy_listbox = tk.Listbox(
            list_frame,
            font=FONT_BUDDY,
            bg=AOL_WHITE,
            fg="black",
            selectbackground=AOL_DARK,
            selectforeground=AOL_WHITE,
            activestyle="none",
            relief="flat",
            yscrollcommand=scrollbar.set,
            height=14,
        )
        self.buddy_listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.buddy_listbox.yview)
        self.buddy_listbox.bind("<Double-Button-1>", self._on_buddy_double_click)

        # ── Status ticker ──
        self.status_var = tk.StringVar(value="Welcome to AOL!")
        status_bar = tk.Label(
            self, textvariable=self.status_var,
            font=("Arial", 8), fg="#333333",
            bg="#E8E8E8", relief="sunken", anchor="w", padx=4
        )
        status_bar.pack(fill="x", side="bottom")

        # ── Button row ──
        btn_row = tk.Frame(self, bg=AOL_BG)
        btn_row.pack(fill="x", padx=4, pady=4, side="bottom")

        tk.Button(btn_row, text="IM", font=FONT_HEADER,
                  bg=AOL_DARK, fg=AOL_WHITE, relief="raised", bd=2,
                  command=self._open_im_prompt).pack(side="left", padx=2, expand=True, fill="x")

        tk.Button(btn_row, text="List", font=FONT_HEADER,
                  bg=AOL_BTN_BG, fg="black", relief="raised", bd=2,
                  command=self._request_list).pack(side="left", padx=2, expand=True, fill="x")

        tk.Button(btn_row, text="Sign Off", font=FONT_HEADER,
                  bg="#8B0000", fg=AOL_WHITE, relief="raised", bd=2,
                  command=self._sign_off).pack(side="left", padx=2, expand=True, fill="x")

    # ── Login flow ────────────────────────────────────────────────────────────
    def _show_login(self):
        dlg = LoginDialog(self)
        self.wait_window(dlg)
        if dlg.result is None:
            self.destroy()
            return
        username, password, host, port = dlg.result
        self._connect(host, port, username, password)

    def _connect(self, host: str, port: int, username: str, password: str):
        self._set_status("Connecting to AOL...")
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.settimeout(8)
            sock.connect((host, port))
            sock.settimeout(None)
        except OSError as exc:
            messagebox.showerror("AOL", f"Could not connect:\n{exc}")
            self.after(100, self._show_login)
            return

        # Handshake
        sock.send(b"HELLO")
        resp = sock.recv(BUFFER).decode().strip()
        if resp != "HELLO":
            messagebox.showerror("AOL", "Server did not respond correctly.")
            sock.close()
            self.after(100, self._show_login)
            return

        # Auth
        sock.send(f"AUTH:{username}:{password}".encode())
        resp = sock.recv(BUFFER).decode().strip()
        if "YES" not in resp:
            messagebox.showerror("AOL", "Invalid Screen Name or Password.")
            sock.close()
            self.after(100, self._show_login)
            return

        self.client_socket = sock
        self.my_name = username
        self.running = True

        self.screen_name_lbl.config(text=f"  {username}")
        self._set_status(f"Signed in as {username}")
        self._add_buddy(username, is_self=True)

        # Start receiver thread
        self.rec_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.rec_thread.start()

        # Ask for current online list
        self._request_list()

    # ── Networking ────────────────────────────────────────────────────────────
    def _recv_loop(self):
        buf = ""
        while self.running:
            try:
                chunk = self.client_socket.recv(BUFFER).decode()
                if not chunk:
                    break
                buf += chunk
            except OSError:
                break

            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line:
                    self.after(0, self._handle_server_msg, line)

        self.after(0, self._on_disconnected)

    def _handle_server_msg(self, msg: str):
        if msg.startswith("SIGNIN:"):
            user = msg.split(":", 1)[1]
            self._add_buddy(user)
            self._set_status(f"{user} has signed on!")
            self._system_notice(f"{user} has signed on!")

        elif msg.startswith("SIGNOFF:"):
            user = msg.split(":", 1)[1]
            self._remove_buddy(user)
            self._set_status(f"{user} has signed off.")
            self._system_notice(f"{user} has signed off.")
            if user in self.chat_windows:
                self.chat_windows[user].append_system(f"{user} has signed off.")

        elif msg.startswith("FROM:"):
            _, sender, text = msg.split(":", 2)
            win = self._get_or_open_chat(sender)
            win.append_message(sender, text, is_self=False)
            win.lift()
            self._set_status(f"New message from {sender}")

        elif msg.startswith("SYSMSG:"):
            notice = msg.split(":", 1)[1]
            self._system_notice(notice)

        else:
            # Anything that doesn't match a known prefix is a LIST response
            users = [u.strip() for u in msg.split(",") if u.strip()]
            if users:
                self._sync_buddy_list(users)

    def _send_to_server(self, recipient: str, msg: str):
        if self.client_socket:
            try:
                self.client_socket.send(f"TO:{recipient}:{msg}".encode())
            except OSError:
                pass

    def _request_list(self):
        if self.client_socket:
            try:
                self.client_socket.send(b"LIST")
            except OSError:
                pass

    # ── Buddy list helpers ────────────────────────────────────────────────────
    def _add_buddy(self, username: str, is_self: bool = False):
        items = list(self.buddy_listbox.get(0, "end"))
        if any(username in item for item in items):
            return
        label = f"● {username}" + (" (me)" if is_self else "")
        self.buddy_listbox.insert("end", label)
        self._update_count()

    def _remove_buddy(self, username: str):
        items = list(self.buddy_listbox.get(0, "end"))
        for i, item in enumerate(items):
            # Match the bare username inside the decorated label
            if f"● {username}" in item:
                self.buddy_listbox.delete(i)
                break
        self._update_count()

    def _sync_buddy_list(self, users: list[str]):
        self.buddy_listbox.delete(0, "end")
        for u in users:
            is_self = u == self.my_name
            label = f"● {u}" + (" (me)" if is_self else "")
            self.buddy_listbox.insert("end", label)
        self._update_count()

    def _update_count(self):
        n = self.buddy_listbox.size()
        self.buddy_count_lbl.config(text=f"({n}/{n})")

    # ── Chat window helpers ───────────────────────────────────────────────────
    def _get_or_open_chat(self, buddy: str) -> ChatWindow:
        if buddy not in self.chat_windows or not self.chat_windows[buddy].winfo_exists():
            win = ChatWindow(self, self.my_name, buddy, self._send_to_server)
            self.chat_windows[buddy] = win
        return self.chat_windows[buddy]

    def _system_notice(self, msg: str):
        if self.system_win is None or not self.system_win.winfo_exists():
            self.system_win = ChatWindow(self, "AOL", "System Notices", lambda *_: None)
            self.system_win.title("AOL System Notices")
        self.system_win.append_system(msg)

    # ── Button handlers ───────────────────────────────────────────────────────
    def _on_buddy_double_click(self, _event):
        sel = self.buddy_listbox.curselection()
        if not sel:
            return
        item = self.buddy_listbox.get(sel[0])
        # Strip ● and (me)
        buddy = item.replace("●", "").replace("(me)", "").strip()
        if buddy == self.my_name:
            return
        win = self._get_or_open_chat(buddy)
        win.lift()

    def _open_im_prompt(self):
        buddy = simpledialog.askstring(
            "Send IM", "Enter Screen Name:", parent=self
        )
        if buddy:
            buddy = buddy.strip()
            win = self._get_or_open_chat(buddy)
            win.lift()

    def _sign_off(self):
        if not self.running:
            return
        if messagebox.askyesno("AOL", "Are you sure you want to sign off?"):
            self._do_sign_off()

    def _do_sign_off(self):
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.send(b"BYE")
            except OSError:
                pass
            try:
                self.client_socket.close()
            except OSError:
                pass
        self.screen_name_lbl.config(text="Not Signed In")
        self.buddy_listbox.delete(0, "end")
        self._set_status("You have signed off. Goodbye!")
        self.after(1500, self._show_login)

    def _on_disconnected(self):
        if not self.running:
            return
        self.running = False
        messagebox.showwarning("AOL", "You have been disconnected from AOL.")
        self._set_status("Disconnected.")
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
#  Demo control socket (disabled unless DEMO_PORT env var is set)
#  Commands sent as lines: "SEND:buddy:message" or "RECV:sender:message"
# ─────────────────────────────────────────────────────────────────────────────
def _run_demo_server(app: "BuddyList", port: int) -> None:
    import os
    srv = socket(AF_INET, SOCK_STREAM)
    srv.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    srv.bind(("localhost", port))
    srv.listen(5)
    while True:
        conn, _ = srv.accept()
        data = conn.recv(4096).decode().strip()
        conn.close()
        for line in data.splitlines():
            if line.startswith("SEND:"):
                _, buddy, msg = line.split(":", 2)
                def do_send(b=buddy, m=msg):
                    win = app._get_or_open_chat(b)
                    win.append_message(app.my_name, m, is_self=True)
                    app._send_to_server(b, m)
                app.after(0, do_send)
            elif line.startswith("RECV:"):
                _, sender, msg = line.split(":", 2)
                def do_recv(s=sender, m=msg):
                    app._handle_server_msg(f"FROM:{s}:{m}")
                app.after(0, do_recv)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    import os
    app = BuddyList()
    demo_port = os.environ.get("DEMO_PORT")
    if demo_port:
        t = threading.Thread(target=_run_demo_server, args=(app, int(demo_port)), daemon=True)
        t.start()
    app.mainloop()


if __name__ == "__main__":
    main()
