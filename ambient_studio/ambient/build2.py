"""Real CC0 footage + real public-domain recordings, looped seamlessly.
python -m ambient.build2 --kind rain|storm|fire --hours 3 --out out.mp4"""
from __future__ import annotations
import argparse, pathlib, subprocess, tempfile
import numpy as np
from scipy.io import wavfile
from . import synth
from .themes import THEMES
import time, urllib.parse, urllib.request

SR = synth.SR
ROOT = pathlib.Path(__file__).resolve().parent.parent / "assets"
FIRE_FILTER = ("[0:v]split[a][b];[a]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=40:5,eq=brightness=-0.15[bg];"
               "[b]scale=1080:1080[fg];[bg][fg]overlay=(W-w)/2:0,fps=30[x]")
WIDE_FILTER = "[0:v]scale=1920:1080,fps=30[x]"


def _load(path: pathlib.Path, tmp: pathlib.Path) -> np.ndarray:
    wav = tmp / "t.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(path), "-ar", str(SR), "-ac", "2", str(wav)], check=True)
    return wavfile.read(str(wav))[1].T / 32768.0


def _loop(x: np.ndarray, seconds: float, fade: float = 4.0, shift: float = 0.0) -> np.ndarray:
    f = int(SR * fade)
    out = np.zeros((2, int(seconds * SR) + f))
    pos = -int(shift * SR)
    while pos < out.shape[1]:
        w = np.ones(x.shape[1]); w[:f] = np.sin(np.linspace(0, np.pi / 2, f)); w[-f:] = np.cos(np.linspace(0, np.pi / 2, f))
        a, b = max(0, pos), min(out.shape[1], pos + x.shape[1])
        out[:, a:b] += (x * w)[:, a - pos:b - pos]
        pos += x.shape[1] - f
    return out[:, :int(seconds * SR)]


def fetch(ref: str) -> pathlib.Path:
    """repo:<path> is shipped; commons:<File title> is downloaded once (retry on 429) and cached."""
    kind, name = ref.split(":", 1)
    if kind == "repo":
        return ROOT / name
    cache = pathlib.Path.home() / ".cache" / "ambient"; cache.mkdir(parents=True, exist_ok=True)
    dst = cache / urllib.parse.quote(name, safe="")
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(name.replace(" ", "_"))
    for attempt in range(3):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ambient-studio/1.0 (github actions; public-domain/CC0 only)"}), timeout=300)
            dst.write_bytes(r.read()); time.sleep(5); return dst
        except Exception as e:
            print("retry", name, e); time.sleep(20)
    raise SystemExit(f"could not download {name}")


def audio(kind: str, seconds: int, tmp: pathlib.Path, seed: int) -> pathlib.Path:
    r = np.random.default_rng(seed)  # seed varies offsets and levels so videos of one theme differ
    x = np.zeros((2, int(seconds * SR)))
    for src, gain, fade in THEMES[kind]["audio"]:
        g = gain * (r.uniform(0.8, 1.15) if gain < 1 else 1.0)
        if src.startswith("synth:"):
            x += g * synth.make_loop(src[6:], seconds, seed)
        else:
            x += g * _loop(_load(fetch(src), tmp), seconds, fade, shift=r.uniform(0, 40))
    x = synth.normalise(x, -24)
    wavfile.write(str(tmp / "a.wav"), SR, (np.clip(x.T, -1, 1) * 32767).astype(np.int16))
    return tmp / "a.wav"


def video(kind: str, seed: int, tmp: pathlib.Path) -> pathlib.Path:
    """Every clip is cropped to 16:9 (square clips get a blurred fill), played forward then backward and faded at the edges;
    the clips of a theme are shuffled by the seed and joined into one loop."""
    refs = list(THEMES[kind]["video"]); np.random.default_rng(seed).shuffle(refs)
    parts = []
    for i, ref in enumerate(refs):
        src = fetch(ref)
        w, h = [int(v) for v in subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(src)],
                                               capture_output=True, text=True, check=True).stdout.strip().split(",")[:2]]
        sq = abs(w / h - 16 / 9) > 0.5
        fl = FIRE_FILTER if sq else WIDE_FILTER
        if not sq:
            fl = "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30[x]"
        out = tmp / f"c{i}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", "60", "-i", str(src), "-filter_complex",
                        fl + ";[x]split[p][q];[q]reverse[r];[p][r]concat=n=2:v=1:a=0,fade=t=in:d=0.6,setsar=1[v]", "-map", "[v]", "-an",
                        "-c:v", "libx264", "-crf", "24", "-maxrate", "2500k", "-bufsize", "5000k", "-pix_fmt", "yuv420p", str(out)], check=True)
        parts.append(out)
    lst = tmp / "list.txt"; lst.write_text("".join(f"file '{p}'\n" for p in parts))
    out = tmp / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True)
    return out


def build(kind: str, hours: float, seed: int, out: str, audio_s: int = 300) -> None:
    tmp = pathlib.Path(tempfile.mkdtemp())
    wav = audio(kind, audio_s, tmp, seed)
    vid = video(kind, seed, tmp)
    dur = int(hours * 3600)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(-(-dur // audio_s)), "-i", str(wav), "-t", str(dur),
                    "-c:a", "aac", "-b:a", "160k", str(tmp / "a.m4a")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(vid), "-i", str(tmp / "a.m4a"),
                    "-map", "0:v", "-map", "1:a", "-c", "copy", "-t", str(dur), "-movflags", "+faststart", out], check=True)
    import shutil; shutil.rmtree(tmp, ignore_errors=True)  # no leftovers


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(THEMES))
    ap.add_argument("--hours", type=float, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(a.kind, a.hours, a.seed, a.out)
