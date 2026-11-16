from cinema_tycoon.engine import Game
import cinema_tycoon.content as content

game = Game.new(seed=42)
theater = game.state.theaters[0]
theater.auto_schedule = True
theater.auto_stock = True
theater.stock_budget = 50000
game.starter_targets(theater.id)

report = game.advance()
for tr in report['theaters']:
    print(tr['concession_detail'])
