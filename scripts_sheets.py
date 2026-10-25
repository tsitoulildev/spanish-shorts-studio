import sys, subprocess, pathlib, urllib.parse
sys.path.insert(0, "ambient_studio")
from ambient.build2 import fetch
from ambient.themes import THEMES
out = pathlib.Path("/tmp/sheets"); out.mkdir(exist_ok=True)
extra = ["commons:" + t for t in [
 "Cosumnes River Preserve (37682282934).webm", "Klamath River (28205908032).webm", "Rogue River rafting -- Wild and Scenic Rogue River (21222575954).webm",
 "Smith River Falls Recreation Site (34664512116).webm", "White Wild and Scenic River (30126165673).webm", "Yakima River Canyon (26511143804).webm",
 "Delaneys Falls.webm", "Little Applegate River (50982975823).webm", "Chopaka Lake (28054947691).webm", "Mann Lake Recreation Site (33051524893).webm",
 "Slow falling across Lake Okanagan near Maude Roxby Wetlands.webm", "KLO Creek gurgles during an early winter snowfall.webm",
 "Ocean surface waves 03.ogv", "Ocean surface waves 05.ogv", "Ocean surface waves 08.ogv", "Ocean surface waves 10.ogv", "Irminger Bow in Waves (OOI).webm",
 "Fire آتش 01.ogv", "Fire آتش 02.ogv", "Fire آتش 03.ogv", "Fire آتش 05.ogv", "Fire آتش 09.ogv",
 "Little White in Early Spring, as seen from Okanagan Lake.webm", "Aerial View of freezing fog in the Okanagan Highlands.webm"]]
refs = []
for t in THEMES.values():
    refs += [v for v in t["video"] if v.startswith("commons:")]
refs += extra
seen = set()
for i, ref in enumerate(dict.fromkeys(refs)):
    try:
        f = fetch(ref)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout.strip() or 0)
        fr = []
        for k, frac in enumerate((0.1, 0.5, 0.9)):
            p = out / f"f{i}_{k}.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(d * frac), "-i", str(f), "-frames:v", "1", "-vf", "scale=426:240:force_original_aspect_ratio=decrease,pad=426:240:(ow-iw)/2:(oh-ih)/2", str(p)])
            fr.append(p)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y"] + sum([["-i", str(p)] for p in fr], []) + ["-filter_complex", "hstack=inputs=3", str(out / f"sheet_{i:02d}.jpg")])
        (out / f"sheet_{i:02d}.txt").write_text(ref[8:])
        print("ok", i, ref)
        f.unlink()  # keep the cache small
    except BaseException as e:
        print("FAIL", ref, e)
