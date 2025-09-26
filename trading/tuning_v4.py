# multi_tuning.py
import itertools
import pandas as pd
from trading_v3_backtest import run_single_game

# Define hyperparameter search space
alphas = [0.2, 0.5, 1.0]
betas = [0.2, 0.5, 1.0]
exposures = [0.1, 0.2, 0.3]        # max capital exposure %
base_gaps = [0.5, 1.0, 2.0]        # base threshold in price points
recent_events = [5, 8, 12]         # scoring run lookback

results = []

for alpha, beta, exp, gap, runlen in itertools.product(alphas, betas, exposures, base_gaps, recent_events):
    print(f"Testing alpha={alpha}, beta={beta}, exp={exp}, base_gap={gap}, runlen={runlen}")
    res = run_single_game(
        "trading/example-game.json",
        alpha=alpha,
        beta=beta,
        capital_start=100_000,
    )
    results.append({
        "alpha": alpha,
        "beta": beta,
        "exposure": exp,
        "base_gap": gap,
        "recent_events": runlen,
        "final_value": res["final_value"],
        "pnl": res["pnl"],
        "max_drawdown": res["max_drawdown"],
        "sharpe": res["sharpe"],
        "num_trades": res["num_trades"]
    })

df = pd.DataFrame(results)
df.to_csv("multi_game_tuning.csv", index=False)
print(df.sort_values("pnl", ascending=False).head(10))
