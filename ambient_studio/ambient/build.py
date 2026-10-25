"""python -m ambient.build --kind storm --hours 3 --seed 1 --out out.mp4"""
from __future__ import annotations
import argparse, subprocess, tempfile, pathlib
from . import synth, visual

TITLES = {
    "rain": "Gentle Rain on the Window", "storm": "Thunderstorm and Heavy Rain",
    "fire": "Crackling Fireplace", "rainfire": "Rain and Fireplace",
}


def build(kind: str, hours: float, seed: int, out: str, audio_s: int = 180, video_s: int = 20) -> None:
    tmp = pathlib.Path(tempfile.mkdtemp())
    wav, vid = tmp / "a.wav", tmp / "v.mp4"
    synth.write_wav(wav, synth.normalise(synth.make_loop(kind, audio_s, seed)))
    visual.render_loop("fire" if kind == "fire" else kind, video_s, seed, str(vid))
    dur = int(hours * 3600)
    reps = -(-dur // audio_s)
    # audio: loop the seamless wav, encode once (AAC copy-looping would click at seams)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", str(reps), "-i", str(wav), "-t", str(dur),
                    "-c:a", "aac", "-b:a", "128k", str(tmp / "a.m4a")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(vid), "-i", str(tmp / "a.m4a"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-t", str(dur), "-movflags", "+faststart", out], check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(TITLES))
    ap.add_argument("--hours", type=float, default=3)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(a.kind, a.hours, a.seed, a.out)
