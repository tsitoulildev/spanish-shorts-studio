"""Deterministic plan for each upload slot (3 per day): theme, length, seed, title, description, tags."""
from __future__ import annotations
import datetime as dt

KINDS = ["rain", "ocean", "river", "storm", "snow", "autumn"]
MINUTES = 20  # length of every video
T = {
    "rain": ["Rain on the Window at Night — {m} Minutes of Gentle Rain for Sleep", "Night City Rain Sounds — {m} Minutes of Rain Ambience", "{m} Minutes of Soft Rain on a Window — Sleep, Study, Relax"],
    "ocean": ["Ocean Waves on a Tropical Beach — {m} Minutes to Relax", "Calm Sea Waves Ambience — {m} Minutes for Sleep", "Beach Waves and Pebbles — {m} Minutes of Ocean Sounds"],
    "fire": ["Cozy Fireplace Crackling — {m} Minutes of Fire Sounds", "Warm Fire Ambience — {m} Minutes to Relax and Sleep", "Crackling Fire in the Hearth — {m} Minutes"],
    "river": ["River and Forest Stream Sounds — {m} Minutes of Flowing Water", "Mountain Stream Ambience — {m} Minutes for Focus and Sleep", "Running Water in the Wild — {m} Minutes"],
    "storm": ["Thunderstorm and Heavy Rain — {m} Minutes for Deep Sleep", "Distant Thunder and Rain Sounds — {m} Minutes", "Lightning Storm Ambience with Rain — {m} Minutes"],
    "snow": ["Snowfall and Soft Winter Wind — {m} Minutes of Winter Calm", "Quiet Snowy Landscapes — {m} Minutes of Winter Ambience", "Falling Snow Ambience — {m} Minutes to Relax"],
    "autumn": ["Autumn Rain over the Lake — {m} Minutes of Rain Sounds", "Rainy Autumn Morning — {m} Minutes of Calm Rain", "Soft Autumn Rain — {m} Minutes for Sleep and Study"],
}
DESC = {
    "rain": "Real rain footage and rain recordings, looped without a break. Good for sleep, studying, reading or background calm.",
    "ocean": "Real ocean footage with a recording of waves on a beach, looped without a break. Good for relaxing, sleep or focus.",
    "fire": "Real fire footage with the sound of a crackling fire (the sound is generated), looped without a break. Good for relaxing, reading or sleep.",
    "river": "Real river and stream footage with recordings of flowing water, looped without a break. Good for focus, relaxing or sleep.",
    "storm": "Thunder and rain recordings over real storm footage, looped without a break. Good for sleep, focus or a stormy evening in.",
    "snow": "Real snowfall footage with a soft wind (the wind sound is generated), looped without a break. Good for relaxing, reading or sleep.",
    "autumn": "Real autumn rain footage with rain recordings, looped without a break. Good for sleep, studying or a quiet morning.",
}
CREDITS = "Footage and recordings: public domain / CC0 material from Wikimedia Commons, edited and looped."


def slot_index(now: dt.datetime, slot: int) -> int:
    return (now.date() - dt.date(2026, 10, 25)).days * 3 + slot


def plan(idx: int) -> dict:
    kind = KINDS[idx % len(KINDS)]
    title = T[kind][(idx // len(KINDS)) % 3].format(m=MINUTES)
    return {"id": f"{kind}-{idx:04d}", "kind": kind, "hours": round(MINUTES / 60, 4), "seed": 1000 + idx, "title": title,
            "description": f"{DESC[kind]}\n\n{CREDITS}",
            "tags": ["ambient", "sleep sounds", "relaxing", kind, "white noise", "study"]}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(plan(int(sys.argv[1]))))
