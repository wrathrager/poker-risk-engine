import json
from datetime import datetime
from rich.console import Console
from rich.prompt import IntPrompt, Prompt, Confirm
from rich.table import Table
from treys import Deck, Card

# Local Engine Imports
from engine.hand_evaluator import get_hand_percentile
from engine.equity_calculator import calculate_true_equity_and_var
from engine.session_tracker import SessionManager
from models.opponent import OpponentProfile
from models.risk_manager import DecisionEngine

console = Console()

def format_cards(cards):
    """Safely handles both string lists and Treys integer lists."""
    if not cards: return []
    if isinstance(cards[0], int): return [Card.int_to_str(c) for c in cards]
    return cards

def print_table_state(pot, players_state, board, street, sb_idx, bb_idx):
    table = Table(title=f"Table State: {street}", show_header=True, header_style="bold magenta")
    table.add_column("Player", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Stack", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("In Pot This Round", justify="right")
    
    for i, p in enumerate(players_state):
        role = "SB ($10)" if i == sb_idx else "BB ($20)" if i == bb_idx else ""
        status = "[red]Folded[/red]" if p['folded'] else "[bold green]Active[/bold green]"
        table.add_row(p['name'], role, f"${p['stack']:.1f}", status, f"${p['current_contribution']:.1f}")
        
    console.print(table)
    console.print(f"Total Pot: [bold green]${pot:.1f}[/bold green]")
    if board:
        console.print(f"Board: [bold cyan]{board}[/bold cyan]\n")
    else:
        console.print("\n")

def run_betting_round(street, players_state, start_idx, pot, engine_kwargs):
    active_count = sum(1 for p in players_state if not p['folded'])
    if active_count <= 1:
        return pot

    current_max_bet = max((p['current_contribution'] for p in players_state), default=0.0)
    players_acted = set()
    total_players = len(players_state)
    idx = start_idx
    
    while True:
        active_unfolded = [p for p in players_state if not p['folded']]
        if len(active_unfolded) <= 1:
            break
            
        all_matched = all(p['current_contribution'] == current_max_bet for p in active_unfolded)
        all_acted = len(players_acted) >= len(active_unfolded)
        if all_acted and all_matched:
            break
                
        p_idx = idx % total_players
        p = players_state[p_idx]
        
        if p['folded'] or p['stack'] <= 0:
            idx += 1
            continue

        call_amount = current_max_bet - p['current_contribution']
        can_check = (call_amount == 0)
        choices = ["check", "bet"] if can_check else ["fold", "call", "raise"]

        if p['is_hero']:
            console.print(f"\n[bold yellow]--- YOUR TURN ({street}) ---[/bold yellow]")
            console.print(f"To Call: ${call_amount:.1f} | Current Stack: ${p['stack']:.1f}")
            
            if call_amount > 0 or current_max_bet > 0:
                # Calculate dynamic bluff probability based on who is still in the hand and the bet size
                active_opponents = [opp for opp in active_unfolded if not opp['is_hero']]
                if active_opponents:
                    avg_bluff = sum(opp['profile'].compute_live_bluff_prob(current_max_bet, pot) for opp in active_opponents) / len(active_opponents)
                else:
                    avg_bluff = 0.20

                # Run Next-Gen True Equity and VaR Engine
                console.print("[dim]Simulating True Equity vs Bluff & Value Ranges...[/dim]")
                equity_data = calculate_true_equity_and_var(
                    hero_hand=engine_kwargs['hero_cards'], 
                    board=engine_kwargs['board'], 
                    pot=pot, 
                    call_amount=call_amount, 
                    bluff_prob=avg_bluff, 
                    simulations=1000
                )
                
                metrics = DecisionEngine.evaluate(equity_data, call_amount, p['stack'])
                
                console.print(f"True Equity: {metrics['equity_pct']}% | Estimated EV: ${metrics['ev']}")
                console.print(f"Risk Profile -> 95% Confidence VaR: [red]${metrics['var_95']}[/red] | 99% VaR: [red]${metrics['var_99']}[/red]")
                console.print(f"Engine Advice: [bold underline]{metrics['action']}[/bold underline] | Max Safe Call (30% Kelly): ${metrics['risk_cap']}")
            
            action = Prompt.ask("Your action?", choices=choices).lower()
            p['street_actions'].append((street, action, call_amount))

            if action == "fold":
                p['folded'] = True
            elif action in ["call", "check"]:
                actual_call = min(call_amount, p['stack'])
                p['stack'] -= actual_call
                p['current_contribution'] += actual_call
                pot += actual_call
            elif action in ["raise", "bet"]:
                min_raise = current_max_bet + 20.0
                raise_total = float(Prompt.ask(f"Enter total bet amount (minimum ${min_raise:.1f})", default=str(min_raise)))
                raise_total = min(raise_total, p['stack'] + p['current_contribution'])
                added = raise_total - p['current_contribution']
                p['stack'] -= added
                p['current_contribution'] = raise_total
                pot += added
                current_max_bet = raise_total
                players_acted.clear()

        else:
            action = Prompt.ask(f"Action for {p['name']} (Facing ${call_amount:.1f})?", choices=choices).lower()
            p['street_actions'].append((street, action, call_amount))
            
            if action == "fold":
                p['folded'] = True
            elif action in ["call", "check"]:
                actual_call = min(call_amount, p['stack'])
                p['stack'] -= actual_call
                p['current_contribution'] += actual_call
                pot += actual_call
            elif action in ["raise", "bet"]:
                min_raise = current_max_bet + 20.0
                raise_total = float(Prompt.ask(f"Enter {p['name']}'s total bet (min ${min_raise:.1f})", default=str(min_raise)))
                raise_total = min(raise_total, p['stack'] + p['current_contribution'])
                added = raise_total - p['current_contribution']
                p['stack'] -= added
                p['current_contribution'] = raise_total
                pot += added
                current_max_bet = raise_total
                players_acted.clear()

        players_acted.add(p_idx)
        idx += 1
        
    return pot

def evaluate_showdown_continuous(villain_dict, board_cards):
    console.print(f"\n[cyan]Evaluating Rationality for {villain_dict['name']}...[/cyan]")
    raw_cards = Prompt.ask(f"Enter 2 hole cards for {villain_dict['name']} (e.g., Ah Kd)")
    villain_cards = raw_cards.strip().split()
    
    if len(villain_cards) == 2:
        hand_percentile = get_hand_percentile(board_cards, villain_cards, simulations=400)
        aggressively_played = any(a[1] in ['bet', 'raise'] for a in villain_dict['street_actions'])
        
        console.print(f"Mathematical Hand Percentile vs Board: [yellow]{hand_percentile * 100:.1f}%[/yellow]")
        villain_dict['profile'].update_at_showdown(hand_percentile, aggressively_played)
        
        prof = villain_dict['profile']
        console.print(f"Updated Persona -> Rationality: {prof.rationality_index:.2f} | Bluffing: {prof.bluff_index:.2f} | Aggression: {prof.aggression_index:.2f}")

def play_hand(hand_num: int, players_state: list[dict], session: SessionManager, dealer_offset: int, is_manual: bool):
    console.print(f"\n[bold magenta]==================== HAND {hand_num} ====================[/bold magenta]")
    deck = Deck()
    board = []
    
    total_players = len(players_state)
    sb_idx = (dealer_offset) % total_players
    bb_idx = (dealer_offset + 1) % total_players
    utg_idx = (dealer_offset + 2) % total_players
    
    for p in players_state:
        p['folded'] = False
        p['current_contribution'] = 0.0
        p['street_actions'] = []
        if not p['is_hero']: p['profile'].hands_played += 1
            
    hero_p = next(p for p in players_state if p['is_hero'])
    
    # Post Blinds
    sb_p, bb_p = players_state[sb_idx], players_state[bb_idx]
    sb_p['stack'] -= min(10.0, sb_p['stack'])
    sb_p['current_contribution'] = min(10.0, sb_p['stack'])
    bb_p['stack'] -= min(20.0, bb_p['stack'])
    bb_p['current_contribution'] = min(20.0, bb_p['stack'])
    pot = sb_p['current_contribution'] + bb_p['current_contribution']

    # Preflop Cards
    if is_manual:
        hero_cards = Prompt.ask("Enter your 2 Hole Cards (e.g., Ah Kd)").strip().split()
    else:
        hero_cards = format_cards(deck.draw(2))

    streets = [("Preflop", 0), ("Flop", 3), ("Turn", 1), ("River", 1)]
    
    for street_name, cards_to_draw in streets:
        if cards_to_draw > 0:
            if is_manual:
                board_input = Prompt.ask(f"Enter the {cards_to_draw} {street_name} card(s) (e.g., 2d 5c Jh)").strip().split()
                board.extend(board_input)
            else:
                board.extend(format_cards(deck.draw(cards_to_draw)))
                
        # CRITICAL FIX: Only reset contributions if we are past the Preflop stage.
        # Otherwise, the SB ($10) and BB ($20) get erased from the state tracker!
        if street_name != "Preflop":
            for p in players_state: p['current_contribution'] = 0.0
                
        print_table_state(pot, players_state, board, street_name, sb_idx, bb_idx)
        if not hero_p['folded']: console.print(f"Hero Cards: [bold yellow]{hero_cards}[/bold yellow]")

        start_idx = utg_idx if street_name == "Preflop" else sb_idx
        pot = run_betting_round(street_name, players_state, start_idx, pot, {'hero_cards': hero_cards, 'board': board})
        
        active = [p for p in players_state if not p['folded']]
        if len(active) == 1:
            console.print(f"\n[bold green]{active[0]['name']} wins ${pot:.1f} (Walkover)[/bold green]")
            active[0]['stack'] += pot
            return

    # Showdown
    active_at_showdown = [p for p in players_state if not p['folded']]
    console.print("\n[bold yellow]================ SHOWDOWN ================[/bold yellow]")
    
    winner_name = Prompt.ask("Who won the hand?", choices=[p['name'] for p in active_at_showdown])
    for p in active_at_showdown:
        if p['name'] == winner_name:
            p['stack'] += pot
            console.print(f"[bold green]Awarded ${pot:.1f} to {p['name']}.[/bold green]")

    for p in active_at_showdown:
        if not p['is_hero']: evaluate_showdown_continuous(p, board)
            
    # Track Bankroll Memory (For Tilt mechanics)
    for p in players_state:
        if not p['is_hero']:
            p['profile'].current_stack = p['stack']
            p['profile'].peak_stack = max(p['profile'].peak_stack, p['stack'])
def export_json(session: SessionManager, players_state: list[dict]):
    opponents = [p for p in players_state if not p['is_hero']]
    hero = next(p for p in players_state if p['is_hero'])
    data = {
        "timestamp": datetime.now().isoformat(),
        "final_hero_stack": hero['stack'],
        "opponent_profiles": [
            {
                "name": p['name'],
                "final_stack": p['stack'],
                "hands_played": p['profile'].hands_played,
                "vpip_prob": round(p['profile'].vpip_prob, 3),
                "aggression_factor": round(p['profile'].af, 2),
                "inferred_bluff_prior": round(p['profile'].prior_bluff, 3)
            } for p in opponents
        ]
    }
    filename = "poker_session_summary.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    console.print(f"\n[bold green]Complete multi-hand session data saved to {filename}[/bold green]")
if __name__ == "__main__":
    console.print("[bold green]Next-Gen Poker Risk & EV Engine[/bold green]")
    mode = Prompt.ask("Select Mode", choices=["1", "2"], default="1")
    is_manual = (mode == "2")
    
    if is_manual:
        console.print("[yellow]Manual Entry Mode: You will manually enter all cards dealt.[/yellow]")
    else:
        console.print("[cyan]Auto-Deal Simulation Mode: Engine will simulate cards automatically.[/cyan]")

    num_deals = IntPrompt.ask("Hands to play?", default=5)
    num_opponents = IntPrompt.ask("Opponents at table?", default=3)
    
    session = SessionManager(1000.0)
    players_state = [{'name': f"Player_{i+1}", 'profile': OpponentProfile(f"Player_{i+1}"), 'stack': 1000.0, 'folded': False, 'current_contribution': 0.0, 'street_actions': [], 'is_hero': False} for i in range(num_opponents)]
    players_state.append({'name': "HERO", 'profile': None, 'stack': 1000.0, 'folded': False, 'current_contribution': 0.0, 'street_actions': [], 'is_hero': True})
    
    for h in range(1, num_deals + 1):
        play_hand(h, players_state, session, dealer_offset=h-1, is_manual=is_manual)
        
    # JSON Export (omitted here, uses same logic as before)