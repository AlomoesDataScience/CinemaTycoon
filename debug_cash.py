from cinema_tycoon.engine import Game

game = Game.new()
print(f"Start cash: {game.state.cash}")
for _ in range(12):
    try:
        report = game.advance()
        print(f"Turn {game.state.turn}: Cash {game.state.cash}, Profit {report.get('profit', 0)}")
    except ValueError as e:
        print(e)
        break
