"""Voice rotation: pick the voices for a lesson from pools so the channel does not sound the same every video.

Rule: lesson number n takes pool[n % len(pool)]. Consecutive lesson numbers therefore get different voices whenever a pool
has two or more entries. The dialogue partner (role B) comes from its own pool and is never the same voice as role A.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_POOL_FILE = Path(__file__).resolve().parents[2] / "data" / "voices.json"


def rotation_index(lesson_id: str) -> int:
    """Trailing number of the lesson id: es-a1-greetings-02 -> 2 (0 if there is none)."""
    m = re.search(r"(\d+)\s*$", lesson_id)
    return int(m.group(1)) if m else 0


def load_pools(engine: str, path: Path | str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_POOL_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("engines", {}).get(engine, {})


def load_voice_rules(path: Path | str | None = None) -> dict:
    """Which lessons each voice may read: {'voice': {'varieties': [...], 'plain_only': bool}}."""
    p = Path(path) if path else DEFAULT_POOL_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("voice_rules", {})


ACCENT_LETTERS = re.compile(r"ll|z|c[eiéí]|\by[aeiouáéíóú]", re.IGNORECASE)


def accent_sensitive(spanish_text: str) -> bool:
    """True if the text has sounds that differ between accents (z/ce/ci, ll, y+vowel): the card respelling fits one accent only."""
    return bool(ACCENT_LETTERS.search(spanish_text))


def pick_voices(lesson_id: str, pools: dict, rotate: int | None = None, variety: str | None = None,
                rules: dict | None = None, sensitive: bool = False) -> dict:
    """Return {'en': voice, 'es': voice_A, 'es_b': voice_B, ...}.

    A voice may read a lesson only if its rules allow the lesson's variety_code, and (plain_only voices) only when the text
    has no accent-sensitive letters. A voseo lesson is never read by a Spain voice; the Spain voice reads only plain text.
    """
    n = rotation_index(lesson_id) if rotate is None else rotate
    chosen: dict[str, str] = {}
    rules = rules or {}

    def allowed(voices):
        def ok(v):
            r = rules.get(v)
            if not r:
                return True
            if variety and variety not in r.get("varieties", [variety]):
                return False
            return not (r.get("plain_only") and sensitive)
        return [v for v in voices if ok(v)] or voices

    for lang, roles in pools.items():
        a_pool, b_pool = allowed(roles.get("A") or []), allowed(roles.get("B") or [])
        if a_pool:
            chosen[lang] = a_pool[n % len(a_pool)]
        if b_pool:
            candidates = [v for v in b_pool if v != chosen.get(lang)] or b_pool
            chosen[f"{lang}_b"] = candidates[n % len(candidates)]
    return chosen


# Voices whose licence asks for a credit line in the video description. Keep this list next to the pools.
CREDITS = {
    "piper:es_ES-sharvard-medium@1": "Spanish voice: es_ES-sharvard-medium speaker 1 (Piper voices, CC BY 3.0, "
                                     "https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_ES/sharvard/medium)",
    "piper:es_AR-daniela-high": "Spanish voice: es_AR-daniela-high (Piper voices, CC BY-SA 4.0, "
                                "https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_AR/daniela/high)",
}


def credits_for(voices: dict) -> str:
    """Credit lines for the voices used in a lesson (empty string if none is required)."""
    return "\n".join(CREDITS[v] for v in dict.fromkeys(voices.values()) if v in CREDITS)
