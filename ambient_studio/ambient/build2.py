"""Real CC0 footage + real public-domain recordings, looped seamlessly.
python -m ambient.build2 --kind rain|storm|fire --hours 3 --out out.mp4"""
from __future__ import annotations
import argparse, pathlib, subprocess, tempfile
import numpy as np
from scipy.io import wavfile
from . import synth

SR = synth.SR
ROOT = pathlib.Path(__file__).resolve().parent.parent / "assets"
VIDEO = {"rain": "rain_window_night.webm", "storm": "lightning_storm.ogv", "fire": "fire.webm"}
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


def audio(kind: str, seconds: int, tmp: pathlib.Path, seed: int) -> pathlib.Path:
    A = ROOT / "audio"
    if kind in ("rain", "storm"):
        x = _loop(_load(A / "rain1.ogg", tmp), seconds) + 0.5 * _loop(_load(A / "rain_veranda.ogg", tmp), seconds, 3, shift=7)
        if kind == "storm":
            x = 0.9 * x + 0.8 * _loop(_load(A / "rain_thunder.ogg", tmp), seconds, 3, shift=2)
    else:
        x = synth.make_loop("fire", seconds, seed)
    x = synth.normalise(x, -24)
    wavfile.write(str(tmp / "a.wav"), SR, (np.clip(x.T, -1, 1) * 32767).astype(np.int16))
    return tmp / "a.wav"


def build(kind: str, hours: float, seed: int, out: str, audio_s: int = 300) -> None:
    tmp = pathlib.Path(tempfile.mkdtemp())
    wav = audio(kind, audio_s, tmp, seed)
    fl = FIRE_FILTER if kind == "fire" else WIDE_FILTER
    fc = fl + ";[x]split[p][q];[q]reverse[r];[p][r]concat=n=2:v=1:a=0[v]"  # ping-pong: no visible jump at the loop point
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ROOT / "video" / VIDEO[kind]), "-filter_complex", fc, "-map", "[v]",
                    "-an", "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", str(tmp / "v.mp4")], check=True)
    dur = int(hours * 3600)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(-(-dur // audio_s)), "-i", str(wav), "-t", str(dur),
                    "-c:a", "aac", "-b:a", "160k", str(tmp / "a.m4a")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(tmp / "v.mp4"), "-i", str(tmp / "a.m4a"),
                    "-map", "0:v", "-map", "1:a", "-c", "copy", "-t", str(dur), "-movflags", "+faststart", out], check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(VIDEO))
    ap.add_argument("--hours", type=float, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(a.kind, a.hours, a.seed, a.out)
