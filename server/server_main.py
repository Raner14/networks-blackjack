import socket
import select
import time

from common.constants import (
    OFFER_BROADCAST_UDP_PORT,
    REQUEST_MESSAGE_BYTES,
    CLIENT_PAYLOAD_MESSAGE_BYTES,
    SERVER_PAYLOAD_MESSAGE_BYTES,
)
from common.protocol import (
    pack_offer,
    unpack_request,
    pack_server_payload,
    unpack_client_payload_decision,
)
from common.net_utils import recv_exact

from server.game import Deck, BlackjackRound, RESULT_NOT_OVER

BROADCAST_ADDR = "255.255.255.255"
OFFER_INTERVAL_SEC = 1.0


def play_session_blackjack(client_sock: socket.socket, rounds: int) -> None:
    """
    Plays `rounds` blackjack rounds with one connected client.
    Uses server/game.py for rules + state.
    """
    deck = Deck()

    for round_i in range(rounds):
        game = BlackjackRound(deck)

        # 1) Initial deal: send 3 payloads (player, player, dealer upcard)
        initial_cards = game.start()  # [player1, player2, dealer_up]
        for c in initial_cards:
            client_sock.sendall(pack_server_payload(RESULT_NOT_OVER, c.rank, c.suit))

        player_turn = True
        last_decision = None

        # 2) Round loop
        while True:
            if player_turn:
                # wait for client decision
                raw = recv_exact(client_sock, CLIENT_PAYLOAD_MESSAGE_BYTES)
                dec = unpack_client_payload_decision(raw)
                if dec is None:
                    print("[SERVER] Invalid client decision payload")
                    return
                last_decision = dec["decision"]

                if last_decision == "Stand":
                    player_turn = False

                events = game.apply_decision(last_decision)

            else:
                # dealer phase: server advances without needing more client messages
                events = game.apply_decision("Stand")

            # send all produced events (usually 1; may be 2 when revealing hole+final, etc.)
            for result, card in events:
                client_sock.sendall(pack_server_payload(result, card.rank, card.suit))
                if result != 0:
                    # round ended
                    break

            if events and events[-1][0] != 0:
                break


def main():
    server_name = "RanServer"  # תשנה לשם השרת שלכם

    # --- TCP listen socket (publish its port in the offer) ---
    tcp_listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_listen.bind(("", 0))
    tcp_listen.listen()
    tcp_port = tcp_listen.getsockname()[1]

    # --- UDP broadcast socket for offers ---
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    print(f"[SERVER] Name='{server_name}' | UDP offers on {OFFER_BROADCAST_UDP_PORT} | TCP port={tcp_port}")

    next_offer_time = 0.0

    try:
        while True:
            now = time.monotonic()

            # 1) Broadcast offer every interval (when idle / waiting for a client)
            if now >= next_offer_time:
                offer = pack_offer(tcp_port, server_name)
                udp_sock.sendto(offer, (BROADCAST_ADDR, OFFER_BROADCAST_UDP_PORT))
                next_offer_time = now + OFFER_INTERVAL_SEC

            # 2) Non-blocking accept (so we can still broadcast offers)
            timeout = max(0.0, next_offer_time - time.monotonic())
            rlist, _, _ = select.select([tcp_listen], [], [], timeout)

            if tcp_listen in rlist:
                client_sock, client_addr = tcp_listen.accept()
                print(f"[SERVER] TCP client connected from {client_addr}")

                try:
                    # read + parse request
                    req_bytes = recv_exact(client_sock, REQUEST_MESSAGE_BYTES)
                    req = unpack_request(req_bytes)

                    if req is None:
                        print("[SERVER] Invalid request received")
                        continue

                    rounds = req["rounds"]
                    team = req["client_team_name"]
                    print(f"[SERVER] Request OK: rounds={rounds} team='{team}'")

                    # play blackjack session
                    play_session_blackjack(client_sock, rounds)

                finally:
                    client_sock.close()
                    print("[SERVER] Client disconnected, back to broadcasting...")

    except KeyboardInterrupt:
        print("\n[SERVER] Stopped.")
    finally:
        udp_sock.close()
        tcp_listen.close()


if __name__ == "__main__":
    main()
