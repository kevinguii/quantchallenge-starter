import math
from enum import Enum
from typing import Optional

DEBUG = True

class Side(Enum):
    BUY = 0
    SELL = 1

class Ticker(Enum):
    TEAM_A = 0

def place_market_order(side: Side, ticker: Ticker, quantity: float) -> None:
    if DEBUG:
        print(f"Python Market order: {side.name} {ticker.name} {quantity} shares")

def place_limit_order(side: Side, ticker: Ticker, quantity: float, price: float, ioc: bool = False) -> int:
    return 0

def cancel_order(ticker: Ticker, order_id: int) -> bool:
    return True

class Strategy:
    """Risk-aware basketball trading strategy with schema-safe event handling."""

    def reset_state(self):
        self.home_score = 0
        self.away_score = 0
        self.time_remaining = 2400
        self.position = 0
        self.last_trade_time = -1
        self.market_price = 50
        # Momentum & efficiency
        self.home_made_shots = 0
        self.home_attempts = 0
        self.away_made_shots = 0
        self.away_attempts = 0
        self.recent_home_points = []
        self.recent_away_points = []
        
        

    def __init__(self,alpha = 0.5, beta = 0.5):
        self.alpha = alpha
        self.beta = beta
        self.reset_state()
    
    def on_trade_update(
        self, ticker: Ticker, side: Side, quantity: float, price: float
    ) -> None:

        if DEBUG:
            print(f"Python Trade update: {ticker} {side} {quantity} shares @ {price}")

    def on_orderbook_update(
        self, ticker: Ticker, side: Side, quantity: float, price: float
    ) -> None:
        self.market_price = price
    # ---------------------------
    # Helpers
    # ---------------------------
    def update_momentum(self, points_scored, home_away):
        if home_away == "home":
            self.recent_home_points.append(points_scored)
            if len(self.recent_home_points) > 5:
                self.recent_home_points.pop(0)
        elif home_away == "away":
            self.recent_away_points.append(points_scored)
            if len(self.recent_away_points) > 5:
                self.recent_away_points.pop(0)

    def compute_win_probability(self) -> float:
        score_diff = self.home_score - self.away_score
        time_factor = math.exp(-self.time_remaining / 600)  # exponential weighting
        base_prob = 0.5 + 0.05 * score_diff

        # Simple momentum/efficiency factor
        momentum_factor = 0.5 + 0.05 * (score_diff)  

        # Combine with weights
        win_prob = (
            self.alpha * (base_prob * (1 + time_factor)) +
            self.beta * momentum_factor
        ) / (self.alpha + self.beta)

        return min(max(win_prob, 0), 1)

    def compute_trade_size(self, win_prob, max_exposure_pct: float = 0.2):
        """
        Capital-aware sizing:
        - max_exposure_pct: fraction of capital allowed to be invested in this position (e.g., 0.2 = 20%)
        - position size is proportional to edge = |win_prob - market_prob|
        """
        # current market probability
        market_prob = self.market_price / 100.0
        edge = win_prob - market_prob

        # max shares allowed by exposure (capital * exposure) / price_per_share
        # price_per_share = market_price (dollars)
        if self.market_price <= 0:
            return 0
        max_shares_by_exposure = int((getattr(self, "capital", 100_000) * max_exposure_pct) / (self.market_price / 100.0))

        # scale by edge (edge range [-1,1], normalize by 0.5 maximum possible)
        scale = max(0.0, min(1.0, abs(edge) / 0.5))
        shares = int(max_shares_by_exposure * scale)

        # ensure at least 0
        return max(0, shares)


    def check_stop_loss(self):
        if len(self.recent_away_points) >= 3 and sum(self.recent_home_points[-3:]) <= 1:
            return True
        return False

    def on_account_update(
        self,
        ticker: Ticker,
        side: Side,
        price: float,
        quantity: float,
        capital_remaining: float,
    ) -> None:
        if side == Side.BUY:
            self.position += quantity
        else:
            self.position -= quantity

    # ---------------------------
    # Event handler
    # ---------------------------
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
                             time_seconds: Optional[float]):

        self.home_score = home_score
        self.away_score = away_score
        if time_seconds is not None:
            self.time_remaining = time_seconds

        # Throttle trading frequency
        if self.last_trade_time is not None and abs(self.last_trade_time - self.time_remaining) < 5:
            return
        self.last_trade_time = self.time_remaining

        # Skip ignorable events
        if event_type in ["NOTHING", "START_PERIOD", "END_PERIOD", "TIMEOUT", "SUBSTITUTION", "UNKNOWN"]:
            return

        # Handle scoring
        points = 0
        if event_type == "SCORE":
            if shot_type == "FREE_THROW":
                points = 1
            elif shot_type in ["TWO_POINT", "LAYUP", "DUNK"]:
                points = 2
            elif shot_type == "THREE_POINT":
                points = 3

            if points > 0 and home_away in ["home", "away"]:
                self.update_momentum(points, home_away)
                if home_away == "home":
                    self.home_made_shots += 1
                    self.home_attempts += 1
                elif home_away == "away":
                    self.away_made_shots += 1
                    self.away_attempts += 1

        # Handle misses
        if event_type == "MISSED":
            if home_away == "home":
                self.home_attempts += 1
            elif home_away == "away":
                self.away_attempts += 1

        # Efficiency not updated for BLOCK, STEAL, REBOUND, TURNOVER, FOUL, JUMP_BALL

        # Compute win probability
        win_prob = self.compute_win_probability()
        trade_qty = self.compute_trade_size(win_prob)

        # Stop-loss
        if self.check_stop_loss() and self.position > 0:
            place_market_order(Side.SELL, Ticker.TEAM_A, self.position)
            if DEBUG:
                print(f"Stop-loss triggered. Sold {self.position} shares.")
            self.position = 0
            return

        # Trading decisions
        if win_prob * 100 > self.market_price + 1:
            place_market_order(Side.BUY, Ticker.TEAM_A, trade_qty)
            self.position += trade_qty
            if DEBUG:
                print(f"BUY {trade_qty} shares. New position: {self.position}")
        elif win_prob * 100 < self.market_price - 1:
            place_market_order(Side.SELL, Ticker.TEAM_A, trade_qty)
            self.position -= trade_qty
            if DEBUG:
                print(f"SELL {trade_qty} shares. New position: {self.position}")

        if DEBUG:
            print(f"{event_type} | Score {home_score}-{away_score} | Position {self.position}")

        # Reset state at game end
        if event_type == "END_GAME":
            self.reset_state()