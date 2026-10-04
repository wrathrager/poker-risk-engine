def evaluate_bluff_opportunity(pot: float, proposed_bet: float, active_opponents: list, board_cards: list, hero_equity: float = 0.0) -> dict:
    """
    Calculates if a bluff is +EV based on Break-Even Fold Equity vs. Estimated Actual Fold Equity.
    """
    if not active_opponents:
        return {
            "fe_break_even": 0.0,
            "actual_fold_equity": 1.0,
            "bluff_ev": pot,
            "is_viable": True, 
            "advice": "No opponents. Take the pot."
        }

    # 1. Calculate Break-Even Fold Equity
    fe_break_even = proposed_bet / (pot + proposed_bet) if (pot + proposed_bet) > 0 else 0.0
    
    # 2. Estimate Board Texture (Wet vs Dry)
    # A simplified heuristic: more cards of same suit or connected ranks = wetter board = lower fold equity
    suits = [card[-1] for card in board_cards] if board_cards else []
    ranks = [card[0] for card in board_cards] if board_cards else []
    
    suit_counts = {s: suits.count(s) for s in set(suits)}
    max_suit = max(suit_counts.values()) if suit_counts else 0
    
    # Wet board penalty: 3 to a flush reduces fold equity significantly
    board_wetness_penalty = 1.0
    if max_suit >= 3:
        board_wetness_penalty = 0.7  # 30% reduction in fold equity
    elif max_suit == 2:
        board_wetness_penalty = 0.9
        
    # 3. Calculate Combined Actual Fold Equity (AFE) across all opponents
    combined_afe = 1.0
    
    for opp in active_opponents:
        # Extract dynamic stats (support both dict and Opponent objects)
        if isinstance(opp, dict):
            rationality = opp.get('rationality', 0.5)
            vpip = opp.get('vpip', 0.3)
        else:
            rationality = getattr(opp, 'rationality', 0.5)
            vpip = getattr(opp, 'vpip', 0.3)
        
        # Rational players fold more often to aggression when they miss.
        # Calling stations (High VPIP, low rationality) rarely fold.
        base_fold_prob = 0.5 + (rationality * 0.2) - (vpip * 0.3)
        
        # Floor/Ceil the probability
        opp_fold_prob = max(0.05, min(0.95, base_fold_prob * board_wetness_penalty))
        
        # To win the bluff, ALL opponents must fold (multiply probabilities)
        combined_afe *= opp_fold_prob

    # 4. Calculate Total Expected Value (EV) of the Bluff
    # EV = (Fold Prob * Pot) + (Call Prob * (EquityWin * TotalPot - EquityLoss * Bet))
    prob_called = 1.0 - combined_afe
    ev_if_called = (hero_equity * (pot + proposed_bet)) - ((1 - hero_equity) * proposed_bet)
    
    bluff_ev = (combined_afe * pot) + (prob_called * ev_if_called)
    
    # 5. Risk Assessment
    is_viable = bluff_ev > 0 and combined_afe > fe_break_even
    
    advice = "Fold/Check"
    if is_viable:
        if hero_equity > 0.2:
            advice = "High +EV Semi-Bluff"
        else:
            advice = "Profitable Pure Bluff"
            
    # Multi-way pots kill fold equity exponentially
    if len(active_opponents) >= 3:
        advice = "Extreme Risk: Multi-way bluff"
        is_viable = False

    return {
        "fe_break_even": fe_break_even,
        "actual_fold_equity": combined_afe,
        "bluff_ev": bluff_ev,
        "is_viable": is_viable,
        "advice": advice
    }

class DecisionEngine:
    @staticmethod
    def evaluate(equity_data: dict, call_amount: float, bankroll: float, bluff_data: dict = None):
        true_ev = equity_data["ev"]
        eq = equity_data["true_equity"]
        
        # Fractional Kelly based on true equity
        p = eq
        q = 1.0 - p
        b = abs(true_ev / call_amount) if call_amount > 0 else 1.0
        
        kelly_fraction = max(0.0, (b * p - q) / b) if b > 0 else 0.0
        risk_cap = bankroll * (kelly_fraction * 0.3) # 30% Kelly for safety

        action = "FOLD"
        if true_ev > 0:
            action = "CALL" if true_ev < call_amount * 1.5 else "RAISE"
        elif bluff_data and bluff_data.get("is_viable", False):
            action = "BLUFF / RAISE"

        return {
            "action": action,
            "ev": round(true_ev, 2),
            "equity_pct": round(eq * 100, 2),
            "var_95": round(equity_data["var_95"], 2),
            "var_99": round(equity_data["var_99"], 2),
            "risk_cap": round(risk_cap, 2),
            "bluff_advice": bluff_data["advice"] if bluff_data else "N/A"
        }
