from copy import deepcopy
from dataclasses import asdict
import json
import math
from pathlib import Path
import tempfile
import unittest

from cinema_tycoon.content import MACHINES
from cinema_tycoon.engine import Game
from cinema_tycoon.persistence import SAVE_VERSION, load_game, save_game, validate


class ConcessionTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.new()
        self.theater = self.game.state.theaters[0]
        self.packaged = next(p for p in self.game.state.products if p.category == 'packaged' and p.deal == 'wholesale')
        self.kernel = next(p for p in self.game.state.products if p.category == 'kernels')
        self.syrup = next(p for p in self.game.state.products if p.category == 'syrup')
        self.topping = next(p for p in self.game.state.products if p.category == 'topping')
        self.vendor = next(p for p in self.game.state.products if p.deal == 'vendor')

    def buy(self, product, units):
        self.game.buy_stock(self.theater.id, product.id, units)

    def test_reserve_does_not_sell_and_display_movement_preserves_inventory(self):
        self.buy(self.packaged, 500)
        self.assertEqual(self.game.concession_sales(self.theater, 2000)['units'], 0)
        total = self.theater.stock[self.packaged.id]
        self.game.put_on_display(self.theater.id, self.packaged.id, 100)
        self.assertEqual(self.theater.stock[self.packaged.id] + self.theater.display[self.packaged.id], total)
        self.game.put_on_display(self.theater.id, self.packaged.id, 20)
        self.assertEqual(self.theater.stock[self.packaged.id], total - 20)
        before = asdict(self.theater)
        with self.assertRaises(ValueError):
            self.game.put_on_display(self.theater.id, self.packaged.id, 301)
        self.assertEqual(before, asdict(self.theater))
        self.assertLessEqual(self.game.concession_sales(self.theater, 2000)['units'], 20)

    def test_popcorn_requires_kernels_and_topping_and_never_overproduces(self):
        self.game.set_recipe(self.theater.id, self.kernel.id, self.topping.id, 1000)
        self.buy(self.kernel, 10)
        self.assertEqual(self.game.concession_sales(self.theater, 10000)['units'], 0)
        self.buy(self.topping, 1)
        before = self.theater.stock[self.kernel.id]
        report = self.game.concession_sales(self.theater, 10000)
        self.assertEqual(report['units'], self.topping.yield_per_unit)
        used = math.ceil(report['units'] / self.game.machine_yield(self.theater, self.kernel))
        self.assertEqual(report['items'][0]['inputs_used'], used)
        self.assertLess(self.theater.stock[self.kernel.id], before)
        self.assertEqual(self.theater.stock[self.topping.id], 0)
        self.assertEqual(report['supplies'], round(report['units'] * 0.18, 2))
        self.assertGreaterEqual(report['production_waste'], 0)

    def test_popcorn_limit_is_enforced(self):
        self.buy(self.kernel, 100)
        self.game.set_recipe(self.theater.id, self.kernel.id, 0, 25)
        self.assertEqual(self.game.concession_sales(self.theater, 100000)['units'], 25)

    def test_soda_requires_loading_consumes_stock_and_respects_tank_volume(self):
        self.buy(self.syrup, 30)
        self.assertEqual(self.game.concession_sales(self.theater, 2000)['units'], 0)
        before = asdict(self.theater)
        with self.assertRaises(ValueError):
            self.game.fill_tank(self.theater.id, self.syrup.id, 20)
        self.assertEqual(before, asdict(self.theater))
        before_units = self.theater.stock[self.syrup.id]
        self.game.fill_tank(self.theater.id, self.syrup.id, 2)
        portions = 2 * self.game.machine_yield(self.theater, self.syrup)
        self.assertEqual(self.theater.stock[self.syrup.id], before_units - 2)
        report = self.game.concession_sales(self.theater, 10000)
        self.assertEqual(report['units'], portions)
        self.assertEqual(self.theater.tanks[self.syrup.id], 0)
        self.assertEqual(report['supplies'], round(portions * 0.12, 2))

    def test_equipment_changes_yield_and_upkeep_without_minting_tank_stock(self):
        self.buy(self.syrup, 2)
        self.game.fill_tank(self.theater.id, self.syrup.id, 1)
        old_tank = self.theater.tanks.copy()
        old_yield = self.game.machine_yield(self.theater, self.syrup)
        old_fixed = self.game.fixed_cost(self.theater)
        self.game.install_concession_equipment(self.theater.id, 'soda', 'efficient')
        self.assertGreater(self.game.machine_yield(self.theater, self.syrup), old_yield)
        self.assertGreater(self.game.fixed_cost(self.theater), old_fixed)
        self.assertEqual(self.theater.tanks, old_tank)
        self.game.install_concession_equipment(self.theater.id, 'merchandiser')
        self.assertEqual(self.game.display_capacity(self.theater), 500)
        with self.assertRaises(ValueError):
            self.game.install_concession_equipment(self.theater.id, 'merchandiser')

    def test_higher_prices_reduce_demand(self):
        self.buy(self.packaged, 300)
        self.game.put_on_display(self.theater.id, self.packaged.id, 300)
        expensive = Game(deepcopy(self.game.state))
        expensive.set_concession_price(self.theater.id, self.packaged.id, self.packaged.retail * 3)
        affordable = self.game.concession_sales(self.theater, 500)['items'][0]
        costly = expensive.concession_sales(expensive.state.theaters[0], 500)['items'][0]
        self.assertGreater(affordable['demand'], costly['demand'])
        self.assertGreater(affordable['sold'], costly['sold'])
        self.assertAlmostEqual(costly['revenue'], costly['sold'] * costly['price'], 2)

    def test_vendor_contract_has_fixed_prices_commission_and_no_inventory_cost(self):
        before = self.game.state.cash
        self.game.sign_contract(self.theater.id, self.vendor.id)
        self.assertEqual(before, self.game.state.cash)
        with self.assertRaises(ValueError):
            self.game.set_concession_price(self.theater.id, self.vendor.id, 2)
        with self.assertRaises(ValueError):
            self.buy(self.vendor, 10)
        report = self.game.concession_sales(self.theater, 10000)
        row = report['items'][0]
        self.assertEqual(row['sold'], 200)
        self.assertEqual(row['revenue'], round(200 * self.vendor.retail * self.vendor.commission, 2))
        self.assertEqual(self.theater.stock, {})
        self.assertEqual(self.game.concession_sales(self.theater, 10000)['units'], 200)
        self.game.cancel_contract(self.theater.id, self.vendor.id)
        self.assertEqual(self.game.concession_sales(self.theater, 10000)['units'], 0)

    def test_automation_respects_monthly_limit_across_multiple_runs_and_saves(self):
        self.game.auto_program(self.theater.id)
        self.game.set_stock_target(self.theater.id, self.packaged.id, 1000, 100)
        self.theater.stock_budget = 100
        self.game.auto_restock(self.theater)
        spent = self.theater.automation_spent
        self.assertGreater(spent, 0)
        self.assertLessEqual(spent, 100)
        self.game.prepare_counter(self.theater)
        before = self.game.state.cash
        self.game.auto_restock(self.theater)
        self.assertEqual(before, self.game.state.cash)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'save.json'
            save_game(self.game, path)
            loaded = load_game(path)
            loaded.auto_restock(loaded.state.theaters[0])
            self.assertEqual(loaded.state.cash, before)
        self.theater.auto_stock = True
        self.game.advance()
        self.assertEqual(self.theater.automation_spent, 0)

    def test_cash_floor_and_invalid_targets_leave_state_unchanged(self):
        self.game.auto_program(self.theater.id)
        self.game.starter_targets(self.theater.id)
        self.theater.cash_reserve = self.game.state.cash
        self.game.auto_restock(self.theater)
        self.assertFalse(self.theater.stock)
        for product, reserve, display in ((self.vendor, 10, 10), (self.kernel, 10, 1), (self.packaged, 10000, 300)):
            before = asdict(self.theater)
            with self.assertRaises(ValueError):
                self.game.set_stock_target(self.theater.id, product.id, reserve, display)
            self.assertEqual(asdict(self.theater), before)

    def test_fill_gaps_keeps_manual_bookings_and_replacement_removes_all_conflicts(self):
        film, other = self.game.state.films[:2]
        film.minutes, other.minutes = 60, 150
        self.game.schedule(self.theater.id, film.id, 18)
        self.game.schedule(self.theater.id, film.id, 19)
        self.game.auto_program(self.theater.id, fill_only=True)
        self.assertEqual(self.theater.schedule[18], film.id)
        self.assertEqual(self.theater.schedule[19], film.id)
        self.game.schedule(self.theater.id, other.id, 18, replace=True)
        self.assertEqual(self.theater.schedule[18], other.id)
        self.assertNotIn(19, self.theater.schedule)
        self.assertNotIn(20, self.theater.schedule)
        validate(self.game.state)

    def test_full_counter_month_reconciles_and_save_reproduces_sales(self):
        self.game.auto_program(self.theater.id)
        self.game.starter_targets(self.theater.id)
        self.theater.stock_budget = 1500
        self.theater.auto_stock = self.theater.auto_prepare = True
        self.game.sign_contract(self.theater.id, self.vendor.id)
        self.game.install_concession_equipment(self.theater.id, 'popcorn', 'efficient')
        self.game.set_concession_price(self.theater.id, self.kernel.id, 6.25)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'save.json'
            save_game(self.game, path)
            loaded = load_game(path)
            report = self.game.advance()
            self.assertEqual(report, loaded.advance())
        self.assertAlmostEqual(report['opening_cash'] + report['profit'] - report['capital'], report['closing_cash'], 2)
        details = report['theaters'][0]['concession_detail']
        self.assertGreater(details['revenue'], 0)
        self.assertGreater(details['supplies'], 0)
        self.assertTrue({'vendor', 'popcorn', 'soda', 'packaged'} <= {row['kind'] for row in details['items']})
        validate(self.game.state)

    def test_invalid_saved_inventory_and_machine_references_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            for field, value in (('tanks', {self.packaged.id: 10}), ('kernel_id', self.packaged.id),
                                 ('display', {self.kernel.id: 10}), ('popcorn_machine', 'missing'),
                                 ('contracts', [self.packaged.id]), ('prices', {self.vendor.id: 4})):
                data = asdict(self.game.state)
                data['theaters'][0][field] = value
                path.write_text(json.dumps({'version': SAVE_VERSION, 'state': data}))
                with self.assertRaises(ValueError):
                    load_game(path)


if __name__ == '__main__':
    unittest.main()
