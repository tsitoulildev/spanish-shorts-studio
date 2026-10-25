import json, urllib.request, urllib.parse, sys
def get(u, t=40):
    req = urllib.request.Request(u, headers={"User-Agent": "ambient-probe/1.0 (github actions)"})
    return urllib.request.urlopen(req, timeout=t)
def commons(kind, q):
    p = dict(action="query", generator="search", gsrnamespace=6, gsrsearch=f"filetype:{kind} {q}", gsrlimit=10, prop="imageinfo",
             iiprop="url|size|extmetadata", iiextmetadatafilter="LicenseShortName", format="json")
    try:
        d = json.load(get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)))
        for pg in d.get("query", {}).get("pages", {}).values():
            i = pg["imageinfo"][0]
            print(kind, q, "|", pg["title"], "|", i["extmetadata"].get("LicenseShortName", {}).get("value"), "|", i["size"], "|", i["url"])
    except Exception as e:
        print("commons fail", q, e)
for q in ["rain", "thunder", "fireplace", "crackling fire", "rainfall"]:
    commons("audio", q)
for q in ["rain window", "fireplace", "fire burning", "thunderstorm", "lightning"]:
    commons("video", q)
print("== pollinations")
try:
    r = get("https://image.pollinations.ai/prompt/cozy%20stone%20fireplace%20burning%20logs%20dark%20room%20photorealistic?width=1920&height=1080&nologo=true&seed=1", 150)
    b = r.read(); open("p.jpg", "wb").write(b); print("ok", r.status, len(b), r.headers.get("content-type"))
except Exception as e:
    print("pollinations fail", e)
print("== archive")
try:
    q = urllib.parse.urlencode({"q": "(rain OR thunder OR fireplace) AND mediatype:audio AND licenseurl:*publicdomain*", "fl[]": "identifier", "rows": 10, "output": "json"})
    print(get("https://archive.org/advancedsearch.php?" + q).read().decode()[:1500])
except Exception as e:
    print("archive fail", e)
for u in ["https://freesound.org/apiv2/search/text/?query=rain", "https://api.pexels.com/videos/search?query=rain", "https://pixabay.com/api/videos/?q=rain"]:
    try: print(u, get(u).status)
    except Exception as e: print(u, "->", e)
