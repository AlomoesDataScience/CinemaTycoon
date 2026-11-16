import json

with open("cinema_tycoon/data/films.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for genre, parts in data["logline_components"].items():
    new_format = {
        "templates": [
            "The story follows {protagonist} who {incident} {complication} {stakes}.",
            "When {protagonist} {incident}, they must fight back {complication} {stakes}.",
            "In this gripping tale, {protagonist} {incident}. But {complication} {stakes}.",
            "{protagonist} {incident}, {complication} {stakes}."
        ],
        "vocabulary": {
            "protagonist": parts.get("protagonists", []),
            "incident": parts.get("inciting_incidents", []),
            "complication": parts.get("complications", []),
            "stakes": parts.get("stakes", [])
        }
    }
    # Some cleaning: if stakes ends with punctuation, we might want to be careful, but we'll append it anyway.
    cleaned_stakes = []
    for s in parts.get("stakes", []):
        if s.endswith("."): s = s[:-1]
        cleaned_stakes.append(s)
    new_format["vocabulary"]["stakes"] = cleaned_stakes
    
    data["logline_components"][genre] = new_format

with open("cinema_tycoon/data/films.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

