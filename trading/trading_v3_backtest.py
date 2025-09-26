# single_backtest.py
import json
import math
import statistics
import importlib

# Change this if your strategy module is named differently
STRATEGY_MODULE = "trading_v4"

def max_drawdown(equity_curve):
    peak = -float("inf")
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd

def compute_sharpe(returns):
    if len(returns) < 2:
        return 0.0
    mean = statistics.mean(returns)
    stdev = statistics.stdev(returns)
    if stdev == 0:
        return 0.0
    return mean / stdev

def run_single_game(json_file, alpha=0.5, beta=0.5, capital_start=100_000, trailing_stop_pct=0.10):
    """
    Backtest a single game.
    """
    strategy_mod = importlib.import_module(STRATEGY_MODULE)
    Strategy = strategy_mod.Strategy
    Side = strategy_mod.Side
    Ticker = strategy_mod.Ticker

    bot = Strategy(alpha=alpha, beta=beta)
    bot.capital = capital_start
    bot.position = 0
    bot.avg_entry_price = 0
    bot.max_fav_price = 0
    bot.trades = []
    equity_curve = []

    # Monkeypatch market orders to simulate fills
    def place_market_order_local(side, ticker, quantity):
        qty = int(max(0, round(quantity)))
        price = bot.market_price
        if qty == 0:
            return
        if side == Side.BUY:
            bot.capital -= price * qty / 100.0
            bot.position += qty
        else:
            bot.capital += price * qty / 100.0
            bot.position -= qty

        # Update max favorable price for trailing stop
        if bot.position > 0:
            bot.max_fav_price = max(bot.max_fav_price, price)
        elif bot.position <= 0:
            bot.max_fav_price = price

        bot.trades.append({
            "time": getattr(bot, "time_remaining", None),
            "side": side.name,
            "qty": qty,
            "price": price,
            "capital": bot.capital,
            "position": bot.position
        })

    strategy_mod.place_market_order = place_market_order_local

    with open(json_file, "r") as f:
        events = json.load(f)

    for event in events:
        bot.on_game_event_update(
            event_type=event["event_type"],
            home_away=event["home_away"],
            home_score=event["home_score"],
            away_score=event["away_score"],
            player_name=event.get("player_name"),
            substituted_player_name=event.get("substituted_player_name"),
            shot_type=event.get("shot_type"),
            assist_player=event.get("assist_player"),
            rebound_type=event.get("rebound_type"),
            coordinate_x=event.get("coordinate_x"),
            coordinate_y=event.get("coordinate_y"),
            time_seconds=event.get("time_seconds")
        )

        # Trailing stop for long positions
        if bot.position > 0 and bot.max_fav_price > 0:
            if bot.market_price < bot.max_fav_price * (1 - trailing_stop_pct):
                place_market_order_local(Side.SELL, Ticker.TEAM_A, abs(bot.position))
                bot.avg_entry_price = 0
                bot.max_fav_price = bot.market_price
                print(f"Trailing stop triggered at price {bot.market_price}")

        # Record equity
        equity = bot.capital + bot.position * bot.market_price / 100.0
        equity_curve.append(equity)

    final_value = equity_curve[-1] if equity_curve else bot.capital
    returns = [equity_curve[i] - equity_curve[i-1] for i in range(1, len(equity_curve))] if len(equity_curve) >= 2 else []
    sharpe = compute_sharpe(returns)
    dd = max_drawdown(equity_curve)

    result = {
        "final_value": final_value,
        "pnl": final_value - capital_start,
        "max_drawdown": dd,
        "sharpe": sharpe,
        "num_trades": len(bot.trades),
        "trades": bot.trades,
        "equity_curve": equity_curve
    }
    return result

if __name__ == "__main__":
    res = run_single_game("trading/example-game.json", alpha=0.5, beta=0.5)
    print(f"Final Value: {res['final_value']:.2f}, PnL: {res['pnl']:.2f}, Max DD: {res['max_drawdown']:.2%}, Sharpe: {res['sharpe']:.2f}, Trades: {res['num_trades']}")
