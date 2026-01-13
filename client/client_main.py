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

from client.strategy import DeckCounter, choose_decision, hand_value

from colorama import init, Fore, Style
init(autoreset=True)  # Auto-reset colors after each print


def format_card(rank, suit):
    """Format card with colors: Red for ♥♦, Black for ♣♠"""
    suits = {0: "♥", 1: "♦", 2: "♣", 3: "♠"}
    ranks = {1: "A", 11: "J", 12: "Q", 13: "K"}

    r_str = ranks.get(rank, str(rank))
    s_str = suits.get(suit, "?")

    # Red suits (Hearts, Diamonds), Black suits (Clubs, Spades)
    if suit in (0, 1):  # Hearts, Diamonds
        color = Fore.RED
    else:  # Clubs, Spades
        color = Fore.WHITE

    return f"{color}[{r_str}{s_str}]{Style.RESET_ALL}"


def main():
    team_name = "RanTeam"

    # 1. Ask user for input (Instruction Requirement)
    # while True:
    #     user_input = input("Please enter number of rounds to play: ")
    #     try:
    #         rounds = int(user_input)
    #     except ValueError:
    #         print("Invalid input, defaulting to 3 rounds.")
    #         rounds = 3
    #         break
    #
    #     if rounds > 255:
    #         print("Error: Cannot play more than 255 rounds because the protocol uses only 1 byte. Please choose again.")
    #         continue
    #
    #     break

    # 2. Run forever (Instruction Requirement)
    while True:
        # 🆕 NEW: Ask for rounds at the start of each session
        print("\n" + Fore.CYAN + "=" * 60)
        print("🎮 NEW SESSION - Ready to connect to a server")
        print("=" * 60 + Style.RESET_ALL)

        while True:
            user_input = input("Enter number of rounds to play (or 'q' to quit): ")

            # Allow quitting
            if user_input.lower() == 'q':
                print("[CLIENT] Exiting...")
                return

            try:
                rounds = int(user_input)
            except ValueError:
                print("❌ Invalid input. Please enter a number or 'q' to quit.")
                continue

            # Validate rounds
            if rounds <= 0:
                print("❌ Error: Must play at least 1 round.")
                continue

            if rounds > 255:
                print("❌ Error: Cannot play more than 255 rounds (protocol limit).")
                continue

            break  # Valid input, proceed


        # 🆕 Select game mode (שורה 65 החדשה)
        print("\nSelect game mode:")
        print("  1) AUTO - Strategy plays automatically")
        print("  2) MANUAL - You decide each move")

        while True:
            mode_input = input("Enter mode (1 or 2): ").strip()
            if mode_input == '1':
                auto_mode = True
                print("[CLIENT] Mode: AUTO\n")
                break
            elif mode_input == '2':
                auto_mode = False
                print("[CLIENT] Mode: MANUAL\n")
                break
            else:
                print("❌ Invalid choice. Enter 1 or 2.")

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
            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket
            tcp_sock.settimeout(15.0)  # 15 seconds timeout for connect
            tcp_sock.connect((server_ip, server_port))  # connect to server

            # Send request
            tcp_sock.sendall(pack_request(rounds, team_name))
            print(f"[CLIENT] Sent request: rounds={rounds} team='{team_name}'")

            # Play session statistics
            stats = {
                "wins": 0,
                "losses": 0,
                "ties": 0
            }

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

                    print(f"[CLIENT] {who}: {format_card(r, s)}") # format card

                player_turn = True
                last_decision = None

                while True:
                    # If it's still player turn, decide and send decision
                    if player_turn:
                        # 🆕 Mode-based decision
                        if auto_mode:
                            # Automatic strategy
                            decision = choose_decision(player_ranks, dealer_up_rank, deck_counter)
                            dec_color = Fore.GREEN if decision == "Stand" else Fore.YELLOW
                            print(f"[CLIENT] {dec_color}AUTO decision -> {decision}{Style.RESET_ALL}")
                        else:
                            # Manual mode
                            total, soft = hand_value(player_ranks)
                            soft_str = f"{Fore.CYAN} (soft){Style.RESET_ALL}" if soft else ""

                            print(f"\n{Fore.YELLOW}[CLIENT] 🎯 YOUR TURN{Style.RESET_ALL}")
                            print(f"[CLIENT] Your total: {Fore.CYAN}{total}{Style.RESET_ALL}{soft_str}")
                            # Display all player cards with varied suits for visual variety
                            player_cards_display = ' '.join([format_card(r, i % 4) for i, r in enumerate(player_ranks)])
                            print(f"[CLIENT] Your cards: {player_cards_display}")

                            bust_prob = deck_counter.bust_probability_if_hit(player_ranks)
                            prob_color = Fore.RED if bust_prob > 0.6 else Fore.YELLOW if bust_prob > 0.4 else Fore.GREEN
                            print(f"[CLIENT] {prob_color}📊 Bust chance if Hit: {bust_prob * 100:.1f}%{Style.RESET_ALL}")

                            while True:
                                choice = input(
                                    f"{Fore.CYAN}[CLIENT] Your decision (h=Hit / s=Stand): {Style.RESET_ALL}").strip().lower()
                                if choice == 'h':
                                    decision = "Hittt"
                                    break
                                elif choice == 's':
                                    decision = "Stand"
                                    break
                                else:
                                    print(f"{Fore.RED}❌ Invalid input. Enter 'h' or 's'.{Style.RESET_ALL}")

                            dec_color = Fore.GREEN if decision == "Stand" else Fore.YELLOW
                            print(f"[CLIENT] {dec_color}MANUAL decision -> {decision}{Style.RESET_ALL}\n")

                        last_decision = decision
                        tcp_sock.sendall(pack_client_payload_decision(decision))

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

                    # Print card event
                    card_str = format_card(rank, suit)
                    if res != 0:
                        # final card event
                        print(f"[CLIENT] {who} (Final): {card_str}")
                    else:
                        # regular card event
                        print(f"[CLIENT] {who}: {card_str}")


                    if res != 0:
                        # Round ended (1=tie,2=loss,3=win)
                        outcome = "UNKNOWN"
                        if res == 1:
                            outcome = "TIE"
                            stats["ties"] += 1
                        elif res == 2:
                            outcome = "LOSS"
                            stats["losses"] += 1
                        elif res == 3:
                            outcome = "WIN"
                            stats["wins"] += 1

                        print(f"[CLIENT] Round ended -> {outcome}")
                        break

            tcp_sock.close()

            print("\n" + "=" * 30)
            print(f"SESSION SUMMARY ({rounds} rounds)")
            print("=" * 30)
            print(f"Wins:   {stats['wins']}")
            print(f"Losses: {stats['losses']}")
            print(f"Ties:   {stats['ties']}")

            win_rate = (stats['wins'] / rounds) * 100 if rounds > 0 else 0
            print(f"Win Rate: {win_rate:.1f}%")
            print("=" * 30 + "\n")

            print("[CLIENT] Session finished. Returning to listen state...\n")

        except socket.timeout:
            print("\n[CLIENT] Error: Server stopped responding (Timeout).")
            print("[CLIENT] Returning to listen state...\n")

        except Exception as e:
            print(f"[CLIENT] Error during session: {e}")
            # We don't exit, we just loop back to listen for offers


if __name__ == "__main__":
    main()
