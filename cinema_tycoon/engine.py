"""Deterministic monthly simulation, independent of the terminal interface."""
import calendar
import math
import random

from .content import (ACTING, CONCESSION_PRODUCERS, EQUIPMENT, EVENTS, FILM_VARIABLES, FLAVORS, GENRES,
                      PRODUCT_TYPES, QUIRKS, TIMELINE, era_for, MACHINES, TITLE_GRAMMARS, LOGLINE_COMPONENTS, DIRECTORS)
from .models import City, Film, Product, State, Studio, Theater
from .concessions import Concessions
from .programming import Programming
from .rules import load_rules, audience_factor

OPEN_HOUR, CLOSE_HOUR = 0, 24


def clamp(value, low, high):
    return max(low, min(high, value))


class Game(Concessions, Programming):
    def __init__(self, state: State):
        self.state = state
        self.rules = load_rules()

    @property
    def inflation(self):
        return math.exp((self.state.year - 1985) * 0.035)

    @classmethod
    def new(cls, company="Silver Screen Co.", year=1985, month=1, seed=42, max_settlements=250):
        if not company.strip() or len(company.strip()) > 60:
            raise ValueError("Company name must contain 1–60 characters.")
        if not 1895 <= year <= 2100 or not 1 <= month <= 12:
            raise ValueError("Choose a year from 1895 to 2100 and a month from 1 to 12.")
        if not 3 <= max_settlements <= 10000:
            raise ValueError("Settlement count must be between 3 and 10,000.")
        game = cls(State(company.strip(), year, month, seed, max_settlements=max_settlements))
        game.state.cash = round(65000 * game.inflation, 2)
        game.state.month_open_cash = game.state.cash
        rng = game.rng()
        studio_roots = rng.sample(("Lantern", "Silver Birch", "Atlas", "Marigold", "Northstar", "Bluebird", "Meridian", "Beacon"), 4)
        for root in studio_roots:
            name = root + rng.choice((" Pictures", " Films", " Motion Works", " Studios"))
            game.state.studios.append(Studio(game.id(), name, rng.uniform(35, 85),
                rng.uniform(35, 85), rng.uniform(20, 80), rng.uniform(150000, 800000), game.director(rng)))
        for name, population in (("New York", 8000000), ("Los Angeles", 3900000), ("Chicago", 2700000)):
            game.create_city(name, population)
        home = game.create_city("Maple Falls", 58000) if max_settlements > 3 else game.state.cities[2]
        theater = Theater(game.id(), "The Majestic", home.id)
        theater.ticket_price = round(4.0 * game.inflation, 2)
        game.state.theaters.append(theater)
        for _ in range(14):
            game.generate_product()
        for _ in range(10):
            game.generate_film()
        game.state.news = ["Welcome to your first month. Book films, stock concessions, then open the doors."]
        return game

    def rng(self):
        self.state.rng_counter += 1
        return random.Random(f"{self.state.seed}:{self.state.rng_counter}")

    def id(self):
        result = self.state.next_id
        self.state.next_id += 1
        return result

    def active(self):
        if self.state.bankrupt:
            raise ValueError("This company has closed. Start a new game from the main menu.")

    def get(self, collection, item_id):
        for item in getattr(self.state, collection):
            if item.id == item_id:
                return item
        raise ValueError(f"No {collection.rstrip('s')} with ID {item_id}.")

    def spend(self, amount, category):
        self.active()
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid cost.")
        amount = round(amount, 2)
        if amount > self.state.cash:
            raise ValueError(f"You need ${amount:,.2f}; available cash is ${self.state.cash:,.2f}.")
        self.state.cash = round(self.state.cash - amount, 2)
        self.state.planning_spend[category] = round(self.state.planning_spend.get(category, 0) + amount, 2)

    @staticmethod
    def director(rng):
        return rng.choice(DIRECTORS["first_names"]) + " " + rng.choice(DIRECTORS["last_names"])

    def create_city(self, name=None, population=None):
        if len(self.state.cities) >= self.state.max_settlements:
            raise ValueError("All configured settlements have been discovered.")
        rng = self.rng()
        if name is None:
            name = rng.choice(("Cedar", "Willow", "Silver", "Pine", "Briar", "Copper")) + " " + rng.choice(("Grove", "Creek", "Falls", "Ridge", "Bay", "Springs"))
            if any(c.name == name for c in self.state.cities):
                name += f" {len(self.state.cities) + 1}"
        population = population or rng.randint(7000, 180000)
        city = City(self.id(), name, population, round(0.75 + min(population / 300000, 1.25), 2),
                    {g: rng.uniform(0.8, 1.25) for g in GENRES}, {f: rng.randint(15, 95) for f in FLAVORS})
        self.state.cities.append(city)
        return city

    def generate_product(self, type_index=None):
        rng = self.rng()
        available = era_for(self.state.year).product_types
        idx = available[len(self.state.products) % len(available)] if type_index is None else type_index
        pdata = PRODUCT_TYPES[idx]
        
        kind = pdata["kind"]
        flavors = pdata["flavors"]
        quality = rng.randint(30, 95)
        
        brand = rng.choice(list(CONCESSION_PRODUCERS.keys()))
        producer = CONCESSION_PRODUCERS[brand]["company"]
        
        category = pdata["category"]
        unit = pdata["unit"]
        deal = pdata["deal"]
        commission = pdata["commission"]
        spoilage = pdata["spoilage_rate"]
        ingredient_kind = pdata["ingredient_kind"]
        service_name = pdata["service_name"]
        yield_per_unit = pdata["yield_per_unit"]
        
        wholesale = round(0.35 + quality * 0.012 + rng.uniform(0, 0.25), 2)
        retail = round(wholesale * 4.5, 2)

        if category == "kernels":
            yield_per_unit = 18 + quality // 7
            wholesale, retail = round(5 + quality * 0.07, 2), round(6.50 + quality * 0.03, 2)
        elif category == "syrup":
            yield_per_unit = 35 + quality // 4
            wholesale, retail = round(6 + quality * 0.08, 2), round(4.50 + quality * 0.02, 2)
        elif category == "topping":
            wholesale = round((8 if kind == "Dairy butter" else 4) + quality * 0.03, 2)

        product = Product(
            self.id(), f"{brand} {kind}", quality,
            {f: int(clamp(v + rng.randint(-10, 10), 0, 100)) for f, v in zip(FLAVORS, flavors)},
            wholesale, retail, self.state.turn, producer=producer,
            category=category, yield_per_unit=yield_per_unit, deal=deal, commission=commission,
            unit=unit, brand=brand, service_name=service_name, ingredient_kind=ingredient_kind,
            spoilage_rate=spoilage,
        )
        self.state.products.append(product)
        return product

    def generate_film(self):
        rng = self.rng()
        studio = rng.choice(self.state.studios)
        era = era_for(self.state.year)
        genre = rng.choice(era.allowed_genres)
        variables = {name: rng.uniform(10, 95) for name in FILM_VARIABLES}
        variables["execution_competence"] = clamp(studio.competence + rng.uniform(-25, 25), 5, 99)
        variables["sincerity"] = clamp(studio.quality * 0.5 + rng.uniform(0, 50), 5, 99)
        variables["production_budget"] = round((20000 + studio.size * 15000) * rng.uniform(0.6, 1.4) * self.inflation)
        
        grammar = TITLE_GRAMMARS.get(genre, TITLE_GRAMMARS.get("Drama"))
        title = rng.choice(grammar["templates"])
        for key, words in grammar["vocabulary"].items():
            token = "{" + key + "}"
            while token in title:
                title = title.replace(token, rng.choice(words), 1)

        if any(f.title == title for f in self.state.films):
            title += f" — No. {self.state.next_id}"
            
        minutes = rng.choice(era.film_runtimes)
        acting = rng.choice(ACTING)
        quirks = rng.sample(QUIRKS, rng.randint(0, 2))
        
        log_comp = LOGLINE_COMPONENTS.get(genre, LOGLINE_COMPONENTS.get("Drama"))
        synopsis_base = rng.choice(log_comp["templates"])
        for key, words in log_comp["vocabulary"].items():
            token = "{" + key + "}"
            while token in synopsis_base:
                synopsis_base = synopsis_base.replace(token, rng.choice(words), 1)
        
        synopsis = synopsis_base + " "
        synopsis += "Scenes often depart from chronological order. " if variables["avant_garde"] > 60 else "Scenes follow the central story in chronological order. "
        synopsis += f"The viewing notes describe {acting.lower()}. "
        if quirks:
            synopsis += "The screener includes " + ", ".join(q.lower() for q in quirks) + ". "
        synopsis += f"The production sheet lists {studio.director} as director and a ${variables['production_budget']:,.0f} budget."
        
        film = Film(self.id(), title, genre, rng.choice(GENRES[genre]), minutes, studio.id,
                    self.state.turn, round(120 * self.inflation + variables["production_budget"] / 5500, 2),
                    variables, acting, quirks, synopsis)
        self.state.films.append(film)
        return film

    def available_films(self):
        return [f for f in self.state.films if self.state.turn - f.release_turn < 4]

    def buy_stock(self, theater_id, product_id, quantity):
        self.active()
        if not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number.")
        theater, product = self.get("theaters", theater_id), self.get("products", product_id)
        if product.deal != "wholesale":
            raise ValueError("This supplier stocks its own case. Sign its vendor contract instead.")
        if sum(theater.stock.values()) + sum(theater.display.values()) + quantity > 10000:
            raise ValueError("Each theater can store at most 10,000 concession units.")
        self.spend(product.wholesale * quantity, "stock")
        theater.stock[product_id] = theater.stock.get(product_id, 0) + quantity

    def set_price(self, theater_ids, price):
        self.active()
        if not math.isfinite(price) or not 2 <= price <= 25:
            raise ValueError("Ticket price must be between $2 and $25.")
        targets = [self.get("theaters", i) for i in theater_ids]
        for theater in targets:
            theater.ticket_price = round(price, 2)

    def renovate(self, theater_id):
        theater = self.get("theaters", theater_id)
        if theater.condition >= 100:
            raise ValueError("This theater is already in perfect condition.")
        cost = round(1500 + (100 - theater.condition) * 65, 2)
        self.spend(cost, "capital")
        theater.condition = 100
        return cost

    def property_price(self, city_id):
        return round((100000 + self.get("cities", city_id).rent_factor * 25000) * self.inflation)

    def buy_theater(self, city_id=None, name="New Picture House"):
        self.active()
        if not name.strip() or len(name.strip()) > 60:
            raise ValueError("Theater name must contain 1–60 characters.")
        if city_id is None:
            if len(self.state.cities) >= self.state.max_settlements:
                raise ValueError("All settlements have been discovered; choose an existing city.")
            # Fixed acquisition quote means generating a town cannot change the agreed cost.
            self.spend(round(145000 * self.inflation), "capital")
            city = self.create_city()
        else:
            city = self.get("cities", city_id)
            self.spend(self.property_price(city_id), "capital")
        theater = Theater(self.id(), name.strip(), city.id)
        theater.ticket_price = round(4.0 * self.inflation, 2)
        self.state.theaters.append(theater)
        return theater

    def choose_event(self, choice_id):
        event = EVENTS.get(self.state.pending_event)
        if not event or choice_id not in event["choices"]:
            raise ValueError("Choose one of the current event's listed options.")
        choice = event["choices"][choice_id]
        self.spend(choice["cost"], "events")
        self.state.flags.append(choice["flag"])
        self.state.reputation = clamp(self.state.reputation + choice["reputation"], 0, 100)
        self.state.event_demand += choice.get("demand", 0)
        self.state.pending_event = ""

    @staticmethod
    def quality(film):
        v = film.variables
        return clamp(v["execution_competence"] * 0.38 + v["sincerity"] * 0.19 + v["creative_ambition"] * 0.13
                     + v["mainstream_appeal"] * 0.30 - abs(v["weirdness"] - 45) * 0.10
                     - v["critical_polarization"] * 0.04 + v["avant_garde"] * 0.025 - len(film.quirks) * 2, 5, 95)

    @staticmethod
    def product_match(product, city):
        similarity = 1 - sum(abs(product.flavors[f] - city.flavors[f]) for f in FLAVORS) / 500
        return 0.5 * similarity + 0.5 * product.quality / 100

    def fixed_cost(self, theater):
        city = self.get("cities", theater.city_id)
        era = era_for(self.state.year)
        return round((2300 * city.rent_factor + 1500 + 950
                      + sum(self.staffing(r)["payroll"] + self.rules["rooms"]["monthly_upkeep"]
                            + EQUIPMENT[r.equipment]["maintenance"] for r in theater.rooms)
                      + MACHINES["popcorn"][theater.popcorn_machine]["upkeep"]
                      + MACHINES["soda"][theater.soda_machine]["upkeep"]
                      + (15 if theater.merchandiser else 0)
                      + (100 - theater.condition) * 8) * era.operating_cost * self.inflation, 2)

    def booking_cost(self, theater):
        return round(sum(self.get("films", i).license_fee for i in {fid for r in theater.rooms if r.open
                     for day in r.weekly.values() for fid in day.values()}), 2)

    def advance(self):
        self.active()
        if self.state.year >= 9998 and self.state.month == 12:
            raise ValueError("The supported calendar has ended. Start a new company to continue.")
        if self.state.pending_event:
            raise ValueError("Resolve the pending event before advancing the month.")
        s, rng = self.state, self.rng()
        era, days = era_for(s.year), calendar.monthrange(s.year, s.month)[1]
        news, demand, surprise_cost = [], 1.0, 0.0
        roll = rng.random()
        if roll < 0.12:
            demand = 0.84
            news.append("Persistent rain disrupts travel: attendance falls this month.")
        elif roll < 0.24:
            demand = 1.14
            news.append("A local moviegoing craze lifts attendance this month.")
        elif roll < 0.32:
            surprise_cost = 650.0
            news.append("An electrical fault requires $650 in emergency repairs.")
        for theater in s.theaters:
            if theater.program_policy != "manual" or theater.auto_schedule:
                try:
                    news.extend(self.auto_program(theater.id, fill_only=theater.program_policy == "fill"))
                except ValueError as error:
                    news.append(f"{theater.name}: automatic programming skipped: {error}")
            if theater.auto_stock:
                news.extend(self.auto_restock(theater))
            if theater.auto_prepare:
                self.prepare_counter(theater)
        reports, studio_income = [], {}
        revenue, expenses = 0.0, surprise_cost
        for theater in s.theaters:
            city = self.get("cities", theater.city_id)
            audience, tickets = 0, 0.0
            local_count = sum(t.city_id == city.id for t in s.theaters)
            monthly_market = int(city.population * 0.30 / local_count)
            weekday_counts = self.monthly_weekdays()
            royalty_rate = self.rules.get("studio_royalty", 0.50)
            room_reports = []
            screenings = []
            total_potential = 0
            for room in theater.rooms:
                staffing = self.staffing(room)
                for weekday, program in sorted(room.weekly.items()):
                    daily_uses = {}
                    if not room.open:
                        continue
                    for hour, film_id in sorted(program.items()):
                        film = self.get("films", film_id)
                        occupancy = 0.08 + self.quality(film) / 500 + EQUIPMENT[room.equipment]["appeal"]
                        occupancy *= city.tastes[film.genre] * era.demand * demand * (1 + s.event_demand)
                        factor, demographics = audience_factor(self.rules, weekday, hour, film.genre)
                        occupancy *= factor
                        occupancy *= (0.5 + theater.condition / 200) * (0.8 + s.reputation / 250)
                        occupancy *= math.exp((8 - theater.ticket_price) * 0.12)
                        occupancy *= max(0.6, 1 - (s.turn - film.release_turn) * 0.13)
                        occupancy *= 0.86 ** daily_uses.get(film_id, 0) * rng.uniform(0.88, 1.12)
                        daily_uses[film_id] = daily_uses.get(film_id, 0) + 1
                        raw_people = int(room.seats * weekday_counts[weekday] * clamp(occupancy, 0, 0.95)
                                         * staffing["coverage"])
                        screenings.append({"room_id": room.id, "weekday": weekday, "film": film, "raw_people": raw_people, "demographics": demographics})
                        total_potential += raw_people

            scale = min(1.0, monthly_market / total_potential) if total_potential > 0 else 1.0
            room_audiences = {r.id: 0 for r in theater.rooms}
            room_weekdays = {r.id: [0] * 7 for r in theater.rooms}
            snack_modifiers = {"packaged": 0.0, "popcorn": 0.0, "soda": 0.0}
            for sc in screenings:
                people = min(int(round(sc["raw_people"] * scale)), max(0, monthly_market - audience))
                audience += people
                room_audiences[sc["room_id"]] += people
                room_weekdays[sc["room_id"]][sc["weekday"]] += people
                gross = round(people * theater.ticket_price, 2)
                tickets += gross
                studio_income[sc["film"].studio_id] = studio_income.get(sc["film"].studio_id, 0) + round(gross * royalty_rate, 2)
                for demo_name, weight in sc["demographics"].items():
                    prefs = self.rules["audiences"][demo_name]["snacks"]
                    for snack_type, modifier in prefs.items():
                        snack_modifiers[snack_type] += people * weight * modifier

            if audience > 0:
                snack_modifiers = {k: v / audience for k, v in snack_modifiers.items()}
            
            for room in theater.rooms:
                staffing = self.staffing(room)
                room_reports.append({"room": room.name, "room_id": room.id, "attendance": room_audiences[room.id],
                                     "weekdays": room_weekdays[room.id], "staff": room.staff, **staffing})
                if staffing["coverage"] < 1:
                    news.append(f"{theater.name} / {room.name}: staff cover {staffing['coverage']:.0%} of the program; admissions reduced.")
            snacks = self.concession_sales(theater, audience, snack_modifiers)
            snack_revenue, units, spoiled = snacks["revenue"], snacks["units"], snacks["spoiled"]
            buyers = snacks["unserved"]
            fixed, licenses, royalty = self.fixed_cost(theater), self.booking_cost(theater), round(tickets * royalty_rate, 2)
            costs = round(fixed + licenses + royalty + snacks["supplies"], 2)
            snack_revenue, tickets = round(snack_revenue, 2), round(tickets, 2)
            revenue += tickets + snack_revenue
            expenses += costs
            reports.append({"theater": theater.name, "theater_id": theater.id, "attendance": audience, "tickets": tickets,
                "concessions": snack_revenue, "units_sold": units, "spoiled": spoiled,
                "concession_detail": snacks, "rooms": room_reports,
                "unserved_snack_demand": buyers, "fixed": fixed, "licenses": licenses, "royalties": royalty,
                "contribution": round(tickets + snack_revenue - costs, 2)})
            theater.condition = max(0, theater.condition - rng.uniform(1.3, 3.2))
            theater.automation_spent = 0.0
        revenue, expenses = round(revenue, 2), round(expenses, 2)
        # Stock, events and capital were paid during planning; do not charge them twice.
        s.cash = round(s.cash + revenue - expenses, 2)
        stock_cost, event_cost, capital = (s.planning_spend.get(k, 0.0) for k in ("stock", "events", "capital"))
        profit = round(revenue - expenses - stock_cost - event_cost, 2)
        s.last_report = {"date": f"{s.year:04d}-{s.month:02d}", "opening_cash": s.month_open_cash,
            "revenue": revenue, "operating_costs": expenses, "stock_purchases": stock_cost,
            "event_costs": event_cost, "capital": capital, "profit": profit, "closing_cash": s.cash,
            "emergency_repairs": surprise_cost, "theaters": reports}
        for studio in s.studios:
            # The wider industry supplies most of a studio's income; our royalties also count.
            studio.cash += studio_income.get(studio.id, 0) + rng.uniform(-50000, 55000)
            trend = 0.5 if studio.cash > 300000 else -0.7
            studio.quality = clamp(studio.quality + rng.uniform(-2, 2) + trend, 10, 95)
            studio.competence = clamp(studio.competence + rng.uniform(-2, 2) + trend, 10, 95)
            studio.size = clamp(studio.size + rng.uniform(-1, 1) + trend, 10, 95)
            if rng.random() < 0.07:
                departed = studio.director
                studio.director = self.director(rng)
                studio.competence = max(10, studio.competence - rng.uniform(5, 13))
                news.append(f"{departed} leaves {studio.name}; {studio.director} takes over its next slate.")
            if studio.cash < 0:
                studio.cash = 100000
                studio.size = max(10, studio.size - 15)
                news.append(f"{studio.name} restructures after financial losses.")
        s.turn += 1
        s.month += 1
        if s.month == 13:
            s.month, s.year = 1, s.year + 1
        s.event_demand = 0
        s.planning_spend.clear()
        s.month_open_cash = s.cash
        expired = {f.id for f in s.films if s.turn - f.release_turn >= 4}
        for theater in s.theaters:
            removed = 0
            for room in theater.rooms:
                for program in room.weekly.values():
                    for hour in list(program):
                        if program[hour] in expired:
                            del program[hour]
                            removed += 1
            if removed:
                news.append(f"{theater.name}: {removed} expired weekly bookings removed; check the schedules.")
        # Keep the catalogue bounded; old stocked products remain available.
        s.films = [f for f in s.films if f.id not in expired]
        for _ in range(5):
            self.generate_film()
        if s.turn % 2 == 0:
            product = self.generate_product()
            news.append(f"Wholesale arrival: {product.name} (quality {product.quality}/100).")
        for turn, event_id in TIMELINE:
            event = EVENTS[event_id]
            if turn == s.turn and ("requires" not in event or event["requires"] in s.flags):
                s.pending_event = event_id
        if era_for(s.year).name != era.name:
            news.append(f"Economic conditions shift to {era_for(s.year).name}.")
        s.news = news or ["A quiet month in the industry. Five new films enter distribution."]
        s.bankrupt = s.cash < 0
        if s.bankrupt:
            s.news.append("The company cannot meet its obligations and has closed.")
        return s.last_report
