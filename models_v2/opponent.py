import math

class Opponent:
    def __init__(self, name: str, alpha: float = 0.20):
        self.name = name
        self.base_alpha = alpha
        self.alpha = alpha  # Recency weight (higher = faster adaptation to gear shifts)
        
        # Core Behavioral Indices (Initialized to population midpoints)
        self.rationality = 0.50        # How logically their bets map to actual hand strength
        self.bluff_index = 0.20         # Propensity to aggressively bet sub-par hands
        self.aggression_index = 0.35    # Ratio of aggressive actions (bet/raise) to passive (call/check)
        self.vpip = 0.25                # Voluntarily Put In Pot percentage
        
        # Meta-state trackers
        self.hand_count = 0
        self.starting_stack = 0.0
        self.current_stack = 0.0
        self.is_on_tilt = False

    def _ema_update(self, current_val: float, observation: float) -> float:
        """
        Calculates the Exponential Moving Average:
        EMA_t = (alpha * Observation) + ((1 - alpha) * EMA_{t-1})
        """
        updated_val = (self.alpha * observation) + ((1.0 - self.alpha) * current_val)
        return max(0.01, min(0.99, updated_val))  # Keep within open bounds (0, 1)

    def record_action(self, action_type: str, street: str, is_vpip: bool = False):
        """
        Updates short-term action stats (Aggression & VPIP) per hand/street using EMA.
        """
        self.hand_count += 1
        
        # 1. Update Aggression Index (Bet/Raise = 1.0, Call/Check/Fold = 0.0)
        is_aggressive = 1.0 if action_type.lower() in ['bet', 'raise'] else 0.0
        self.aggression_index = self._ema_update(self.aggression_index, is_aggressive)

        # 2. Update Preflop VPIP on preflop actions
        if street.lower() == 'preflop':
            obs_vpip = 1.0 if is_vpip else 0.0
            self.vpip = self._ema_update(self.vpip, obs_vpip)

    def record_showdown(self, actual_hand_percentile: float, perceived_line_strength: float):
        """
        Updates Rationality and Bluff Index when cards are revealed at showdown.
        
        :param actual_hand_percentile: True strength of hand (0.0 = total trash, 1.0 = nut hand)
        :param perceived_line_strength: Betting line aggression score (0.0 = passive, 1.0 = massive bets)
        """
        # 1. Rationality Update: Deviation between true strength and bet line
        # Small deviation = rational play (1.0). Large deviation = erratic/unpredictable play (0.0)
        deviation = abs(actual_hand_percentile - perceived_line_strength)
        observed_rationality = max(0.0, 1.0 - (deviation * 1.5))
        self.rationality = self._ema_update(self.rationality, observed_rationality)

        # 2. Bluff Index Update: High aggression line with low actual percentile
        is_bluff_condition = perceived_line_strength > 0.60 and actual_hand_percentile < 0.40
        observed_bluff = 1.0 if is_bluff_condition else 0.0
        
        self.bluff_index = self._ema_update(self.bluff_index, observed_bluff)

    def adjust_for_tilt(self, stack_loss_ratio: float):
        """
        Dynamic Hyperparameter adjustment:
        If stack drops significantly (>25%), temporarily increase alpha to adapt faster
        to tilt-induced gear shifts.
        """
        if stack_loss_ratio > 0.25:
            # Increase alpha temporarily so recent tilt hands dominate history faster
            self.alpha = min(0.50, self.base_alpha * 2.0)
            self.is_on_tilt = True
        else:
            self.alpha = self.base_alpha  # Reset to baseline
            self.is_on_tilt = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "rationality": round(self.rationality, 3),
            "bluff_index": round(self.bluff_index, 3),
            "bluff_frequency": round(self.bluff_index, 3),
            "aggression_index": round(self.aggression_index, 3),
            "vpip": round(self.vpip, 3),
            "alpha": round(self.alpha, 2),
            "is_on_tilt": self.is_on_tilt
        }

    def get_profile(self) -> dict:
        return self.to_dict()

    def update_after_hand(self, showdown_data: dict):
        """
        Updates EMA trackers from end-of-hand summary.
        """
        self.hand_count += 1
        stack_change_pct = showdown_data.get('stack_change_pct', 0.0)
        
        # Check tilt adjustment
        if stack_change_pct < -0.25:
            self.adjust_for_tilt(abs(stack_change_pct))
        else:
            self.adjust_for_tilt(0.0)
            
        # VPIP update
        is_vpip = 1.0 if showdown_data.get('voluntarily_played', False) else 0.0
        self.vpip = self._ema_update(self.vpip, is_vpip)
        
        # Aggression update
        is_aggressed = 1.0 if showdown_data.get('aggressed', False) else 0.0
        self.aggression_index = self._ema_update(self.aggression_index, is_aggressed)
        
        # Showdown updates if available
        if 'hand_percentile' in showdown_data:
            pct = showdown_data['hand_percentile']
            perceived_line = 0.8 if is_aggressed else 0.3
            self.record_showdown(actual_hand_percentile=pct, perceived_line_strength=perceived_line)

    def compute_live_bluff_prob(self, bet_size: float, pot_size: float) -> float:
        bet_ratio = bet_size / max(pot_size, 1.0)
        tilt_mult = 1.5 if self.is_on_tilt else 1.0
        prob = self.bluff_index * tilt_mult * (1.0 + 0.5 * bet_ratio) * (self.aggression_index / 0.35)
        return min(0.95, max(0.05, prob))

# Alias for compatibility with main.py integration
OpponentTracker = Opponent
