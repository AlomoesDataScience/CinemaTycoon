"""Versioned, atomic JSON saves. Loading never executes saved code."""
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import tempfile

from .content import CONCESSION_PRODUCERS, EQUIPMENT, EVENTS, FILM_VARIABLES, FLAVORS, GENRES, MACHINES
from .engine import Game
from .models import City, Film, Product, State, Studio, Theater, Room

SAVE_VERSION = 4


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(data, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def save_game(game, path):
    atomic_json(path, {"version": SAVE_VERSION, "state": asdict(game.state)})


def require(condition, message="The save contains invalid game data."):
    if not condition:
        raise ValueError(message)


def number(value, minimum=-1e15, maximum=1e15):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and minimum <= value <= maximum


def integer(value, minimum=0, maximum=1000000000):
    return type(value) is int and minimum <= value <= maximum


def label(value):
    return isinstance(value, str) and 0 < len(value) <= 300 and not any(ord(c) < 32 for c in value)


def validate(state):
    """Reject broken references and unsafe ranges before the simulation can touch them."""
    require(label(state.company))
    require(integer(state.year, 1895, 9998) and integer(state.month, 1, 12))
    require(integer(state.turn) and integer(state.rng_counter) and type(state.seed) is int)
    require(integer(state.max_settlements, 3, 10000) and len(state.cities) <= state.max_settlements)
    require(number(state.cash) and number(state.month_open_cash) and number(state.reputation, 0, 100))
    require(number(state.event_demand, 0, 1))
    require(type(state.bankrupt) is bool and state.bankrupt == (state.cash < 0))
    require(isinstance(state.planning_spend, dict) and set(state.planning_spend) <= {"capital", "stock", "events"})
    require(all(number(v, 0) for v in state.planning_spend.values()))
    require(abs(state.cash - (state.month_open_cash - sum(state.planning_spend.values()))) < 0.02)
    require(isinstance(state.flags, list) and all(label(f) for f in state.flags))
    require(isinstance(state.news, list) and all(isinstance(n, str) for n in state.news))
    require(state.pending_event == "" or state.pending_event in EVENTS)
    require(state.studios and state.cities and state.theaters and state.products and state.films)
    all_items = state.studios + state.cities + state.theaters + state.products + state.films
    require(all(integer(item.id, 1) for item in all_items))
    ids = [item.id for item in all_items]
    require(len(ids) == len(set(ids)) and integer(state.next_id, max(ids) + 1))
    studio_ids, city_ids = {s.id for s in state.studios}, {c.id for c in state.cities}
    films, products = {f.id: f for f in state.films}, {p.id: p for p in state.products}
    for studio in state.studios:
        require(label(studio.name) and label(studio.director) and number(studio.cash))
        require(all(number(v, 0, 100) for v in (studio.quality, studio.competence, studio.size)))
    for city in state.cities:
        require(label(city.name) and integer(city.population, 1) and number(city.rent_factor, 0.1, 10))
        require(set(city.tastes) == set(GENRES) and all(number(v, 0.1, 3) for v in city.tastes.values()))
        require(set(city.flavors) == set(FLAVORS) and all(number(v, 0, 100) for v in city.flavors.values()))
    for film in state.films:
        require(label(film.title) and film.studio_id in studio_ids and film.genre in GENRES)
        require(film.subgenre in GENRES[film.genre] and integer(film.minutes, 1, 720))
        require(integer(film.release_turn, max(0, state.turn - 3), state.turn))
        require(number(film.license_fee, 0) and set(film.variables) == set(FILM_VARIABLES))
        require(all(number(v, 0, 1e12 if k == "production_budget" else 100) for k, v in film.variables.items()))
        require(label(film.acting) and isinstance(film.quirks, list) and all(label(q) for q in film.quirks))
        require(isinstance(film.synopsis, str))
    for product in state.products:
        require(label(product.name) and integer(product.quality, 0, 100))
        require(label(product.producer))
        require(product.category in ("packaged", "kernels", "syrup", "topping"))
        require(integer(product.yield_per_unit, 1, 1000) and label(product.unit))
        require(product.deal in ("wholesale", "vendor") and number(product.commission, 0.01, 1))
        require(product.deal != "vendor" or product.category == "packaged")
        require(number(product.wholesale, 0.01) and number(product.retail, 0.01))
        require(integer(product.introduced_turn, 0, state.turn))
        require(set(product.flavors) == set(FLAVORS) and all(number(v, 0, 100) for v in product.flavors.values()))
        require(isinstance(product.brand, str) and isinstance(product.service_name, str) and isinstance(product.ingredient_kind, str))
        require(number(product.spoilage_rate, 0, 1))
    for theater in state.theaters:
        require(label(theater.name) and label(theater.group) and theater.city_id in city_ids)
        require(isinstance(theater.rooms, list) and 1 <= len(theater.rooms) <= 100)
        require(len({r.id for r in theater.rooms}) == len(theater.rooms))
        require(integer(theater.seats, 1, 10000) and number(theater.condition, 0, 100))
        require(integer(theater.equipment, 0, len(EQUIPMENT) - 1) and number(theater.ticket_price, 2, 25))
        require(type(theater.auto_stock) is bool and type(theater.auto_schedule) is bool)
        require(number(theater.stock_budget, 0, 100000))
        require(number(theater.automation_spent, 0, 100000))
        require(theater.popcorn_machine in MACHINES["popcorn"] and theater.soda_machine in MACHINES["soda"])
        require(type(theater.merchandiser) is bool and type(theater.auto_prepare) is bool)
        require(theater.program_policy in ("manual", "fill", "replace") and number(theater.cash_reserve, 0, 1e9))
        require(integer(theater.popcorn_limit, 0, 10000))
        require(theater.kernel_id == 0 or theater.kernel_id in products and products[theater.kernel_id].category == "kernels")
        require(theater.topping_id == 0 or theater.topping_id in products and products[theater.topping_id].category == "topping")
        for mapping in (theater.display, theater.tanks, theater.stock_targets, theater.display_targets):
            require(isinstance(mapping, dict) and all(pid in products and integer(q, 0, 10000) for pid, q in mapping.items()))
        require(all(products[pid].category == "packaged" and products[pid].deal == "wholesale" for pid in theater.display))
        require(sum(theater.display.values()) <= 300 + 200 * theater.merchandiser)
        require(all(products[pid].category == "syrup" for pid in theater.tanks))
        require(sum(theater.tanks.values()) <= MACHINES["soda"][theater.soda_machine]["capacity"])
        require(all(products[pid].deal == "wholesale" for pid in theater.stock_targets))
        require(all(products[pid].deal == "wholesale" for pid in theater.display_targets))
        require(all(not q or products[pid].category == "packaged" for pid, q in theater.display_targets.items()))
        require(sum(theater.display_targets.values()) <= 300 + 200 * theater.merchandiser)
        require(sum(theater.stock_targets.values()) + sum(theater.display_targets.values()) <= 10000)
        require(isinstance(theater.contracts, list) and len(theater.contracts) <= 2 and len(set(theater.contracts)) == len(theater.contracts))
        require(all(pid in products and products[pid].deal == "vendor" for pid in theater.contracts))
        require(isinstance(theater.prices, dict) and all(pid in products and products[pid].category != "topping"
                and products[pid].deal == "wholesale" and number(price, 0.25, 30) for pid, price in theater.prices.items()))
        for room in theater.rooms:
            require(integer(room.id, 1) and label(room.name) and integer(room.seats, 1, 10000))
            require(integer(room.staff, 0, 100) and type(room.open) is bool)
            require(integer(room.equipment, 0, len(EQUIPMENT) - 1) and label(room.film_pool))
            require(integer(room.auto_start, 0, 23) and integer(room.auto_end, room.auto_start + 1, 24))
            require(isinstance(room.weekly, dict) and set(room.weekly) == set(range(7)))
            occupied = set()
            for day, program in room.weekly.items():
                require(isinstance(program, dict))
                for hour, film_id in program.items():
                    require(integer(hour, 0, 23) and film_id in films)
                    hours = {(day * 24 + hour + i) % 168 for i in range(films[film_id].hours)}
                    require(not hours & occupied)
                    occupied.update(hours)
        require(all(pid in products and integer(count, 0, 10000) for pid, count in theater.stock.items()))
        require(sum(theater.stock.values()) + sum(theater.display.values()) <= 10000)
    if state.last_report:
        report = state.last_report
        require(isinstance(report, dict) and isinstance(report["date"], str))
        for key in ("opening_cash", "revenue", "operating_costs", "stock_purchases", "event_costs", "capital", "profit", "closing_cash", "emergency_repairs"):
            require(number(report[key]))
        require(isinstance(report["theaters"], list))
        for row in report["theaters"]:
            require(label(row["theater"]))
            require(all(number(row[k]) for k in ("attendance", "tickets", "concessions", "units_sold", "spoiled", "fixed", "licenses", "royalties", "contribution", "unserved_snack_demand")))
            if "rooms" in row:
                require(isinstance(row["rooms"], list))
                for room in row["rooms"]:
                    require(label(room["room"]) and integer(room["room_id"], 1) and integer(room["staff"], 0, 100))
                    require(number(room["coverage"], 0, 1))
                    require(all(number(room[key], 0) for key in ("attendance", "hours", "required", "uncovered_hours", "payroll")))
                    require(isinstance(room["weekdays"], list) and len(room["weekdays"]) == 7 and all(integer(n) for n in room["weekdays"]))
            if "concession_detail" in row:
                detail = row["concession_detail"]
                require(isinstance(detail, dict))
                require(all(number(detail[key], 0) for key in ("revenue", "supplies", "units", "spoiled", "unserved", "production_waste", "tank_waste")))
                require(isinstance(detail["items"], list))
                for item in detail["items"]:
                    require(label(item["product"]) and item["kind"] in ("packaged", "vendor", "popcorn", "soda"))
                    require(all(number(item[key], 0) for key in ("price", "demand", "available", "sold", "revenue", "inputs_used", "vendor_remittance")))
                    require(number(item["margin"]))
                    if "offer" in item:
                        require(label(item["offer"]))


def load_game(path):
    try:
        path = Path(path)
        require(path.stat().st_size <= 20_000_000, "Save is too large to load.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        require(payload["version"] in (1, 2, 3, SAVE_VERSION), "This save uses an unsupported version.")
        data = payload["state"]
        require(isinstance(data, dict))
        if payload["version"] == 1:
            # The original brand becomes its producer without consuming game randomness.
            for product in data["products"]:
                require(label(product["name"]))
                brand = product["name"].split()[0]
                product.setdefault("producer", CONCESSION_PRODUCERS.get(brand, f"{brand} Food Company"))
        for product in data["products"]:
            product.setdefault("brand", "")
            product.setdefault("service_name", "")
            product.setdefault("ingredient_kind", "")
            product.setdefault("spoilage_rate", 0.05)
        for theater in data["theaters"]:
            if "rooms" not in theater and payload["version"] < 4:
                daily = theater.pop("schedule", {})
                theater["rooms"] = [{"id": 1, "name": "Screen 1", "seats": theater.pop("seats", 80),
                    "equipment": theater.pop("equipment", 0), "staff": 3,
                    "weekly": {str(d): daily.copy() for d in range(7)}}]
            require("rooms" in theater)
            theater["rooms"] = [Room(**r) for r in theater["rooms"]]
            for room in theater["rooms"]:
                room.weekly = {int(d): {int(h): fid for h, fid in schedule.items()} for d, schedule in room.weekly.items()}
        for name, cls in (("studios", Studio), ("films", Film), ("products", Product), ("cities", City), ("theaters", Theater)):
            data[name] = [cls(**item) for item in data[name]]
        for theater in data["theaters"]:
            theater.stock = {int(k): v for k, v in theater.stock.items()}
            for field in ("display", "prices", "tanks", "stock_targets", "display_targets"):
                setattr(theater, field, {int(k): v for k, v in getattr(theater, field).items()})
            if payload["version"] < 3:
                theater.program_policy = "replace" if theater.auto_schedule else "manual"
                theater.auto_schedule = False
        state = State(**data)
        validate(state)
        game = Game(state)
        if payload["version"] < 3 and not any(p.category == "kernels" for p in state.products):
            # Keep all old stock as packaged goods; add new ingredients to the vendor catalogue.
            for kind in range(6, 14):
                game.generate_product(type_index=kind)
            for theater in state.theaters:
                if theater.auto_stock and not state.bankrupt:
                    game.starter_targets(theater.id)
                    theater.auto_prepare = True
        validate(state)
        return game
    except OSError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError, IndexError) as error:
        raise ValueError(f"Cannot load this save: {error}") from error
