# ♠️ Next-Gen Poker Risk & EV Engine

A terminal-based Texas Hold'em decision engine powered by Game Theory, Bayesian opponent modeling, Value at Risk (VaR) mathematics, and Fold Equity bluff detection. Backtested against 10,000+ real poker hand histories from the Pluribus AI and HandHQ cash game datasets.

---

## Table of Contents

- [Overview](#overview)
- [Engine v1.0: Core Math Stack](#engine-v10-core-math-stack)
- [Engine v2.0: Adaptive Bluff Risk & EMA Tracking](#engine-v20-adaptive-bluff-risk--ema-tracking)
- [Backtesting Methodology](#backtesting-methodology)
- [Benchmark Results: Engine v1.0](#benchmark-results-engine-v10)
- [Benchmark Results: Engine v2.0](#benchmark-results-engine-v20)
- [Final Verdict: v1.0 vs v2.0](#final-verdict-v10-vs-v20)
- [Limitations & Future Work](#limitations--future-work)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation & Usage](#installation--usage)

---

## Overview

Traditional poker calculators commit the **Bluff-Catcher Fallacy**: they assume a single, flat equity number against a uniform opponent range, inflating EV on weak hands and providing zero guidance on when to bluff. This engine solves both problems.

**Engine v1.0** introduces True Equity via Value/Bluff range decomposition, Monte Carlo VaR tail-risk modeling, and continuous Bayesian opponent persona tracking with stack-velocity tilt detection.

**Engine v2.0** extends v1.0 with a GTO-grounded **Bluff Risk Model** (Fold Equity arbitrage) and replaces cumulative-mean opponent tracking with **Exponential Moving Averages (EMA)** for 85% faster adaptation to real-time strategy shifts.

Both engines were validated against the [`gabbler/PokerData`](https://huggingface.co/datasets/gabbler/PokerData) dataset containing Pluribus (Facebook AI) game logs and HandHQ anonymized NLH cash game histories.

---

## Engine v1.0: Core Math Stack

### 1. True Equity Calculation (Value/Bluff Range Decomposition)

Standard equity calculators treat the opponent's range as a single uniform distribution $R$. This engine splits it into a **Value matrix** $R_{\text{val}}$ and a **Bluff matrix** $R_{\text{bluff}}$:

$$\text{EV}_{\text{True}} = P(\text{Fold}) \cdot \text{Pot} + P(\text{Call}) \left[ P_{\text{val}} \cdot \text{Eq}(H, R_{\text{val}}) + P_{\text{bluff}} \cdot \text{Eq}(H, R_{\text{bluff}}) \right] - \text{Cost}$$

Hands in the top 70th percentile of the villain's betting range are classified as $R_{\text{val}}$; lower percentiles are classified as $R_{\text{bluff}}$. This prevents artificially inflated EV when a villain happens to be bluffing with trash.

### 2. Value at Risk (VaR) via Monte Carlo Simulation

The engine runs **1,000-iteration Monte Carlo rollouts** to produce 95% and 99% confidence intervals for chip exposure:

- **$\text{VaR}_{0.95}$**: The 5th-percentile worst-case chip loss. Realized loss should exceed this bound in ≤ 5% of all calling decisions.
- **$\text{VaR}_{0.99}$**: The 1st-percentile tail-risk bound. Violation rate should be ≤ 1%.

### 3. Continuous Bayesian Persona Profiling

Instead of using static player categories (TAG, LAG, Fish), the engine maintains three **continuous indices** per opponent updated at every showdown:

| Index | Range | Meaning |
| --- | --- | --- |
| **Rationality** | 0.0 – 1.0 | How closely bets correlate with actual hand strength |
| **Bluff Index** | 0.0 – 1.0 | Frequency of aggressive plays with sub-par holdings |
| **Aggression** | 0.0 – 1.0 | Ratio of bets/raises to calls/checks |

### 4. Memory & Tilt Mechanics

The engine tracks **stack velocity** (bankroll rate-of-change). If an opponent loses ≥ 30% of their stack within ≤ 5 hands:

$$\text{Stack Loss Rate} = \frac{S_t - S_{t-k}}{S_{t-k}} \le -0.30 \quad \text{for } k \le 5$$

A tilt modifier inflates the opponent's bluff probability and reduces their rationality, modeling the well-documented psychological phenomenon of "loss-chasing" behavior.

---

## Engine v2.0: Adaptive Bluff Risk & EMA Tracking

### 5. Bluff Risk Model (Fold Equity Mathematics)

Engine v2.0 adds an entirely new decision dimension: **evaluating the mathematical viability of bluffing** before chips are committed.

**Break-Even Fold Equity** ($FE_{BE}$) — the minimum fold rate needed for a bluff to be profitable:

$$FE_{BE} = \frac{B}{P + B}$$

**Actual Fold Equity** ($AFE$) — estimated probability opponents fold, adjusted by Bayesian modeling:

$$AFE = \text{BaseFoldProb} \times \text{RationalityModifier} \times \text{BoardTextureModifier}$$

**Semi-Bluff EV Equation** — if called, Hero may still improve:

$$EV_{\text{bluff}} = (AFE \times P) + (1 - AFE) \left[ Eq \times (P + B) - (1 - Eq) \times B \right]$$

If $AFE > FE_{BE}$ and $EV_{\text{bluff}} > 0$, the bluff is flagged as **+EV**. Multi-way pots (≥ 3 opponents) are automatically suppressed due to exponential fold equity decay.

### 6. Exponential Moving Average (EMA) Opponent Tracking

Engine v1.0 uses cumulative showdown updates that suffer from **historical lag** — a player who tilts after 50 calm hands barely moves the average. Engine v2.0 replaces this with EMA:

$$\text{Index}_t = \alpha \cdot X_t + (1 - \alpha) \cdot \text{Index}_{t-1}$$

| Hyperparameter | Value | Effective Memory Window |
| --- | --- | --- |
| Default $\alpha$ | 0.20 | ~9 most recent hands |
| Tilt-boosted $\alpha$ | 0.45 – 0.50 | ~3–4 hands (activated on ≥ 25% stack drawdown) |

Older observations decay at rate $(1-\alpha)^k$, ensuring that ancient hand history cannot drown out a current gear-shift.

---

## Backtesting Methodology

Both engines were validated against real hand histories from the [`gabbler/PokerData`](https://huggingface.co/datasets/gabbler/PokerData) HuggingFace dataset using a **5-phase backtesting protocol**:

| Phase | What It Tests | Dataset Used | Key Metric |
| --- | --- | --- | --- |
| **Phase 1** | True Equity vs. Naive Equity | HandHQ 50NL (250 river showdowns) | Mean Squared Error (MSE) of EV prediction vs actual payoff |
| **Phase 2** | VaR tail-risk calibration | HandHQ 50NL (250 calling decisions) | Kupiec Coverage Test: empirical violation rates |
| **Phase 3** | Bayesian persona convergence speed | Pluribus AI (170 hands) + HandHQ | Convergence $N$ until $\Delta P_\theta < 0.02$ |
| **Phase 4** | Tilt detection accuracy | HandHQ (2,997 hands, 274 player timelines) | Post-trigger VPIP/PFR behavioral shift |
| **Phase 5** | `pokerkit` ↔ `treys` data bridge | All `.phh` files | Parsing success rate, card format conversion |

**v2.0 adds two additional benchmarks:**

| Test | What It Tests | Key Metric |
| --- | --- | --- |
| **Bluff Risk Validation** | Fold Equity arbitrage: does the model correctly separate +EV bluffs from -EV spew? | Realized EV lift per decision |
| **EMA vs Cumulative** | Adaptation speed to opponent gear-shifts and tilt | Number of hands to reflect a style change |

---

## Benchmark Results: Engine v1.0

> Detailed plots and raw data are in [`results/`](results/)

### Phase 1: True Equity vs Naive Equity

| Metric | Value |
| --- | --- |
| Naive EV MSE | **373.01** |
| True Equity EV MSE | **372.27** |
| MSE Reduction | **0.20%** |

The range-decomposed True Equity model produces marginally lower prediction error than naive uniform-range equity on 250 river showdown decisions.

### Phase 2: VaR Calibration (Kupiec Coverage Test)

| Confidence Level | Target Failure Rate | Empirical Violation Rate | Status |
| --- | --- | --- | --- |
| **95% VaR** | 5.0% (pass: 4.2% – 5.8%) | **1.60%** | Conservative (overly cautious) |
| **99% VaR** | 1.0% (pass: 0.6% – 1.4%) | **0.80%** | ✅ **PASSED** |

The 99% VaR is well-calibrated. The 95% VaR is overly conservative — it rarely underestimates risk, but it also restricts too many marginal +EV calls.

### Phase 3: Bayesian Persona Convergence

| Player Type | Convergence Hands ($N$) | Final Rationality | Final Bluff Index |
| --- | --- | --- | --- |
| **Pluribus (GTO AI)** | **15 hands** (Target: ≤ 30) ✅ | **1.00** | **0.10** |
| **Human Recreational** | — | **0.66** | **0.46** |

The engine correctly identifies Pluribus as a near-perfectly rational GTO player and recreational humans as lower-rationality, higher-bluff-frequency opponents.

### Phase 4: Memory & Tilt Trigger Detection

| Metric | Value |
| --- | --- |
| Tilt Triggers Identified (≥ 30% stack loss in ≤ 5 hands) | **97 events** |
| Post-Trigger VPIP Escalation | **+1.44%** |
| Post-Trigger PFR Change | **−0.41%** |
| Prediction Accuracy Lift ($\Delta LL$) | **+0.21** |

---

## Benchmark Results: Engine v2.0

> Detailed plots and raw data are in [`results_v2/`](results_v2/)

### Bluff Risk Model Validation

| Metric | Value |
| --- | --- |
| Total Bluff Scenarios Evaluated | **250** |
| Identified as +EV (Viable) | **38** (15.2%) |
| Flagged as −EV (Filtered) | **212** (84.8%) |
| Realized EV on +EV Bluffs | **+$4.49** |
| Realized EV on Filtered Bluffs | **$2.74** |
| **Decision Alpha Lift** | **+$1.76 per decision** |
| Opponent Fold Rate on +EV Spots | **31.6%** |
| Opponent Fold Rate on −EV Spots | **15.1%** |

### EMA Opponent Tracker vs Cumulative Average

| Metric | EMA Tracker (v2.0) | Cumulative Mean (v1.0) |
| --- | --- | --- |
| Adaptation Speed | **~4.2 hands** | ~28.5 hands |
| **Strategy Lag Reduction** | — | **85.3% slower** |
| Dynamic Tilt $\alpha$ Boost | $0.20 \to 0.45$ on ≥ 25% drawdown | N/A (fixed linear update) |

---

## Final Verdict: v1.0 vs v2.0

### ✅ Did v2.0 Improve Over v1.0? **Yes.**

Engine v2.0 delivers two concrete, measurable improvements:

**1. Offensive Decision-Making (Bluff Risk Model)**
Engine v1.0 is entirely **reactive** — it evaluates calling/folding EV but provides zero guidance on *when to bluff*. Engine v2.0 introduces a complete **offensive decision layer** using Fold Equity mathematics. Across 250 historical decision points, the model's +EV bluff recommendations yielded a **+$1.76 per-decision alpha lift** and correctly identified spots where opponents fold at **2× the base rate** (31.6% vs 15.1%). This is the single largest capability upgrade: the engine goes from a defensive calculator to a full-spectrum strategy advisor.

**2. Real-Time Opponent Adaptation (EMA Tracker)**
Engine v1.0's cumulative-mean opponent profiling is accurate over long sessions but **dangerously sluggish** during short-term strategy shifts. If a tight player goes on tilt after a bad beat, v1.0 requires ~28 additional hands to meaningfully adjust their profile. Engine v2.0's EMA tracker reflects the same shift in **~4.2 hands** (an 85% reduction in strategy lag), and its dynamic $\alpha$-boosting mechanism automatically accelerates learning when it detects large bankroll drawdowns.

### Where v1.0 Remains Strong

- **Core Equity & VaR Math**: The True Equity range-decomposition and Monte Carlo VaR simulation are shared between both engines and remain the foundation.
- **Bayesian Convergence**: The Pluribus benchmark (convergence at $N = 15$ hands, Rationality → 1.00) demonstrates solid profiling accuracy regardless of the tracking mechanism.
- **Simplicity**: Engine v1.0's `OpponentProfile` class is ~54 lines. Engine v2.0's `Opponent` class is ~130 lines. For educational or lightweight use-cases, v1.0 is easier to understand and modify.

---

## Limitations & Future Work

### Mathematical Limitations

1. **Marginal True Equity MSE Improvement (0.20%)**: The Value/Bluff range split produces only a tiny MSE reduction over naive equity on the tested dataset. This is likely because the 50NL HandHQ logs contain obfuscated cards (`????`) for most players, limiting the number of fully-revealed river showdowns available for calibration. A larger dataset with complete hole-card visibility (e.g., full Pluribus logs with all 6 players' cards revealed) would likely show a larger separation.

2. **Conservative 95% VaR (1.6% vs 5.0% target)**: The Monte Carlo simulator overestimates tail risk at the 95% level. This means the engine will occasionally advise folding on borderline +EV calls that a perfectly calibrated model would take. The variance scaling in `generate_range()` may need a wider sampling distribution.

3. **Board Texture Heuristic is Simplified**: The Bluff Risk Model's board-wetness penalty uses a simple suit-count rule (3-to-a-flush → 0.7× fold equity). It does not account for straight draws, paired boards, or dynamic textures that significantly alter fold equity in practice.

4. **Fold Equity Estimation is Not Observed**: The AFE (Actual Fold Equity) is a model-estimated probability derived from opponent rationality and VPIP, not a directly observed fold rate. Without a much larger sample of bluff → outcome pairs, the AFE predictions cannot be rigorously calibrated.

### System Limitations

1. **6-Max / Heads-Up Only**: The `treys` evaluator and the engine's equity calculator are designed for 2-card Texas Hold'em (NLHE). The WSOP Event #43 data (4-card Omaha / mixed games) could not be used for benchmarking.

2. **No Positional Awareness**: Neither engine factors in seat position (UTG, BTN, BB) when estimating ranges or fold equity. Position is one of the most significant variables in poker strategy.

3. **No Bet-Sizing Optimization**: The Bluff Risk Model evaluates a fixed half-pot bet sizing. A production-grade engine would optimize bet size as a continuous variable to maximize fold equity relative to risk.

4. **Offline-Only Profiling**: Opponent EMA trackers reset between sessions. Persistent cross-session databases would provide stronger priors on regular opponents.

### Future Work

- **Positional range weighting** for True Equity (UTG ranges vs. BTN ranges)
- **Continuous bet-size optimization** for bluff sizing (not just half-pot)
- **Multi-street bluff planning** (barreling: flop → turn → river continuation)
- **Observed fold-rate calibration** with a much larger labeled dataset
- **VaR recalibration** using variance-adjusted sampling or importance-weighted Monte Carlo

---

## Tech Stack

| Component | Technology |
| --- | --- |
| Language | Python 3.10+ |
| Card Evaluation | [Treys](https://github.com/msaindon/treys) (32-bit integer lookup) |
| Terminal UI | [Rich](https://github.com/Textualize/rich) |
| Statistical Processing | NumPy |
| Hand History Parsing | [PokerKit](https://github.com/uoftcprg/pokerkit) |
| Dataset | [gabbler/PokerData](https://huggingface.co/datasets/gabbler/PokerData) (HuggingFace) |
| Visualization | Matplotlib, Seaborn |

---

## Project Structure

```
poker-risk-engine/
├── main.py                    # Engine v1.0 CLI (True Equity + VaR + Persona Profiling)
├── main_v2.py                 # Engine v2.0 CLI (+ Bluff Risk + EMA Tracking)
│
├── engine/                    # Shared computation core
│   ├── equity_calculator.py   # True Equity & Monte Carlo VaR (1,000 sims)
│   ├── hand_evaluator.py      # Treys card evaluation & hand percentile scoring
│   └── session_tracker.py     # Post-game session reporting
│
├── models/                    # Engine v1.0 models
│   ├── opponent.py            # Cumulative Bayesian persona profiling
│   └── risk_manager.py        # Kelly Criterion decision engine
│
├── models_v2/                 # Engine v2.0 models
│   ├── opponent.py            # EMA-driven adaptive opponent tracking
│   └── risk_manager.py        # Bluff Risk Model + enhanced decision engine
│
├── results/                   # Engine v1.0 benchmark outputs
│   ├── benchmark_report.json  # Phase 1-4 metrics
│   ├── README.md              # v1.0 results summary
│   ├── phase1_ev_mse.png      # True Equity vs Naive MSE comparison
│   ├── phase2_var_calibration.png  # Kupiec VaR coverage test
│   ├── phase3_persona_convergence.png  # Pluribus vs Human profiling
│   └── phase4_tilt_dynamics.png  # Post-tilt behavioral shift analysis
│
├── results_v2/                # Engine v2.0 benchmark outputs
│   ├── benchmark_report.json  # Bluff Risk + EMA metrics
│   ├── README.md              # v2.0 results summary
│   ├── bluff_risk_ev_scatter.png  # Fold Equity arbitrage scatter
│   ├── bluff_recommendation_matrix.png  # Bluff classification distribution
│   └── ema_vs_cumulative_adaptation.png  # EMA vs cumulative tracking comparison
│
└── .gitignore
```

---

## Installation & Usage

### 1. Clone & Setup

```bash
git clone https://github.com/wrathrager/poker-risk-engine.git
cd poker-risk-engine
python3 -m venv venv
source venv/bin/activate
pip install treys numpy rich
```

### 2. Run Engine v1.0

```bash
python main.py
```

### 3. Run Engine v2.0 (with Bluff Risk + EMA Tracking)

```bash
python main_v2.py
```

### 4. Run Benchmarks (requires additional dependencies)

```bash
pip install datasets pokerkit matplotlib seaborn pandas huggingface-hub
python benchmark.py       # Engine v1.0 validation
python benchmark_v2.py    # Engine v2.0 validation
```

---
