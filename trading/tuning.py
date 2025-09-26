# single_tuning.py
import itertools
import pandas as pd
from trading_v3_backtest import run_single_game

alphas = [0.2, 0.5, 1.0, 2.0]
betas = [0.2, 0.5, 1.0, 2.0]

results = []

for alpha, beta in itertools.product(alphas, betas):
    print(f"Testing alpha={alpha}, beta={beta}")
    res = run_single_game("trading/example-game.json", alpha=alpha, beta=beta)
    results.append({
        "alpha": alpha,
        "beta": beta,
        "final_value": res["final_value"],
        "pnl": res["pnl"],
        "max_drawdown": res["max_drawdown"],
        "sharpe": res["sharpe"],
        "num_trades": res["num_trades"]
    })

df = pd.DataFrame(results)
df.to_csv("single_game_tuning.csv", index=False)
print(df)
