# AOL Retro Chatroom

A retro AOL Instant Messenger-inspired TCP chatroom built in Python with a tkinter GUI.

> Originally created 2017 — updated with retro AOL GUI and modernized server (2026) by engineerNV

---

## Requirements

- Python 3.6+
- `tkinter` — ships with most Python installs
  ```bash
  # Ubuntu/Debian only
  sudo apt install python3-tk
  ```

---

## Running

```bash
# Terminal 1 — start the server
python3 chat-server.py

# Terminal 2+ — launch the GUI client
python3 chat-client-gui.py

# Optional: CLI client for quick testing
python3 chat-client.py
```

---

## Accounts

| Username | Password |
|----------|----------|
| test1    | p000     |
| test2    | p000     |
| test3    | p000     |
| engineerNV | p591   |

> To add accounts, edit the `USERS` dict at the top of `chat-server.py`.

---

## Configuration

| Setting | Location |
|---------|----------|
| Server host/port | `SERVER_HOST` / `SERVER_PORT` in `chat-server.py` |
| Client default host/port | `SERVER_HOST` / `SERVER_PORT` in `chat-client-gui.py` (also editable in the login dialog) |
| GUI theme colors & fonts | `AOL_*` constants in `chat-client-gui.py` |

---

## Protocol

All messages are newline-terminated and colon-delimited.

| Direction | Message | Meaning |
|-----------|---------|---------|
| Client → Server | `HELLO` | Initiate handshake |
| Server → Client | `HELLO` | Handshake ack |
| Client → Server | `AUTH:username:password` | Login attempt |
| Server → Client | `AUTHYES` / `AUTHNO` | Login result |
| Client → Server | `LIST` | Request online users |
| Server → Client | `user1, user2, ...` | Online users list |
| Client → Server | `TO:recipient:message` | Send private message |
| Server → Client | `FROM:sender:message` | Receive private message |
| Server → Client | `SIGNIN:username` | User came online (broadcast) |
| Server → Client | `SIGNOFF:username` | User went offline (broadcast) |
| Server → Client | `SYSMSG:text` | System notice (e.g. recipient offline) |
| Client → Server | `BYE` | Sign off |

---

## Files

| File | Description |
|------|-------------|
| `chat-server.py` | Multi-threaded TCP server with thread-safe locking and structured logging |
| `chat-client-gui.py` | Tkinter GUI client with retro AOL Instant Messenger aesthetic |
| `chat-client.py` | Original CLI client — kept for reference and testing |
| `CLAUDE.md` | Developer reference: architecture, protocol, and common tasks |
