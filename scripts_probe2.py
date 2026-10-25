import json, urllib.request, urllib.parse, time
def get(u):
    for a in range(5):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "ambient-probe/1.0 (github actions)"}), timeout=60)
        except Exception as e:
            time.sleep(15)
    raise SystemExit("fail " + u)
def search(kind, q):
    p = dict(action="query", generator="search", gsrnamespace=6, gsrsearch=f"filetype:{kind} {q}", gsrlimit=30, prop="imageinfo",
             iiprop="url|size|extmetadata", iiextmetadatafilter="LicenseShortName", format="json")
    d = json.load(get("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p)))
    for pg in d.get("query", {}).get("pages", {}).values():
        i = pg["imageinfo"][0]; lic = i["extmetadata"].get("LicenseShortName", {}).get("value", "")
        if lic in ("CC0", "Public domain") or lic.startswith("CC0") or lic.lower().startswith("public domain") or lic.startswith("PD"):
            print(kind, "|", q, "|", pg["title"], "|", lic, "|", i.get("width"), "x", i.get("height"), "|", round(i.get("duration", 0)), "s |", i["size"])
    time.sleep(3)
for q in ["rain forest", "rain jungle", "thunderstorm", "snow falling", "snowfall winter", "waves beach", "ocean waves", "river stream", "waterfall", "forest wind trees", "mountain lake", "campfire", "fireplace", "autumn rain", "rain street", "storm clouds timelapse", "northern lights", "desert dunes", "stars night sky timelapse", "clouds timelapse", "fog forest", "sunset beach"]:
    search("video", q)
print("=== AUDIO")
for q in ["rain forest ambience", "thunder", "ocean waves", "beach waves", "river stream", "waterfall", "wind", "forest birds", "campfire crackling", "fire crackling", "snow", "night crickets", "jungle", "rain on roof", "rain on leaves", "thunderstorm"]:
    search("audio", q)
