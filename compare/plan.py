"""Metadata for slot idx: pair, seed, title, description, tags (Education category)."""
from __future__ import annotations
import datetime as dt, json, sys
from pairs import pair
import render


def flag_emoji(iso2):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in iso2.upper())


def slot_index(now: dt.datetime, slot: int) -> int:
    return (now.date() - dt.date(2026, 10, 27)).days * 3 + slot


def plan(idx: int) -> dict:
    a, b = pair(idx)
    ca, cb = render.DATA["countries"][a], render.DATA["countries"][b]
    seed = 5000 + idx
    cats = render.choose(a, b, seed)
    words = "\n".join(f"{render.CAT[k][1]} = {render.CAT[k][0].capitalize().replace('gdp', 'GDP').replace('Gdp', 'GDP')}" for k in cats)
    title = f"{ca['en']} vs {cb['en']} {flag_emoji(ca['iso2'])}{flag_emoji(cb['iso2'])} Who Wins? | {ca['es']} vs {cb['es']} #shorts"
    if len(title) > 100:
        title = f"{ca['en']} vs {cb['en']} {flag_emoji(ca['iso2'])}{flag_emoji(cb['iso2'])} Who Wins? #shorts"
    desc = (f"{ca['en']} vs {cb['en']}: {len(cats)} rounds with real data. Who wins? Comment your country!\n"
            f"{ca['es']} contra {cb['es']}: ¿quién gana? ¡Comenta tu país!\n\n"
            f"Learn the Spanish words in this video:\n{words}\n\n"
            f"Data: World Bank Open Data (CC BY 4.0), data.worldbank.org, latest available year per country. Maps: Natural Earth (public domain).\n\n"
            f"#countrycomparison #{ca['en'].replace(' ', '').lower()} #{cb['en'].replace(' ', '').lower()} #learnspanish #shorts")
    tags = ["country comparison", f"{ca['en']} vs {cb['en']}", ca["en"], cb["en"], ca["es"], cb["es"], "learn spanish", "who wins", "geography", "data"]
    return {"id": f"cmp-{idx:04d}-{a}-{b}", "a": a, "b": b, "seed": seed, "title": title, "description": desc, "tags": tags, "categoryId": "27"}


if __name__ == "__main__":
    print(json.dumps(plan(int(sys.argv[1])), ensure_ascii=False))
