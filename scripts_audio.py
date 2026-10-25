import sys, subprocess, pathlib, signal, re
sys.path.insert(0, "ambient_studio")
from ambient.build2 import fetch
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("too long")))
OUT = pathlib.Path("clips"); OUT.mkdir(exist_ok=True)
AUDIO = {"thunder1": "Thunderstorm after hot summer day 17 minutes 01 of 04.ogg", "thunder3": "Thunderstorm after hot summer day 17 minutes 03 of 04.ogg",
         "ocean_tropical": "Ocean Waves on a Tropical Beach.ogg", "pebble_beach": "On a pebble beach.ogg",
         "stream_close": "433589 jackthemurray stream-river-water-up-close.wav", "swale": "Swale.ogg",
         "shallow_river": "Shallow small river with stony riverbed.ogg", "rain_other": "Rain thunder and other noises.ogg"}
VIDEO = {"ocean__Ocean_surface_waves": "Ocean surface waves.ogv", "ocean__Ocean_surface_waves_02": "Ocean surface waves 02.ogv", "ocean__Ocean_surface_waves_04": "Ocean surface waves 04.ogv"}
(OUT / "audio").mkdir(exist_ok=True)
for name, title in AUDIO.items():
    try:
        signal.alarm(900); f = fetch("commons:" + title)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-t", "400", "-i", str(f), "-ac", "2", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "4", str(OUT / "audio" / f"{name}.ogg")], check=True)
        # sheet substitute: duration + mean volume, so I can sanity check without listening
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(OUT / "audio" / f"{name}.ogg"), "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
        print("ok", name, [l.strip() for l in r.splitlines() if "mean_volume" in l or "max_volume" in l or "Duration" in l], flush=True)
        f.unlink(); signal.alarm(0)
    except BaseException as e:
        signal.alarm(0); print("FAIL", title, e, flush=True)
for name, title in VIDEO.items():
    try:
        signal.alarm(900); f = fetch("commons:" + title)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-t", "30", "-i", str(f), "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
                        "-c:v", "libx264", "-crf", "24", "-maxrate", "3000k", "-bufsize", "6000k", "-pix_fmt", "yuv420p", str(OUT / f"{name}.mp4")], check=True)
        f.unlink(); signal.alarm(0); print("ok", name, flush=True)
    except BaseException as e:
        signal.alarm(0); print("FAIL", title, e, flush=True)
