from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cinema_tycoon.content import FLAVORS, era_for
from cinema_tycoon.engine import Game
from cinema_tycoon.persistence import load_game, save_game, validate

ROOT = Path(__file__).resolve().parent.parent


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.new(seed=42)
        self.theater = self.game.state.theaters[0]

    def run_month(self, game=None):
        game = game or self.game
        if game.state.pending_event:
            import cinema_tycoon.content as content
            choices = list(content.EVENTS[game.state.pending_event]["choices"].keys())
            game.choose_event(choices[-1])
        return game.advance()

    def test_seed_reproduces_world_and_different_seed_changes_it(self):
        self.assertEqual(asdict(self.game.state), asdict(Game.new(seed=42).state))
        self.assertNotEqual(asdict(self.game.state), asdict(Game.new(seed=43).state))

    def test_invalid_setup(self):
        for args in ({"company": " "}, {"year": 1800}, {"month": 13}, {"max_settlements": 2}):
            with self.assertRaises(ValueError):
                Game.new(**args)

    def test_hour_rounding_and_short_loops(self):
        film = self.game.state.films[0]
        for minutes, hours, repeats in ((20, 1, 3), (45, 1, 1), (60, 1, 1), (61, 2, 1), (135, 3, 1)):
            film.minutes = minutes
            self.assertEqual((film.hours, film.repeats), (hours, repeats))

    def test_overlap_and_invalid_hours_rejected_without_mutation(self):
        film = self.game.state.films[0]
        film.minutes = 90
        self.game.schedule(self.theater.id, film.id, 18)
        before = self.theater.schedule.copy()
        for hour in (17, 18, 19, -1, 24):
            with self.assertRaises(ValueError):
                self.game.schedule(self.theater.id, film.id, hour)
            self.assertEqual(before, self.theater.schedule)
        self.game.schedule(self.theater.id, film.id, 20)

    def test_repeated_title_has_one_license(self):
        film = self.game.state.films[0]
        film.minutes = 60
        self.game.schedule(self.theater.id, film.id, 12)
        self.game.schedule(self.theater.id, film.id, 13)
        self.assertEqual(self.game.booking_cost(self.theater), film.license_fee)

    def test_short_loops_do_not_multiply_admissions(self):
        other = Game(deepcopy(self.game.state))
        for game, minutes in ((self.game, 20), (other, 60)):
            game.state.films[0].minutes = minutes
            game.schedule(self.theater.id, game.state.films[0].id, 18)
        a, b = self.game.advance(), other.advance()
        self.assertEqual(a["theaters"][0]["attendance"], b["theaters"][0]["attendance"])

    def test_automation_uses_no_hidden_quality(self):
        other = Game(deepcopy(self.game.state))
        for film in other.state.films:
            for key in film.variables:
                film.variables[key] = 0
        self.game.auto_program(self.theater.id)
        other.auto_program(self.theater.id)
        self.assertEqual(self.theater.schedule, other.state.theaters[0].schedule)
        validate(self.game.state)

    def test_failed_stock_purchase_leaves_state_unchanged(self):
        product = self.game.state.products[0]
        for quantity in (-1, 0, 1.5, 10001):
            before = asdict(self.game.state)
            with self.assertRaises(ValueError):
                self.game.buy_stock(self.theater.id, product.id, quantity)
            self.assertEqual(before, asdict(self.game.state))
        self.game.state.cash = 0
        with self.assertRaises(ValueError):
            self.game.buy_stock(self.theater.id, product.id, 1)
        self.assertFalse(self.theater.stock)

    def test_stock_charged_once_and_spoilage_without_audience(self):
        product = self.game.state.products[0]
        self.game.buy_stock(self.theater.id, product.id, 100)
        report = self.game.advance()
        self.assertEqual(self.theater.stock[product.id], 95)
        self.assertEqual(report["stock_purchases"], round(product.wholesale * 100, 2))
        self.assertEqual(report["revenue"], 0)
        self.assertAlmostEqual(report["closing_cash"], 65000 - report["operating_costs"] - report["stock_purchases"], 2)

    def test_automation_respects_budget_inventory_and_reserve(self):
        self.game.auto_program(self.theater.id)
        self.game.starter_targets(self.theater.id)
        self.theater.stock_budget = 600
        self.game.auto_restock(self.theater)
        self.assertLessEqual(65000 - self.game.state.cash, 600)
        before = self.game.state.cash
        self.game.auto_restock(self.theater)
        self.assertEqual(before, self.game.state.cash)
        self.theater.stock.clear()
        self.game.state.cash = 10000
        self.game.auto_restock(self.theater)
        self.assertFalse(self.theater.stock)

    def test_month_rollover_and_report_reconciles_capital(self):
        game = Game.new(year=1985, month=12)
        theater = game.state.theaters[0]
        game.auto_program(theater.id)
        game.renovate(theater.id)
        game.upgrade(theater.id)
        game.buy_stock(theater.id, game.state.products[0].id, 200)
        report = game.advance()
        self.assertEqual((game.state.year, game.state.month), (1986, 1))
        self.assertAlmostEqual(report["opening_cash"] + report["profit"] - report["capital"], report["closing_cash"], 2)
        self.assertGreater(report["capital"], 6500)
        validate(game.state)

    def test_event_branch_depends_on_choice(self):
        for choice, expected in (("sponsor", "festival_return"), ("decline", "")):
            game = Game.new()
            game.state.theaters[0].auto_schedule = True
            game.advance()
            self.assertEqual(game.state.pending_event, "festival")
            with self.assertRaises(ValueError):
                game.advance()
            game.choose_event(choice)
            for _ in range(3):
                game.advance()
            self.assertEqual(game.state.pending_event, expected)
            if expected:
                game.choose_event("host")
                self.assertEqual(game.state.event_demand, 0.18)
                game.advance()
                self.assertEqual(game.state.event_demand, 0)

    def test_expired_films_leave_schedule_and_catalogue(self):
        originals = {f.id for f in self.game.state.films}
        self.theater.auto_schedule = True
        for _ in range(4):
            self.run_month()
        self.assertFalse(originals & {f.id for f in self.game.available_films()})
        self.assertFalse(originals & set(self.theater.schedule.values()))
        validate(self.game.state)

    def test_concessions_have_all_flavors_and_new_arrivals(self):
        count = len(self.game.state.products)
        self.run_month()
        self.run_month()
        self.assertEqual(len(self.game.state.products), count + 1)
        for product in self.game.state.products:
            self.assertEqual(set(product.flavors), set(FLAVORS))

    def test_price_affects_demand_and_rejects_nonfinite_values(self):
        other = Game(deepcopy(self.game.state))
        for game in (self.game, other):
            game.auto_program(self.theater.id)
        other.set_price([self.theater.id], 20)
        a, b = self.game.advance(), other.advance()
        self.assertGreater(a["theaters"][0]["attendance"], b["theaters"][0]["attendance"])
        for price in (float("nan"), float("inf"), 0, 26):
            with self.assertRaises(ValueError):
                self.game.set_price([self.theater.id], price)

    def test_empty_theater_eventually_bankrupts_and_blocks_spending(self):
        while not self.game.state.bankrupt:
            self.run_month()
        self.assertLess(self.game.state.cash, 0)
        with self.assertRaises(ValueError):
            self.game.advance()
        with self.assertRaises(ValueError):
            self.game.buy_stock(self.theater.id, self.game.state.products[0].id, 1)
        validate(self.game.state)

    def test_expansion_is_transactional_and_creates_town_on_purchase(self):
        before = asdict(self.game.state)
        with self.assertRaises(ValueError):
            self.game.buy_theater()
        self.assertEqual(before, asdict(self.game.state))
        self.theater.auto_schedule = self.theater.auto_stock = True
        self.game.state.cash = 200000
        self.game.state.month_open_cash = 200000
        count = len(self.game.state.cities)
        cash = self.game.state.cash
        new = self.game.buy_theater(name="The Bijou")
        self.assertEqual(len(self.game.state.cities), count + 1)
        self.assertEqual(self.game.state.cash, round(cash - 145000, 2))
        self.game.set_price([self.theater.id, new.id], 9)
        self.assertTrue(all(t.ticket_price == 9 for t in self.game.state.theaters))
        report = self.run_month()
        self.assertEqual(len(report["theaters"]), 2)
        self.assertEqual(report["capital"], 145000)
        self.assertAlmostEqual(report["opening_cash"] + report["profit"] - report["capital"], report["closing_cash"], 2)

    def test_settlement_limit_and_existing_city_purchase(self):
        game = Game.new(max_settlements=3)
        self.assertEqual(len(game.state.cities), 3)
        with self.assertRaises(ValueError):
            game.buy_theater()
        game.state.cash = game.state.month_open_cash = 200000
        game.buy_theater(game.state.cities[0].id)
        self.assertEqual(len(game.state.cities), 3)
        self.assertEqual(len(game.state.theaters), 2)
        validate(game.state)

    def test_era_filters_are_consumed_by_generators(self):
        rules = replace(era_for(1985), allowed_genres=("Drama",), film_runtimes=(20,), product_types=(0,), max_equipment=0)
        with patch("cinema_tycoon.engine.era_for", return_value=rules), patch("cinema_tycoon.programming.era_for", return_value=rules):
            film = self.game.generate_film()
            self.assertEqual((film.genre, film.minutes), ("Drama", 20))
            self.assertTrue(self.game.generate_product().name.endswith("Popcorn"))
            with self.assertRaises(ValueError):
                self.game.upgrade(self.theater.id)

    def test_historical_date_changes_economic_costs(self):
        early, modern = Game.new(year=1932), Game.new(year=1985)
        self.assertLess(early.fixed_cost(early.state.theaters[0]), modern.fixed_cost(modern.state.theaters[0]))

    def test_save_load_preserves_future_randomness_and_pending_event(self):
        self.theater.auto_schedule = self.theater.auto_stock = True
        self.game.advance()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "save.json"
            save_game(self.game, path)
            loaded = load_game(path)
            self.assertEqual(asdict(self.game.state), asdict(loaded.state))
            for game in (self.game, loaded):
                game.choose_event("sponsor")
            for _ in range(6):
                for game in (self.game, loaded):
                    if game.state.pending_event:
                        game.choose_event("small")
                self.assertEqual(self.game.advance(), loaded.advance())
            self.assertEqual(asdict(self.game.state), asdict(loaded.state))

    def test_corrupt_saves_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "save.json"
            payloads = ["{", json.dumps({"version": 999}), "[]"]
            data = {"version": 1, "state": asdict(self.game.state)}
            for mutate in (
                lambda s: s.update(cash=float("nan")),
                lambda s: s["theaters"][0].update(schedule={"18": 999999}),
                lambda s: s["theaters"][0].update(stock={"999999": 20}),
                lambda s: s["theaters"][0].update(equipment=99),
                lambda s: s["films"][0].update(minutes=0),
                lambda s: s.update(pending_event="unknown"),
                lambda s: s.update(last_report={"date": "1985-01"}),
            ):
                bad = deepcopy(data)
                mutate(bad["state"])
                payloads.append(json.dumps(bad))
            for payload in payloads:
                path.write_text(payload)
                with self.assertRaises(ValueError):
                    load_game(path)

    def test_year_long_simulation_survives_and_reconciles_every_month(self):
        self.game.state.cash += 50000
        self.game.state.month_open_cash += 50000
        self.theater.auto_schedule = self.theater.auto_stock = True
        for _ in range(12):
            report = self.run_month()
            self.assertAlmostEqual(report["opening_cash"] + report["profit"] - report["capital"], report["closing_cash"], 2)
            self.assertGreaterEqual(self.game.state.cash, 0)
            validate(self.game.state)


class ConsoleTests(unittest.TestCase):
    def test_full_console_path_and_load(self):
        commands = ["nonsense", "1", "Test Pictures", "1985", "1", "h", "1", "1",
                    "1", "u", "1", "b", "6", "7", "y", "1", "2", "2", "3", "b", "b", "b", "8", "y", "6", "1",
                    "9", "0", "2", "2", "7", "0", "4"]
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, "main.py", "--save-dir", temp], cwd=ROOT,
                input="\n".join(commands) + "\n", text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertNotIn("Could not complete", result.stdout)
            self.assertIn("MONTHLY STATEMENT", result.stdout)
            self.assertIn("Decision recorded", result.stdout)
            self.assertIn("See you at the pictures", result.stdout)
            loaded = load_game(Path(temp) / "manual.json")
            self.assertEqual(loaded.state.turn, 1)
            self.assertIn("festival_partner", loaded.state.flags)

    def test_eof_writes_recovery_save(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, "main.py", "--save-dir", temp], cwd=ROOT,
                input="1\nRecovery Pictures\n1985\n1\n", text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(load_game(Path(temp) / "recovery.json").state.company, "Recovery Pictures")

    def test_demo_command(self):
        result = subprocess.run([sys.executable, "main.py", "--demo", "2"], cwd=ROOT,
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Demo finished after 2 months", result.stdout)


if __name__ == "__main__":
    unittest.main()
