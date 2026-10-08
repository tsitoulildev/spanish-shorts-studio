"""Automatic quality gate for a finished lesson video.

Why: the goal is automated content that is still good. Nobody should have to open each video to find out that it is too
long, too quiet, has dead air, a black frame, or a voice that says something other than the script. This module measures
the finished video with ffmpeg and (optionally) checks the spoken audio against the script with Whisper, then returns
FAIL / WARN lines. The server script fails the lesson on any FAIL.

The thresholds are first values taken from real renders and are meant to be tuned with more data.
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from .lessons import MAX_SHORT_SECONDS

LOUDNESS_RANGE = (-18.0, -11.0)   # integrated LUFS; Shorts are usually mastered near -14
MAX_TRUE_PEAK = -0.5              # dBFS
MAX_SINGLE_GAP = 3.2              # s: longest silence allowed (designed "your turn" pauses are at most 2.6 s plus padding)
SILENCE_SLACK = 1.25              # measured silence may exceed the designed pauses by 25% ...
SILENCE_EXTRA = 1.5               # ... plus this many seconds before it counts as dead air
MAX_ONSET = 0.6                   # s: first sound must start almost at once (value in the first 1-2 s)
FAIL_ONSET = 2.0
MAX_BLACK = 0.3                   # s of black picture allowed in total
MIN_TRANSCRIPT_MATCH = 0.80       # similarity between script text and what Whisper hears, per clip
SIZE = (1080, 1920)


def _run(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stderr + r.stdout


def measure(video: Path | str) -> dict:
    """Numbers about the finished video. Pure measurement, no judgement."""
    v = str(video)
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
         "-of", "json", v], capture_output=True, text=True, check=True).stdout)
    vs = next((s for s in probe["streams"] if s["codec_type"] == "video"), {})
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    num, _, den = (vs.get("r_frame_rate") or "0/1").partition("/")
    duration = float(probe["format"]["duration"])
    m = {"duration": duration, "width": vs.get("width"), "height": vs.get("height"),
         "fps": round(float(num) / float(den or 1), 2) if float(den or 1) else 0.0, "has_audio": has_audio}

    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", v, "-af", "ebur128=peak=true", "-f", "null", "-"])
    tail = out[out.rfind("Summary:"):] if "Summary:" in out else out
    i = re.search(r"\bI:\s+(-?[\d.]+|-inf)\s+LUFS", tail)
    p = re.search(r"\bPeak:\s+(-?[\d.]+|-inf)\s+dBFS", tail)
    m["lufs"] = float(i.group(1)) if i and i.group(1) != "-inf" else -70.0
    m["peak"] = float(p.group(1)) if p and p.group(1) != "-inf" else -70.0

    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", v, "-af", "silencedetect=n=-45dB:d=0.15", "-f", "null", "-"])
    gaps, start = [], None
    for line in out.splitlines():
        s = re.search(r"silence_start: (-?[\d.]+)", line)
        e = re.search(r"silence_end: ([\d.]+)", line)
        if s:
            start = max(0.0, float(s.group(1)))
        elif e and start is not None:
            gaps.append((start, float(e.group(1))))
            start = None
    if start is not None:                       # silence that runs to the end of the file
        gaps.append((start, duration))
    m["onset"] = round(gaps[0][1], 2) if gaps and gaps[0][0] <= 0.05 else 0.0
    m["silence_total"] = round(sum(b - a for a, b in gaps), 2)
    m["silence_longest"] = round(max((b - a for a, b in gaps), default=0.0), 2)

    out = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", v, "-vf", "blackdetect=d=0.1:pix_th=0.10", "-an", "-f", "null", "-"])
    m["black_total"] = round(sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", out)), 2)
    return m


def evaluate(m: dict, planned_silence: float | None = None, audio_checks: bool = True) -> list[tuple[str, str]]:
    """Judge the measurements. Returns [(level, message)], level is FAIL or WARN. Empty list = clean pass."""
    r: list[tuple[str, str]] = []
    if m["duration"] > MAX_SHORT_SECONDS:
        r.append(("FAIL", f"duration {m['duration']:.1f} s is over the {MAX_SHORT_SECONDS:.0f} s Short limit"))
    if (m["width"], m["height"]) != SIZE:
        r.append(("FAIL", f"size {m['width']}x{m['height']} is not {SIZE[0]}x{SIZE[1]}"))
    if abs(m["fps"] - 30) > 0.5:
        r.append(("FAIL", f"frame rate {m['fps']} is not 30"))
    if m["black_total"] > MAX_BLACK:
        r.append(("FAIL", f"{m['black_total']:.2f} s of black picture"))
    if audio_checks:
        if not m["has_audio"]:
            r.append(("FAIL", "no audio track"))
        else:
            lo, hi = LOUDNESS_RANGE
            if not lo <= m["lufs"] <= hi:
                r.append(("FAIL", f"loudness {m['lufs']:.1f} LUFS outside {lo:.0f}..{hi:.0f}"))
            if m["peak"] > MAX_TRUE_PEAK:
                r.append(("FAIL", f"peak {m['peak']:.1f} dBFS above {MAX_TRUE_PEAK}"))
            onset = m.get("onset", 0.0)
            if onset > FAIL_ONSET:
                r.append(("FAIL", f"first sound at {onset:.1f} s: no value in the first {FAIL_ONSET:.0f} s"))
            elif onset > MAX_ONSET:
                r.append(("WARN", f"first sound at {onset:.1f} s (aim for under {MAX_ONSET} s)"))
            if m["silence_longest"] > MAX_SINGLE_GAP:
                r.append(("FAIL", f"a silence of {m['silence_longest']:.1f} s (limit {MAX_SINGLE_GAP} s)"))
            if planned_silence is not None:
                allowed = planned_silence * SILENCE_SLACK + SILENCE_EXTRA
                if m["silence_total"] > allowed:
                    r.append(("WARN", f"silence {m['silence_total']:.1f} s vs {planned_silence:.1f} s designed "
                                      f"(dead air above {allowed:.1f} s)"))
    return r


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def similarity(expected: str, heard: str) -> float:
    return SequenceMatcher(None, normalize(expected), normalize(heard)).ratio()


def transcript_check(manifest: dict, audio_dir: Path | str, model_name: str = "small") -> list[tuple[str, str]] | None:
    """Whisper listens to every spoken clip and we compare it with the script text.

    Returns None when faster-whisper is not installed (check skipped). Whisper is forgiving (it repairs mispronounced
    words from context), so this catches wrong/garbled words, not subtle accent problems.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    out: list[tuple[str, str]] = []
    for s in manifest["segments"]:
        if s["speed"] == "silent":
            continue
        wav = Path(audio_dir) / f"{s['id']}.wav"
        if not wav.exists():
            out.append(("FAIL", f"clip {s['id']}: audio file missing"))
            continue
        segs, _ = model.transcribe(str(wav), language=s["lang"], beam_size=5)
        heard = " ".join(x.text for x in segs).strip()
        score = similarity(s["text"], heard)
        if len(re.findall(r"\w+", s["text"])) <= 2:   # Whisper is unreliable on one or two isolated words
            out.append(("INFO", f"clip {s['id']} [{s['lang']}] too short for a reliable check (match {score:.2f}): wanted '{s['text']}' heard '{heard}'"))
            continue
        line = f"clip {s['id']} [{s['lang']}] match {score:.2f}: wanted '{s['text']}' heard '{heard}'"
        out.append(("WARN" if score < MIN_TRANSCRIPT_MATCH else "INFO", line))
    return out


def run_qa(lesson_dir: Path | str, engine: str, transcribe: bool = False) -> tuple[bool, str]:
    """QA for one built lesson folder. Returns (passed, report text). Passed means no FAIL line."""
    d = Path(lesson_dir)
    video = d / f"lesson_{engine}.mp4"
    manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    silent_engine = engine == "tone"
    planned = sum(s["est_seconds"] for s in manifest["segments"] if s["speed"] == "silent")
    planned += 0.2 * sum(1 for s in manifest["segments"] if s["speed"] != "silent")   # padding after each clip
    m = measure(video)
    lines = [f"{d.name} ({engine}): {m['duration']:.1f} s, {m['width']}x{m['height']}@{m['fps']:g}, "
             f"first sound {m.get('onset', 0.0):.1f} s, {m['lufs']:.1f} LUFS, peak {m['peak']:.1f} dBFS, silence {m['silence_total']:.1f} s "
             f"(designed about {planned:.1f} s, longest gap {m['silence_longest']:.1f} s), black {m['black_total']:.2f} s"]
    results = evaluate(m, None if silent_engine else planned, audio_checks=not silent_engine)
    first = next((x for x in manifest["segments"] if x["speed"] != "silent"), None)
    if first and first["lang"] != manifest.get("target_code", first["lang"]) and first["id"] != "cold":
        results.append(("WARN", f"the first spoken line is '{first['id']}', not a Spanish cold open"))
    if silent_engine:
        lines.append("INFO audio checks skipped: 'tone' is a silent test engine")
    elif transcribe:
        tc = transcript_check(manifest, d / f"audio_{engine}")
        if tc is None:
            lines.append("INFO transcript check skipped: faster-whisper is not installed")
        else:
            results += [x for x in tc if x[0] != "INFO"]
            lines += [f"INFO {msg}" for lvl, msg in tc if lvl == "INFO"]
    lines += [f"{lvl} {msg}" for lvl, msg in results]
    passed = not any(lvl == "FAIL" for lvl, _ in results)
    lines.append("QA: " + ("PASS" if passed else "FAIL") + (" (with warnings)" if passed and any(l == "WARN" for l, _ in results) else ""))
    return passed, "\n".join(lines)
