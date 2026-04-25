# Network Chatroom

A retro AOL-inspired TCP chatroom built in Python with a tkinter GUI.

## Architecture

- **chat-server.py** — Multi-threaded TCP server (`localhost:12000`). One thread per client. Handles auth, routing, broadcast events.
- **chat-client-gui.py** — Tkinter GUI client with retro AOL aesthetic. Two threads: one receives from server, one drives the UI.
- **chat-client.py** — Original CLI client (kept for reference/testing).

## Protocol

All messages are newline-terminated, colon-delimited text:

| Direction       | Message                   | Meaning                        |
|----------------|---------------------------|--------------------------------|
| Client → Server | `HELLO`                   | Initiate handshake             |
| Server → Client | `HELLO`                   | Handshake ack                  |
| Client → Server | `AUTH:username:password`  | Login attempt                  |
| Server → Client | `AUTHYES`                 | Login success                  |
| Server → Client | `AUTHNO`                  | Login failure (max 3 tries)    |
| Client → Server | `LIST`                    | Request online users           |
| Server → Client | `user1, user2, ...`       | Online users list              |
| Client → Server | `TO:recipient:message`    | Send private message           |
| Server → Client | `FROM:sender:message`     | Receive private message        |
| Server → Client | `SIGNIN:username`         | Broadcast: user came online    |
| Server → Client | `SIGNOFF:username`        | Broadcast: user went offline   |
| Client → Server | `BYE`                     | Sign off                       |

## Hardcoded Accounts

| Username | Password |
|----------|----------|
| test1    | p000     |
| test2    | p000     |
| test3    | p000     |
| engineerNV | p591   |

## Running

```bash
# Terminal 1 — start server
python3 chat-server.py

# Terminal 2+ — launch GUI client
python3 chat-client-gui.py
```

## Requirements

- Python 3.6+
- tkinter (ships with most Python installs; on Ubuntu: `sudo apt install python3-tk`)
- No external pip packages

## Common Tasks

### Change server port/address
Edit `chat-server.py` lines 10–11 and `chat-client-gui.py` `SERVER_HOST`/`SERVER_PORT` constants at the top.

### Add users
Edit the `USERS` dict in `chat-server.py` `serverOps()`.

### Modify the GUI theme
All colors/fonts are defined in the `AOL_*` constants block near the top of `chat-client-gui.py`.
