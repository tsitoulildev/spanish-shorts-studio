"""Download candidate CC0/PD clips slowly, store a trimmed 1080p copy (30 s, no audio) plus a contact sheet for review."""
import sys, subprocess, pathlib, signal, os, re
sys.path.insert(0, "ambient_studio")
from ambient.build2 import fetch
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("too long")))
OUT = pathlib.Path("clips"); OUT.mkdir(exist_ok=True)
T = """Klamath River (27693694384).webm|river
Running Stream Of Water.webm|river
Wallowa River (35001236162).webm|river
Sixes River (33895113543).webm|river
Cosumnes River Preserve (37682282934).webm|river
Klamath River (28205908032).webm|river
Yakima River Canyon (26511143804).webm|river
White Wild and Scenic River (30126165673).webm|river
Smith River Falls Recreation Site (34664512116).webm|river
Delaneys Falls.webm|river
Little Applegate River (50982975823).webm|forest
Snow falling in Charlton MA 2025-12-14.webm|snow
KLO Creek gurgles during an early winter snowfall.webm|snow
Aerial view of Lake Okanagan snowfall near Bertram Creek.webm|snow
Slow falling across Lake Okanagan near Maude Roxby Wetlands.webm|snow
Aerial View of freezing fog in the Okanagan Highlands.webm|snow
20141103Regen.ogv|autumn
Overlooking Browne Lake on a Calm Rainy Morning in Late Autumn.webm|autumn
Chopaka Lake (28054947691).webm|lake
Mann Lake Recreation Site (33051524893).webm|lake
Little White in Early Spring, as seen from Okanagan Lake.webm|lake
Ocean surface waves 03.ogv|ocean
Ocean surface waves 05.ogv|ocean
Ocean surface waves 08.ogv|ocean
Irminger Bow in Waves (OOI).webm|ocean
Fire آتش 01.ogv|fire
Fire آتش 03.ogv|fire
Fire آتش 05.ogv|fire
Fire آتش 09.ogv|fire""".splitlines()
def slug(t): return re.sub(r"[^A-Za-z0-9]+", "_", t.rsplit(".", 1)[0]).strip("_")[:60] or "clip"
for n, line in enumerate(T):
    title, tag = line.split("|")
    name = f"{tag}__{slug(title)}"
    try:
        signal.alarm(900)
        f = fetch("commons:" + title)
        mp4 = OUT / f"{name}.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-t", "30", "-i", str(f), "-an", "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
                        "-c:v", "libx264", "-crf", "24", "-maxrate", "3000k", "-bufsize", "6000k", "-pix_fmt", "yuv420p", str(mp4)], check=True)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout.strip())
        fr = []
        for k, frac in enumerate((0.1, 0.5, 0.9)):
            p = OUT / f"_{n}_{k}.png"
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(d * frac), "-i", str(mp4), "-frames:v", "1", "-vf", "scale=426:240", str(p)])
            fr.append(p)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y"] + sum([["-i", str(p)] for p in fr], []) + ["-filter_complex", "hstack=inputs=3", str(OUT / f"{name}.jpg")])
        for p in fr: p.unlink()
        f.unlink()
        signal.alarm(0); print("ok", name, flush=True)
    except BaseException as e:
        signal.alarm(0); print("FAIL", title, e, flush=True)
    if n % 4 == 3:
        subprocess.run("git add -A clips && git -c user.name=github-actions -c user.email=actions@github.com commit -qm 'clips (partial)' && git push -q origin HEAD:refs/heads/ambient-clips -f", shell=True)
