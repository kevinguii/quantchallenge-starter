# trading_v3.py
import math
from enum import Enum
from typing import Optional, List

# Turn off for large runs
DEBUG = True

class Side(Enum):
    BUY = 0
    SELL = 1

class Ticker(Enum):
    TEAM_A = 0

def place_market_order(side: Side, ticker: Ticker, quantity: float) -> None:
    """
    In live/sandbox this will be provided by the platform.
    During local backtests the backtester will monkeypatch this function.
    Keep a lightweight debug print for local runs.
    """
    if DEBUG:
        print(f"Python Market order: {side.name} {ticker.name} {quantity} shares")
    # In sandbox this function should be provided; do not implement fills here.

def place_limit_order(side: Side, ticker: Ticker, quantity: float, price: float, ioc: bool = False) -> int:
    """Placeholder limit order (sandbox provides real implementation)."""
    if DEBUG:
        print(f"Place limit order: {side.name} {ticker.name} {quantity} @ {price} (IOC={ioc})")
    return 0

def cancel_order(ticker: Ticker, order_id: int) -> bool:
    """Placeholder cancel (sandbox provides real implementation)."""
    if DEBUG:
        print(f"Cancel order: {ticker.name} id={order_id}")
    return True

class Strategy:
    """
    Enhanced trading strategy:
    - score/time exponential weighting
    - scoring-run-differential momentum (last N scoring events)
    - capital-aware sizing with exposure cap (applies to short and long)
    - dynamic threshold (larger early, smaller late)
    """

    def reset_state(self) -> None:
        # Game state
        self.home_score = 0
        self.away_score = 0
        self.time_remaining = 2400.0  # seconds (default)
        # Position & capital (backtester will set bot.capital; keep defaults)
        self.position = 0
        # Timing control
        self.last_trade_time = -1.0
        # Market
        self.market_price = 50.0  # market-implied probability in 0..100 scale
        # Momentum trackers (scoring-run differential)
        self.recent_scoring_events: List[tuple] = []  # list of (home_or_away, points)
        # self.recent_max_events = 8  # length of run history to consider
        # Shooting efficiency (optional small effect)
        self.home_made_shots = 0
        self.home_attempts = 0
        self.away_made_shots = 0
        self.away_attempts = 0
        # # Risk controls / params (defaults; can be tuned by caller/backtester)
        # self.max_exposure_pct = 0.20  # max fraction of capital exposed to position
        # self.base_gap = 1.0           # base percentage gap (in price points) required vs market
        # self.min_gap = 0.5            # minimum gap late in game
        # self.cooldown_seconds = 3     # minimal seconds between trades to reduce overtrading

    def __init__(self,
                 alpha: float = 0.5,
                 beta: float = 0.5,
                 max_exposure_pct: float = 0.20,
                 base_gap: float = 1.0,
                 min_gap: float = 0.5,
                 recent_max_events: int = 8,
                 cooldown_seconds: int = 3):
        """
        Initialize strategy with hyperparameters.
        """
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.max_exposure_pct = float(max_exposure_pct)
        self.base_gap = float(base_gap)
        self.min_gap = float(min_gap)
        self.recent_max_events = int(recent_max_events)
        self.cooldown_seconds = int(cooldown_seconds)

        self.reset_state()

    # -------------------
    # Utility / helper
    # -------------------
    def update_scoring_run(self, home_away: str, points: int) -> None:
        """Append a scoring event and trim the history."""
        if home_away not in ("home", "away"):
            return
        self.recent_scoring_events.append((home_away, points))
        if len(self.recent_scoring_events) > self.recent_max_events:
            self.recent_scoring_events.pop(0)

    def scoring_run_differential(self) -> float:
        """
        Compute the net scoring run differential (home - away) over the recent window.
        Returns a small normalized value (e.g., -1..1-ish depending on runs).
        """
        if not self.recent_scoring_events:
            return 0.0
        net = 0
        for side, pts in self.recent_scoring_events:
            if side == "home":
                net += pts
            else:
                net -= pts
        # Normalize by max possible points in window (approx 3 points per scoring event)
        norm = max(1.0, len(self.recent_scoring_events) * 3.0)
        return float(net) / norm  # roughly in [-something, +something], usually small

    def compute_win_probability(self) -> float:
        """
        Combine:
          - score_diff weighted by time (exponential)
          - momentum: scoring-run differential
          - small efficiency factor from FG%
        Returns prob in [0,1] for home win.
        """
        score_diff = float(self.home_score - self.away_score)

        # time_factor: when time_remaining is small -> time_factor small, boosting score_diff importance
        # Use exponential decay to increase importance of score when little time remains
        time_decay = math.exp(-self.time_remaining / 600.0)  # range (0, ~1), larger when time small
        # base probability from score diff (scaled modestly)
        base_from_score = 0.5 + (0.04 * score_diff) * (1.0 + time_decay)

        # momentum from scoring runs (normalized)
        run_diff = self.scoring_run_differential()  # negative -> away running, positive -> home running
        momentum_factor = 0.5 + 0.2 * run_diff  # weight this modestly

        # small efficiency factor (optional, stabilizes model)
        home_eff = (self.home_made_shots / max(1, self.home_attempts))
        away_eff = (self.away_made_shots / max(1, self.away_attempts))
        eff_factor = 0.5 + 0.1 * (home_eff - away_eff)

        # Combine with weights alpha (score/time) and beta (momentum)
        # We'll incorporate eff_factor as a small correction
        weighted = (self.alpha * base_from_score + self.beta * momentum_factor + 0.5 * eff_factor) / (self.alpha + self.beta + 0.5)

        # ensure numeric stability
        win_prob = min(max(weighted, 0.01), 0.99)
        if DEBUG:
            print(f"[WinProb] time_rem={self.time_remaining:.1f} score_diff={score_diff} time_decay={time_decay:.3f} run_diff={run_diff:.3f} => prob={win_prob:.3f}")
        return win_prob

    def dynamic_gap_threshold(self) -> float:
        """
        Determine how big the gap between model probability and market price must be to trade.
        Logic: early in game -> require larger gap; late in game -> allow smaller gap.
        Output is in price points (market price is 0..100).
        """
        # time_factor in [0..1], 1 means early (full time), 0 means end
        time_factor = min(max(self.time_remaining / 2400.0, 0.0), 1.0)
        # threshold scales between (base_gap * (1 + time_factor)) and min_gap at end
        threshold = max(self.min_gap, self.base_gap * (1.0 + time_factor))
        # allow tiny threshold when very late (last 30s)
        if self.time_remaining < 30:
            threshold = max(self.min_gap * 0.25, threshold * 0.25)
        if DEBUG:
            print(f"[Gap] time_rem={self.time_remaining:.1f} threshold={threshold:.2f}")
        return threshold

    def compute_trade_size(self, win_prob: float, max_exposure_pct: Optional[float] = None) -> int:
        """
        Capital-aware sizing:
         - max_exposure_pct (fraction of capital allowed in position). If not provided, use self.max_exposure_pct.
         - size scales with edge = abs(win_prob - market_prob)
         - returns integer number of shares
        """
        if max_exposure_pct is None:
            max_exposure_pct = self.max_exposure_pct

        # market implied probability -> price in dollars for share
        market_prob = (self.market_price / 100.0)
        if self.market_price <= 0:
            return 0

        # edge: model minus market (signed); we use magnitude to size
        edge = win_prob - market_prob

        # maximum shares allowed by exposure
        capital = getattr(self, "capital", 100_000.0)
        price_per_share = self.market_price / 100.0
        max_shares_by_exposure = int((capital * max_exposure_pct) / max(1e-9, price_per_share))

        # scale by normalized edge: assume edge in [-0.5, 0.5] roughly; normalize by 0.5
        scale = min(1.0, max(0.0, abs(edge) / 0.5))
        target_shares = int(max_shares_by_exposure * scale)

        # impose minimum trade size to avoid micro trades
        min_trade = 10
        shares = max(0, target_shares)
        if 0 < shares < min_trade:
            shares = min_trade

        if DEBUG:
            print(f"[Size] capital={capital:.1f} price={price_per_share:.2f} max_by_exp={max_shares_by_exposure} edge={edge:.3f} scale={scale:.2f} -> shares={shares}")
        return shares

    def check_run_stop_loss(self) -> bool:
        """
        Stop-loss based on scoring-run differential going strongly against our position.
        If we are long and the away team has run differential strongly positive vs home, exit.
        If we are short and the home team has run differential strongly positive vs away, exit.
        """
        run_diff = self.scoring_run_differential()  # positive = home advantage
        # threshold for run shock (in normalized units); tuneable
        shock_threshold = 0.4

        if self.position > 0 and run_diff < -shock_threshold:
            if DEBUG:
                print(f"[Stop] Long stop-loss triggered: run_diff={run_diff:.3f}")
            return True
        if self.position < 0 and run_diff > shock_threshold:
            if DEBUG:
                print(f"[Stop] Short stop-loss triggered: run_diff={run_diff:.3f}")
            return True
        return False

    # ----------------------
    # Platform callbacks
    # ----------------------
    def on_trade_update(self, ticker: Ticker, side: Side, quantity: float, price: float) -> None:
        """Called when any trade occurs on the exchange (not necessarily ours)."""
        if DEBUG:
            print(f"Trade update: {ticker} {side.name} {quantity} @ {price}")

    def on_orderbook_update(self, ticker: Ticker, side: Side, quantity: float, price: float) -> None:
        """
        Update local market price. In live environment this may be called frequently.
        We set market_price to the provided price (assumes it is mid/indicative).
        """
        self.market_price = price

    def on_account_update(self, ticker: Ticker, side: Side, price: float, quantity: float, capital_remaining: float) -> None:
        """
        Called when one of our orders is filled. The backtester will call this or update via monkeypatch.
        Update position conservatively here if needed by platform semantics.
        """
        if side == Side.BUY:
            self.position += quantity
        else:
            self.position -= quantity
        # Update capital if platform provides it (we rely on backtester for that)

    def on_game_event_update(self,
                             event_type: str,
                             home_away: str,
                             home_score: int,
                             away_score: int,
                             player_name: Optional[str],
                             substituted_player_name: Optional[str],
                             shot_type: Optional[str],
                             assist_player: Optional[str],
                             rebound_type: Optional[str],
                             coordinate_x: Optional[float],
                             coordinate_y: Optional[float],
                             time_seconds: Optional[float]) -> None:
        """
        Main event handler called for every parsed event in the game feed.
        This function:
          - updates internal game state
          - updates momentum and efficiency counters
          - decides whether to place a market order
        """
        # Update game state
        self.home_score = int(home_score)
        self.away_score = int(away_score)
        if time_seconds is not None:
            self.time_remaining = float(time_seconds)

        # throttle to avoid spamming reacts on same second
        if self.last_trade_time is not None and self.last_trade_time >= 0:
            if abs(self.last_trade_time - self.time_remaining) < self.cooldown_seconds:
                return
        self.last_trade_time = self.time_remaining

        # ignore low-value events
        if event_type in ["NOTHING", "START_PERIOD", "END_PERIOD", "SUBSTITUTION", "UNKNOWN"]:
            return

        # --- update scoring / efficiency ---
        scored_points = 0
        if event_type == "SCORE":
            if shot_type == "FREE_THROW":
                scored_points = 1
            elif shot_type in ("TWO_POINT", "LAYUP", "DUNK"):
                scored_points = 2
            elif shot_type == "THREE_POINT":
                scored_points = 3

            if scored_points > 0 and home_away in ("home", "away"):
                self.update_scoring_run(home_away, scored_points)
                if home_away == "home":
                    self.home_made_shots += 1
                    self.home_attempts += 1
                else:
                    self.away_made_shots += 1
                    self.away_attempts += 1

        elif event_type == "MISSED":
            # attempt registered, no points
            if home_away == "home":
                self.home_attempts += 1
            elif home_away == "away":
                self.away_attempts += 1

        # compute model win probability
        win_prob = self.compute_win_probability()

        # dynamic threshold (in price points)
        gap = self.dynamic_gap_threshold()

        # trading decision logic
        market_price = float(self.market_price)  # 0..100
        model_price = win_prob * 100.0
        diff = model_price - market_price  # positive -> model favors home vs market

        # Stop-loss based on scoring-run shock
        if self.check_run_stop_loss() and self.position != 0:
            # close entire position aggressively
            if self.position > 0:
                place_market_order(Side.SELL, Ticker.TEAM_A, abs(self.position))
            else:
                place_market_order(Side.BUY, Ticker.TEAM_A, abs(self.position))
            self.position = 0
            if DEBUG:
                print("[Action] Run-based stop-loss executed, position closed.")
            return

        # Determine whether to trade and quantity
        # If model_price > market + gap => buy, if model_price < market - gap => sell (short)
        if diff > gap:
            # buy (go long)
            qty = self.compute_trade_size(win_prob)
            # enforce exposure: don't exceed max exposure in value
            capital = getattr(self, "capital", 100_000.0)
            price_per = max(0.01, market_price / 100.0)
            max_shares_allowed = int((capital * self.max_exposure_pct) / price_per)
            # limit qty to exposure left
            allowed_qty = max(0, max_shares_allowed - max(0, int(self.position)))
            qty = min(qty, allowed_qty)
            if qty > 0:
                place_market_order(Side.BUY, Ticker.TEAM_A, qty)
                # optimistic position update; backtester will reflect true fills via on_account_update / monkeypatch
                self.position += qty
                if DEBUG:
                    print(f"[Trade] BUY {qty} @ {market_price:.2f} | pos={self.position}")
            else:
                if DEBUG:
                    print("[Trade] BUY skipped due to exposure cap or zero qty.")
        elif diff < -gap:
            # sell / short
            qty = self.compute_trade_size(win_prob)
            capital = getattr(self, "capital", 100_000.0)
            price_per = max(0.01, market_price / 100.0)
            max_shares_allowed = int((capital * self.max_exposure_pct) / price_per)
            # allowed short qty = max_shares_allowed - abs(short position)
            allowed_qty_short = max(0, max_shares_allowed - max(0, -int(self.position)))
            qty = min(qty, allowed_qty_short)
            if qty > 0:
                place_market_order(Side.SELL, Ticker.TEAM_A, qty)
                self.position -= qty
                if DEBUG:
                    print(f"[Trade] SELL {qty} @ {market_price:.2f} | pos={self.position}")
            else:
                if DEBUG:
                    print("[Trade] SELL skipped due to exposure cap or zero qty.")
        else:
            # no trade
            if DEBUG:
                print(f"[NoTrade] diff={diff:.2f} gap={gap:.2f} (model={model_price:.2f} market={market_price:.2f})")

        # end of event processing

        # if end of game, reset
        if event_type == "END_GAME":
            if DEBUG:
                print("[Game] END_GAME - resetting state")
            self.reset_state()
