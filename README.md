# networks-blackjack

A client-server implementation of the Blackjack card game using Python sockets.  
The project demonstrates a custom **binary application-layer protocol** over **UDP (broadcast discovery)** and **TCP (game session)**.

---

## Project Structure

- **`server/`**
  - `server_main.py` — UDP offer broadcaster + TCP server (accepts clients, runs game session)
  - `game.py` — Blackjack rules + deck/round state (server-authoritative)
- **`client/`**
  - `client_main.py` — listens for UDP offers, connects via TCP, plays automatically
  - `strategy.py` — client decision logic ("Hittt"/"Stand") based on probability heuristics
- **`common/`**
  - `constants.py` — protocol constants + fixed message sizes
  - `protocol.py` — pack/unpack (serialization/deserialization) for all message types
  - `net_utils.py` — helpers (e.g., `recv_exact` for TCP fixed-length reads)

---

## Requirements

- Python **3.10+**
- Running on the same machine (localhost) or the same LAN
- If broadcast is blocked (Windows Firewall), allow Python for **Private networks**

---

## How to Run

From the project root:

### 1) Start the Server

```bash
python -m server.server_main
```

### 2) Start the Client

```bash
python -m client.client_main
```

Expected flow:
1. Server broadcasts UDP offers every ~1 second
2. Client receives an offer, connects via TCP, sends a request
3. Server runs the requested number of blackjack rounds and sends payload updates

---

## Protocol Specification

All integers are encoded in **Big-Endian** network byte order (`struct` with `!`).

### General Constants
- **Magic Cookie:** `0xabcddcba` (4 bytes) — every message must start with this value
- **UDP Offer Port:** `13122`
- **Encoding:**
  - Binary fields via `struct.pack/unpack`
  - Fixed strings are padded with `0x00`

### Message Types

| Type ID | Name | Direction | Transport | Purpose |
| --- | --- | --- | --- | --- |
| `0x02` | Offer | Server → Client | UDP | Broadcast server availability + TCP port |
| `0x03` | Request | Client → Server | TCP | Start a game session (round count + team name) |
| `0x04` | Payload | Both directions | TCP | Gameplay updates / decisions |

---

## Packet Formats

### 1) Offer (UDP) — 39 bytes
Broadcasted every ~1 second.

| Field | Size | Type | Notes |
| --- | --- | --- | --- |
| Magic Cookie | 4 | `uint32` | `0xabcddcba` |
| Message Type | 1 | `uint8` | `0x02` |
| Server TCP Port | 2 | `uint16` | TCP port clients should connect to |
| Server Name | 32 | `char[32]` | UTF-8 bytes padded with `0x00` |

**Struct format:** `!IBH32s`

---

### 2) Request (TCP) — 38 bytes
Sent immediately after TCP connection.

| Field | Size | Type | Notes |
| --- | --- | --- | --- |
| Magic Cookie | 4 | `uint32` | `0xabcddcba` |
| Message Type | 1 | `uint8` | `0x03` |
| Rounds | 1 | `uint8` | 0–255 (practically use 1+) |
| Team Name | 32 | `char[32]` | UTF-8 bytes padded with `0x00` |

**Struct format:** `!IBB32s`

---

### 3) Client Payload (TCP) — 10 bytes
Client decision message.

| Field | Size | Type | Notes |
| --- | --- | --- | --- |
| Magic Cookie | 4 | `uint32` | `0xabcddcba` |
| Message Type | 1 | `uint8` | `0x04` |
| Decision | 5 | `char[5]` | ASCII: `"Hittt"` or `"Stand"` |

**Struct format:** `!IB5s`

---

### 4) Server Payload (TCP) — 9 bytes
Server update message.

| Field | Size | Type | Notes |
| --- | --- | --- | --- |
| Magic Cookie | 4 | `uint32` | `0xabcddcba` |
| Message Type | 1 | `uint8` | `0x04` |
| Result | 1 | `uint8` | 0=Active, 1=Tie, 2=Loss, 3=Win |
| Rank | 2 | `uint16` | 1–13 (1=A, 11=J, 12=Q, 13=K) |
| Suit | 1 | `uint8` | 0=Hearts, 1=Diamonds, 2=Clubs, 3=Spades *(HDCS)* |

**Struct format:** `!IBBHB`

> Note: `rank=13` means **King** (value 10), not “13 points”.

---

## Game Flow (Session)

### Discovery + Connection
1. Server broadcasts **Offer** on UDP port `13122`
2. Client receives Offer, extracts `server_tcp_port`
3. Client connects to `(server_ip, server_tcp_port)` over TCP
4. Client sends **Request** (`rounds`, `team_name`)

### Round Flow (Blackjack over Payloads)
For each round, the server sends initial cards as **three server payloads** (all with `result=0`):
1. Player card #1
2. Player card #2
3. Dealer up-card (visible)

Then:
- While the round is active (`result=0`), the client may send **Client Payload** decisions:
  - `"Hittt"` to draw another player card
  - `"Stand"` to stop drawing and let dealer play
- The server replies with **Server Payload** updates (new cards) and eventually sends a final payload with:
  - `result` in `{1,2,3}` meaning Tie/Loss/Win
- After the final payload (`result != 0`), the next round begins (until `rounds` completed)

---

## Blackjack Rules (Server-Authoritative)

- **Deck:** Standard 52-card deck; reshuffled when empty
- **Card values:**
  - 2–10 = face value
  - J/Q/K (11/12/13) = 10
  - Ace (1) = 1 or 11 (whichever gives best total ≤ 21)
- **Dealer rule:** Hits until total ≥ 17; stands on soft 17
- **Outcome:** Best total ≤ 21 wins; bust (>21) is automatic loss; equal totals = tie

---

## Client Strategy (`client/strategy.py`)

The client uses a probability-based heuristic:
1. Tracks **seen cards** to estimate remaining deck composition
2. Computes **bust probability** if choosing `"Hittt"`
3. Decision rules (high level):
   - Always **Hit** if total ≤ 11
   - Usually **Stand** on strong totals (hard ≥ 17, soft ≥ 18)
   - Otherwise compare bust probability vs a threshold influenced by dealer up-card strength

This strategy is meant to be simple and demonstrative, not perfect Blackjack basic strategy.

---

## Notes / Debugging Tips

- If the client does not receive offers:
  - Ensure both machines are on the same LAN (or test on localhost)
  - Check Windows Firewall rules for Python (Private networks)
- TCP reads use `recv_exact(...)` because **TCP is a byte stream** (a single `recv(n)` may return fewer than `n` bytes)

---

