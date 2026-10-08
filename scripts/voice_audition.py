"""Voice audition: render the same Spanish text with every candidate voice so a person can listen and choose.

Runs on a GitHub runner (workflow voices.yml). Claude cannot hear audio, so this only produces the samples; the choice is
made by listening. Every engine is wrapped in try/except: one failing engine never stops the others.

Output folder: <out>/<id>.mp3 plus index.json describing each sample (engine, voice, licence note).
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

TEXT = "Buenos días. Buenas tardes. Buenas noches. ¿Cómo estás? Estoy bien, gracias. Mucho gusto. Hasta luego."
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
MAX_PIPER_VOICES = 14
MAX_SPEAKERS_PER_VOICE = 3


def to_mp3(src: Path, dst: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-b:a", "96k", str(dst)], check=True)


def fetch(url: str, dst: Path) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            dst.write_bytes(r.read())
        return True
    except Exception as exc:          # noqa: BLE001
        print(f"  download failed {url}: {exc}")
        return False


def kokoro(out: Path, index: list) -> None:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipe = KPipeline(lang_code="e")
    for v, note in (("ef_dora", "female (Kokoro, current voice)"), ("em_alex", "male"), ("em_santa", "male")):
        audio = [a.detach().cpu().numpy() if hasattr(a, "detach") else a for _, _, a in pipe(TEXT, voice=v, speed=0.95)]
        wav = out / f"kokoro_{v}.wav"
        sf.write(wav, np.concatenate(audio), 24000)
        to_mp3(wav, out / f"kokoro_{v}.mp3")
        wav.unlink()
        index.append({"id": f"kokoro_{v}", "engine": "Kokoro", "voice": v, "note": note,
                      "licence": "Apache-2.0 code; weights licence not separately confirmed"})


def piper(out: Path, index: list) -> None:
    work = out / "_piper"
    work.mkdir(exist_ok=True)
    voices_json = work / "voices.json"
    if not fetch(HF + "voices.json", voices_json):
        return
    voices = json.loads(voices_json.read_text(encoding="utf-8"))
    keys = sorted(k for k, v in voices.items() if v["language"]["family"] == "es")
    order = {"high": 0, "medium": 1, "low": 2, "x_low": 3}
    keys.sort(key=lambda k: (order.get(voices[k]["quality"], 9), k))
    print("Piper Spanish voices found:", keys)
    for key in keys[:MAX_PIPER_VOICES]:
        v = voices[key]
        paths = list(v["files"])
        onnx = next((p for p in paths if p.endswith(".onnx")), None)
        cfg = next((p for p in paths if p.endswith(".onnx.json")), None)
        card = next((p for p in paths if p.endswith("MODEL_CARD")), None)
        if not onnx or not cfg:
            continue
        model, config = work / Path(onnx).name, work / Path(cfg).name
        if not (fetch(HF + onnx, model) and fetch(HF + cfg, config)):
            continue
        licence = "see model card"
        if card and fetch(HF + card, work / f"{key}.card.txt"):
            txt = (work / f"{key}.card.txt").read_text(encoding="utf-8", errors="ignore")
            licence = " ".join(line.strip() for line in txt.splitlines() if "licen" in line.lower())[:240] or "see model card"
        speakers = max(1, int(v.get("num_speakers") or 1))
        for sid in range(min(speakers, MAX_SPEAKERS_PER_VOICE)):
            name = f"piper_{key}" + (f"_s{sid}" if speakers > 1 else "")
            wav = out / f"{name}.wav"
            cmd = [sys.executable, "-m", "piper", "-m", str(model), "-f", str(wav)]
            if speakers > 1:
                cmd += ["--speaker", str(sid)]
            r = subprocess.run(cmd, input=TEXT, text=True, capture_output=True)
            if r.returncode != 0 or not wav.exists():
                print(f"  piper failed for {name}: {r.stderr[-300:]}")
                continue
            to_mp3(wav, out / f"{name}.mp3")
            wav.unlink()
            index.append({"id": name, "engine": "Piper", "voice": key + (f" speaker {sid}" if speakers > 1 else ""),
                          "note": f"quality {v['quality']}, gender unknown: listen", "licence": licence})


def edge(out: Path, index: list) -> None:
    import edge_tts

    async def one(voice: str, label: str) -> None:
        mp3 = out / f"edge_{voice}.mp3"
        await edge_tts.Communicate(TEXT, voice, rate="-5%").save(str(mp3))
        index.append({"id": f"edge_{voice}", "engine": "Edge-TTS", "voice": voice, "note": label,
                      "licence": "unofficial Microsoft online service: quality benchmark only, NOT approved for production"})

    for voice, label in (("es-MX-DaliaNeural", "female, Mexico"), ("es-ES-ElviraNeural", "female, Spain"),
                         ("es-US-PalomaNeural", "female, US Spanish"), ("es-AR-ElenaNeural", "female, Argentina")):
        try:
            asyncio.run(one(voice, label))
        except Exception as exc:      # noqa: BLE001
            print(f"  edge failed for {voice}: {exc}")


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "output/voices")
    out.mkdir(parents=True, exist_ok=True)
    index: list = []
    for fn in (kokoro, piper, edge):
        try:
            print(f"== {fn.__name__}")
            fn(out, index)
        except Exception as exc:      # noqa: BLE001
            print(f"{fn.__name__} failed: {exc}")
    (out / "index.json").write_text(json.dumps({"text": TEXT, "samples": index}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(index)} samples written to {out}")
    return 0 if index else 1


if __name__ == "__main__":
    raise SystemExit(main())
