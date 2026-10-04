import random
import numpy as np
from treys import Deck, Evaluator, Card
from engine.hand_evaluator import format_cards

evaluator = Evaluator()

def generate_range(available_deck, board, is_value=True):
    """
    Iteratively finds a hand fitting the Value or Bluff range.
    Uses a max-attempt fallback to completely prevent RecursionErrors.
    """
    # Preflop bypass: If there is no board, we cannot evaluate a 5-card hand.
    if len(board) < 3:
        return random.sample(available_deck, 2)
        
    # Try up to 50 times to find a hand that matches the required strength
    for _ in range(50):
        opp_hand = random.sample(available_deck, 2)
        score = evaluator.evaluate(board, opp_hand)
        rank_class = evaluator.get_rank_class(score)
        
        # Classes 1-6 (Straight to Straight Flush) and top pairs are "Value"
        is_strong = rank_class <= 7 
        
        if is_value and is_strong:
            return opp_hand
        if not is_value and not is_strong:
            return opp_hand
            
    # Fallback: If the board is extremely weird and we can't find a match in 50 tries, 
    # just return a random hand so the engine doesn't crash.
    return random.sample(available_deck, 2)

def calculate_true_equity_and_var(hero_hand: list[str], board: list[str], pot: float, call_amount: float, bluff_prob: float, simulations: int = 1000):
    hero_cards = format_cards(hero_hand)
    board_cards = format_cards(board)
    needed_community = 5 - len(board_cards)
    
    outcomes = []
    wins_value = 0
    wins_bluff = 0

    full_deck = Deck().cards
    dead_cards = set(hero_cards + board_cards)
    available_deck = [c for c in full_deck if c not in dead_cards]

    for _ in range(simulations):
        draw = random.sample(available_deck, needed_community)
        current_board = board_cards + draw
        
        # Determine if this universe is a bluff or value bet based on villain's bluff prob
        is_bluff_universe = random.random() < bluff_prob
        villain_cards = generate_range([c for c in available_deck if c not in draw], current_board, is_value=not is_bluff_universe)
        
        hero_score = evaluator.evaluate(current_board, hero_cards)
        villain_score = evaluator.evaluate(current_board, villain_cards)
        
        won = hero_score < villain_score
        tie = hero_score == villain_score
        
        if won:
            net_profit = pot
            if is_bluff_universe: wins_bluff += 1
            else: wins_value += 1
        elif tie:
            net_profit = (pot / 2) - (call_amount / 2)
            if is_bluff_universe: wins_bluff += 0.5
            else: wins_value += 0.5
        else:
            net_profit = -call_amount
            
        outcomes.append(net_profit)

    # Calculate VaR (Value at Risk)
    outcomes.sort()
    var_95 = outcomes[int(simulations * 0.05)]  # 5th percentile worst outcome
    var_99 = outcomes[int(simulations * 0.01)]  # 1st percentile worst outcome
    
    true_equity = (wins_value + wins_bluff) / simulations
    ev = np.mean(outcomes)

    return {
        "true_equity": true_equity,
        "ev": ev,
        "var_95": var_95,
        "var_99": var_99
    }