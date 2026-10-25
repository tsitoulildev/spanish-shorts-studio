"""Deterministic plan for each upload slot (3 per day): kind, hours, seed, title, description, tags."""
from __future__ import annotations
import datetime as dt

KINDS = ["rain", "storm", "fire"]
MINUTES = 20  # length of every video
T = {
    "rain": ["Rain on the Window at Night — {m} Minutes of Gentle Rain for Sleep", "Night City Rain Sounds — {m} Minutes of Rain Ambience", "{m} Minutes of Soft Rain on a Window — Sleep, Study, Relax"],
    "storm": ["Thunderstorm and Heavy Rain — {m} Minutes for Deep Sleep", "Distant Thunder and Rain Sounds — {m} Minutes", "Lightning Storm Ambience with Rain — {m} Minutes"],
    "fire": ["Cozy Fireplace Crackling — {m} Minutes of Fire Sounds", "Warm Fireplace Ambience — {m} Minutes to Relax and Sleep", "Crackling Fire in the Hearth — {m} Minutes"],
}
DESC = {
    "rain": "Real rain footage and rain recordings, looped without a break. Good for sleep, studying, reading or background calm.",
    "storm": "Thunder, rain and lightning over the hills, looped without a break. Good for sleep, focus or a stormy evening in.",
    "fire": "A real fireplace with the sound of a crackling fire, looped without a break. Good for relaxing, reading or sleep.",
}
CREDITS = "Footage and recordings: public domain / CC0 material from Wikimedia Commons, edited and looped. Fire crackle audio is generated."


def slot_index(now: dt.datetime, slot: int) -> int:
    return (now.date() - dt.date(2026, 10, 25)).days * 3 + slot


def plan(idx: int) -> dict:
    kind = KINDS[idx % 3]
    title = T[kind][(idx // 3) % 3].format(m=MINUTES)
    return {"id": f"{kind}-{idx:04d}", "kind": kind, "hours": round(MINUTES / 60, 4), "seed": 1000 + idx, "title": title,
            "description": f"{DESC[kind]}\n\n{CREDITS}",
            "tags": ["ambient", "sleep sounds", "relaxing", kind, "white noise", "study"]}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(plan(int(sys.argv[1]))))
