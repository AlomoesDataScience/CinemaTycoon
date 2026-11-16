"""Player-editable balance data; loaded when a company is created or loaded."""
import json
import math
from pathlib import Path
from .content import GENRES

RULES_PATH = Path(__file__).resolve().parent.parent / "balance.json"


def load_rules(path=RULES_PATH):
    def number(value, low=0, high=1e12):
        return type(value) in (int, float) and math.isfinite(value) and low <= value <= high
    def check(condition):
        if not condition:
            raise ValueError("Invalid balance value")
    try:
        data = json.loads(Path(path).read_text())
        check(len(data["weekday_demand"]) == 7 and all(number(v, 0, 10) for v in data["weekday_demand"]))
        check(data["audiences"] and all(set(a.get("taste", {})) == set(GENRES) and all(number(v, 0, 10) for v in a["taste"].values()) for a in data["audiences"].values()))
        covered = []
        for part in data["dayparts"]:
            check(isinstance(part["name"], str) and part["name"])
            check(type(part["start"]) is int and type(part["end"]) is int and 0 <= part["start"] < part["end"] <= 24)
            check(number(part["demand"], 0, 10) and part["audiences"])
            check(set(part["audiences"]) <= set(data["audiences"]))
            check(all(number(v, 0, 100) for v in part["audiences"].values()) and sum(part["audiences"].values()) > 0)
            covered.extend(range(part["start"], part["end"]))
        check(sorted(covered) == list(range(24)))
        check("all" in data["film_pools"])
        for key, pool in data["film_pools"].items():
            check(isinstance(key, str) and key and isinstance(pool["label"], str))
            check(number(pool["min_budget"]) and number(pool["max_budget"], pool["min_budget"]))
            check(set(pool.get("genres", list(GENRES))) <= set(GENRES))
        check(all(number(data["staff"][k], 0.01) for k in ("monthly_wage", "hours_per_person", "workers_per_screen_hour")))
        check(all(number(data["rooms"][k]) for k in ("build_base", "build_per_seat", "monthly_upkeep")))
        check(type(data["rooms"]["max_rooms"]) is int and 1 <= data["rooms"]["max_rooms"] <= 100)
        if "studio_royalty" in data:
            check(number(data["studio_royalty"], 0.05, 0.95))
        else:
            data["studio_royalty"] = 0.25
        return data
    except (ValueError, TypeError, KeyError, OSError, AttributeError) as error:
        raise ValueError(f"Invalid balance file {path}. Check the values against MODDING.md.") from error


def audience_factor(rules, weekday, hour, genre):
    part = next(p for p in rules["dayparts"] if p["start"] <= hour < p["end"])
    weights = part["audiences"]
    taste = sum(weight * rules["audiences"][name]["taste"][genre] for name, weight in weights.items()) / sum(weights.values())
    return rules["weekday_demand"][weekday] * part["demand"] * taste, weights
