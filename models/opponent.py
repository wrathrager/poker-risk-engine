class OpponentProfile:
    def __init__(self, name: str):
        self.name = name
        # Continuous Indices (0.0 to 1.0)
        self.bluff_index = 0.20
        self.rationality_index = 0.80
        self.aggression_index = 0.30 
        
        self.hands_played = 0
        self.peak_stack = 1000.0
        self.current_stack = 1000.0
        
    def get_tilt_modifier(self):
        """Calculates memory-based emotional state based on recent stack changes."""
        drawdown = (self.peak_stack - self.current_stack) / max(1.0, self.peak_stack)
        if drawdown > 0.40:
            return 1.5  # Heavy tilt/desperation (increases bluffing, reduces rationality)
        elif drawdown > 0.15:
            return 0.7  # Fear/Tightening up (reduces bluffing)
        return 1.0      # Baseline

    def compute_live_bluff_prob(self, bet_size: float, pot_size: float) -> float:
        bet_ratio = bet_size / max(pot_size, 1.0)
        tilt = self.get_tilt_modifier()
        
        # Heavy bets from players with high bluff indices on tilt = Very high bluff prob
        prob = self.bluff_index * tilt * (1.0 + 0.5 * bet_ratio) * self.aggression_index
        return min(0.95, max(0.05, prob))

    def update_at_showdown(self, hand_percentile: float, aggressively_played: bool):
        """
        hand_percentile: 0.0 (worst) to 1.0 (nuts).
        Updates indices based on mathematical rationality.
        """
        self.hands_played += 1
        
        if aggressively_played:
            if hand_percentile > 0.75:
                # Rational Value Bet
                self.rationality_index = min(1.0, self.rationality_index + 0.05)
                self.bluff_index = max(0.0, self.bluff_index - 0.02)
            elif hand_percentile > 0.50:
                # Thin Value / Semi-Bluff
                self.rationality_index = min(1.0, self.rationality_index + 0.01)
            else:
                # Pure Bluff / Spew
                self.bluff_index = min(1.0, self.bluff_index + 0.10)
                self.rationality_index = max(0.0, self.rationality_index - 0.08)
                self.aggression_index = min(1.0, self.aggression_index + 0.05)
        else:
            # Passive play with strong hand = Trapping/Rational
            # Passive play with weak hand = Normal folding/checking
            if hand_percentile > 0.85:
                self.rationality_index = min(1.0, self.rationality_index + 0.02)