class DecisionEngine:
    @staticmethod
    def evaluate(equity_data: dict, call_amount: float, bankroll: float):
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

        return {
            "action": action,
            "ev": round(true_ev, 2),
            "equity_pct": round(eq * 100, 2),
            "var_95": round(equity_data["var_95"], 2),
            "var_99": round(equity_data["var_99"], 2),
            "risk_cap": round(risk_cap, 2)
        }