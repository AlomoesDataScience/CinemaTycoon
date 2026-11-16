# Editing the theater simulation

Edit `balance.json` beside `main.py`. No Python changes are needed for weekday demand, audience preferences, film pools, wages or room costs. Keep valid JSON: use double quotes and no comments or trailing commas. Back up the file before experimenting.

Rules are read when you create or load a company. Return to the main menu and reload after editing. Saves keep the world and random state, but use the current balance file when loaded. Changing the rules intentionally changes future results. Bad values produce a readable error instead of starting a partially configured simulation.

These are fictional game balance values. Historical content and geographic accuracy are separate future work.

## Days and audiences

`weekday_demand` has seven entries, ordered **Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday**. A value of `1` is neutral. `0.8` reduces attendance by 20%; `1.4` increases it by 40%, before seating and market limits. The engine counts actual weekdays in the current month, including leap years.

`dayparts` divides the full 24-hour day into non-overlapping intervals. `start` is inclusive and `end` exclusive, using integer hours. Every hour from 0 through 23 must occur exactly once. End-of-day is 24. These numeric values always use a 24-hour clock even when the player interface uses AM/PM.

Each daypart has:

- `name`: its label in the booking screen.
- `demand`: the general turnout multiplier for that time of day.
- `audiences`: relative weights for the named audience groups. They are normalized, so `{ "families": 2, "adults": 1 }` means two-thirds families and one-third adults.

`audiences` defines each group's taste multiplier for every existing film genre: Drama, Comedy, Adventure, Mystery, Horror and Science Fiction. A taste of `1` is neutral. The default families favor Comedy and Adventure; night owls favor Horror and Science Fiction. These are editable fictional cohorts, not claims about real audience research.

The attendance factor for a booking is:

```text
weekday demand × daypart demand × weighted audience genre preference
```

The rest of the model also considers city tastes, film quality, prices, condition, equipment, reputation, film age, repeats, staffing and monthly events. There is no hidden extra evening/weekend bonus outside these settings.

Shows belong to the weekday on which they start. A Sunday 11 PM show lasting two hours occupies Sunday 11 PM and Monday midnight. Its audience and staff-hour totals are attributed to the starting day. A month's accounts include shows whose start dates fall in that month; a weekly overnight booking still blocks its occupied hours in the following day.

## Film pools

`film_pools` is an object whose keys become persistent room preferences. Keep an `all` entry. Each pool has `label`, `min_budget` (inclusive), and `max_budget` (exclusive). You can add a `genres` array to restrict the pool further.

For example, add this member to `film_pools`:

```json
"horror_nights": {
  "label": "Horror nights",
  "min_budget": 0,
  "max_budget": 1000000000,
  "genres": ["Horror", "Mystery"]
}
```

The default Indie/small pool covers budgets below $500,000; Mid-budget covers $500,000–$899,999; Big-budget starts at $900,000. These are game-dollar production scale labels. All values are editable.

Autofill draws uniformly at random from matching titles that fit the remaining opening window and do not overlap another booking. It does not use hidden quality, local tastes or predicted profit to recommend films. It may repeat a title. Reproducibility comes from the saved world random state.

An empty pool leaves the existing program intact and reports that no films matched. If you remove a pool that a saved room uses, automatic programming reports the missing pool and keeps its program; select another pool in Rooms & staff or Automation. Per-room opening windows limit automatic filling only. Manual screenings can start at any of the 24 hours and cross midnight.

## Staff and rooms

`staff.monthly_wage` is the base monthly wage per assigned employee. `hours_per_person` is the month's staff-hour capacity per employee. `workers_per_screen_hour` is the number of workers required per occupied room-hour. Fractional values are allowed for these three positive settings.

```text
required staff hours = occupied screening hours × workers per screen hour
staff coverage = min(1, assigned staff × hours per person / required staff hours)
```

Staffing coverage scales the room's admissions. Zero staff means zero admissions when there is a program. The manager screen rounds required headcount up; rooms may have 0–100 assigned staff. This is an aggregate monthly model rather than individual shift scheduling. Wages are paid for the entire month, including idle or closed rooms. The economy preset scales operating costs, including wages.

`rooms.build_base + rooms.build_per_seat × seats` is the room construction cost. Rooms can have 20–300 seats when built through the UI. `monthly_upkeep` applies to every room, in addition to its projection maintenance and staff payroll. `max_rooms` controls the build limit (1–100); lowering it does not delete existing rooms.

The company begins with one 80-seat room and three assigned workers. New rooms start with zero staff and an empty program. Closed rooms have no admissions or active film licenses but still pay their staff, room and equipment upkeep. Licenses are paid once per unique title per theater each month, shared across its open rooms.

Concessions remain shared by the whole theater. Their sales receive the combined attendance of its open rooms. Concession operation is included in central theater staffing; individual counter shifts are not modeled.

## Editing deeper content

`cinema_tycoon/content.py` contains procedural vocabulary, equipment, concessions, events and era filters. `programming.py` owns interval checks and staffing, `rules.py` validates the balance file, and `engine.py` applies the attendance multipliers. Changing the genre vocabulary requires matching changes in the balance file and may require save migration.

Run checks after changes:

```bash
python3 -m unittest discover -s tests -v
```

Some default-balance tests deliberately check that weekends outperform weekdays. If your mod reverses that design, those particular expected outcomes should be updated along with the mod.
