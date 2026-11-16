"""Screen transitions, single-key workflows and save compatibility."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cinema_tycoon.cli import App, films_menu, scheduling_menu, stock_menu
from cinema_tycoon.engine import Game
from cinema_tycoon.persistence import SAVE_VERSION, load_game, save_game
from cinema_tycoon.terminal import yes_no

CLEAR = '\033[2J\033[H'


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.new()
        self.theater = self.game.state.theaters[0]

    def drive(self, action, keys, answers=()):
        output = io.StringIO()
        keys = iter(keys)
        seen = []
        def press(prompt):
            seen.append((prompt, output.getvalue().split(CLEAR)[-1]))
            return next(keys)
        with redirect_stdout(output), patch('cinema_tycoon.terminal.interactive_terminal', return_value=True), \
             patch('cinema_tycoon.terminal.read_key', side_effect=press), patch('builtins.input', side_effect=answers):
            action()
        return seen, output.getvalue()

    def test_add_selects_film_then_slot_and_rejects_non_yes_no(self):
        film = max(self.game.available_films(), key=lambda f: f.variables['production_budget'])
        original = self.game.state.films[-1]
        original.minutes = 60
        self.game.schedule(self.theater.id, original.id, 0)
        seen, _ = self.drive(lambda: scheduling_menu(self.game, self.theater), ['a', '1', '1', 'maybe', 'n', 'a', '1', '1', 'y', 'b'])
        self.assertIn('LARGEST BUDGET FIRST', seen[1][1])
        self.assertIn(film.title, seen[1][1])
        self.assertIn('CHOOSE TIME', seen[2][1])
        self.assertIn('REPLACE CONFLICTING', seen[3][1])
        self.assertIn('Choose Y, N', seen[4][1])
        self.assertIn('Original bookings kept', seen[5][1])
        self.assertEqual(self.theater.schedule[0], film.id)

    def test_remove_and_paged_choices_use_keys_not_ids(self):
        self.game.auto_program(self.theater.id)
        first = min(self.theater.schedule)
        self.drive(lambda: scheduling_menu(self.game, self.theater), ['r', '2', 'b'])
        self.assertNotIn(first, self.theater.schedule)
        seen, _ = self.drive(lambda: films_menu(self.game), ['n', '1', '', 'b'])
        self.assertIn('Page 2/2', seen[1][1])
        self.assertIn('Production observations', seen[2][1])

    def test_notes_wait_then_return_to_choices(self):
        seen, _ = self.drive(lambda: films_menu(self.game), ['1', '', 'b'])
        self.assertIn('Press Enter', seen[1][0])
        self.assertNotIn('DISTRIBUTION CATALOGUE', seen[1][1])
        self.assertIn('DISTRIBUTION CATALOGUE', seen[2][1])

    def test_monthly_report_remains_visible(self):
        self.game.auto_program(self.theater.id)
        self.game.advance()
        with tempfile.TemporaryDirectory() as temp:
            app = App(temp)
            app.game = self.game
            seen, _ = self.drive(app.play, ['7', '', '0', ''])
        self.assertIn('Press Enter', seen[1][0])
        self.assertIn('MONTHLY STATEMENT', seen[1][1])
        self.assertNotIn('SILVER SCREEN', seen[1][1])
        self.assertIn('SILVER SCREEN', seen[2][1])

    def test_buy_stock_then_display_with_buttons(self):
        seen, _ = self.drive(lambda: stock_menu(self.game, self.theater),
                            ['1', '1', 'y', '2', '1', 'b'], ['20', '10'])
        product = self.game.state.products[0]
        self.assertIn(product.producer, seen[1][1])
        self.assertIn('Stock delivered to reserve', seen[3][1])
        self.assertEqual(self.theater.stock[product.id], 10)
        self.assertEqual(self.theater.display[product.id], 10)

    def test_options_changes_only_selected_setting_and_new_game_uses_seed(self):
        with tempfile.TemporaryDirectory() as temp:
            app = App(temp)
            self.drive(app.options_menu, ['2', 'b'], ['1234'])
            self.assertEqual(app.options, {'autosave': True, 'seed': 1234, 'settlements': 250, 'time_format': '12h'})
            reloaded = App(temp)
            with patch.object(reloaded, 'play'), patch('builtins.input', side_effect=['Test', '1985', '1']), redirect_stdout(io.StringIO()):
                reloaded.new_game()
            self.assertEqual(reloaded.game.state.seed, 1234)

    def test_yes_no_never_defaults_on_empty_or_invalid_input(self):
        keys = iter(['', 'yes', 'b', 'n'])
        with patch('cinema_tycoon.terminal.read_key', side_effect=lambda prompt: next(keys)), redirect_stdout(io.StringIO()):
            self.assertFalse(yes_no('Replace?'))

    def test_day_and_room_buttons_apply_only_to_selected_scope(self):
        room = self.game.add_room(self.theater.id, 'Second screen', 40)
        self.drive(lambda: scheduling_menu(self.game, self.theater), ['m', '2', 'd', '3', 'a', '1', '1', 'b'])
        self.assertTrue(room.weekly[5])
        self.assertTrue(room.weekly[6])
        self.assertFalse(room.weekly[0])
        self.assertFalse(any(self.theater.rooms[0].weekly.values()))

    def test_clock_option_persists_and_drives_formatting(self):
        from cinema_tycoon import terminal
        self.addCleanup(setattr, terminal, 'TIME_FORMAT', '12h')
        with tempfile.TemporaryDirectory() as temp:
            app = App(temp)
            self.assertEqual(terminal.format_time(18), '6:00 PM')
            self.drive(app.options_menu, ['4', 'b'])
            reloaded = App(temp)
            self.assertEqual(reloaded.options['time_format'], '24h')
            self.assertEqual(terminal.format_time(18), '18:00')

    def test_legacy_version_two_keeps_owned_goods_and_adds_ingredients(self):
        self.game.buy_stock(self.theater.id, self.game.state.products[0].id, 100)
        data = asdict(self.game.state)
        data['products'] = data['products'][:6]
        for p in data['products']:
            for field in ('category', 'yield_per_unit', 'deal', 'commission', 'unit'):
                del p[field]
        for t in data['theaters']:
            for field in ('display', 'prices', 'contracts', 'popcorn_machine', 'soda_machine', 'merchandiser', 'tanks', 'kernel_id', 'topping_id', 'popcorn_limit', 'stock_targets', 'display_targets', 'program_policy', 'cash_reserve', 'auto_prepare', 'automation_spent'):
                del t[field]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'legacy.json'
            original = json.dumps({'version': 2, 'state': data})
            path.write_text(original)
            loaded = load_game(path)
            self.assertEqual(path.read_text(), original)
            self.assertEqual(loaded.state.cash, self.game.state.cash)
            self.assertEqual(loaded.state.theaters[0].stock, self.theater.stock)
            self.assertEqual(loaded.state.theaters[0].display, {})
            self.assertTrue(any(p.category == 'kernels' for p in loaded.state.products))
            self.assertTrue(any(p.category == 'syrup' for p in loaded.state.products))
            self.assertTrue(all(p.deal == 'wholesale' for p in loaded.state.products[:6]))
            save_game(loaded, path)
            self.assertEqual(asdict(load_game(path).state), asdict(loaded.state))

    def test_invalid_producer_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            for producer in (None, '', 'Bad\nCompany'):
                data = asdict(self.game.state)
                data['products'][0]['producer'] = producer
                path.write_text(json.dumps({'version': SAVE_VERSION, 'state': data}))
                with self.assertRaises(ValueError):
                    load_game(path)


if __name__ == '__main__':
    unittest.main()
