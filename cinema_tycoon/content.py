"""Editable content and era/event hooks loaded from JSON."""
import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

with open(DATA_DIR / "concessions.json", "r", encoding="utf-8") as f:
    _concessions = json.load(f)
    CONCESSION_PRODUCERS = _concessions["producers"]
    PRODUCT_TYPES = _concessions["product_types"]
    MACHINES = _concessions["machines"]
    TOPPING_NOTES = _concessions["topping_notes"]

with open(DATA_DIR / "films.json", "r", encoding="utf-8") as f:
    _films = json.load(f)
    GENRES = _films["genres"]
    TITLE_GRAMMARS = _films["title_grammars"]
    LOGLINE_COMPONENTS = _films["logline_components"]
    ACTING = tuple(_films["acting_styles"])
    QUIRKS = tuple(_films["production_quirks"])
    DIRECTORS = _films["directors"]

with open(DATA_DIR / "events.json", "r", encoding="utf-8") as f:
    _events = json.load(f)
    EVENTS = _events["events"]
    TIMELINE = tuple(tuple(x) for x in _events["timeline"])

with open(DATA_DIR / "equipment.json", "r", encoding="utf-8") as f:
    EQUIPMENT = tuple(json.load(f))

with open(DATA_DIR / "eras.json", "r", encoding="utf-8") as f:
    _eras = json.load(f)

FLAVORS = ("savory", "salty", "bitter", "sweet", "sour")
FILM_VARIABLES = ("execution_competence", "creative_ambition", "sincerity", "weirdness",
                  "avant_garde", "critical_polarization", "mainstream_appeal", "production_budget")

@dataclass(frozen=True)
class EraRules:
    name: str
    demand: float
    operating_cost: float
    note: str
    allowed_genres: tuple
    film_runtimes: tuple
    product_types: tuple
    max_equipment: int

def era_for(year: int) -> EraRules:
    last_era = _eras[-1]
    for era in _eras:
        if era["start_year"] <= year <= era["end_year"]:
            last_era = era
            break
    return EraRules(
        name=last_era["name"],
        demand=last_era["demand"],
        operating_cost=last_era["operating_cost"],
        note=last_era["note"],
        allowed_genres=tuple(last_era["allowed_genres"]),
        film_runtimes=tuple(last_era["film_runtimes"]),
        product_types=tuple(last_era["product_types"]),
        max_equipment=last_era["max_equipment"],
    )
