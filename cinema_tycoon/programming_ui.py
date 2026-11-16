import calendar

from .content import EQUIPMENT
from .terminal import ask, format_time, header, menu, money, pause, select, time_range, whole, yes_no

DAY_GROUPS = [(tuple(range(7)), "Every day"), (tuple(range(5)), "Weekdays · Monday–Friday"),
              ((5, 6), "Weekend · Saturday & Sunday")] + [((d,), calendar.day_name[d]) for d in range(7)]


def film_choices(game):
    return [(f.id, f"{f.title}\n      {f.genre} / {f.subgenre} · {f.minutes} min · {f.hours}h block"
             f"\n      Budget ${f.variables['production_budget']:,.0f} · license {money(f.license_fee)}/month · {4 - game.state.turn + f.release_turn} months left")
            for f in sorted(game.available_films(), key=lambda f: (-f.variables['production_budget'], f.id))]


def show_schedule(game, theater, room=None, days=None):
    room = room or theater.rooms[0]
    days = list(range(7)) if days is None else days
    print(f"{room.name} · {room.seats} seats · {'open' if room.open else 'closed'}")
    for day in days:
        program = room.weekly[day]
        entries = list(sorted(program.items()))
        print(f"  {calendar.day_name[day]}: {len(entries)} bookings")
        visible = entries if len(days) == 1 else entries[:2]
        for hour, pid in visible:
            film = game.get("films", pid)
            print(f"    {time_range(hour, film.hours)} · {film.title}")
        if len(visible) < len(entries):
            print("    … Select this day to view its whole program.")
    staff = game.staffing(room)
    print(f"Staff: {room.staff} assigned / {staff['required']} needed this month · coverage {staff['coverage']:.0%}")
    print(f"Random fill: {room.film_pool} · {time_range(room.auto_start, room.auto_end - room.auto_start)}")
    print(f"Theater licenses {money(game.booking_cost(theater))}/month · total overhead ~{money(game.fixed_cost(theater))}\n")


def pick_pool(game, room):
    pool = select("RANDOM FILM POOL", [(key, f"{value['label']} · {len(game.films_in_pool(key))} available")
                                     for key, value in game.rules["film_pools"].items()],
                  lambda: print("Autofill picks randomly from this pool. It does not review hidden film scores."))
    if pool is not None:
        room.film_pool = pool
    return pool


def scheduling_menu(game, theater):
    room, days, notice = theater.rooms[0], tuple(range(7)), ""
    while True:
        key = menu(f"PROGRAM FILMS · {theater.name}", [("a", "Add a film to the selected days"), ("r", "Remove bookings"),
            ("d", "Choose weekdays / weekend / a day"), ("m", "Choose room"), ("f", "Read film notes"),
            ("u", "Random-fill gaps from a film pool"), ("w", "Set automatic opening hours"),
            ("p", "Copy a day's program"), ("c", "Clear selected days"), ("b", "Back")],
            lambda: show_schedule(game, theater, room, days), notice)
        notice = ""
        try:
            if key == "b":
                return
            if key == "d":
                selected = select("CHOOSE DAYS", DAY_GROUPS)
                if selected is not None:
                    days = selected
                continue
            if key == "m":
                rid = select("CHOOSE ROOM", [(r.id, f"{r.name} · {r.seats} seats") for r in theater.rooms])
                if rid is not None:
                    room = game.room(theater.id, rid)
                continue
            if key == "f":
                from .cli import films_menu
                films_menu(game)
                continue
            game.active()
            if key == "a":
                pid = select("ADD FILM · LARGEST BUDGET FIRST", film_choices(game))
                if pid is None:
                    continue
                film = game.get("films", pid)
                slots = []
                for hour in range(24):
                    conflicts = game.schedule_conflicts(theater.id, pid, hour, room.id, days)
                    part = next(p for p in game.rules["dayparts"] if p["start"] <= hour < p["end"])
                    audience = max(part["audiences"], key=part["audiences"].get).replace("_", " ")
                    slots.append((hour, time_range(hour, film.hours) + (f" · replaces {len(conflicts)} weekly bookings" if conflicts else " · free")
                                  + f"\n      {part['name']} · mostly {audience}"))
                hour = select(f"CHOOSE TIME · {film.title}", slots,
                    lambda: print(f"Room: {room.name} · Days: {', '.join(calendar.day_abbr[d] for d in days)}"))
                if hour is None:
                    continue
                conflicts = game.schedule_conflicts(theater.id, pid, hour, room.id, days)
                if conflicts:
                    header("REPLACE CONFLICTING BOOKINGS")
                    for day, start in sorted(conflicts):
                        print(f"  {calendar.day_name[day]} {format_time(start)} · {game.get('films', room.weekly[day][start]).title}")
                    if not yes_no("Replace these bookings, including any overlap on adjacent days?"):
                        notice = "Original bookings kept."
                        continue
                game.schedule(theater.id, pid, hour, replace=bool(conflicts), room_id=room.id, days=days)
                notice = "Film booked on the selected days."
            elif key == "r":
                entry = select("REMOVE BOOKING", [("all", "Remove all selected days at one start time")] +
                    [((day, hour), f"{calendar.day_name[day]} {format_time(hour)} · {game.get('films', pid).title}")
                     for day in days for hour, pid in sorted(room.weekly[day].items())])
                if entry == "all":
                    hour = select("REMOVE START TIME", [(h, format_time(h)) for h in sorted({h for d in days for h in room.weekly[d]})])
                    if hour is not None:
                        for d in days:
                            room.weekly[d].pop(hour, None)
                elif entry is not None:
                    del room.weekly[entry[0]][entry[1]]
            elif key == "u":
                pool = pick_pool(game, room)
                if pool is not None:
                    notice = " ".join(game.auto_program(theater.id, fill_only=True, room_id=room.id, days=days, pool=pool))
            elif key == "w":
                start = select("AUTO OPENING TIME", [(h, format_time(h)) for h in range(24)])
                if start is not None:
                    end = select("AUTO CLOSING TIME", [(h, format_time(h) + (" (end of day)" if h == 24 else "")) for h in range(start + 1, 25)])
                    if end is not None:
                        room.auto_start, room.auto_end = start, end
            elif key == "p":
                source = select("COPY FROM DAY", [(d, calendar.day_name[d]) for d in range(7)])
                if source is not None:
                    target = select("COPY TO DAYS", DAY_GROUPS)
                    if target is not None and yes_no("Replace the target days and any adjacent overnight conflicts?"):
                        game.copy_program(theater.id, room.id, source, target, replace=True)
                        notice = "Program copied."
            elif key == "c" and yes_no("Clear the selected days in this room?"):
                for day in days:
                    room.weekly[day].clear()
        except ValueError as error:
            notice = str(error)


def rooms_menu(game, theater):
    notice = ""
    while True:
        def context():
            for room in theater.rooms:
                staffing = game.staffing(room)
                print(f"{room.name}: {room.seats} seats · {room.staff} staff · {staffing['coverage']:.0%} coverage")
            print(f"Cash {money(game.state.cash)} · wages {money(game.rules['staff']['monthly_wage'])}/person/month\n")
        key = menu("ROOMS & STAFF", [("1", "Manage a room"), ("2", "Build a room"), ("3", "Staff all rooms for current programs"), ("b", "Back")], context, notice)
        notice = ""
        try:
            if key == "b":
                return
            game.active()
            if key == "2":
                header("BUILD A ROOM")
                name = ask("Room name", f"Screen {len(theater.rooms) + 1}")
                seats = whole("Seats", 80, 20, 300)
                print("A new room adds capacity, projection upkeep and room costs. It starts without staff or bookings.")
                if yes_no(f"Build for {money(game.room_price(seats))}?"):
                    game.add_room(theater.id, name, seats)
                    notice = "Room built. Assign staff and a program before running it."
            elif key == "3":
                required = [(r, game.staffing(r)["required"]) for r in theater.rooms]
                if any(count > 100 for _, count in required):
                    raise ValueError("A room needs over 100 staff under these balance rules. Shorten its program or revise the staffing rules.")
                payroll = sum(n for _, n in required) * game.rules["staff"]["monthly_wage"]
                if yes_no(f"Set staff to each room's required count? Base monthly payroll will be {money(payroll)}."):
                    for room, count in required:
                        game.set_staff(theater.id, room.id, count)
            elif key == "1":
                rid = select("CHOOSE ROOM", [(r.id, r.name) for r in theater.rooms])
                if rid is None:
                    continue
                room = game.room(theater.id, rid)
                action = menu(room.name, [("1", "Set staff count"), ("2", "Toggle open/closed"),
                    ("3", "Upgrade projection"), ("4", "Set automatic film pool"), ("b", "Back")],
                    lambda: show_schedule(game, theater, room))
                if action == "1":
                    need = game.staffing(room)["required"]
                    print(f"Current month needs {need} staff. Shortages reduce admissions proportionally; payroll is due even when closed.")
                    count = whole("Assigned staff", room.staff, 0, 100)
                    if yes_no(f"Set base payroll to {money(count * game.rules['staff']['monthly_wage'])}/month?"):
                        game.set_staff(theater.id, rid, count)
                elif action == "2":
                    room.open = not room.open
                    notice = "Room status updated. Assigned staff and room upkeep still cost money."
                elif action == "3":
                    if room.equipment >= len(EQUIPMENT) - 1:
                        raise ValueError("Best demo projection is already installed.")
                    upgrade = EQUIPMENT[room.equipment + 1]
                    if yes_no(f"Install {upgrade['name']} for {money(upgrade['cost'])}? Monthly equipment upkeep becomes {money(upgrade['maintenance'])}."):
                        game.upgrade(theater.id, rid)
                elif action == "4":
                    pick_pool(game, room)
        except ValueError as error:
            notice = str(error)
