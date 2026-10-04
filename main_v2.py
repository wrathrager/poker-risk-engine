import json
from datetime import datetime
from rich.console import Console
from rich.prompt import IntPrompt, Prompt, Confirm
from rich.table import Table
from treys import Deck, Card

# Engine V2 Imports
from engine.hand_evaluator import get_hand_percentile
from engine.equity_calculator import calculate_true_equity_and_var
from engine.session_tracker import SessionManager
from models_v2.opponent import OpponentTracker
from models_v2.risk_manager import DecisionEngine, evaluate_bluff_opportunity

console = Console()

# Persistent state across all hands in the session
opponent_trackers = {}

def format_cards(cards):
    """Safely handles both string lists and Treys integer lists."""
    if not cards: return []
    if isinstance(cards[0], int): return [Card.int_to_str(c) for c in cards]
    return cards

def initialize_table(player_names: list[str]):
    """Creates EMA trackers for each non-Hero opponent."""
    global opponent_trackers
    for name in player_names:
        if name != "Hero":
            opponent_trackers[name] = OpponentTracker(name=name, alpha=0.25)

def print_table_state(pot, players_state, board, street, sb_idx, bb_idx):
    table = Table(title=f"Table State: {street} (Engine v2.0 - Adaptive & Bluff Risk)", show_header=True, header_style="bold magenta")
    table.add_column("Player", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Stack", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Rationality (EMA)", style="blue")
    table.add_column("Bluff Index", style="red")
    table.add_column("In Pot", justify="right")
    
    for i, p in enumerate(players_state):
        role = "SB ($10)" if i == sb_idx else "BB ($20)" if i == bb_idx else ""
        status = "[red]Folded[/red]" if p['folded'] else "[bold green]Active[/bold green]"
        
        if p['is_hero']:
            rat_str, bluff_str = "Hero", "Hero"
        else:
            prof = opponent_trackers[p['name']].get_profile()
            tilt_flag = " [bold red](TILT)[/bold red]" if prof['is_on_tilt'] else ""
            rat_str = f"{prof['rationality']:.2f}"
            bluff_str = f"{prof['bluff_index']:.2f}{tilt_flag}"
            
        table.add_row(p['name'], role, f"${p['stack']:.1f}", status, rat_str, bluff_str, f"${p['current_contribution']:.1f}")
        
    console.print(table)
    console.print(f"Total Pot: [bold green]${pot:.1f}[/bold green]")
    if board:
        console.print(f"Board: [bold cyan]{board}[/bold cyan]\n")
    else:
        console.print("\n")

def hero_decision_advisor(pot: float, call_amount: float, active_players: list, board: list, hero_cards: list, hero_stack: float):
    """
    Evaluates EV for Calling/Folding AND runs the Bluff Risk Model for Hero.
    """
    active_opponents_profiles = [
        opponent_trackers[p['name']].get_profile()
        for p in active_players if p['name'] != 'Hero' and not p['folded']
    ]
    
    avg_bluff_prob = (
        sum(p['bluff_frequency'] for p in active_opponents_profiles) / len(active_opponents_profiles)
        if active_opponents_profiles else 0.30
    )
    
    # 1. True Equity & VaR
    eq_results = calculate_true_equity_and_var(
        hero_hand=hero_cards,
        board=board,
        pot=pot,
        call_amount=call_amount,
        bluff_prob=avg_bluff_prob,
        simulations=500
    )
    hero_equity = eq_results['true_equity']

    # 2. Evaluate Bluff Opportunity (Half-Pot Bet heuristic)
    proposed_bluff_size = pot * 0.5 if pot > 0 else 20.0
    bluff_data = evaluate_bluff_opportunity(
        pot=pot,
        proposed_bet=proposed_bluff_size,
        active_opponents=active_opponents_profiles,
        board_cards=board,
        hero_equity=hero_equity
    )

    metrics = DecisionEngine.evaluate(eq_results, call_amount, hero_stack, bluff_data=bluff_data)

    # 3. Display Rich Tactical Panel
    table = Table(title="🤖 Risk & Strategy Decision Advisor (v2)", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold yellow")
    
    table.add_row("True Equity", f"{hero_equity * 100:.1f}%")
    table.add_row("Call EV", f"${eq_results['ev']:.2f}")
    table.add_row("95% VaR (Worst Case)", f"[red]${eq_results['var_95']:.2f}[/red]")
    table.add_row("99% VaR (Tail Risk)", f"[red]${eq_results['var_99']:.2f}[/red]")
    table.add_row("Max Safe Call (30% Kelly)", f"${metrics['risk_cap']:.2f}")
    table.add_row("---", "---")
    table.add_row("Proposed Bluff Bet (Half-Pot)", f"${proposed_bluff_size:.2f}")
    table.add_row("Break-Even Fold Equity (FE_BE)", f"{bluff_data['fe_break_even'] * 100:.1f}%")
    table.add_row("Actual Est. Fold Equity (AFE)", f"{bluff_data['actual_fold_equity'] * 100:.1f}%")
    table.add_row("Bluff EV", f"${bluff_data['bluff_ev']:.2f}")
    
    bluff_rec_str = f"[bold green]{bluff_data['advice']}[/bold green]" if bluff_data['is_viable'] else "[bold red]Negative EV Bluff[/bold red]"
    table.add_row("Bluff Recommendation", bluff_rec_str)
    table.add_row("Engine Final Advice", f"[bold underline cyan]{metrics['action']}[/bold underline cyan]")

    console.print(table)
    
    return {
        "call_ev": eq_results['ev'],
        "hero_equity": hero_equity,
        "bluff_viable": bluff_data['is_viable'],
        "bluff_data": bluff_data,
        "metrics": metrics
    }

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
            
            hero_decision_advisor(
                pot=pot,
                call_amount=call_amount,
                active_players=players_state,
                board=engine_kwargs['board'],
                hero_cards=engine_kwargs['hero_cards'],
                hero_stack=p['stack']
            )
            
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
            
            # Record action into opponent EMA tracker
            opponent_trackers[p['name']].record_action(
                action_type=action,
                street=street,
                is_vpip=(action in ['call', 'raise', 'bet'])
            )
            
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

def end_of_hand_update(players_state: list, starting_stacks: dict, hand_showdown_results: dict = None):
    """
    Called at the end of every hand to run EMA updates on all opponents.
    """
    for p in players_state:
        name = p['name']
        if name == 'Hero':
            continue
            
        tracker = opponent_trackers[name]
        start_stack = starting_stacks[name]
        end_stack = p['stack']
        
        # Calculate stack change percentage for dynamic tilt acceleration
        stack_change_pct = (end_stack - start_stack) / start_stack if start_stack > 0 else 0.0
        
        vpip_this_hand = any(act[1] in ['call', 'raise', 'bet'] for act in p.get('street_actions', []))
        raised_this_hand = any(act[1] in ['raise', 'bet'] for act in p.get('street_actions', []))
        
        # Build post-hand observation payload
        showdown_data = {
            'voluntarily_played': vpip_this_hand,
            'aggressed': raised_this_hand,
            'stack_change_pct': stack_change_pct
        }
        
        if hand_showdown_results and name in hand_showdown_results:
            showdown_data['hand_percentile'] = hand_showdown_results[name]['percentile']
            
        # Execute EMA update
        tracker.update_after_hand(showdown_data)
        
        # Log active tilt warning if detected
        profile = tracker.get_profile()
        if profile['is_on_tilt']:
            console.print(f"[bold red]⚠️ TILT DETECTED: {name} lost {abs(stack_change_pct)*100:.1f}% stack. EMA learning rate boosted to {profile['alpha']}![/bold red]")

def play_hand(hand_num: int, players_state: list[dict], session: SessionManager, dealer_offset: int, is_manual: bool):
    console.print(f"\n[bold magenta]==================== HAND {hand_num} ====================[/bold magenta]")
    deck = Deck()
    board = []
    
    total_players = len(players_state)
    sb_idx = (dealer_offset) % total_players
    bb_idx = (dealer_offset + 1) % total_players
    utg_idx = (dealer_offset + 2) % total_players
    
    starting_stacks = {p['name']: p['stack'] for p in players_state}
    
    for p in players_state:
        p['folded'] = False
        p['current_contribution'] = 0.0
        p['street_actions'] = []
            
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
        active_count = sum(1 for p in players_state if not p['folded'])
        if active_count <= 1:
            break
            
        if cards_to_draw > 0:
            if is_manual:
                new_cards = Prompt.ask(f"Enter {cards_to_draw} card(s) for the {street_name} (e.g. 7h 8c)").strip().split()
                board.extend(new_cards)
            else:
                board.extend(format_cards(deck.draw(cards_to_draw)))

        start_action_idx = utg_idx if street_name == "Preflop" else sb_idx
        print_table_state(pot, players_state, board, street_name, sb_idx, bb_idx)
        
        if hero_p['folded']:
            console.print(f"[dim]Your Hole Cards: {hero_cards} (FOLDED)[/dim]")
        else:
            console.print(f"Your Hole Cards: [bold cyan]{hero_cards}[/bold cyan]")
            
        pot = run_betting_round(
            street=street_name, 
            players_state=players_state, 
            start_idx=start_action_idx, 
            pot=pot, 
            engine_kwargs={'hero_cards': hero_cards, 'board': board}
        )

        for p in players_state:
            p['current_contribution'] = 0.0

    # Showdown
    active_players = [p for p in players_state if not p['folded']]
    showdown_results = {}
    
    if len(active_players) > 1:
        console.print("\n[bold green]--- SHOWDOWN ---[/bold green]")
        for villain in active_players:
            if not villain['is_hero']:
                raw_cards = Prompt.ask(f"Enter 2 hole cards for {villain['name']} (or press Enter to skip)", default="").strip()
                if raw_cards:
                    villain_cards = raw_cards.split()
                    if len(villain_cards) == 2 and len(board) >= 3:
                        pct = get_hand_percentile(board, villain_cards, simulations=300)
                        showdown_results[villain['name']] = {'percentile': pct}
                        
        winner_name = Prompt.ask("Who won the hand?", choices=[p['name'] for p in active_players])
        winner = next(p for p in active_players if p['name'] == winner_name)
        winner['stack'] += pot
    elif len(active_players) == 1:
        winner = active_players[0]
        winner['stack'] += pot
        console.print(f"\n[bold green]{winner['name']} wins ${pot:.1f} (all opponents folded)![/bold green]")

    end_of_hand_update(players_state, starting_stacks, showdown_results)

def main():
    console.print("[bold magenta]♠️ Next-Gen Poker Risk & EV Engine v2.0 (EMA + Bluff Risk Model)[/bold magenta]\n")
    mode = Prompt.ask("Select execution mode", choices=["1", "2"], default="1")
    is_manual = (mode == "2")
    
    player_names = ["Hero", "Villain_1", "Villain_2"]
    initialize_table(player_names)
    
    players_state = [
        {"name": "Hero", "is_hero": True, "stack": 1000.0, "folded": False, "current_contribution": 0.0, "street_actions": []},
        {"name": "Villain_1", "is_hero": False, "stack": 1000.0, "folded": False, "current_contribution": 0.0, "street_actions": []},
        {"name": "Villain_2", "is_hero": False, "stack": 1000.0, "folded": False, "current_contribution": 0.0, "street_actions": []},
    ]
    
    session = SessionManager()
    hand_num = 1
    
    while True:
        play_hand(hand_num, players_state, session, dealer_offset=(hand_num - 1), is_manual=is_manual)
        hand_num += 1
        if not Confirm.ask("\nPlay another hand?", default=True):
            break
            
    console.print("\n[bold green]Session completed. Thank you for using Poker Risk Engine v2.0![/bold green]")

if __name__ == "__main__":
    main()
