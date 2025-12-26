"""
Protocol serialization/deserialization layer.

This file should contain ONLY:
- fixed-length name encoding/decoding (32 bytes)
- pack_* functions: fields -> bytes
- unpack_* functions: bytes -> fields (with validation)

No sockets, no game logic.
"""

from __future__ import annotations

import struct
from typing import Optional, Dict, Any

from common.constants import (
    PROTOCOL_MAGIC_COOKIE,
    MSG_TYPE_OFFER,
    MSG_TYPE_REQUEST,
    MSG_TYPE_PAYLOAD,
    TEAM_NAME_FIELD_BYTES,
    CLIENT_DECISION_FIELD_BYTES,
    OFFER_MESSAGE_BYTES,
    REQUEST_MESSAGE_BYTES,
    CLIENT_PAYLOAD_MESSAGE_BYTES,
    SERVER_PAYLOAD_MESSAGE_BYTES,
)



def encode_fixed_name_32(name: str) -> bytes:
    """
    Encode a name into exactly 32 bytes : TEAM_NAME_FIELD_BYTES
    - If shorter: pad with 0x00
    - If longer: truncate
    """
    b = name.encode("utf-8", errors="replace")
    b = b[:TEAM_NAME_FIELD_BYTES]
    return b.ljust(TEAM_NAME_FIELD_BYTES, b"\x00")


def decode_fixed_name_32(raw: bytes) -> str:
    """
    Decode a 32-byte name field back into a Python string.
    Stop at the first 0x00 byte.
    """
    name_bytes = raw.split(b"\x00", 1)[0]  # take bytes before the first 0x00
    return name_bytes.decode("utf-8", errors="replace")


# -------------------------
# Offer(UDP): Server -> Client
# cookie(4) | type(1=0x2) | server_tcp_port(2) | server_name(32)
# -------------------------

def pack_offer(server_tcp_port: int, server_name: str) -> bytes:
    """
    Build an Offer message (39 bytes).
    """
    if not (0 <= server_tcp_port <= 0xFFFF):
        raise ValueError("server_tcp_port must fit in 2 bytes (0..65535)")
    name_bytes = encode_fixed_name_32(server_name)

    return struct.pack("!IBH32s", PROTOCOL_MAGIC_COOKIE, MSG_TYPE_OFFER, server_tcp_port, name_bytes) #



def unpack_offer(data: bytes) -> Optional[dict]:
    """
    Parse and validate an Offer message.
    Return dict with: server_tcp_port, server_name
    Return None if invalid.
    """
    # length check (Offer must be exactly 39 bytes)
    if len(data) != OFFER_MESSAGE_BYTES:
        return None

    # unpack according to the offer format
    cookie, msg_type, tcp_port, name_b = struct.unpack("!IBH32s", data)

    # validate cookie and message type
    if cookie != PROTOCOL_MAGIC_COOKIE:
        return None
    if msg_type != MSG_TYPE_OFFER:
        return None

    # decode the fixed-length name
    server_name = decode_fixed_name_32(name_b)

    return {
        "server_tcp_port": tcp_port,
        "server_name": server_name,
    }



# -------------------------
# Request(TCP): Client -> Server
# cookie(4) | type(1=0x3) | rounds(1) | team_name(32)
# -------------------------

def pack_request(rounds: int, client_team_name: str) -> bytes:
    """
    Build a Request message (38 bytes):
    cookie(4) | type(1=0x3) | rounds(1) | team_name(32)
    """
    if not (0 <= rounds <= 255):
        raise ValueError("rounds must fit in 0..255 (1 byte)")

    name_b = encode_fixed_name_32(client_team_name)

    # Network byte order (big-endian): ! I B B 32s
    return struct.pack(
        "!IBB32s",
        PROTOCOL_MAGIC_COOKIE,
        MSG_TYPE_REQUEST,
        rounds,
        name_b,
    )



def unpack_request(data: bytes):
    """
    Parse and validate a Request message.
    Return dict with: rounds, client_team_name
    Return None if invalid.
    """
    # length check (Request must be exactly 38 bytes)
    if len(data) != REQUEST_MESSAGE_BYTES:
        return None

    # unpack according to the request format
    cookie, msg_type, rounds, name_b = struct.unpack("!IBB32s", data)

    # validate cookie and message type
    if cookie != PROTOCOL_MAGIC_COOKIE:
        return None
    if msg_type != MSG_TYPE_REQUEST:
        return None

    # (optional sanity) rounds is 1 byte anyway, but you can still validate
    if not (0 <= rounds <= 255):
        return None

    # decode the fixed-length name
    team_name = decode_fixed_name_32(name_b)

    return {
        "rounds": rounds,
        "client_team_name": team_name,
    }



# -------------------------
# Payload (TCP) - Client -> Server (Decision)
# cookie(4) | type(1=0x4) | decision(5)  where decision is b"Hittt" or b"Stand"
# -------------------------

def pack_client_payload_decision(decision: str) -> bytes:
    """
    Build a client payload decision message (10 bytes):
    cookie(4) | type(1=0x4) | decision(5)
    decision must be exactly "Hittt" or "Stand".
    """
    if decision not in ("Hittt", "Stand"):
        raise ValueError('decision must be "Hittt" or "Stand"')

    decision_b = decision.encode("ascii")  # should be 5 bytes
    if len(decision_b) != CLIENT_DECISION_FIELD_BYTES:
        raise ValueError("decision must be exactly 5 bytes")

    return struct.pack(
        "!IB5s",
        PROTOCOL_MAGIC_COOKIE,
        MSG_TYPE_PAYLOAD,
        decision_b,
    )



def unpack_client_payload_decision(data: bytes):
    """
    Parse and validate a client payload decision message (10 bytes).
    Return dict with: decision
    Return None if invalid.
    """
    if len(data) != CLIENT_PAYLOAD_MESSAGE_BYTES:
        return None

    cookie, msg_type, decision_b = struct.unpack("!IB5s", data)

    if cookie != PROTOCOL_MAGIC_COOKIE:
        return None
    if msg_type != MSG_TYPE_PAYLOAD:
        return None

    decision = decision_b.decode("ascii", errors="replace")
    if decision not in ("Hittt", "Stand"):
        return None

    return {"decision": decision}



# -------------------------
# Payload (TCP) - Server -> Client (Result + Card)
# cookie(4) | type(1=0x4) | result(1) | rank(2) | suit(1)
# result: 0x0 not over, 0x1 tie, 0x2 loss, 0x3 win
# rank: 1..13 in 2 bytes
# suit: 0..3 in 1 byte (HDCS)
# -------------------------

def pack_server_payload(result: int, rank: int, suit: int) -> bytes:
    """
    Build a server payload message (9 bytes):
    cookie(4) | type(1=0x4) | result(1) | rank(2) | suit(1)
    """
    if not (0 <= result <= 3):
        raise ValueError("result must be 0..3")
    if not (1 <= rank <= 13):
        raise ValueError("rank must be 1..13")
    if not (0 <= suit <= 3):
        raise ValueError("suit must be 0..3")

    return struct.pack(
        "!IBBHB",
        PROTOCOL_MAGIC_COOKIE,
        MSG_TYPE_PAYLOAD,
        result,
        rank,
        suit,
    )



def unpack_server_payload(data: bytes):
    """
    Parse and validate a server payload message (9 bytes).
    Return dict with: result, rank, suit
    Return None if invalid.
    """
    if len(data) != SERVER_PAYLOAD_MESSAGE_BYTES:
        return None

    cookie, msg_type, result, rank, suit = struct.unpack("!IBBHB", data)

    if cookie != PROTOCOL_MAGIC_COOKIE:
        return None
    if msg_type != MSG_TYPE_PAYLOAD:
        return None
    if not (0 <= result <= 3 and 1 <= rank <= 13 and 0 <= suit <= 3):
        return None

    return {"result": result, "rank": rank, "suit": suit}

