import random
from treys import Evaluator, Deck, Card

evaluator = Evaluator()

def format_cards(cards: list[str]) -> list[int]:
    return [Card.new(c) for c in cards]

def get_hand_percentile(board_str: list[str], hand_str: list[str], simulations: int = 500) -> float:
    """
    Returns a score from 0.0 (worst) to 1.0 (nuts).
    Evaluates the hand against N random opponent hands on the current board.
    """
    if not board_str or len(board_str) < 3:
        return 0.5  # Preflop approximation
        
    board = format_cards(board_str)
    hand = format_cards(hand_str)
    dead_cards = set(board + hand)
    
    deck = Deck().cards
    available_deck = [c for c in deck if c not in dead_cards]
    
    hero_score = evaluator.evaluate(board, hand)
    wins = 0
    
    for _ in range(simulations):
        opp_hand = random.sample(available_deck, 2)
        opp_score = evaluator.evaluate(board, opp_hand)
        # Treys: lower score is a stronger hand
        if hero_score < opp_score:
            wins += 1
            
    return wins / simulations
