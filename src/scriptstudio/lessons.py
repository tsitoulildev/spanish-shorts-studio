"""Language-lesson builder (format v2): lesson JSON -> cards, TTS manifest, silent preview video.

A lesson is a small show, not a word list:
  hook -> (scene) -> phrases as prompt-then-answer with a "your turn" beat -> mini dialogue (two voices)
  -> quick quiz (think, then the answer is spoken) -> end card.

No network or models are needed here. Audio (TTS) is produced by scriptstudio.tts on the machine that runs the pipeline.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_LESSON_KEYS = ("id", "source_language", "target_language", "target_code", "level", "topic", "phrases")
FONT_BOLD = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/Library/Fonts/Arial Bold.ttf")
FONT_REG = ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
            "/Library/Fonts/Arial.ttf")
SIZES = {"short": (1080, 1920), "wide": (1920, 1080)}
PAUSE_SECONDS = 1.3      # minimum learner repeat time ("your turn") after each Spanish phrase
GUESS_SECONDS = 0.7      # beat after the English prompt before the answer is spoken
THINK_SECONDS = 2.0      # quiz thinking time
MAX_SHORT_SECONDS = 40.0  # hard limit for one Short (real audio length, checked when the video is assembled)
ESTIMATE_SLACK = 1.15     # estimates run ~10% high; a lesson whose estimate exceeds MAX*SLACK is rejected early
OUTRO_SECONDS = 2.5
SAFE_SIDE = 0.05          # share of the width kept free on each side
SAFE_BOTTOM = 0.87        # nothing below this share of the height (Shorts title and buttons sit there)
SOURCE_CODE = "en"

THEME = {
    "bg_top": (14, 20, 44), "bg_bottom": (44, 24, 78),
    "ink": (246, 248, 252), "mute": (160, 170, 196),
    "accent": (255, 196, 61), "accent2": (92, 225, 190), "panel": (255, 255, 255, 26), "good": (80, 220, 140),
}
# Background changes between card kinds so the picture never feels static (pattern interrupt, no sound needed).
PALETTES = {
    "q": ((14, 20, 44), (44, 24, 78)),        # questions / prompts: indigo
    "a": ((8, 38, 52), (16, 70, 76)),         # answers: teal
    "talk": ((52, 20, 60), (22, 18, 56)),     # dialogue: magenta-indigo
    "quiz": ((60, 36, 8), (30, 18, 52)),      # quiz: warm amber-violet
}


# Visual rotation: same dark, readable backgrounds with the colour channels permuted, so consecutive lessons do not look
# identical. Permuting channels keeps every background dark, so the white text stays readable.
LOOKS = ((0, 1, 2), (2, 0, 1), (1, 2, 0))


def look_colors(rgb: tuple, look: int) -> tuple:
    order = LOOKS[look % len(LOOKS)]
    return tuple(rgb[i] for i in order)


def look_index(lesson_id: str) -> int:
    m = re.search(r"(\d+)\s*$", lesson_id or "")
    return (int(m.group(1)) if m else 0) % len(LOOKS)


class LessonError(ValueError):
    pass


@dataclass(frozen=True)
class Card:
    kind: str                      # hook, scene, phrase_q, phrase_a, dialogue, quiz_q, quiz_a, outro
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Segment:
    id: str
    lang: str          # language code the TTS should speak ("-" for silence)
    text: str
    speed: str         # "slow", "clear", "normal", "fast" or "silent"
    card: int          # index of the card shown while this segment plays
    est_seconds: float
    voice: str = "A"   # "A" main voice, "B" second voice (dialogue partner)


def load_lesson(path: Path | str) -> dict:
    lesson = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate_lesson(lesson)
    if problems:
        raise LessonError("; ".join(problems))
    return lesson


def validate_lesson(lesson: dict) -> list[str]:
    problems = [f"missing '{k}'" for k in REQUIRED_LESSON_KEYS if not lesson.get(k)]
    phrases = lesson.get("phrases") or []
    seen = set()
    for i, p in enumerate(phrases, 1):
        for k in ("target", "translation"):
            if not str(p.get(k, "")).strip():
                problems.append(f"phrase {i}: missing '{k}'")
        key = str(p.get("target", "")).strip().lower()
        if key in seen:
            problems.append(f"phrase {i}: duplicate target '{p.get('target')}'")
        seen.add(key)
    if phrases and not 3 <= len(phrases) <= 20:
        problems.append("a lesson should have between 3 and 20 phrases")
    for i, d in enumerate(lesson.get("dialogue") or [], 1):
        if d.get("speaker") not in ("A", "B"):
            problems.append(f"dialogue line {i}: speaker must be 'A' or 'B'")
        for k in ("target", "translation"):
            if not str(d.get(k, "")).strip():
                problems.append(f"dialogue line {i}: missing '{k}'")
    for i, q in enumerate(lesson.get("quiz") or [], 1):
        if not str(q.get("prompt", "")).strip() or not str(q.get("answer", "")).strip():
            problems.append(f"quiz {i}: needs 'prompt' and 'answer'")
        ch = q.get("choices")
        if ch and q.get("answer") not in ch:
            problems.append(f"quiz {i}: 'answer' must be one of 'choices'")
    if not problems and not lesson.get("allow_long"):
        est = sum(g.est_seconds for g in plan(lesson)[1])
        if est > MAX_SHORT_SECONDS * ESTIMATE_SLACK:
            problems.append(f"too long for a Short: estimated {est:.0f} s, limit {MAX_SHORT_SECONDS:.0f} s "
                            f"(split it into parts, or set \"allow_long\": true for a non-Short video)")
    return problems


def repeat_seconds(text: str) -> float:
    """Time the viewer gets to say a phrase back: longer phrases get longer, but never dead air (1.4 to 2.6 s)."""
    words = max(1, len(re.findall(r"\w+", text)))
    return round(min(2.6, max(1.4, 0.9 + 0.45 * words)), 2)


def estimate_seconds(text: str, slow: bool = False) -> float:
    words = max(1, len(re.findall(r"\w+", text)))
    # +0.2 s per clip: the TTS edges (about 0.5 s of silence per clip) are trimmed away when the video is assembled.
    return round(max(1.0, words * (0.62 if slow else 0.42) + 0.2), 2)


def plan(lesson: dict) -> tuple[list[Card], list[Segment]]:
    """Build the ordered cards and the spoken/silent segments that play on each card."""
    cards: list[Card] = []
    segs: list[Segment] = []
    tc = lesson["target_code"]
    phrases = lesson["phrases"]

    def add(card: Card) -> int:
        cards.append(card)
        return len(cards) - 1

    def say(sid, lang, text, speed, ci, voice="A", extra=0.0):
        segs.append(Segment(sid, lang, text, speed, ci, round(estimate_seconds(text, speed == "slow") + extra, 2), voice))

    def hold(sid, ci, secs):
        segs.append(Segment(sid, "-", "", "silent", ci, secs))

    # Cold open: the first thing the viewer hears and reads is one useful Spanish phrase (value in the first second).
    # The hook card keeps the same phrase on screen and adds the promise above it, so the opening is one
    # connected beat (phrase, then the promise about that phrase) instead of two unrelated cards.
    cold = lesson.get("cold_open")
    lead = None
    if cold:
        lead = phrases[int(cold["phrase"]) - 1]
        ci = add(Card("cold", {"phrase": lead}))
        say("cold", tc, lead["target"], "clear", ci, extra=0.3)

    hook = lesson.get("hook") or f"Learn {lesson['topic']} in {lesson['target_language']}."
    ci = add(Card("hook", {"text": hook, "phrase": lead}))
    say("hook", SOURCE_CODE, hook, "fast", ci)

    if lesson.get("scene"):
        ci = add(Card("scene", {"text": lesson["scene"]}))
        say("scene", SOURCE_CODE, lesson["scene"], "fast", ci)

    n = len(phrases)
    for i, p in enumerate(phrases, 1):
        # Active recall: first the English prompt (spoken fast), then the Spanish answer (spoken once,
        # clearly), then a short "your turn" beat. Two quick cuts per phrase instead of one long static card.
        ci = add(Card("phrase_q", {"i": i, "n": n, "phrase": p}))
        say(f"p{i:02d}_q", SOURCE_CODE, p["translation"].rstrip("."), "fast", ci)
        hold(f"p{i:02d}_guess", ci, GUESS_SECONDS)
        ci = add(Card("phrase_a", {"i": i, "n": n, "phrase": p}))
        say(f"p{i:02d}_a", tc, p["target"], "clear", ci)
        hold(f"p{i:02d}_repeat", ci, repeat_seconds(p["target"]))

    dlg = lesson.get("dialogue") or []
    for j, line in enumerate(dlg):
        ci = add(Card("dialogue", {"lines": dlg, "current": j}))
        say(f"d{j + 1:02d}", tc, line["target"], "clear", ci, voice=line["speaker"], extra=0.2)

    for k, q in enumerate(lesson.get("quiz") or [], 1):
        ci = add(Card("quiz_q", {"q": q, "k": k}))
        say(f"q{k:02d}_ask", SOURCE_CODE, q["prompt"], "fast", ci)
        hold(f"q{k:02d}_think", ci, THINK_SECONDS)
        ci = add(Card("quiz_a", {"q": q, "k": k}))
        say(f"q{k:02d}_ans", tc, q["answer"], "clear", ci, extra=0.4)

    outro = lesson.get("outro") or "Say them out loud once more. Follow for the next lesson."
    ci = add(Card("outro", {"text": outro, "title": "You just learned", "phrases": phrases}))
    say("outro", SOURCE_CODE, outro, "fast", ci)
    return cards, segs


def build_manifest(lesson: dict) -> list[Segment]:
    return plan(lesson)[1]


def card_durations(segs: list[Segment], n_cards: int | None = None) -> list[float]:
    n = n_cards if n_cards is not None else max(s.card for s in segs) + 1
    dur = [0.0] * n
    for s in segs:
        dur[s.card] += s.est_seconds
    return [round(d, 2) for d in dur]


# ---------------------------------------------------------------- drawing

def _font(candidates, size):
    from PIL import ImageFont
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    raise LessonError("No usable TrueType font found; install DejaVu or Arial.")


class _Canvas:
    def __init__(self, W: int, H: int, palette: str = "q", look: int = 0):
        from PIL import Image, ImageDraw
        import numpy as np
        self.W, self.H, self.s = W, H, min(W, H) / 1080
        self.issues: list[str] = []   # layout problems found while drawing (text outside the safe zone, clipped, too low)
        t, b = (look_colors(c, look) for c in PALETTES.get(palette, PALETTES["q"]))
        ramp = np.linspace(0, 1, H)[:, None, None]
        arr = (np.array(t) * (1 - ramp) + np.array(b) * ramp).astype("uint8")
        arr = np.repeat(arr, W, axis=1)
        self.im = Image.fromarray(arr, "RGB").convert("RGBA")
        self._glow(int(W * 0.85), int(H * 0.12), int(min(W, H) * 0.55), THEME["accent2"], 40)
        self._glow(int(W * 0.1), int(H * 0.9), int(min(W, H) * 0.6), THEME["accent"], 28)
        self.im = self.im.convert("RGB")  # RGB base so translucent panels blend instead of replacing pixels
        self.d = ImageDraw.Draw(self.im, "RGBA")
        self.f = lambda sz, bold=True: _font(FONT_BOLD if bold else FONT_REG, int(sz * self.s))

    def _glow(self, cx, cy, r, color, alpha):
        from PIL import Image, ImageDraw, ImageFilter
        layer = Image.new("RGBA", self.im.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse((cx - r, cy - r, cx + r, cy + r), fill=(*color, alpha))
        self.im = Image.alpha_composite(self.im, layer.filter(ImageFilter.GaussianBlur(r // 3)))

    def wrap(self, text, font, max_w):
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if self.d.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def text(self, text, size, y, color, bold=True, max_w=None, gap=1.28, x=None, align="center"):
        font = self.f(size, bold)
        max_w = max_w or int(self.W - 2 * 90 * self.s)
        for line in self.wrap(text, font, max_w):
            w = self.d.textlength(line, font=font)
            px = (self.W - w) / 2 if align == "center" else (x if x is not None else 90 * self.s)
            self._check(line, px, y, w, font.size)
            self.d.text((px, y), line, font=font, fill=color)
            y += int(font.size * gap)
        return y

    def _check(self, text, px, y, w, size):
        """Shorts UI covers the bottom of the screen and the sides: keep every line inside the safe zone."""
        if px < SAFE_SIDE * self.W or px + w > (1 - SAFE_SIDE) * self.W:
            self.issues.append(f"'{text}' leaves the side safe zone")
        if y + size > SAFE_BOTTOM * self.H:
            self.issues.append(f"'{text}' reaches below the bottom safe zone")

    def height(self, text, size, bold=True, max_w=None, gap=1.28):
        font = self.f(size, bold)
        max_w = max_w or int(self.W - 2 * 90 * self.s)
        return len(self.wrap(text, font, max_w)) * int(font.size * gap)

    def panel(self, x0, y0, x1, y1, fill=None, outline=None, r=36):
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=int(r * self.s), fill=fill or THEME["panel"],
                                 outline=outline, width=3 if outline else 0)

    def chip(self, text, x, y, color, size=34):
        font = self.f(size)
        w = self.d.textlength(text, font=font)
        pad = int(22 * self.s)
        self._check(text, x + pad, y, w, font.size + pad)
        self.d.rounded_rectangle((x, y, x + w + 2 * pad, y + font.size + pad), radius=int(30 * self.s),
                                 fill=(*color, 255))
        self.d.text((x + pad, y + pad // 2 - 2), text, font=font, fill=(20, 20, 36))
        return x + w + 2 * pad

    def progress(self, i, n):
        m = int(70 * self.s)
        y = int(48 * self.s)
        self.d.rounded_rectangle((m, y, self.W - m, y + int(10 * self.s)), radius=6, fill=(255, 255, 255, 40))
        self.d.rounded_rectangle((m, y, m + int((self.W - 2 * m) * i / max(1, n)), y + int(10 * self.s)), radius=6,
                                 fill=(*THEME["accent"], 255))

    def save(self, path: Path):
        self.im.save(path)


def _draw_card(card: Card, idx: int, total: int, lesson: dict, W: int, H: int) -> "_Canvas":
    pal = {"phrase_a": "a", "quiz_a": "a", "dialogue": "talk", "quiz_q": "quiz", "outro": "a"}.get(card.kind, "q")
    c = _Canvas(W, H, pal, look_index(lesson.get("id", "")))
    T = THEME
    s, k, dat = c.s, card.kind, card.data
    c.progress(idx + 1, total)
    mx = int(90 * s)

    def tag(label, color=T["accent2"]):
        c.chip(label, mx, int(H * 0.07), color)

    if k == "hook" and dat.get("phrase"):
        p = dat["phrase"]
        tag(f"{lesson['source_language']} → {lesson['target_language']}  ·  {lesson['level']}")
        y = c.text(dat["text"], 72, int(H * 0.17), T["ink"], max_w=W - 2 * mx)
        top = max(y + int(50 * s), int(H * 0.36))
        h = c.height(p["target"], 100, max_w=W - 2 * mx - 80)
        c.panel(mx, top, W - mx, top + h + int(250 * s), outline=(*T["accent"], 220))
        yy = c.text(p["target"], 100, top + int(40 * s), T["accent"], max_w=W - 2 * mx - 80)
        if p.get("pronunciation"):
            yy = c.text(p["pronunciation"], 54, yy + int(10 * s), T["ink"], max_w=W - 2 * mx - 80)
        c.text(p["translation"], 58, yy + int(30 * s), T["mute"], max_w=W - 2 * mx - 80)
        c.text(lesson["topic"], 48, top + h + int(250 * s) + int(70 * s), T["accent2"])
    elif k == "hook":
        tag(f"{lesson['source_language']} → {lesson['target_language']}  ·  {lesson['level']}")
        y = c.text(dat["text"], 84, int(H * 0.36), T["ink"])
        c.text(lesson["topic"], 52, y + int(50 * s), T["accent"])
    elif k == "scene":
        tag("Imagine this")
        c.panel(mx, int(H * 0.26), W - mx, int(H * 0.34) + c.height(dat["text"], 56, max_w=W - 2 * mx - 80) + int(120 * s))
        c.text(dat["text"], 56, int(H * 0.34) + int(60 * s), T["ink"], max_w=W - 2 * mx - 80)
    elif k == "phrase_q":
        tag(f"{dat['i']} / {dat['n']}  ·  How do you say…")
        c.text(dat["phrase"]["translation"], 100, int(H * 0.36), T["ink"])
        c.chip("Think of it in Spanish", mx, int(H * 0.68), T["accent"], 40)
    elif k == "cold":
        p = dat["phrase"]
        tag("Remember this")
        h = c.height(p["target"], 116, max_w=W - 2 * mx - 80)
        top = int(H * 0.30)
        c.panel(mx, top, W - mx, top + h + int(380 * s), outline=(*T["accent"], 220))
        yy = c.text(p["target"], 116, top + int(50 * s), T["accent"], max_w=W - 2 * mx - 80)
        if p.get("pronunciation"):
            yy = c.text(p["pronunciation"], 58, yy + int(10 * s), T["ink"], max_w=W - 2 * mx - 80)
        c.text(p["translation"], 64, yy + int(40 * s), T["mute"], max_w=W - 2 * mx - 80)
    elif k == "phrase_a":
        p = dat["phrase"]
        tag(f"{dat['i']} / {dat['n']}")
        y = c.text(p["translation"], 52, int(H * 0.18), T["mute"])
        top = max(y + int(30 * s), int(H * 0.26))
        h = c.height(p["target"], 104, max_w=W - 2 * mx - 80) + int(60 * s)
        c.panel(mx, top, W - mx, top + h + int(170 * s), outline=(*T["accent"], 200))
        yy = c.text(p["target"], 104, top + int(40 * s), T["accent"], max_w=W - 2 * mx - 80)
        if p.get("pronunciation"):
            c.text(p["pronunciation"], 56, yy + int(10 * s), T["ink"], max_w=W - 2 * mx - 80)
        y = top + h + int(170 * s) + int(50 * s)
        if p.get("when"):
            c.chip("Use it", mx, y, T["accent2"], 30)
            y = c.text(p["when"], 46, y + int(80 * s), T["ink"], bold=False, x=mx, align="left")
        c.chip("Your turn: say it out loud", mx, min(y + int(60 * s), H - int(260 * s)), T["accent"], 42)
    elif k == "dialogue":
        tag("Mini conversation", T["accent"])
        y = int(H * 0.24)
        for j, line in enumerate(dat["lines"]):
            active = j == dat["current"]
            shown = j <= dat["current"]
            left = line["speaker"] == "A"
            bw = int((W - 2 * mx) * 0.82)
            x0 = mx if left else W - mx - bw
            h = c.height(line["target"], 56, max_w=bw - 70) + c.height(line["translation"], 38, False, max_w=bw - 70) + int(90 * s)
            if shown:
                col = (*T["accent"], 255) if left else (*T["accent2"], 255)
                c.panel(x0, y, x0 + bw, y + h, fill=col if active else (255, 255, 255, 34))
                ink = (20, 20, 36) if active else T["ink"]
                yy = c.text(line["target"], 56, y + int(28 * s), ink, max_w=bw - 70, x=x0 + 35, align="left")
                c.text(line["translation"], 38, yy, ink if active else T["mute"], False, max_w=bw - 70, x=x0 + 35, align="left")
            y += h + int(36 * s)
    elif k in ("quiz_q", "quiz_a"):
        q = dat["q"]
        tag(f"Quick quiz {dat['k']}", T["accent"])
        y = c.text(q["prompt"], 64, int(H * 0.26), T["ink"])
        if k == "quiz_q":
            y += int(60 * s)
            for letter, ch in zip("ABC", q.get("choices") or []):
                c.panel(mx, y, W - mx, y + int(130 * s), r=30)
                c.chip(letter, mx + int(24 * s), y + int(26 * s), T["accent"], 40)
                c.text(ch, 56, y + int(32 * s), T["ink"], x=mx + int(150 * s), align="left")
                y += int(160 * s)
            c.text("Think… then listen", 44, min(H - int(220 * s), y + int(40 * s)), T["mute"], False)
        else:
            c.panel(mx, int(H * 0.44), W - mx, int(H * 0.44) + int(300 * s), outline=(*T["good"], 220))
            yy = c.text(q["answer"], 88, int(H * 0.44) + int(70 * s), T["good"], max_w=W - 2 * mx - 80)
    else:  # outro: a small reward screen - what the viewer can now say, each line ticked off
        phr = dat.get("phrases") or []
        if phr:
            tag("Done", T["good"])
            y = c.text(dat["title"], 88, int(H * 0.17), T["accent"])
            y += int(40 * s)
            for p in phr:
                c.panel(mx, y, W - mx, y + int(190 * s), fill=(255, 255, 255, 30), r=30)
                c.chip("\u2713", mx + int(30 * s), y + int(52 * s), T["good"], 46)
                yy = c.text(p["target"], 58, y + int(32 * s), T["ink"], max_w=W - 2 * mx - int(230 * s),
                            x=mx + int(170 * s), align="left")
                c.text(p["translation"], 38, yy, T["mute"], False, max_w=W - 2 * mx - int(230 * s),
                       x=mx + int(170 * s), align="left")
                y += int(220 * s)
            c.text(dat["text"], 50, min(y + int(40 * s), int(H * 0.74)), T["ink"], False)
        else:
            yy = c.text(dat["title"], 92, int(H * 0.38), T["accent"])
            c.text(dat["text"], 50, yy + int(50 * s), T["ink"], False)
    return c


def layout_problems(lesson: dict, size: str = "short") -> list[str]:
    """Draw every card in memory and report text outside the safe zone. Empty list = clean."""
    W, H = SIZES[size]
    cards = plan(lesson)[0]
    out = []
    for i, card in enumerate(cards):
        out += [f"card {i} ({card.kind}): {m}" for m in _draw_card(card, i, len(cards), lesson, W, H).issues]
    return out


def render_cards(lesson: dict, out_dir: Path | str, size: str = "short", cards: list[Card] | None = None) -> list[Path]:
    W, H = SIZES[size]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cards = cards or plan(lesson)[0]
    paths = []
    for i, card in enumerate(cards):
        p = out / f"card_{i:02d}_{card.kind}.png"
        _draw_card(card, i, len(cards), lesson, W, H).save(p)
        paths.append(p)
    return paths


# ---------------------------------------------------------------- video

def render_video(cards: list[Path], durations: list[float], out_mp4: Path | str, size: str = "short",
                 audio: Path | str | None = None, motion: bool = True,
                 timers: list | None = None) -> Path:
    """One short clip per card (fade-in, slow push-in), concatenated; optional audio track is muxed.

    timers: per card, None or (start, end) seconds inside the card. A yellow bar near the top shrinks over that window,
    so a silent "your turn" / "think" beat is visibly a countdown instead of dead air."""
    if len(cards) != len(durations):
        raise LessonError("cards and durations differ in length")
    W, H = SIZES[size]
    out_mp4 = Path(out_mp4)
    work = out_mp4.parent / (out_mp4.stem + "_clips")
    work.mkdir(parents=True, exist_ok=True)
    clips = []
    for i, (c, dur) in enumerate(zip(cards, durations)):
        frames = max(2, int(round(dur * 30)))
        clip = work / f"clip_{i:02d}.mp4"
        zoom = (f"zoompan=z='min(1+0.0009*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps=30"
                if motion else f"scale={W}:{H},fps=30")
        vf = f"{zoom},fade=t=in:st=0:d=0.15"
        tm = timers[i] if timers and i < len(timers) else None
        if tm and tm[1] - tm[0] >= 0.3:
            t0, t1 = tm
            bx, bw = int(90 * W / 1080), W - 2 * int(90 * W / 1080)
            bh, by, n = max(8, int(14 * W / 1080)), int(H * 0.13), 24
            # drawbox does not re-evaluate its width per frame, so the bar is n segments that vanish right to left.
            for k in range(n):
                x0, x1 = bx + bw * k // n, bx + bw * (k + 1) // n
                gone = t0 + (t1 - t0) * (n - k) / n
                vf += (f",drawbox=x={x0}:y={by}:w={x1 - x0 + 1}:h={bh}:color=0xFFC832@1:t=fill"
                       f":enable='between(t,{t0:.3f},{gone:.3f})'")
        vf += ",format=yuv420p"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(c)]
        if not motion:
            cmd += ["-t", str(dur)]
        cmd += ["-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)]
        subprocess.run(cmd, check=True)
        clips.append(clip)
    listing = work / "clips.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in clips), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing)]
    if audio:
        cmd += ["-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest"]
    else:
        cmd += ["-c", "copy"]
    cmd.append(str(out_mp4))
    subprocess.run(cmd, check=True)
    return out_mp4


def build_preview(cards: list[Path], durations: list[float], out_mp4: Path | str, size: str = "short",
                  motion: bool = True) -> Path:
    """Silent preview with estimated timings (real timings come from the TTS audio)."""
    return render_video(cards, durations, out_mp4, size, None, motion)


def storyboard(lesson: dict) -> str:
    """The whole Short as one readable timeline: what is heard, what is on screen, how long. Writer and reviewer read this."""
    cards, segs = plan(lesson)
    t = 0.0
    rows = [f"{lesson['id']}  |  {lesson['topic']}  |  hook: {lesson.get('hook', '')}", ""]
    for s_ in segs:
        kind = cards[s_.card].kind
        if s_.speed == "silent":
            what = f"(silent {s_.est_seconds:.1f}s: viewer's turn)"
        else:
            what = f"{s_.lang}/{s_.voice}: {s_.text}"
        rows.append(f"{t:5.1f}s  card {s_.card:02d} {kind:9s} {what}")
        t += s_.est_seconds
    rows += ["", f"estimated length: {t:.1f} s (limit 40 s)"]
    return "\n".join(rows) + "\n"


def contact_sheet(card_paths: list[Path], out: Path, cols: int = 8, thumb_w: int = 270) -> Path:
    """One picture with every card in order: the flow can be judged at a glance."""
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in card_paths]
    th = int(ims[0].height * thumb_w / ims[0].width)
    rows = -(-len(ims) // cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows * th), (10, 10, 14))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((thumb_w, th)), ((i % cols) * thumb_w, (i // cols) * th))
    sheet.save(out)
    return out


def build_all(lesson_path: Path | str, out_dir: Path | str, size: str = "short", preview: bool = True,
              motion: bool = True) -> dict:
    lesson = load_lesson(lesson_path)
    out = Path(out_dir) / lesson["id"]
    cards_spec, segs = plan(lesson)
    durs = card_durations(segs, len(cards_spec))
    cards = render_cards(lesson, out / "cards", size, cards_spec)
    manifest = {
        "lesson_id": lesson["id"],
        "variety_code": lesson.get("variety_code", ""),
        "accent_sensitive": __import__("scriptstudio.voices", fromlist=["x"]).accent_sensitive(
            " ".join([p["target"] for p in lesson["phrases"]] + [x["target"] for x in lesson.get("dialogue") or []]
                     + [q["answer"] for q in lesson.get("quiz") or []])),
        "note": "est_seconds are estimates; real durations come from the audio. Every Spanish line must be checked (docs/LANGUAGE_REVIEW.md) before publishing.",
        "segments": [s.__dict__ for s in segs],
        "card_durations": durs,
        "cards": [p.name for p in cards],
        "card_kinds": [c.kind for c in cards_spec],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "narration.txt").write_text(
        "\n".join(f"[{s.lang}/{s.speed}/{s.voice}] {s.text}" for s in segs if s.speed != "silent") + "\n", encoding="utf-8")
    (out / "storyboard.txt").write_text(storyboard(lesson), encoding="utf-8")
    contact_sheet(cards, out / "cards_sheet.png")
    result = {"dir": out, "cards": len(cards), "segments": len(segs), "seconds": round(sum(durs), 1)}
    if preview:
        result["preview"] = build_preview(cards, durs, out / "preview.mp4", size, motion)
    return result
