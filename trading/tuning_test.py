# tuning.py
import itertools
import pandas as pd
from trading_v3_backtest import run_single_game  # import your backtest runner

# -------------------------
# Hyperparameter ranges
# -------------------------
alphas = [0.1, 0.2, 0.3, 0.5, 1.0]
betas = [0.2, 0.5, 1.0]
exposures = [0.05, 0.1, 0.2, 0.3]  # fraction of capital to risk

results = []

# -------------------------
# Grid Search
# -------------------------
for alpha, beta, exposure in itertools.product(alphas, betas, exposures):
    print(f"Testing alpha={alpha}, beta={beta}, exposure={exposure}")
    res = run_single_game(
        "trading/example-game.json",
        alpha=alpha,
        beta=beta,
        capital_start=100_000,
        trailing_stop_pct=0.10,
    )
    results.append({
        "alpha": alpha,
        "beta": beta,
        "exposure": exposure,
        "final_value": res["final_value"],
        "pnl": res["pnl"],
        "max_drawdown": res["max_drawdown"],
        "sharpe": res["sharpe"],
        "num_trades": res["num_trades"],
    })

# -------------------------
# Save + Display Results
# -------------------------
df = pd.DataFrame(results)
df.to_csv("tuning_results.csv", index=False)

print("\nTop 10 configs by Sharpe ratio:")
print(df.sort_values(by="sharpe", ascending=False).head(10))

print("\nTop 10 configs by PnL:")
print(df.sort_values(by="pnl", ascending=False).head(10))
