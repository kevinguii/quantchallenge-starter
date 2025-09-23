"""
Quant Challenge 2025

Algorithmic strategy template
"""

import math
from enum import Enum
from typing import Optional

DEBUG = True

class Side(Enum):
    BUY = 0
    SELL = 1

class Ticker(Enum):
    # TEAM_A (home team)
    TEAM_A = 0

def place_market_order(side: Side, ticker: Ticker, quantity: float) -> None:
    """Place a market order.
    """
    if DEBUG:
        print(f"Python Market order: {side} {ticker} {quantity} shares")
    pass

def place_limit_order(side: Side, ticker: Ticker, quantity: float, price: float, ioc: bool = False) -> int:
    """Place a limit order.
    """
    return 0

def cancel_order(ticker: Ticker, order_id: int) -> bool:
    """Cancel an order.
    """
    return True

class Strategy:
    """Template for a strategy."""

    def reset_state(self) -> None:
        """Reset the state of the strategy to the start of game position.
        
        Since the sandbox execution can start mid-game, we recommend creating a
        function which can be called from __init__ and on_game_event_update (END_GAME).

        Note: In production execution, the game will start from the beginning
        and will not be replayed.
        """
        self.home_score = 0
        self.away_score = 0
        self.time_remaining = 2400 #default
        self.position = 0
        self.last_trade_time = -1
        self.market_price = 50

    def __init__(self) -> None:
        """Your initialization code goes here."""
        self.reset_state()

    def on_trade_update(
        self, ticker: Ticker, side: Side, quantity: float, price: float
    ) -> None:
        """Called whenever two orders match. Could be one of your orders, or two other people's orders.
        """
        if DEBUG:
            print(f"Python Trade update: {ticker} {side} {quantity} shares @ {price}")

    def on_orderbook_update(
        self, ticker: Ticker, side: Side, quantity: float, price: float
    ) -> None:
        """Called whenever the orderbook changes. This could be because of a trade, or because of a new order, or both.
        """
        self.market_price = price

    def on_account_update(
        self,
        ticker: Ticker,
        side: Side,
        price: float,
        quantity: float,
        capital_remaining: float,
    ) -> None:
        """Called whenever one of your orders is filled.
        """
        if side == Side.BUY:
            self.position += quantity
        else:
            self.position -= quantity
    
    def estimate_home_win_prob(self) -> float:
        """Estimate the probability of the home team winning based on current game state."""
        # Simple heuristic: if home team is leading, increase win probability
        if self.home_score > self.away_score:
            base_prob = 0.6
        elif self.home_score < self.away_score:
            base_prob = 0.4
        else:
            base_prob = 0.5
        
        # Adjust based on time remaining
        time_factor = self.time_remaining / 2400  # assuming a 40-minute game (2400 seconds)
        win_prob = base_prob * time_factor + (1 - time_factor) * 0.5
        if DEBUG:
            print(f"Time: {self.time_remaining}, Score: {self.home_score}-{self.away_score}, Prob: {win_prob:.2f}")
        
        return min(max(win_prob, 0), 1)  # Ensure probability is between 0 and 1

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
                           time_seconds: Optional[float]
        ) -> None:
        """Called whenever a basketball game event occurs.
        """

        self.home_score = home_score
        self.away_score = away_score
        if time_seconds is not None:
            self.time_remaining = time_seconds
        
        # Only act every ~10 seconds to avoid overreactions and overtrading
        if self.last_trade_time is not None and abs(self.last_trade_time - self.time_remaining) < 5:
            return
        
        self.last_trade_time = self.time_remaining

        if event_type in ["NOTHING", "START_PERIOD", "END_PERIOD"]:
            return
        
        win_prob = self.estimate_home_win_prob()
        if DEBUG:
            print(f"Estimated home win probability: {win_prob:.2f}")

        market_price = self.market_price
        trade_qty = 1000
        if win_prob * 100 > market_price + 1:
            place_market_order(Side.BUY, Ticker.TEAM_A, trade_qty)
            self.position += trade_qty
            if DEBUG:
                print(f"Placed BUY order for {trade_qty} shares. New position: {self.position}")
        elif win_prob * 100 < market_price - 1:
            place_market_order(Side.SELL, Ticker.TEAM_A, trade_qty)
            self.position -= trade_qty
            if DEBUG:
                print(f"Placed SELL order for {trade_qty} shares. New position: {self.position}")

        if DEBUG:
            print(f"{event_type} {home_score} - {away_score}")

        if event_type == "END_GAME":
            # IMPORTANT: Highly recommended to call reset_state() when the
            # game ends. See reset_state() for more details.
            self.reset_state()