"""Snapshot of World Bank indicators (CC BY 4.0, https://data.worldbank.org) with English and Spanish country names.
Run in CI (needs internet): python compare/fetch_data.py compare/data/worldbank.json"""
import json, sys, time, urllib.request

IND = ["SP.POP.TOTL", "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD", "AG.SRF.TOTL.K2", "SP.DYN.LE00.IN", "MS.MIL.XPND.CD", "ST.INT.ARVL",
       "IT.NET.USER.ZS", "SL.UEM.TOTL.ZS", "FP.CPI.TOTL.ZG", "NE.EXP.GNFS.CD", "SH.XPD.CHEX.PC.CD", "SE.XPD.TOTL.GD.ZS",
       "EN.POP.DNST", "SP.URB.TOTL.IN.ZS", "EG.ELC.RNEW.ZS", "AG.LND.FRST.ZS", "SP.DYN.TFRT.IN", "SP.POP.65UP.TO.ZS", "IS.AIR.PSGR"]


def get(url):
    for a in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "compare-shorts/1.0"}), timeout=120) as r:
                return json.load(r)
        except Exception as e:
            print("retry", url, e); time.sleep(10)
    raise SystemExit("failed " + url)


def countries(lang):
    d = get(f"https://api.worldbank.org/v2/{lang}/country?format=json&per_page=400")[1]
    return {c["id"]: c for c in d if c["region"]["id"] != "NA"}  # drop aggregates (regions, income groups)


en, es = countries("en"), countries("es")
out = {"source": "World Bank Open Data (CC BY 4.0), data.worldbank.org", "fetched": time.strftime("%Y-%m-%d"), "countries": {}, "values": {}}
for iso3, c in en.items():
    out["countries"][iso3] = {"iso2": c["iso2Code"].lower(), "en": c["name"], "es": es.get(iso3, c)["name"], "region": c["region"]["value"]}
for ind in IND:
    rows = get(f"https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&per_page=20000&mrnev=1")
    vals = {}
    for r in rows[1] or []:
        if r["countryiso3code"] in en and r["value"] is not None:
            vals[r["countryiso3code"]] = [r["value"], r["date"]]
    out["values"][ind] = vals
    print(ind, len(vals))
    time.sleep(1)
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=0)
