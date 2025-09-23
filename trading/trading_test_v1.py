import json
from trading_v1 import Strategy

# Load your example game JSON
with open("trading/example-game.json", "r") as f:
    game_events = json.load(f)

# Instantiate your strategy
bot = Strategy()

# Feed each event to your bot
for event in game_events:
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
