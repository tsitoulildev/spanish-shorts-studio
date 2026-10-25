import urllib.request, urllib.parse, os, sys
B = "https://upload.wikimedia.org/wikipedia/commons/"
FILES = {
 "audio/rain_thunder.ogg": "4/42/Rain_and_thunder.ogg",
 "audio/rain1.ogg": "0/0e/Rain_%281%29.ogg",
 "audio/rain_veranda.ogg": "7/7c/Rain_on_a_veranda_and_t.ogg",
 "audio/rain_thunder_birds.ogg": "a/ab/Rain_thunder_and_birds.ogg",
 "audio/rain_thunder_steps.ogg": "0/09/Rain_thunder_steps.ogg",
 "audio/fire_crackle.ogg": "8/80/Bones_breaking_wood_fire_ice_crackling.ogg",
 "video/rain_window_night.webm": "9/95/Raindrops_against_the_window_in_the_night_city%2C_Las_Palmas.webm",
 "video/fire.webm": "c/cf/ABOedit2015-Video-Fire.webm",
 "video/lightning_storm.ogv": "6/66/Lightning_storm_over_Colorado%2C_USA.ogg",
}
os.makedirs("assets/audio", exist_ok=True); os.makedirs("assets/video", exist_ok=True)
import time
for dst, src in FILES.items():
    if not dst.startswith("video"): continue
    for attempt in range(6):
      try:
        r = urllib.request.urlopen(urllib.request.Request(B + src, headers={"User-Agent": "ambient-fetch/1.0 (github actions; contact via repo)"}), timeout=180)
        open("assets/" + dst, "wb").write(r.read()); print("ok", dst, os.path.getsize("assets/" + dst)); break
      except Exception as e:
        print("retry", dst, e); time.sleep(45)
    time.sleep(20)
