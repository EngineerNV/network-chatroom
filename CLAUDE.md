# LOL Messenger

A retro/synthwave TCP chatroom in Python with a tkinter GUI. (Originally an
AOL-IM tribute, rebranded to "LOL — Lots Of Love" with a synthwave palette,
sound effects, dachshund emojis, image/GIF sharing, and SQLite accounts.)

## Architecture

- **chat-server.py** — Multi-threaded TCP server (`localhost:12000`). One
  thread per client. SQLite-backed accounts (`chat-data.db`) with
  PBKDF2-SHA256 password hashes. Self-service registration. Buffered
  per-client `LineReader` so large base64 media payloads (≤8 MB/line) are
  routed correctly.
- **chat-client-gui.py** — Tkinter GUI client. Two threads: one drains the
  server socket via a `LineSocket` reader, one runs the UI. Includes
  generated sound effects, dachshund + retro emoji picker, animated-GIF
  rendering in the `Text` widget, and a menu bar.
- **chat-client.py** — Original CLI client (kept for reference / testing).

## Protocol

Newline-terminated, colon-delimited UTF-8 text. Media payloads are base64
inline so the protocol stays line-based.

| Direction       | Message                                         | Meaning                          |
|-----------------|-------------------------------------------------|----------------------------------|
| Client → Server | `HELLO`                                         | Initiate handshake               |
| Server → Client | `HELLO`                                         | Handshake ack                    |
| Client → Server | `REGISTER:username:password`                    | Create new account               |
| Server → Client | `REGYES` / `REGNO:reason`                       | Registration result              |
| Client → Server | `AUTH:username:password`                        | Login attempt                    |
| Server → Client | `AUTHYES` / `AUTHNO:reason`                     | Login result (max 3 tries)       |
| Client → Server | `LIST`                                          | Request online users             |
| Server → Client | `user1, user2, ...`                             | Online users list                |
| Client → Server | `TO:recipient:message`                          | Send text DM                     |
| Server → Client | `FROM:sender:message`                           | Receive text DM                  |
| Client → Server | `TOMEDIA:recipient:kind:filename:base64data`    | Send image / GIF                 |
| Server → Client | `FROMMEDIA:sender:kind:filename:base64data`     | Receive image / GIF              |
| Server → Client | `SIGNIN:username`                               | Broadcast: user came online      |
| Server → Client | `SIGNOFF:username`                              | Broadcast: user went offline     |
| Server → Client | `SYSMSG:text`                                   | System notice                    |
| Client → Server | `BYE`                                           | Sign off                         |

`kind` is `image` (PNG) or `gif`. The server logs every routed message into
a `message_log` table (sender, recipient, kind, timestamp).

## Seed Accounts

Inserted on first run if `chat-data.db` does not yet exist:

| Username   | Password |
|------------|----------|
| test1      | p000     |
| test2      | p000     |
| test3      | p000     |
| engineerNV | p591     |

All other accounts are created via the client's `+ CREATE ACCOUNT` button
or `Account → Create new account…` menu item.

## Running

```bash
# Terminal 1 — start the server
python3 chat-server.py

# Terminal 2+ — launch the GUI client
python3 chat-client-gui.py
```

## Requirements

- Python 3.10+ (PEP 604 union syntax is used)
- tkinter (`sudo apt install python3-tk` on Ubuntu)
- An audio player on `PATH` for sound effects (optional):
  - Linux: `paplay`, `aplay`, `play` (sox), or `ffplay`
  - macOS: `afplay` (built in)
  - Windows: `winsound` (built in)
- No external pip packages

## Common Tasks

### Change server port/address
Edit `SERVER_HOST` / `SERVER_PORT` near the top of `chat-server.py`, and
the matching constants in `chat-client-gui.py` (also editable per-session
in the login dialog).

### Add or remove seed users
Edit the `SEED_USERS` dict in `chat-server.py`. Note that seeds are only
written when `chat-data.db` is first created — delete the DB file to
re-seed, or insert rows manually with `sqlite3 chat-data.db`.

### Modify the theme
All colours and fonts are defined as `NEON_*`, `DEEP_*`, and `FONT_*`
constants at the top of `chat-client-gui.py`.

### Edit the emoji palette
Update `DACHSHUND_EMOJIS` and `RETRO_EMOJIS` in `chat-client-gui.py`.

### Add a new sound effect
Extend `SoundFX._build_all()` with another `_write_wav("name", samples)`
call, then `self.sfx.play("name")` from anywhere in the GUI.

### Adjust max media size
Change `MAX_MEDIA_BYTES` in `chat-client-gui.py` (4 MB default) and
`MAX_LINE_BYTES` in `chat-server.py` (8 MB default — server limit must
exceed client limit since base64 inflates by ~33%).
