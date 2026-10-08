"""Voice (TTS) engines and audio assembly for lessons.

Engines
- kokoro:      free, Apache-2.0 code, CPU-friendly. Spanish voice ef_dora (female). Owner rule: Spanish is always a female voice.
- mixed:       per-voice engine ('kokoro:<voice>' or 'piper:<voice>'), chosen from data/voices.json.
- chatterbox:  free, MIT, Multilingual (Spanish incl.). GPU recommended. Adds an inaudible watermark.
- tone:        offline test stand-in (sine beeps, NOT speech) used for tests and pipeline checks.

The real engines load heavy models and are meant to run on your own machine or a CI runner. They are imported lazily.
"""
from __future__ import annotations

import json
import struct
import subprocess
import wave
from pathlib import Path
from typing import Protocol

from .lessons import MAX_SHORT_SECONDS, LessonError, render_video

SAMPLE_RATE = 24000
# Kokoro leaves ~0.3-0.6 s of silence at the start and end of every clip. That dead air made the video drag
# (more than half of a 36 s Short was silence), so the edges are trimmed and only the designed pauses remain.
TRIM_EDGES = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
              "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse")
PAUSE_AFTER = {"slow": 0.3, "clear": 0.2, "normal": 0.2, "fast": 0.15}
KOKORO_SPEED = {"slow": 0.8, "clear": 0.92, "normal": 1.0, "fast": 1.05}

DEFAULT_VOICES = {
    "kokoro": {"en": "af_heart", "es": "ef_dora", "es_b": "ef_dora"},
    "chatterbox": {},
    "tone": {},
    "mixed": {"en": "kokoro:af_heart", "es": "piper:es_AR-daniela-high", "es_b": "piper:es_AR-daniela-high"},
}
KOKORO_LANG_CODES = {"en": "a", "es": "e", "fr": "f", "it": "i", "pt": "p", "hi": "h", "ja": "j", "zh": "z"}


class Engine(Protocol):
    name: str

    def synth(self, text: str, lang: str, speed: str, voice: str = "A") -> tuple[list[float], int]: ...


def write_wav(path: Path, samples, sample_rate: int) -> None:
    """Write mono 16-bit PCM from floats in [-1, 1] (list, numpy array or torch tensor)."""
    if hasattr(samples, "detach"):
        samples = samples.detach().cpu().numpy()
    if hasattr(samples, "tolist"):
        samples = samples.reshape(-1).tolist()
    frames = b"".join(struct.pack("<h", max(-32767, min(32767, int(s * 32767)))) for s in samples)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(frames)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


class ToneEngine:
    name = "tone"

    def synth(self, text, lang, speed, voice="A"):
        # Silence on purpose: this engine only checks timing/assembly and must never produce an annoying sound.
        secs = max(0.5, len(text.split()) * (0.55 if speed == "slow" else 0.38))
        return [0.0] * int(SAMPLE_RATE * secs), SAMPLE_RATE


class KokoroEngine:
    name = "kokoro"

    def __init__(self, voices: dict | None = None):
        try:
            from kokoro import KPipeline
        except ImportError as exc:
            raise RuntimeError("Kokoro is not installed. Run: pip install kokoro soundfile (and install espeak-ng).") from exc
        self._KPipeline = KPipeline
        self._pipes: dict[str, object] = {}
        self.voices = {**DEFAULT_VOICES["kokoro"], **(voices or {})}

    def synth(self, text, lang, speed, voice="A"):
        code = KOKORO_LANG_CODES.get(lang)
        key = f"{lang}_b" if voice == "B" and f"{lang}_b" in self.voices else lang
        if code is None or key not in self.voices:
            raise RuntimeError(f"No Kokoro voice configured for language '{lang}'. Pass --voice {lang}=<voice>.")
        pipe = self._pipes.setdefault(code, self._KPipeline(lang_code=code))
        chunks = []
        for _gs, _ps, audio in pipe(text, voice=self.voices[key], speed=KOKORO_SPEED.get(speed, 1.0)):
            a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else audio
            chunks.extend(a.reshape(-1).tolist())
        return chunks, 24000


class ChatterboxEngine:
    name = "chatterbox"

    def __init__(self, voices: dict | None = None, device: str = "cuda"):
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        except ImportError as exc:
            raise RuntimeError("Chatterbox is not installed. Run: pip install chatterbox-tts (Python 3.11, GPU recommended).") from exc
        self._model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")

    def synth(self, text, lang, speed, voice="A"):
        wav = self._model.generate(text, language_id=lang)
        return wav, self._model.sr


PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
PIPER_LENGTH = {"slow": 1.4, "clear": 1.2, "normal": 1.1, "fast": 1.0}   # length-scale: above 1 is slower
PIPER_CACHE = Path.home() / ".cache" / "scriptstudio" / "piper"


def split_speaker(voice: str) -> tuple[str, int | None]:
    """'es_ES-sharvard-medium@1' -> ('es_ES-sharvard-medium', 1); a voice without '@' has no speaker id."""
    name, _, sid = voice.partition("@")
    return name, (int(sid) if sid else None)


def piper_paths(voice: str) -> tuple[str, str]:
    """es_AR-daniela-high -> ('es/es_AR/daniela/high/es_AR-daniela-high.onnx', '...onnx.json')."""
    voice = split_speaker(voice)[0]
    locale, name, quality = voice.split("-")
    base = f"{locale.split('_')[0]}/{locale}/{name}/{quality}/{voice}"
    return base + ".onnx", base + ".onnx.json"


class PiperVoices:
    """Piper (rhasspy) voices run through its command line. Models are downloaded once and cached."""

    def __init__(self, cache: Path | None = None):
        self.cache = Path(cache) if cache else PIPER_CACHE

    def model(self, voice: str) -> Path:
        import urllib.request

        onnx, cfg = piper_paths(voice)
        self.cache.mkdir(parents=True, exist_ok=True)
        for rel in (onnx, cfg):
            dst = self.cache / Path(rel).name
            if not dst.exists() or dst.stat().st_size == 0:
                with urllib.request.urlopen(PIPER_BASE + rel, timeout=180) as r:
                    dst.write_bytes(r.read())
        return self.cache / Path(onnx).name

    def run(self, cmd: list[str], text: str) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, input=text, text=True, capture_output=True)

    def synth(self, voice: str, text: str, speed: str) -> tuple[list[float], int]:
        import sys
        import tempfile

        voice, speaker = split_speaker(voice)
        model = self.model(voice)
        with tempfile.TemporaryDirectory() as d:
            wav = Path(d) / "out.wav"
            base = [sys.executable, "-m", "piper", "-m", str(model), "-f", str(wav)]
            if speaker is not None:
                base += ["--speaker", str(speaker)]
            scale = PIPER_LENGTH.get(speed, 1.0)
            r = self.run(base + (["--length-scale", str(scale)] if scale != 1.0 else []), text)
            if (r.returncode != 0 or not wav.exists()) and scale != 1.0:
                print(f"note: piper rejected --length-scale ({r.stderr[-120:].strip()}); using normal speed")
                r = self.run(base, text)
            if r.returncode != 0 or not wav.exists():
                raise RuntimeError(f"Piper failed for voice {voice}: {r.stderr[-300:]}")
            with wave.open(str(wav), "rb") as w:
                sr, raw = w.getframerate(), w.readframes(w.getnframes())
        n = len(raw) // 2
        return [x / 32768 for x in struct.unpack(f"<{n}h", raw)], sr


class MixedEngine:
    """Per-voice engine choice: a voice is 'kokoro:<name>' or 'piper:<name>'. The voice registry decides who speaks."""
    name = "mixed"

    def __init__(self, voices: dict | None = None, piper: PiperVoices | None = None):
        self.voices = {**DEFAULT_VOICES["mixed"], **(voices or {})}
        self.piper = piper or PiperVoices()
        self._kokoro: KokoroEngine | None = None

    def spec(self, lang: str, voice: str) -> tuple[str, str]:
        key = f"{lang}_b" if voice == "B" and f"{lang}_b" in self.voices else lang
        if key not in self.voices:
            raise RuntimeError(f"No voice configured for '{key}'.")
        engine, _, name = self.voices[key].partition(":")
        if not name:
            raise RuntimeError(f"Voice '{self.voices[key]}' must look like 'kokoro:<name>' or 'piper:<name>'.")
        return engine, name

    def synth(self, text, lang, speed, voice="A"):
        engine, name = self.spec(lang, voice)
        if engine == "piper":
            return self.piper.synth(name, text, speed)
        if engine == "kokoro":
            if self._kokoro is None:
                plain = {k: v.partition(":")[2] for k, v in self.voices.items() if v.startswith("kokoro:")}
                self._kokoro = KokoroEngine(plain)
            return self._kokoro.synth(text, lang, speed, voice)
        raise RuntimeError(f"Unknown voice engine '{engine}' in '{self.voices}'.")


def get_engine(name: str, voices: dict | None = None, device: str = "cuda") -> Engine:
    if name == "tone":
        return ToneEngine()
    if name == "kokoro":
        return KokoroEngine(voices)
    if name == "chatterbox":
        return ChatterboxEngine(voices, device)
    if name == "mixed":
        return MixedEngine(voices)
    raise ValueError(f"Unknown engine '{name}'. Choose: kokoro, mixed, chatterbox, tone.")


def synthesize(manifest_path: Path | str, engine: Engine, audio_dir: Path | str) -> list[Path]:
    m = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    out = Path(audio_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for s in m["segments"]:
        if s["speed"] == "silent":
            continue
        samples, sr = engine.synth(s["text"], s["lang"], s["speed"], s.get("voice", "A"))
        p = out / f"{s['id']}.wav"
        write_wav(p, samples, sr)
        paths.append(p)
    return paths


LOUDNORM = "I=-14:TP=-1.5:LRA=11"


def parse_loudnorm(stderr: str) -> dict | None:
    """The JSON block that ffmpeg's loudnorm prints on its first (measuring) pass; None if unusable (silent audio)."""
    a, b = stderr.rfind("{"), stderr.rfind("}")
    if a < 0 or b < a:
        return None
    try:
        d = json.loads(stderr[a:b + 1])
        vals = {k: float(d[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (ValueError, KeyError):
        return None
    return vals if all(abs(v) < 200 for v in vals.values()) else None


def loudnorm_two_pass(src: Path, dst: Path) -> str:
    """Measure, then apply a linear correction: lands near the target. One pass undershoots (-16.6 to -17.2 LUFS seen)."""
    first = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", f"loudnorm={LOUDNORM}:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True)
    m = parse_loudnorm(first.stderr)
    out_args = ["-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    if m is None:    # silent test audio or unreadable measurement: single pass as before
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", f"loudnorm={LOUDNORM}"] + out_args)
        return "single"
    flt = (f"loudnorm={LOUDNORM}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", flt] + out_args)
    return "two-pass"


def _run(cmd):
    subprocess.run(cmd, check=True)


def assemble(lesson_dir: Path | str, audio_dir: Path | str, out_mp4: Path | str, size: str = "short",
             allow_long: bool = False) -> dict:
    """Join segment audio (+ learner pauses) and the cards into one narrated video.

    Card timing comes from the REAL audio lengths, so the picture always matches the voice.
    """
    lesson_dir, audio_dir, out_mp4 = Path(lesson_dir), Path(audio_dir), Path(out_mp4)
    m = json.loads((lesson_dir / "manifest.json").read_text(encoding="utf-8"))
    n_cards = len(m["cards"])
    card_secs = [0.0] * n_cards
    timers: list = [None] * n_cards   # (start, end) of a silent "your turn"/"think" beat inside each card
    parts: list[Path] = []
    work = out_mp4.parent / (out_mp4.stem + "_work")
    work.mkdir(parents=True, exist_ok=True)

    for s in m["segments"]:
        norm = work / f"{s['id']}.norm.wav"
        if s["speed"] == "silent":
            _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
                  "-t", str(s["est_seconds"]), "-c:a", "pcm_s16le", str(norm)])
        else:
            wav = audio_dir / f"{s['id']}.wav"
            if not wav.exists():
                raise FileNotFoundError(f"missing audio for segment {s['id']}: {wav}")
            pause = PAUSE_AFTER.get(s["speed"], 0.5)
            trimmed = work / f"{s['id']}.trim.wav"
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af", TRIM_EDGES, "-c:a", "pcm_s16le", str(trimmed)])
            try:
                usable = wav_seconds(trimmed) >= 0.15      # a fully silent clip (test engine) trims to nothing: keep the original
            except Exception:
                usable = False
            src = trimmed if usable else wav
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
                  f"aresample={SAMPLE_RATE},apad=pad_dur={pause}", "-ac", "1", "-c:a", "pcm_s16le", str(norm)])
        if s["speed"] == "silent" and s["id"].endswith(("_repeat", "_think")):
            timers[s["card"]] = (round(card_secs[s["card"]], 3), round(card_secs[s["card"]] + wav_seconds(norm), 3))
        card_secs[s["card"]] += wav_seconds(norm)
        parts.append(norm)

    listing = work / "audio.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    full_audio = work / "audio_full.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(full_audio)])

    # Loudness: Kokoro output is quiet (about -25 LUFS). One loudnorm pass brings speech near the Shorts level (-14 LUFS target).
    leveled = work / "audio_leveled.wav"
    loudnorm_two_pass(full_audio, leveled)
    full_audio = leveled
    total = sum(card_secs)
    if size == "short" and not allow_long and total > MAX_SHORT_SECONDS:
        raise LessonError(f"video is {total:.1f} s, over the {MAX_SHORT_SECONDS:.0f} s limit for a Short; "
                          "shorten the lesson (fewer phrases or lines) or split it into parts")
    cards = [lesson_dir / "cards" / c for c in m["cards"]]
    render_video(cards, [round(d, 3) for d in card_secs], out_mp4, size, full_audio, motion=True, timers=timers)
    return {"video": out_mp4, "seconds": round(sum(card_secs), 1), "cards": n_cards}
