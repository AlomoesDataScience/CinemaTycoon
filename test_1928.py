from cinema_tycoon.engine import Game

# Start in 1928
game = Game.new(year=1928)
print("1928 Prices:")
print(f"Cash: {game.state.cash}")
print(f"Ticket Price: {game.state.theaters[0].ticket_price}")
print(f"Theater purchase: {game.property_price(game.state.cities[0].id)}")
print(f"Film budgets: {[f.production_budget for f in game.state.films]}")

# Start in 2020
game = Game.new(year=2020)
print("\n2020 Prices:")
print(f"Cash: {game.state.cash}")
print(f"Ticket Price: {game.state.theaters[0].ticket_price}")
print(f"Theater purchase: {game.property_price(game.state.cities[0].id)}")
print(f"Film budgets: {[f.production_budget for f in game.state.films]}")

