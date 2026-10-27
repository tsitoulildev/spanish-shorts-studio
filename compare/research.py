"""Rank country pairs by demand. Run weekly in CI; writes compare/data/ranking.json.
Signals (all free):
 1. Interest in each country: Wikipedia page views of its English + Spanish article over the last 60 days (Wikimedia REST API).
 2. Rivalry/neighbour bonus: curated rivalries x2, same World Bank region x1.25; pairs need one English- or Spanish-speaking country (channel audience).
 3. If the secret YT_API_KEY exists: YouTube demand for the top candidates = median views of the 10 most viewed Shorts for "<A> vs <B>"
    (search.list, 100 quota units each, capped at MAX_YT searches per run). Demand multiplies the score.
"""
from __future__ import annotations
import datetime as dt, json, math, os, pathlib, statistics, sys, time, urllib.parse, urllib.request

HERE = pathlib.Path(__file__).parent
DATA = json.load(open(HERE / "data" / "worldbank.json", encoding="utf-8"))
QID = json.load(open(HERE / "data" / "wikidata.json"))
sys.path.insert(0, str(HERE))
from pairs import CURATED  # noqa: E402

UA = {"User-Agent": "compare-shorts research (https://github.com/tsitoulildev/spanish-shorts-studio)"}
HUBS = {"ESP", "MEX", "ARG", "COL", "CHL", "PER", "USA", "GBR", "CAN", "AUS", "VEN", "ECU", "CUB", "URY", "BOL", "PRY", "DOM", "GTM", "HND",
        "CRI", "PAN", "SLV", "NIC", "IRL", "NZL"}
RICH = {"USA", "GBR", "CAN", "AUS"}
MAX_YT = int(os.environ.get("MAX_YT", "40"))


def get(url, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for a in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:
            if "404" in str(e):
                return None
            time.sleep(5 * (a + 1))
    return None


def titles():
    ids = [q for c, q in QID.items() if c in DATA["countries"]]
    out = {}
    for i in range(0, len(ids), 50):
        r = get("https://www.wikidata.org/w/api.php", {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "sitelinks",
                                                        "sitefilter": "enwiki|eswiki", "format": "json"})
        for q, e in (r or {}).get("entities", {}).items():
            out[q] = {s: v["title"] for s, v in e.get("sitelinks", {}).items()}
    return out


def views(project, title, start, end):
    t = urllib.parse.quote(title.replace(" ", "_"), safe="")
    r = get(f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/all-access/user/{t}/daily/{start}/{end}")
    return sum(x["views"] for x in (r or {}).get("items", []))


def yt_demand(a, b, key):
    q = f"{DATA['countries'][a]['en']} vs {DATA['countries'][b]['en']}"
    r = get("https://www.googleapis.com/youtube/v3/search", {"part": "id", "q": q, "type": "video", "videoDuration": "short",
                                                              "order": "viewCount", "maxResults": 10, "key": key})
    ids = [x["id"]["videoId"] for x in (r or {}).get("items", [])]
    if not ids:
        return 0
    s = get("https://www.googleapis.com/youtube/v3/videos", {"part": "statistics", "id": ",".join(ids), "key": key})
    v = [int(x["statistics"].get("viewCount", 0)) for x in (s or {}).get("items", [])]
    return statistics.median(v) if v else 0


def main(out):
    end = dt.date.today() - dt.timedelta(days=1); start = end - dt.timedelta(days=60)
    S, E = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
    tt = titles()
    interest = {}
    for c, q in QID.items():
        if c not in DATA["countries"] or q not in tt:
            continue
        v = 0
        if "enwiki" in tt[q]:
            v += views("en.wikipedia", tt[q]["enwiki"], S, E)
        if "eswiki" in tt[q]:
            v += views("es.wikipedia", tt[q]["eswiki"], S, E)
        interest[c] = v
        time.sleep(0.2)
    print("interest measured for", len(interest), "countries")
    cur = {frozenset(p) for p in CURATED}
    top = sorted(interest, key=interest.get, reverse=True)[:80]
    cands = []
    for i, a in enumerate(top):
        for b in top[i + 1:]:
            if a not in HUBS and b not in HUBS:
                continue
            s = math.sqrt(interest[a] * interest[b])
            if a in RICH or b in RICH:  # English-speaking high-RPM audiences (US/UK/CA/AU): Shorts pay several times more there
                s *= 1.3
            if frozenset((a, b)) in cur:
                s *= 2
            elif DATA["countries"][a]["region"] == DATA["countries"][b]["region"]:
                s *= 1.25
            cands.append({"a": a, "b": b, "wiki": round(s)})
    cands.sort(key=lambda x: -x["wiki"])
    key = os.environ.get("YT_API_KEY", "").strip()
    if key:
        for c in cands[:MAX_YT]:
            c["yt_median_views"] = yt_demand(c["a"], c["b"], key)
        # demand matters most: rank the measured ones by wiki score x YouTube demand
        for c in cands[:MAX_YT]:
            c["score"] = c["wiki"] * (1 + math.log10(1 + c["yt_median_views"]))
    for c in cands:
        c.setdefault("score", c["wiki"])
    cands.sort(key=lambda x: -x["score"])
    json.dump({"generated": str(dt.date.today()), "window": [S, E], "youtube_checked": bool(key), "interest": interest, "pairs": cands[:600]},
              open(out, "w"), indent=0)
    print("top pairs:", [(c["a"], c["b"], c["score"]) for c in cands[:15]])


if __name__ == "__main__":
    main(sys.argv[1])
