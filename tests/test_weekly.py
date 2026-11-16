from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from cinema_tycoon.engine import Game
from cinema_tycoon.persistence import load_game, save_game, validate
from cinema_tycoon.rules import audience_factor, load_rules
from cinema_tycoon.terminal import format_time, time_range


class WeeklyManagementTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.new(year=2021, month=2)
        self.theater = self.game.state.theaters[0]
        self.room = self.theater.rooms[0]
        self.film = self.game.state.films[0]
        self.film.minutes = 90

    def test_clock_formats_midnight_noon_and_next_day(self):
        self.assertEqual(format_time(0, '12h'), '12:00 AM')
        self.assertEqual(format_time(12, '12h'), '12:00 PM')
        self.assertEqual(format_time(23, '12h'), '11:00 PM')
        self.assertEqual(format_time(24, '24h'), '00:00')
        self.assertIn('next day', time_range(23, 2))

    def test_weekday_isolation_and_overnight_wrap_conflicts(self):
        self.game.schedule(self.theater.id, self.film.id, 23, days=[6])
        self.assertFalse(self.room.weekly[0])
        with self.assertRaises(ValueError):
            self.game.schedule(self.theater.id, self.film.id, 0, days=[0])
        self.game.schedule(self.theater.id, self.film.id, 0, days=[1])
        self.assertIn(0, self.room.weekly[1])
        self.game.schedule(self.theater.id, self.film.id, 0, days=[0], replace=True)
        self.assertFalse(self.room.weekly[6])
        validate(self.game.state)

    def test_multi_day_replacement_is_atomic(self):
        self.game.schedule(self.theater.id, self.film.id, 18, days=[2])
        original = deepcopy(self.room.weekly)
        with self.assertRaises(ValueError):
            self.game.schedule(self.theater.id, self.film.id, 19, days=[0, 2])
        self.assertEqual(original, self.room.weekly)
        self.game.schedule(self.theater.id, self.film.id, 19, days=[0, 2], replace=True)
        self.assertNotIn(18, self.room.weekly[2])
        self.assertIn(19, self.room.weekly[0])

    def test_independent_rooms_can_screen_simultaneously_and_licenses_are_shared(self):
        second = self.game.add_room(self.theater.id, 'Screen 2', 60)
        self.game.schedule(self.theater.id, self.film.id, 18, room_id=1, days=[5])
        self.game.schedule(self.theater.id, self.film.id, 18, room_id=second.id, days=[5])
        self.assertEqual(self.game.booking_cost(self.theater), self.film.license_fee)
        self.assertEqual(second.staff, 0)
        validate(self.game.state)

    def test_room_build_failure_does_not_charge_or_mutate(self):
        before = asdict(self.game.state)
        with self.assertRaises(ValueError):
            self.game.add_room(self.theater.id, 'Too small', 1)
        self.assertEqual(before, asdict(self.game.state))
        self.game.state.cash = 0
        with self.assertRaises(ValueError):
            self.game.add_room(self.theater.id, 'Unaffordable', 80)
        self.assertEqual(len(self.theater.rooms), 1)

    def test_staffing_shortage_reduces_admissions_and_payroll_changes_cost(self):
        self.game.schedule(self.theater.id, self.film.id, 18)
        staffed = Game(deepcopy(self.game.state))
        self.game.set_staff(self.theater.id, 1, 0)
        self.assertEqual(self.game.staffing(self.room)['coverage'], 0)
        self.assertLess(self.game.fixed_cost(self.theater), staffed.fixed_cost(staffed.state.theaters[0]))
        no_staff, with_staff = self.game.advance(), staffed.advance()
        self.assertEqual(no_staff['theaters'][0]['attendance'], 0)
        self.assertGreater(with_staff['theaters'][0]['attendance'], 0)
        self.assertEqual(no_staff['theaters'][0]['rooms'][0]['coverage'], 0)

    def test_full_day_requires_more_staff_than_evening_program(self):
        self.game.schedule(self.theater.id, self.film.id, 18)
        short = self.game.staffing(self.room)['required']
        self.room.auto_start = 0
        self.room.auto_end = 24
        self.game.auto_program(self.theater.id)
        self.assertGreater(self.game.staffing(self.room)['required'], short)

    def test_weekend_and_daypart_preferences_are_editable(self):
        rules = self.game.rules
        self.assertGreater(audience_factor(rules, 5, 18, 'Comedy')[0], audience_factor(rules, 0, 18, 'Comedy')[0])
        morning = audience_factor(rules, 0, 9, 'Horror')[0] / audience_factor(rules, 0, 9, 'Comedy')[0]
        evening = audience_factor(rules, 5, 23, 'Horror')[0] / audience_factor(rules, 5, 23, 'Comedy')[0]
        self.assertGreater(evening, morning)
        self.assertEqual(self.game.monthly_weekdays(), [4] * 7)
        self.game.schedule(self.theater.id, self.film.id, 18)
        report = self.game.advance()['theaters'][0]['rooms'][0]
        self.assertGreater(report['weekdays'][5], report['weekdays'][0])

    def test_random_autofill_obeys_budget_pool_and_preserves_manual_bookings(self):
        for film in self.game.state.films:
            film.variables['production_budget'] = 1200000
        eligible = self.game.state.films[:2]
        for film in eligible:
            film.variables['production_budget'] = 100000
        manual = self.game.state.films[-1]
        self.game.schedule(self.theater.id, manual.id, 18, days=[0])
        self.game.auto_program(self.theater.id, fill_only=True, pool='indie', days=[0, 5])
        self.assertEqual(self.room.weekly[0][18], manual.id)
        generated = set(self.room.weekly[5].values())
        self.assertTrue(generated)
        self.assertTrue(generated <= {f.id for f in eligible})
        self.assertFalse(self.room.weekly[1])

    def test_empty_pool_does_not_erase_program(self):
        self.game.schedule(self.theater.id, self.film.id, 18)
        for film in self.game.state.films:
            film.variables['production_budget'] = 2000000
        before = deepcopy(self.room.weekly)
        notes = self.game.auto_program(self.theater.id, pool='indie')
        self.assertEqual(before, self.room.weekly)
        self.assertIn('no films match', notes[0])

    def test_copy_a_day_and_restore_on_conflict(self):
        self.game.schedule(self.theater.id, self.film.id, 18, days=[0])
        self.game.copy_program(self.theater.id, 1, 0, [5, 6])
        self.assertEqual(self.room.weekly[0], self.room.weekly[5])
        self.game.schedule(self.theater.id, self.film.id, 17, days=[2])
        before = deepcopy(self.room.weekly)
        with self.assertRaises(ValueError):
            self.game.copy_program(self.theater.id, 1, 0, [1, 2])
        self.assertEqual(before, self.room.weekly)

    def test_keep_stocked_automates_display_and_soda_refills_from_reserve(self):
        candy = next(p for p in self.game.state.products if p.category == 'packaged' and p.deal == 'wholesale')
        syrup = next(p for p in self.game.state.products if p.category == 'syrup')
        for product, target in ((candy, 900), (syrup, 30)):
            self.game.keep_stocked(self.theater.id, product.id, target)
            self.game.buy_stock(self.theater.id, product.id, target)
        self.game.prepare_counter(self.theater)
        display_before, tank_before = self.theater.display[candy.id], self.theater.tanks[syrup.id]
        cash = self.game.state.cash
        report = self.game.concession_sales(self.theater, 10000)
        candy_row = next(r for r in report['items'] if r['product'] == candy.name)
        soda_row = next(r for r in report['items'] if r['product'] == syrup.name)
        self.assertGreater(candy_row['sold'], display_before)
        self.assertGreater(soda_row['sold'], tank_before)
        self.assertEqual(cash, self.game.state.cash)  # Refill transfers do not buy stock twice.
        self.assertTrue(all(v >= 0 for v in self.theater.stock.values()))
        validate(self.game.state)

    def test_recipe_names_describe_food_rather_than_suppliers(self):
        kernel = next(p for p in self.game.state.products if p.category == 'kernels')
        butter = next(p for p in self.game.state.products if 'Dairy butter' in p.name)
        self.game.keep_stocked(self.theater.id, kernel.id, 30)
        self.assertEqual(self.game.recipe_name(self.theater), 'Plain popcorn')
        self.game.keep_stocked(self.theater.id, butter.id, 10)
        self.assertEqual(self.game.recipe_name(self.theater), 'Buttered popcorn')

    def test_legacy_daily_save_becomes_seven_days_and_roundtrips(self):
        self.game.schedule(self.theater.id, self.film.id, 18)
        data = asdict(self.game.state)
        old = data['theaters'][0]
        room = old.pop('rooms')[0]
        old.update(schedule=room['weekly'][0], seats=room['seats'], equipment=room['equipment'])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'v3.json'
            path.write_text(json.dumps({'version': 3, 'state': data}))
            before = path.read_bytes()
            loaded = load_game(path)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([loaded.state.theaters[0].rooms[0].weekly[d] for d in range(7)], [self.room.weekly[0]] * 7)
            save_game(loaded, path)
            again = load_game(path)
            self.assertEqual(asdict(loaded.state), asdict(again.state))
            self.assertEqual(loaded.advance(), again.advance())

    def test_balance_file_rejects_gaps_and_allows_custom_genre_pool(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'balance.json'
            rules = deepcopy(self.game.rules)
            rules['film_pools']['scares'] = {'label': 'Horror nights', 'min_budget': 0, 'max_budget': 1e9, 'genres': ['Horror']}
            path.write_text(json.dumps(rules))
            self.assertIn('scares', load_rules(path)['film_pools'])
            rules['dayparts'][0]['end'] = 5
            path.write_text(json.dumps(rules))
            with self.assertRaises(ValueError):
                load_rules(path)

    def test_room_weekly_overlap_in_save_is_rejected(self):
        self.game.schedule(self.theater.id, self.film.id, 23, days=[6])
        data = asdict(self.game.state)
        data['theaters'][0]['rooms'][0]['weekly'][0][0] = self.film.id
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.json'
            path.write_text(json.dumps({'version': 4, 'state': data}))
            with self.assertRaises(ValueError):
                load_game(path)


if __name__ == '__main__':
    unittest.main()
