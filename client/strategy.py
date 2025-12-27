from __future__ import annotations
from collections import Counter
from typing import List, Tuple


def bj_value(rank: int) -> int:
    if rank == 1:
        return 1
    if 2 <= rank <= 10:
        return rank
    return 10


def hand_value(ranks: List[int]) -> Tuple[int, bool]:
    total = sum(bj_value(r) for r in ranks)
    aces = sum(1 for r in ranks if r == 1)
    soft = False
    if aces > 0 and total + 10 <= 21:
        total += 10
        soft = True
    return total, soft


class DeckCounter:
    """
    Track remaining deck composition (52 cards).
    We only update based on seen cards (player cards + dealer upcard + dealer revealed cards).
    """
    def __init__(self):
        self.counts = Counter()
        for rank in range(1, 14):
            self.counts[rank] = 4  # 4 suits

    def remove_seen(self, rank: int) -> None:
        if self.counts[rank] > 0:
            self.counts[rank] -= 1

    def total_remaining(self) -> int:
        return sum(self.counts.values())

    def bust_probability_if_hit(self, player_ranks: List[int]) -> float:
        total_cards = self.total_remaining()
        if total_cards == 0:
            return 0.0

        bust = 0
        for rank, cnt in self.counts.items():
            if cnt <= 0:
                continue
            new_ranks = player_ranks + [rank]
            new_total, _ = hand_value(new_ranks)
            if new_total > 21:
                bust += cnt

        return bust / total_cards


def choose_decision(player_ranks: List[int], dealer_up_rank: int | None, deck: DeckCounter) -> str:
    """
    Heuristic-statistical strategy:
    - Always hit <= 11
    - Always stand >= 17
    - Otherwise: compute bust probability from remaining deck
      and adjust threshold using dealer upcard (aggressive vs strong dealer card).
    """
    total, soft = hand_value(player_ranks)

    if total <= 11:
        return "Hittt"
    if total >= 17 and not soft:
        return "Stand"
    if total >= 18 and soft:
        return "Stand"

    p_bust = deck.bust_probability_if_hit(player_ranks)

    # Dealer upcard strength: 7-A is "strong", 2-6 is "weak"
    if dealer_up_rank is None:
        threshold = 0.45
    else:
        if dealer_up_rank in (1, 10, 11, 12, 13, 9, 8, 7):
            threshold = 0.55  # be more aggressive
        else:
            threshold = 0.40  # be more conservative

    return "Hittt" if p_bust <= threshold else "Stand"
