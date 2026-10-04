# ♠️ Next-Gen Poker Risk & EV Engine

A terminal-based Texas Hold'em decision engine powered by Game Theory, Bayesian opponent modeling, and Value at Risk (VaR) mathematics. 

Unlike traditional poker calculators that fall for the "Bluff-Catcher Fallacy" (assuming 100% equity when an opponent bluffs), this engine calculates **True Equity** by splitting opponent ranges into *Value* and *Bluff* matrices, and uses continuous behavioral indexing to track opponent tilt, rationality, and aggression.

## ✨ Key Features

* **True Equity Calculation:** Evaluates hand strength independently against perceived value ranges and bluff ranges to prevent artificially inflated expected value (EV) on weak hands.
* **Value at Risk (VaR):** Runs 1,000-simulation Monte Carlo rollouts to provide 95% and 99% confidence intervals for capital exposure, mapping worst-case scenarios before you call.
* **Continuous Persona Profiling:** Abandons static player types. Updates Opponent Rationality, Bluff, and Aggression indices dynamically at showdown based on mathematical hand percentiles.
* **Memory & Tilt Mechanics:** Tracks stack velocity. If an opponent loses 30% of their stack rapidly, the engine temporarily adjusts their parameters for "Fear" or "Tilt."
* **Dual-Mode Execution:**
  * **Auto-Deal Simulation:** AI deals all streets automatically for engine testing and statistical tuning.
  * **Manual Entry Mode:** Use the engine alongside a live game by manually entering known hole and community cards.

## 🛠️ Tech Stack

* **Python 3.10+**
* **[Treys](https://github.com/msaindon/treys):** High-speed 32-bit integer card evaluation.
* **[Rich](https://github.com/Textualize/rich):** Beautiful terminal UI, tables, and color formatting.
* **NumPy:** Statistical array processing for VaR endpoints.

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR-USERNAME/poker-risk-engine.git](https://github.com/YOUR-USERNAME/poker-risk-engine.git)
   cd poker-risk-engine

   sample run screenshots:
   <img width="718" height="787" alt="image" src="https://github.com/user-attachments/assets/6192dea1-91c3-420a-8637-bfd91ff0f412" />
   <img width="583" height="833" alt="image" src="https://github.com/user-attachments/assets/96d50fc6-8e59-477d-a690-ec71b6c8a7b1" />
   <img width="557" height="875" alt="image" src="https://github.com/user-attachments/assets/e96071a5-caed-49cc-9ce9-0235bf31ee97" />
   <img width="653" height="871" alt="image" src="https://github.com/user-attachments/assets/0a30e9d8-47c7-442b-a1fc-94215dbd873d" />
   <img width="583" height="840" alt="image" src="https://github.com/user-attachments/assets/9eb7fcc0-48e8-4988-a0f5-05dafe0b601b" />
   <img width="658" height="883" alt="image" src="https://github.com/user-attachments/assets/79fec11b-f25f-4260-bf09-8cb9f584054e" />
   <img width="653" height="887" alt="image" src="https://github.com/user-attachments/assets/f357e308-c949-4139-b53b-7d7bb704a6d0" />
   <img width="582" height="877" alt="image" src="https://github.com/user-attachments/assets/91632fce-296c-4e3f-92f3-26e4a4efd6fd" />
   <img width="655" height="773" alt="image" src="https://github.com/user-attachments/assets/c5b47572-12b7-4750-9db5-e6e3eece0515" />

   







