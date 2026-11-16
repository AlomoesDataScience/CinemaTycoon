from cinema_tycoon.engine import Game
import cinema_tycoon.content as content

game = Game.new(seed=42)
theater = game.state.theaters[0]
theater.auto_schedule = True
theater.auto_stock = True

def run_month():
    if game.state.pending_event:
        choices = list(content.EVENTS[game.state.pending_event]["choices"].keys())
        game.choose_event(choices[-1])
    return game.advance()

for _ in range(60):
    try:
        report = run_month()
        print(f"Turn {game.state.turn}: Cash {game.state.cash}, Profit {report.get('profit', 0)}")
        if game.state.cash >= 60000:
            print("Reached 60k!")
            break
    except ValueError as e:
        print("Bankrupt at Turn", game.state.turn, e)
        break
