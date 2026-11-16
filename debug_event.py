from cinema_tycoon.models import State
from cinema_tycoon.engine import Game

game = Game.new()
game.advance()
print("Pending:", game.state.pending_event)
import cinema_tycoon.content as content
print("Event choices:", content.EVENTS.get(game.state.pending_event, {}).get("choices", {}).keys())
