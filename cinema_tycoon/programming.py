"""Room schedules repeat weekly; intervals wrap across Sunday midnight."""
import calendar
import math
from copy import deepcopy

from .models import Room
from .content import EQUIPMENT, era_for


class Programming:
    def room(self, theater_id, room_id=1):
        for room in self.get("theaters", theater_id).rooms:
            if room.id == room_id:
                return room
        raise ValueError("That room no longer exists.")

    def weekdays(self, days):
        days = list(range(7)) if days is None else list(days)
        if not days or any(type(d) is not int or not 0 <= d <= 6 for d in days):
            raise ValueError("Choose valid weekdays.")
        return sorted(set(days))

    @staticmethod
    def occupied(day, hour, duration):
        return {(day * 24 + hour + i) % 168 for i in range(duration)}

    def schedule_conflicts(self, theater_id, film_id, hour, room_id=1, days=None):
        room, film = self.room(theater_id, room_id), self.get("films", film_id)
        requested = set().union(*(self.occupied(day, hour, film.hours) for day in self.weekdays(days)))
        return [(day, start) for day, schedule in room.weekly.items() for start, fid in schedule.items()
                if self.occupied(day, start, self.get("films", fid).hours) & requested]

    def schedule(self, theater_id, film_id, hour, replace=False, room_id=1, days=None):
        self.active()
        room, film = self.room(theater_id, room_id), self.get("films", film_id)
        days = self.weekdays(days)
        if film not in self.available_films():
            raise ValueError("That film's distribution window has ended.")
        if type(hour) is not int or not 0 <= hour < 24:
            raise ValueError("Choose an hour from midnight through 11 PM.")
        conflicts = self.schedule_conflicts(theater_id, film_id, hour, room_id, days)
        if conflicts and not replace:
            raise ValueError("That booking overlaps existing screenings.")
        for day, start in conflicts:
            del room.weekly[day][start]
        for day in days:
            room.weekly[day][hour] = film_id

    def films_in_pool(self, pool):
        definition = self.rules["film_pools"].get(pool)
        if definition is None:
            raise ValueError(f"Film pool '{pool}' is missing from balance.json. Choose another pool.")
        return [f for f in self.available_films() if definition["min_budget"] <= f.variables["production_budget"] < definition["max_budget"]
                and f.genre in definition.get("genres", [f.genre])]

    def auto_program(self, theater_id, fill_only=False, room_id=None, days=None, pool=None):
        self.active()
        theater = self.get("theaters", theater_id)
        targets = [self.room(theater_id, room_id)] if room_id is not None else [r for r in theater.rooms if r.open]
        days = self.weekdays(days)
        notes = []
        # Resolve all filters before changing anything, including missing mod definitions.
        selections = [(room, self.films_in_pool(pool or room.film_pool)) for room in targets]
        rng = self.rng()
        for room, films in selections:
            if not films:
                notes.append(f"{room.name}: no films match {pool or room.film_pool}; existing program kept.")
                continue
            if not fill_only:
                for day in days:
                    room.weekly[day].clear()
            for day in days:
                hour = room.auto_start
                while hour < room.auto_end:
                    candidates = [f for f in films if hour + f.hours <= room.auto_end
                        and not self.schedule_conflicts(theater_id, f.id, hour, room.id, [day])]
                    if not candidates:
                        hour += 1
                        continue
                    film = rng.choice(candidates)
                    self.schedule(theater_id, film.id, hour, room_id=room.id, days=[day])
                    hour += film.hours
            notes.append(f"{room.name}: random picks from {pool or room.film_pool} applied.")
        return notes

    def copy_program(self, theater_id, room_id, source_day, target_days, replace=False):
        self.active()
        self.weekdays([source_day])
        room = self.room(theater_id, room_id)
        source = room.weekly[source_day].copy()
        targets = [d for d in self.weekdays(target_days) if d != source_day]
        original = deepcopy(room.weekly)
        try:
            for day in targets:
                if replace:
                    room.weekly[day].clear()
                for hour, pid in source.items():
                    self.schedule(theater_id, pid, hour, replace=replace, room_id=room_id, days=[day])
        except ValueError:
            room.weekly = original
            raise

    def has_program(self, theater):
        return any(r.open and any(r.weekly.values()) for r in theater.rooms)

    def monthly_weekdays(self):
        return [sum(calendar.weekday(self.state.year, self.state.month, d) == w
                    for d in range(1, calendar.monthrange(self.state.year, self.state.month)[1] + 1)) for w in range(7)]

    def staffing(self, room):
        counts = self.monthly_weekdays()
        hours = sum(counts[day] * sum(self.get("films", fid).hours for fid in schedule.values())
                    for day, schedule in room.weekly.items()) if room.open else 0
        needed = hours * self.rules["staff"]["workers_per_screen_hour"]
        supplied = room.staff * self.rules["staff"]["hours_per_person"]
        return {"hours": hours, "required": math.ceil(needed / self.rules["staff"]["hours_per_person"]),
                "coverage": min(1.0, supplied / needed) if needed else 1.0,
                "uncovered_hours": max(0, needed - supplied),
                "payroll": round(room.staff * self.rules["staff"]["monthly_wage"], 2)}

    def room_price(self, seats):
        return round(self.rules["rooms"]["build_base"] + self.rules["rooms"]["build_per_seat"] * seats, 2)

    def add_room(self, theater_id, name, seats):
        theater = self.get("theaters", theater_id)
        if not name.strip() or len(name.strip()) > 60 or type(seats) is not int or not 20 <= seats <= 300:
            raise ValueError("Use a room name of 1–60 characters and 20–300 seats.")
        if len(theater.rooms) >= self.rules["rooms"]["max_rooms"]:
            raise ValueError("This theater has reached the configured room limit.")
        self.spend(self.room_price(seats), "capital")
        room = Room(id=max(r.id for r in theater.rooms) + 1, name=name.strip(), seats=seats, staff=0)
        theater.rooms.append(room)
        return room

    def set_staff(self, theater_id, room_id, count):
        self.active()
        if type(count) is not int or not 0 <= count <= 100:
            raise ValueError("Choose 0–100 staff for the room.")
        self.room(theater_id, room_id).staff = count

    def upgrade(self, theater_id, room_id=1):
        room = self.room(theater_id, room_id)
        if room.equipment >= min(len(EQUIPMENT) - 1, era_for(self.state.year).max_equipment):
            raise ValueError("No further room upgrade is available in this era.")
        self.spend(EQUIPMENT[room.equipment + 1]["cost"], "capital")
        room.equipment += 1
