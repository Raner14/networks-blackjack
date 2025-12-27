from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Tuple


RESULT_NOT_OVER = 0x0
RESULT_TIE      = 0x1
RESULT_LOSS     = 0x2
RESULT_WIN      = 0x3


@dataclass(frozen=True)
class Card:
    rank: int  # 1..13  (Ace=1, J=11, Q=12, K=13)
    suit: int  # 0..3


class Deck:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.cards: List[Card] = []
        self.reset()

    def reset(self) -> None:
        self.cards = [Card(rank, suit) for suit in range(4) for rank in range(1, 14)]
        self.rng.shuffle(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            self.reset()
        return self.cards.pop()


def card_value_for_hand(rank: int) -> int:
    """Blackjack value (Ace handled in hand_value)."""
    if rank == 1:
        return 1
    if 2 <= rank <= 10:
        return rank
    return 10  # J,Q,K


def hand_value(hand: List[Card]) -> Tuple[int, bool]:
    """
    Returns (best_total, is_soft).
    - Count all Aces as 1 first, then upgrade one Ace to 11 if it doesn't bust.
    """
    total = 0
    aces = 0
    for c in hand:
        v = card_value_for_hand(c.rank)
        total += v
        if c.rank == 1:
            aces += 1

    is_soft = False
    if aces > 0 and total + 10 <= 21:  # upgrade one Ace from 1 -> 11 (adds +10)
        total += 10
        is_soft = True

    return total, is_soft


class BlackjackRound:
    """
    Server-authoritative blackjack round:
    - Deal: player gets 2 cards, dealer gets 2 cards (one is 'upcard').
    - Player decisions: Hittt / Stand.
    - Dealer rule: hit until total >= 17 (stand on all 17, including soft 17).
    """

    def __init__(self, deck: Deck):
        self.deck = deck
        self.player: List[Card] = []
        self.dealer: List[Card] = []
        self.phase = "INIT"  # INIT -> PLAYER -> DEALER -> OVER

    def start(self) -> List[Card]:
        self.player = [self.deck.draw(), self.deck.draw()]
        self.dealer = [self.deck.draw(), self.deck.draw()]
        self.phase = "PLAYER"
        # We will send: player[0], player[1], dealer[0] as "upcard"
        return [self.player[0], self.player[1], self.dealer[0]]

    def player_hit(self) -> Card:
        c = self.deck.draw()
        self.player.append(c)
        return c

    def dealer_draw(self) -> Card:
        c = self.deck.draw()
        self.dealer.append(c)
        return c

    def _final_result(self) -> int:
        p_total, _ = hand_value(self.player)
        d_total, _ = hand_value(self.dealer)

        if p_total > 21:
            return RESULT_LOSS
        if d_total > 21:
            return RESULT_WIN
        if p_total > d_total:
            return RESULT_WIN
        if p_total < d_total:
            return RESULT_LOSS
        return RESULT_TIE

    def apply_decision(self, decision: str) -> List[tuple[int, Card]]:
        """
        Returns a list of (result, card_to_send) payloads to transmit.
        We send cards as the game progresses.
        """
        out: List[tuple[int, Card]] = []

        if self.phase != "PLAYER":
            # After player stands, client should keep sending "Stand" while server finishes dealer.
            decision = "Stand"

        if self.phase == "PLAYER":
            if decision == "Hittt":
                c = self.player_hit()
                p_total, _ = hand_value(self.player)
                if p_total > 21:
                    self.phase = "OVER"
                    out.append((RESULT_LOSS, c))  # last card that busted the player
                else:
                    out.append((RESULT_NOT_OVER, c))
                return out

            if decision == "Stand":
                # Switch to dealer phase, reveal dealer hole card first as a "card event"
                self.phase = "DEALER"
                out.append((RESULT_NOT_OVER, self.dealer[1]))  # reveal hole card

        if self.phase == "DEALER":
            while True:
                d_total, _ = hand_value(self.dealer)
                if d_total >= 17:
                    self.phase = "OVER"
                    # Send one "final" payload: use last dealer card (hole or last drawn)
                    last = self.dealer[-1]
                    out.append((self._final_result(), last))
                    return out
                c = self.dealer_draw()
                # dealer drew a card, still not necessarily over yet
                out.append((RESULT_NOT_OVER, c))
                # We return after each dealer draw to keep ping-pong stable
                return out

        # If OVER already:
        last = (self.dealer[-1] if self.dealer else self.player[-1])
        out.append((self._final_result(), last))
        return out
