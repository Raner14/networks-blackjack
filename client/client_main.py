import socket
import sys

from common.constants import (
    OFFER_BROADCAST_UDP_PORT,
    SERVER_PAYLOAD_MESSAGE_BYTES,
)
from common.protocol import (
    unpack_offer,
    pack_request,
    unpack_server_payload,
    pack_client_payload_decision,
)
from common.net_utils import recv_exact

from client.strategy import DeckCounter, choose_decision


def main():
    team_name = "RanTeam"

    # 1. Ask user for input (Instruction Requirement)
    while True:
        user_input = input("Please enter number of rounds to play: ")
        try:
            rounds = int(user_input)
        except ValueError:
            print("Invalid input, defaulting to 3 rounds.")
            rounds = 3
            break

        if rounds > 255:
            print("Error: Cannot play more than 255 rounds because the protocol uses only 1 byte. Please choose again.")
            continue

        break




    # 2. Run forever (Instruction Requirement)
    while True:
        print(f"[CLIENT] Listening for offers on UDP {OFFER_BROADCAST_UDP_PORT}...")

        # --- UDP listen for offers ---
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # --- Cross-platform Reuse Port Fix ---
        # Windows uses SO_REUSEADDR. Linux needs SO_REUSEPORT.
        try:
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except AttributeError:
            pass

        try:
            # SO_REUSEPORT is not defined in Windows python, so we wrap in try/except
            udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            # This happens on Windows, which is fine because REUSEADDR handles it there
            pass
        # -------------------------------------

        udp_sock.bind(("", OFFER_BROADCAST_UDP_PORT))

        server_ip = None
        server_port = None
        server_name = None

        try:
            # 1) wait for a valid offer
            while True:
                data, addr = udp_sock.recvfrom(1024)
                offer = unpack_offer(data)
                if offer is None:
                    continue

                server_ip = addr[0]
                server_port = offer["server_tcp_port"]
                server_name = offer["server_name"]
                print(f"[CLIENT] Received offer from {server_ip} | server_name='{server_name}'")
                break
        finally:
            udp_sock.close()

        # 2) Connect and Play Session
        print(f"[CLIENT] Connecting to {server_ip}:{server_port}...")
        try:
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.connect((server_ip, server_port))

            # Send request
            tcp_sock.sendall(pack_request(rounds, team_name))
            print(f"[CLIENT] Sent request: rounds={rounds} team='{team_name}'")

            wins = 0  # Initialize win counter

            # 3) Play rounds logic
            deck_counter = DeckCounter()

            for round_i in range(rounds):
                print(f"\n[CLIENT] === Round {round_i + 1} ===")

                player_ranks = []
                dealer_up_rank = None

                # initial 3 payloads: player, player, dealer upcard
                for j in range(3):
                    raw = recv_exact(tcp_sock, SERVER_PAYLOAD_MESSAGE_BYTES)
                    srv = unpack_server_payload(raw)
                    if srv is None:
                        raise ValueError("Invalid server payload (initial deal)")

                    r = srv["rank"]
                    s = srv["suit"]
                    res = srv["result"]

                    deck_counter.remove_seen(r)

                    if j < 2:
                        player_ranks.append(r)
                        who = "PLAYER"
                    else:
                        dealer_up_rank = r
                        who = "DEALER_UP"

                    print(f"[CLIENT] {who}: result={res} rank={r} suit={s}")

                player_turn = True
                last_decision = None

                while True:
                    # If it's still player turn, decide and send decision
                    if player_turn:
                        decision = choose_decision(player_ranks, dealer_up_rank, deck_counter)
                        last_decision = decision
                        tcp_sock.sendall(pack_client_payload_decision(decision))
                        print(f"[CLIENT] decision -> {decision}")

                        if decision == "Stand":
                            player_turn = False

                    # Always receive next server payload
                    raw = recv_exact(tcp_sock, SERVER_PAYLOAD_MESSAGE_BYTES)
                    srv = unpack_server_payload(raw)
                    if srv is None:
                        raise ValueError("Invalid server payload")

                    res = srv["result"]
                    rank = srv["rank"]
                    suit = srv["suit"]

                    deck_counter.remove_seen(rank)

                    # If we hit and it's still player turn context, this card is usually for the player
                    if player_turn and last_decision == "Hittt":
                        player_ranks.append(rank)
                        who = "PLAYER_DRAW"
                    else:
                        who = "DEALER_EVENT"

                    print(f"[CLIENT] {who}: result={res} rank={rank} suit={suit}")

                    if res != 0:
                        outcome = {1: "TIE", 2: "LOSS", 3: "WIN"}.get(res, f"RES={res}")
                        print(f"[CLIENT] Round ended -> {outcome}")

                        if res == 3:
                            wins += 1
                        break

            tcp_sock.close()

            win_rats = (wins / rounds) * 100 if rounds > 0 else 0
            print(f"[CLIENT] Finished playing {rounds} rounds, win rate: {win_rats:.1f}%")

            print("[CLIENT] Session finished. Returning to listen state...\n")

        except Exception as e:
            print(f"[CLIENT] Error during session: {e}")
            # We don't exit, we just loop back to listen for offers


if __name__ == "__main__":
    main()
