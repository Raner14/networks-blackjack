# --- Network ports ---
OFFER_BROADCAST_UDP_PORT = 13122  # clients listen for offers (UDP)

# --- Protocol identifiers ---
PROTOCOL_MAGIC_COOKIE = 0xabcddcba

MSG_TYPE_OFFER = 0x2     # UDP: server -> client
MSG_TYPE_REQUEST = 0x3   # TCP: client -> server
MSG_TYPE_PAYLOAD = 0x4   # TCP: both directions

# --- Fixed field sizes (bytes) ---
MAGIC_COOKIE_BYTES = 4
MESSAGE_TYPE_BYTES = 1

TCP_PORT_FIELD_BYTES = 2          # Offer: server TCP port
ROUND_COUNT_FIELD_BYTES = 1       # Request: number of rounds

TEAM_NAME_FIELD_BYTES = 32        # Offer/Request: fixed-length team/server name
CLIENT_DECISION_FIELD_BYTES = 5   # Payload (client->server): "Hittt" or "Stand"

# --- Card encoding sizes (bytes) ---
CARD_RANK_FIELD_BYTES = 2         # rank 01-13 stored in 2 bytes (uint16)
CARD_SUIT_FIELD_BYTES = 1         # suit 0-3 stored in 1 byte (uint8)
CARD_VALUE_FIELD_BYTES = CARD_RANK_FIELD_BYTES + CARD_SUIT_FIELD_BYTES  # 3

ROUND_RESULT_FIELD_BYTES = 1      # Payload (server->client): result byte

# --- Message sizes (bytes) ---
OFFER_MESSAGE_BYTES = (
    MAGIC_COOKIE_BYTES +
    MESSAGE_TYPE_BYTES +
    TCP_PORT_FIELD_BYTES +
    TEAM_NAME_FIELD_BYTES
)  # 39 : cookies(4) + type(1) + port(2) + name(32)

REQUEST_MESSAGE_BYTES = (
    MAGIC_COOKIE_BYTES +
    MESSAGE_TYPE_BYTES +
    ROUND_COUNT_FIELD_BYTES +
    TEAM_NAME_FIELD_BYTES
)  # 38 : cookies(4) + type(1) + rounds(1) + name(32)

CLIENT_PAYLOAD_MESSAGE_BYTES = (
    MAGIC_COOKIE_BYTES +
    MESSAGE_TYPE_BYTES +
    CLIENT_DECISION_FIELD_BYTES
)  # 10 : cookies(4) + type(1) + decision(5)

SERVER_PAYLOAD_MESSAGE_BYTES = (
    MAGIC_COOKIE_BYTES +
    MESSAGE_TYPE_BYTES +
    ROUND_RESULT_FIELD_BYTES +
    CARD_VALUE_FIELD_BYTES
)  # 9 : cookies(4) + type(1) + result(1) + card(3)
   #     card(3): rank(2) + suit(1)
