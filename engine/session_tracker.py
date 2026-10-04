from rich.console import Console
from rich.table import Table

class SessionManager:
    def __init__(self, starting_bankroll: float):
        self.starting_bankroll = starting_bankroll
        self.current_bankroll = starting_bankroll
        
        self.good_decisions = 0
        self.total_decisions = 0
        self.capital_saved = 0.0
        self.ev_generated = 0.0
        self.risk_breaches = 0

    def log_decision(self, net_ev: float, action_taken: str, suggested_action: str, bet_amount: float, max_cap: float):
        self.total_decisions += 1
        
        if action_taken == suggested_action:
            self.good_decisions += 1
            if action_taken == "FOLD" and net_ev < 0:
                self.capital_saved += bet_amount  # Saved money by not calling a -EV bet
            elif action_taken == "CALL":
                self.ev_generated += net_ev

        if action_taken == "CALL" and bet_amount > max_cap:
            self.risk_breaches += 1

    def generate_report(self):
        console = Console()
        table = Table(title="Post-Game Session Report", style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        accuracy = (self.good_decisions / self.total_decisions) * 100 if self.total_decisions else 0

        table.add_row("Total Hands Played", str(self.total_decisions))
        table.add_row("Engine Alignment (Good Decisions)", f"{accuracy:.1f}%")
        table.add_row("Capital Saved via Correct Folds", f"${self.capital_saved:.2f}")
        table.add_row("Theoretical EV Generated", f"${self.ev_generated:.2f}")
        table.add_row("Bankroll Risk Breaches", str(self.risk_breaches))
        
        console.print("\n")
        console.print(table)