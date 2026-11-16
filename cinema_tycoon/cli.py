"""Keyboard-driven terminal menus for the monthly theater simulation."""
import argparse
import calendar
import json
from pathlib import Path

from .content import EQUIPMENT, EVENTS, era_for
from .engine import Game
from .persistence import atomic_json, load_game, save_game
from .terminal import (amount, ask, choice, header, interactive_terminal, menu,
                       money, pause, select, whole, yes_no)
from .concessions_ui import automation_menu, stock_menu
from . import terminal
from .programming_ui import film_choices, show_schedule, scheduling_menu, rooms_menu


def films_menu(game):
    while True:
        pid = select('DISTRIBUTION CATALOGUE · LARGEST BUDGET FIRST', film_choices(game),
                     lambda: print('Select a film to read employee notes. Licenses renew monthly plus 22% of ticket sales.'))
        if pid is None:
            return
        film = game.get('films', pid)
        header(film.title)
        print(game.get('studios', film.studio_id).name)
        print(film.synopsis)
        print('Acting:', film.acting)
        print('Production observations:', ', '.join(film.quirks) or 'No additional observations.')
        pause()


def theater_menu(game, theater):
    notice = ''
    while True:
        def context():
            print(f'{game.get("cities", theater.city_id).name} · group {theater.group} · {len(theater.rooms)} rooms · {sum(r.seats for r in theater.rooms)} seats')
            print(f'Condition {theater.condition:.0f}% · tickets {money(theater.ticket_price)} · cash {money(game.state.cash)}')
            print(f'{sum(len(day) for r in theater.rooms for day in r.weekly.values())} weekly bookings\n')
        key = menu(theater.name.upper(), [('1', 'Program films'), ('2', 'Concessions'), ('3', 'Ticket price'),
            ('4', 'Renovate'), ('5', 'Rooms & staff'), ('6', 'Automation'), ('7', 'Assign group'), ('b', 'Back')], context, notice)
        notice = ''
        try:
            if key == 'b':
                return
            if key == '1':
                scheduling_menu(game, theater)
            elif key == '2':
                stock_menu(game, theater)
            elif key == '3':
                header(f'TICKET PRICE · {theater.name}')
                game.set_price([theater.id], amount('Ticket price', theater.ticket_price, 2, 25))
                notice = 'Ticket price updated.'
            elif key == '4':
                header(f'RENOVATE · {theater.name}')
                cost = 1500 + (100 - theater.condition) * 65
                print('Crews repaint the worn lobby, mend upholstery, repair tired fittings, and give the theater a deep clean.')
                print('Guests return to a fresh, well-kept picture house. Its improved condition helps attendance and reduces repair bills.')
                print('This restores condition to 100%; it does not add seats, screens or projection technology.')
                print(f'Current condition {theater.condition:.0f}% · cash {money(game.state.cash)} · price {money(cost)}')
                if yes_no('Commission the renovation?'):
                    game.renovate(theater.id)
                    notice = 'The lobby and auditorium are refreshed. Condition restored.'
            elif key == '5':
                rooms_menu(game, theater)
            elif key == '6':
                automation_menu(game, theater)
            elif key == '7':
                group = select('ASSIGN GROUP', [('new', 'Create a new group')] + [(g, g) for g in sorted({t.group for t in game.state.theaters})])
                if group is not None:
                    game.active()
                    if group == 'new':
                        group = ask('New group name')
                    if not 1 <= len(group) <= 60:
                        raise ValueError('Group names need 1–60 characters.')
                    theater.group = group
                    notice = 'Group updated.'
        except ValueError as error:
            notice = str(error)


def theaters_menu(game):
    while True:
        pid = select('YOUR THEATERS', [(t.id, f'{t.name} · {game.get("cities", t.city_id).name}\n      {t.group} · {len(t.rooms)} rooms · {sum(len(day) for r in t.rooms for day in r.weekly.values())} weekly bookings') for t in game.state.theaters])
        if pid is None:
            return
        theater_menu(game, game.get('theaters', pid))


def expansion_menu(game):
    city_id = select('PROPERTY & MARKETS', [('new', 'Open in a newly generated town · $38,000')] +
        [(c.id, f'{c.name} · population {c.population:,} · theater {money(game.property_price(c.id))}\n      Prefers {max(c.tastes, key=c.tastes.get)} and {max(c.flavors, key=c.flavors.get)} concessions') for c in game.state.cities],
        lambda: print(f'Cash {money(game.state.cash)} · {len(game.state.cities)}/{game.state.max_settlements} settlements'))
    if city_id is None:
        return
    city_id = None if city_id == 'new' else city_id
    price = 38000 if city_id is None else game.property_price(city_id)
    name = ask('Theater name', 'The Bijou')
    if yes_no(f'Buy {name} for {money(price)}?'):
        game.buy_theater(city_id, name)
        print('Theater opened. Configure its program and concessions before running the month.')
        pause()


def groups_menu(game):
    group = select('BULK MANAGEMENT', [('all', 'All theaters')] + [(g, g) for g in sorted({t.group for t in game.state.theaters})])
    if group is None:
        return
    theaters = [t for t in game.state.theaters if group == 'all' or t.group == group]
    key = menu(f'GROUP · {group}', [('1', 'Set ticket prices'), ('2', 'Random-fill gaps from a film pool'),
        ('3', 'Set programming policy'), ('4', 'Enable/disable purchasing'), ('5', 'Enable/disable counter preparation'), ('b', 'Back')],
        lambda: print('Applies to: ' + ', '.join(t.name for t in theaters)))
    if key == 'b':
        return
    game.active()
    if key == '1':
        game.set_price([t.id for t in theaters], amount('Ticket price for the group', 8, 2, 25))
    elif key == '2':
        pool = select('GROUP FILM POOL', [(key, value['label']) for key, value in game.rules['film_pools'].items()])
        if pool is not None:
            for theater in theaters:
                for room in theater.rooms:
                    room.film_pool = pool
                print(' '.join(game.auto_program(theater.id, fill_only=True, pool=pool)))
    elif key == '3':
        policy = select('GROUP PROGRAMMING', [('manual', 'Manual'), ('fill', 'Fill gaps, preserve bookings'), ('replace', 'Replace program each month')])
        if policy is not None:
            for theater in theaters:
                theater.program_policy, theater.auto_schedule = policy, False
    elif key in ('4', '5'):
        enabled = yes_no('Enable for every theater in this group?')
        for theater in theaters:
            setattr(theater, 'auto_stock' if key == '4' else 'auto_prepare', enabled)
        print('Individual product targets, purchasing ceilings and cash floors remain in effect.')
    print('Group settings applied.')
    pause()


def events_menu(game):
    if not game.state.pending_event:
        header('EVENTS')
        print('No event needs a decision.')
        pause()
        return
    event = EVENTS[game.state.pending_event]
    selected = select(event['title'], [(key, value['label']) for key, value in event['choices'].items()], lambda: print(event['text']))
    if selected is not None:
        game.choose_event(selected)
        print('Decision recorded.')
        pause()


def report_menu(game, *, clear=True):
    report = game.state.last_report
    header('MONTHLY STATEMENT' + (f' · {report["date"]}' if report else ''), clear=clear)
    if not report:
        print('Your first statement arrives after running a month.')
        return
    for row in report['theaters']:
        print(f'\n  {row["theater"]} · {row["attendance"]:,} admissions')
        print(f'    Tickets {money(row["tickets"])} + concession income {money(row["concessions"])}')
        print(f'    Overhead {money(row["fixed"])} · licenses {money(row["licenses"])} · royalties {money(row["royalties"])}')
        print(f'    {row["units_sold"]} concessions sold · {row["spoiled"]} stock units spoiled · {row["unserved_snack_demand"]} unmet item demand')
        for room in row.get('rooms', []):
            print(f"    {room['room']}: {room['attendance']} admissions · {room['staff']} staff · {room['coverage']:.0%} coverage")
            print('      ' + ' · '.join(f'{calendar.day_abbr[d]} {count}' for d, count in enumerate(room['weekdays'])))
        details = row.get('concession_detail')
        if details:
            print(f'    Cups/utilities/oil {money(details["supplies"])} · popcorn waste {details["production_waste"]} · tank waste {details["tank_waste"]}')
            for item in details['items']:
                offer = item.get("offer", item["product"])
                detail_tag = f" ({item['product']})" if offer != item["product"] else ""
                print(f'      {offer}{detail_tag}: {money(item["price"])} · demand {item["demand"]} · sold {item["sold"]} · earned {money(item["revenue"])}')
        print(f'    Contribution before purchased stock: {money(row["contribution"])}')
    for label, key in (('Opening cash', 'opening_cash'), ('Revenue', 'revenue'), ('Operating costs', 'operating_costs'),
                       ('Stock purchases', 'stock_purchases'), ('Event spending', 'event_costs'), ('Operating cash profit', 'profit'),
                       ('Property & improvements', 'capital'), ('Closing cash', 'closing_cash')):
        print(f'  {label:<30} {money(report[key]):>16}')
    print('\nStock is expensed when bought; vendor income is your commission after the supplier takes its share.')


def studios_menu(game):
    header('INDUSTRY DESK')
    for studio in game.state.studios:
        print(f'{studio.name} · {studio.director}')
        print(f'  Quality {studio.quality:.0f} · competence {studio.competence:.0f} · scale {studio.size:.0f} · cash {money(studio.cash)}')


def help_menu():
    header('HOW TO PLAY')
    print('''Menus use single keys: press the displayed key without Enter. B goes back.
Long lists have N/P pages; each choice is numbered 1–9 on its current page.
Names, prices and quantities are the only values you type and submit with Enter.

Each turn is one month. Start in Your theaters → Program films. A adds a film:
choose the title, then its time slot. Overlaps ask Y/N before replacing bookings.
R removes bookings. D chooses weekdays, weekends or a day. M chooses a room.
U randomly fills gaps from your selected film pool. W sets autofill hours.
Manual screenings may start at any hour and run across midnight. Programs
repeat weekly, with stronger weekend demand and different audiences by hour.
Manage Rooms & staff to expand or hire; understaffed programs lose admissions.

Concessions: buy reserve stock, then place packaged goods in the concession
case. Pick kernels and an optional topping for popcorn made to order. Load
syrup packs into fountain tanks. Recipe ingredients must be in reserve.
Choose machines for capacity, yield or flavor. Wholesale prices are per box,
bag, pack or tub; retail prices are per serving. Vendor-owned cases have
fixed prices and pay you commission; the vendor supplies its own stock.

Adjust selling prices, run a month, and compare per-item demand, sales and
margins. Reserve stock does not sell straight from the back room. Packaged
stock spoils 5% monthly; most ingredients 2%, dairy butter 20%, spread 8%.
Mixed soda loses 10% monthly. Popcorn is cooked to demand; incomplete batch
surplus is discarded. A customer can buy a packaged snack, popcorn and soda.

Use Keep counter stocked to pick a product and a reserve target once. Staff
then buy within your limits and refill cases/tanks from reserve during sales.
Automation has separate programming, purchasing and counter-preparation
policies. Review a starter plan, set targets, and enable the policies you want.
Targets buy toward your own choices. A monthly ceiling and company cash
floor limit purchases; they cannot guarantee enough cash for operating bills.

Empty theaters still pay overhead. Read event decisions and your monthly
statement. Cash below zero at settlement closes the company. Save manually
while planning; autosave runs after each completed month. Ctrl+C recovers.
Starting dates use simplified economic presets and constant game dollars.''')


class App:
    def __init__(self, save_dir):
        self.save_dir = Path(save_dir)
        self.options_path = self.save_dir / 'options.json'
        self.options = {'autosave': True, 'seed': 42, 'settlements': 250, 'time_format': '12h'}
        self.game = None
        try:
            loaded = json.loads(self.options_path.read_text())
            if isinstance(loaded, dict):
                if type(loaded.get('autosave')) is bool:
                    self.options['autosave'] = loaded['autosave']
                if loaded.get('time_format') in ('12h', '24h'):
                    self.options['time_format'] = loaded['time_format']
                for key, low, high in (('seed', 0, 2147483647), ('settlements', 3, 10000)):
                    if type(loaded.get(key)) is int and low <= loaded[key] <= high:
                        self.options[key] = loaded[key]
        except (OSError, ValueError):
            pass
        terminal.TIME_FORMAT = self.options['time_format']

    def save(self, name='manual.json'):
        save_game(self.game, self.save_dir / name)
        print(f'Saved to {self.save_dir / name}')

    def company_context(self):
        state = self.game.state
        print(f'{calendar.month_name[state.month]} {state.year} · month {state.turn + 1} · cash {money(state.cash)}')
        print(f'{len(state.theaters)} theater(s) · economy: {era_for(state.year).name}')
        for news in state.news:
            print('  • ' + news)
        if state.pending_event:
            print('Decision required: ' + EVENTS[state.pending_event]['title'])
        if state.bankrupt:
            print('COMPANY CLOSED. Reports and saves remain available.')
        print()

    def play(self):
        notice = ''
        while True:
            key = menu(f'SILVER SCREEN · {self.game.state.company}', [('1', 'Your theaters'), ('2', 'Film catalogue'),
                ('3', 'Property & markets'), ('4', 'Bulk management'), ('5', 'Industry desk'), ('6', 'Events'),
                ('7', 'Last statement'), ('8', 'Run next month'), ('9', 'Save game'), ('h', 'How to play'), ('0', 'Save & return')], self.company_context, notice)
            notice = ''
            try:
                actions = {'1': theaters_menu, '2': films_menu, '3': expansion_menu, '4': groups_menu,
                           '5': studios_menu, '6': events_menu, '7': report_menu}
                if key in actions:
                    actions[key](self.game)
                    if key in ('5', '7'):
                        pause()
                elif key == 'h':
                    help_menu()
                    pause()
                elif key == '8':
                    self.game.active()
                    if self.game.state.pending_event:
                        events_menu(self.game)
                        continue
                    header('RUN NEXT MONTH')
                    for theater in self.game.state.theaters:
                        print(f'{theater.name}: {sum(len(day) for r in theater.rooms for day in r.weekly.values())} weekly bookings · programming {theater.program_policy}')
                        if not self.game.has_program(theater) and theater.program_policy == 'manual' and not theater.auto_schedule:
                            print('  WARNING: no program; this theater will earn no ticket revenue.')
                    if yes_no('Run this month?'):
                        self.game.advance()
                        report_menu(self.game)
                        if self.options['autosave']:
                            self.save('autosave.json')
                        pause()
                elif key in ('9', '0'):
                    header('SAVE GAME')
                    self.save()
                    pause()
                    if key == '0':
                        return
            except (ValueError, OSError) as error:
                notice = f'Could not complete that action: {error}'

    def new_game(self):
        header('OPENING NIGHT')
        print(f'World seed: {self.options["seed"]} (change in Options before starting a new game).')
        name = ask('Company name', 'Silver Screen Co.')
        year = whole('Starting year', 1985, 1895, 2100)
        month = whole('Starting month', 1, 1, 12)
        self.game = Game.new(name, year, month, self.options['seed'], self.options['settlements'])
        self.play()

    def load_menu(self):
        paths = [p for p in sorted(self.save_dir.glob('*.json')) if p.name != 'options.json']
        path = select('LOAD GAME', [(p, p.name) for p in paths])
        if path is not None:
            self.game = load_game(path)
            self.play()

    def options_menu(self):
        notice = ''
        while True:
            key = menu('OPTIONS', [('1', f'Autosave: {"on" if self.options["autosave"] else "off"} (toggle)'),
                ('2', f'Random seed for new worlds: {self.options["seed"]}'),
                ('3', f'Settlement count for new worlds: {self.options["settlements"]}'),
                ('4', f'Clock display: {self.options["time_format"]} (toggle)'), ('b', 'Back')], notice=notice)
            if key == 'b':
                return
            if key == '1':
                self.options['autosave'] = not self.options['autosave']
            elif key == '2':
                header('OPTIONS · RANDOM SEED')
                self.options['seed'] = whole('World seed', self.options['seed'], 0, 2147483647)
            elif key == '3':
                header('OPTIONS · SETTLEMENTS')
                self.options['settlements'] = whole('Settlement count', self.options['settlements'], 3, 10000)
            elif key == '4':
                self.options['time_format'] = '24h' if self.options['time_format'] == '12h' else '12h'
                terminal.TIME_FORMAT = self.options['time_format']
            atomic_json(self.options_path, self.options)
            notice = 'Option saved. Seed and settlement changes apply to new companies.'

    def run(self):
        notice = ''
        try:
            while True:
                key = menu('S I L V E R   S C R E E N', [('1', 'New Game'), ('2', 'Load'), ('3', 'Options'), ('4', 'Quit')], notice=notice)
                notice = ''
                try:
                    if key == '1':
                        self.new_game()
                    elif key == '2':
                        self.load_menu()
                    elif key == '3':
                        self.options_menu()
                    else:
                        print('See you at the pictures.')
                        return
                except (ValueError, OSError) as error:
                    notice = f'Could not complete that action: {error}'
        except (EOFError, KeyboardInterrupt):
            print('\nClosing the console.')
            if self.game is not None:
                try:
                    self.save('recovery.json')
                except OSError as error:
                    print(f'Recovery save failed: {error}')


def main():
    parser = argparse.ArgumentParser(description='Silver Screen: a monthly movie theater tycoon.')
    parser.add_argument('--save-dir', type=Path, default=Path(__file__).resolve().parent.parent / '.saves')
    parser.add_argument('--demo', type=int, metavar='MONTHS')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.demo is not None:
        if not 1 <= args.demo <= 120:
            parser.error('--demo must be between 1 and 120')
        game = Game.new(seed=args.seed)
        for theater in game.state.theaters:
            theater.program_policy = 'fill'
            theater.auto_stock = theater.auto_prepare = True
            theater.stock_budget = 900
            game.starter_targets(theater.id)
        for _ in range(args.demo):
            if game.state.bankrupt:
                break
            if game.state.pending_event:
                game.choose_event('decline')
            game.advance()
            report_menu(game, clear=False)
        print(f'\nDemo finished after {game.state.turn} months: cash {money(game.state.cash)}.')
    else:
        App(args.save_dir).run()
