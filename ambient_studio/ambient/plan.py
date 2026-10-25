"""Deterministic plan for each upload slot (3 per day): kind, hours, seed, title, description, tags."""
from __future__ import annotations
import datetime as dt

KINDS = ["rain", "storm", "fire"]
HOURS = [3, 4, 3, 5, 3]
T = {
    "rain": ["Rain on the Window at Night — {h} Hours of Gentle Rain for Sleep", "Night City Rain Sounds — {h} Hours of Rain Ambience", "{h} Hours of Soft Rain on a Window — Sleep, Study, Relax"],
    "storm": ["Thunderstorm and Heavy Rain — {h} Hours for Deep Sleep", "Distant Thunder and Rain Sounds — {h} Hours", "Lightning Storm Ambience with Rain — {h} Hours"],
    "fire": ["Cozy Fireplace Crackling — {h} Hours of Fire Sounds", "Warm Fireplace Ambience — {h} Hours to Relax and Sleep", "Crackling Fire in the Hearth — {h} Hours"],
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
    hours = HOURS[(idx // 3) % len(HOURS)]
    title = T[kind][(idx // 3) % 3].format(h=hours)
    return {"id": f"{kind}-{idx:04d}", "kind": kind, "hours": hours, "seed": 1000 + idx, "title": title,
            "description": f"{DESC[kind]}\n\n{CREDITS}",
            "tags": ["ambient", "sleep sounds", "relaxing", kind, "white noise", "study"]}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(plan(int(sys.argv[1]))))
