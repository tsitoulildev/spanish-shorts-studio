"""Deterministic plan for each upload slot (3 per day): theme, length, seed, title, description, tags."""
from __future__ import annotations
import datetime as dt

KINDS = ["rain", "ocean", "river", "storm", "snow", "autumn"]
MINUTES = 20  # length of every video
T = {
    "rain": ["Rain on Window at Night 🌧 Relaxing Rain Sounds for Sleep | {m} Min", "Night City Rain Ambience 🌧 Rain Sounds for Study and Focus | {m} Min", "Soft Rain Sounds to Fall Asleep Fast 🌧 Calm Night Rain | {m} Min"],
    "ocean": ["Ocean Waves Sounds for Sleeping 🌊 Calm Sea to Relax | {m} Min", "Beach Waves Ambience 🌊 Relaxing Ocean Sounds for Focus | {m} Min", "Gentle Sea Waves to Fall Asleep 🌊 Ocean Sounds | {m} Min"],
    "river": ["River Sounds for Sleep 🏞 Flowing Water and Forest Streams | {m} Min", "Mountain Stream Ambience 🏞 Water Sounds for Focus and Study | {m} Min", "Relaxing River Sounds 🏞 Nature Water Noise for Calm | {m} Min"],
    "storm": ["Thunderstorm Sounds for Deep Sleep ⛈ Rain and Thunder | {m} Min", "Rain and Thunder Ambience ⛈ Storm Sounds to Relax | {m} Min", "Lightning Storm Over the Hills ⛈ Thunder Sounds for Sleep | {m} Min"],
    "snow": ["Snowfall Ambience ❄ Quiet Winter Wind for Sleep and Calm | {m} Min", "Falling Snow in the Forest ❄ Cozy Winter Sounds to Relax | {m} Min", "Winter Wind and Snowy Landscapes ❄ Calm Ambience | {m} Min"],
    "autumn": ["Autumn Rain Sounds 🍂 Cozy Rain on the Lake for Sleep | {m} Min", "Rainy Autumn Morning 🍂 Calm Rain Ambience for Study | {m} Min", "Soft Autumn Rain to Relax 🍂 Rain Sounds for Reading | {m} Min"],
}
USE = "Perfect for sleep, studying, reading, meditation, focus or just a calm background."
HASH = {"rain": "#rainsounds #sleepsounds #relaxing", "ocean": "#oceansounds #wavesounds #relaxing", "river": "#riversounds #naturesounds #relaxing",
        "storm": "#thunderstorm #rainandthunder #sleepsounds", "snow": "#snowfall #winterambience #relaxing", "autumn": "#rainsounds #autumn #relaxing"}
DESC = {
    "rain": "Real rain footage and real rain recordings, looped without a break.",
    "ocean": "Real ocean footage with a recording of waves on a beach, looped without a break.",
    "river": "Real river and stream footage with recordings of flowing water, looped without a break.",
    "storm": "Real thunderstorm recordings over real storm footage, looped without a break.",
    "snow": "Real snowfall footage with a soft wind (the wind sound is generated), looped without a break.",
    "autumn": "Real autumn rain footage with real rain recordings, looped without a break.",
}
CREDITS = "Footage and recordings: public domain / CC0 material from Wikimedia Commons, edited and looped."


def slot_index(now: dt.datetime, slot: int) -> int:
    return (now.date() - dt.date(2026, 10, 25)).days * 3 + slot


def plan(idx: int) -> dict:
    kind = KINDS[idx % len(KINDS)]
    title = T[kind][(idx // len(KINDS)) % 3].format(m=MINUTES)
    return {"id": f"{kind}-{idx:04d}", "kind": kind, "hours": round(MINUTES / 60, 4), "seed": 1000 + idx, "title": title,
            "description": f"{DESC[kind]} {USE}\n\n{CREDITS}\n\n{HASH[kind]}",
            "tags": ["ambient", "sleep sounds", "relaxing", kind, "white noise", "study"]}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(plan(int(sys.argv[1]))))
