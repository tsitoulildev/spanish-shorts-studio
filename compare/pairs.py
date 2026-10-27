"""Which two countries each Short compares. Curated rivalries first (what people search for and argue about), with a
Spanish-speaking or English-speaking country in every pair (the channel teaches English<->Spanish); then neighbours."""
from __future__ import annotations
import json, pathlib

CURATED = [("ESP", "MEX"), ("ARG", "BRA"), ("USA", "MEX"), ("ESP", "GBR"), ("COL", "VEN"), ("CHL", "PER"), ("ARG", "CHL"), ("ESP", "PRT"),
           ("USA", "CHN"), ("ESP", "ITA"), ("MEX", "COL"), ("ARG", "URY"), ("ESP", "FRA"), ("USA", "CAN"), ("GBR", "FRA"), ("ESP", "ARG"),
           ("PER", "ECU"), ("CUB", "DOM"), ("USA", "RUS"), ("MEX", "BRA"), ("COL", "ECU"), ("BOL", "PRY"), ("ESP", "DEU"), ("USA", "GBR"),
           ("GTM", "HND"), ("CRI", "PAN"), ("MEX", "CAN"), ("ARG", "MEX"), ("CHL", "BOL"), ("VEN", "BRA"), ("ESP", "GRC"), ("USA", "IND"),
           ("GBR", "IRL"), ("AUS", "NZL"), ("USA", "JPN"), ("COL", "PER"), ("SLV", "NIC"), ("ESP", "MAR"), ("MEX", "ESP"), ("USA", "BRA"),
           ("CAN", "AUS"), ("ARG", "COL"), ("CHL", "URY"), ("GBR", "DEU"), ("USA", "DEU"), ("ESP", "NLD"), ("MEX", "PER"), ("ARG", "PER"),
           ("ESP", "CHL"), ("USA", "ESP"), ("GRC", "TUR"), ("CHN", "IND"), ("JPN", "KOR"), ("DEU", "FRA"), ("ITA", "FRA"), ("BRA", "COL")]


def pair(idx: int) -> tuple[str, str]:
    if idx < len(CURATED):
        return CURATED[idx]
    # afterwards: every Spanish/English-speaking country against every other country with data, in a fixed order
    data = json.load(open(pathlib.Path(__file__).parent / "data" / "worldbank.json", encoding="utf-8"))
    hubs = ["ESP", "MEX", "ARG", "COL", "CHL", "PER", "USA", "GBR", "CAN", "AUS", "VEN", "ECU", "CUB", "URY", "BOL", "PRY", "DOM", "GTM", "HND", "CRI", "PAN", "SLV", "NIC", "IRL", "NZL"]
    others = sorted(c for c in data["countries"] if "NY.GDP.PCAP.CD" in data["values"] and c in data["values"]["NY.GDP.PCAP.CD"]
                    and c in data["values"]["SP.POP.TOTL"] and data["values"]["SP.POP.TOTL"][c][0] > 2e6)
    seen = {frozenset(p) for p in CURATED}
    k = idx - len(CURATED)
    for h in hubs:
        for o in others:
            if o == h or frozenset((h, o)) in seen:
                continue
            seen.add(frozenset((h, o)))
            if k == 0:
                return (h, o)
            k -= 1
    raise IndexError("no more pairs")
