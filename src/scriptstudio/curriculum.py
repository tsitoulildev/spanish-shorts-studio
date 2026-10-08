"""Topic arcs: one topic spans several Shorts and is replaced only when every part exists.

`next_part` decides what to write next from the files in lessons/, and `brief` turns it into a ready-to-use prompt
(for Claude or a human) that carries every rule of the channel, so each new lesson starts from the same quality bar.
"""
from __future__ import annotations

import json
from pathlib import Path

CURRICULUM_FILE = Path(__file__).resolve().parents[2] / "data" / "curriculum.json"


def load_topics(path: Path | str | None = None) -> list[dict]:
    return json.loads(Path(path or CURRICULUM_FILE).read_text(encoding="utf-8"))["topics"]


def lesson_id(topic: dict, part: dict, level_prefix: str = "es") -> str:
    return f"{level_prefix}-{topic['level'].lower()}-{topic['id']}-{part['n']:02d}"


def next_part(topics: list[dict], lessons_dir: Path | str = "lessons", pending: set[str] | None = None) -> tuple[dict, dict] | None:
    """First topic that is not fully written, and its first missing part. Topics finish before the next one starts.
    `pending` = lesson ids already written on a branch but not yet approved: they count as taken, so a run never
    writes the same lesson twice while a human has not reviewed it."""
    existing = {p.stem for p in Path(lessons_dir).glob("*.json")} | set(pending or ())
    for t in topics:
        for part in t["parts"]:
            if lesson_id(t, part) not in existing:
                return t, part
    return None


def brief(topic: dict, part: dict, previous_voice_note: str = "") -> str:
    n_parts = len(topic["parts"])
    return f"""Write the lesson file lessons/{lesson_id(topic, part)}.json for an English-to-Spanish Short.

Topic: {topic['title']} (level {topic['level']}), part {part['n']} of {n_parts}: {part['angle']}.
Draft phrases to start from (check and improve them): {'; '.join(part['seeds'])}

Rules (all mandatory):
- First read docs/LESSON_SPEC.md (one story: the hook promises, the first phrase keeps it, a question comes before its answer, dialogue and quiz reuse only met phrases) and follow docs/AUTOMATION.md.
- Format: copy the structure of lessons/es-a1-greetings-01.json (hook, cold_open, 3 to 5 phrases, dialogue A/B, quiz, outro).
- Before you finish: `python -m scriptstudio storyboard <file>` and answer the reviewer checklist.
- Every phrase has "when" (a usage tip beyond the translation) and "pronunciation" (English-style respelling).
- Hook promises a concrete result in at most 14 words. Outro names the next step{' (part ' + str(part['n'] + 1) + ' is next)' if part['n'] < n_parts else ' (the next topic comes after this part)'}.
- Total spoken length must fit 40 seconds; run `python -m scriptstudio check` and the build before declaring it done.
- Spanish variety: Argentine (Rioplatense), voseo. Keep "review_status": "NOT reviewed" until you have checked every Spanish line and recorded it in docs/LANGUAGE_REVIEW.md, then set "auto-reviewed: ...".
- Not a copy of any existing channel: original sentences, no lyrics, no quotes from books.
{previous_voice_note}""".strip()


def status(topics: list[dict], lessons_dir: Path | str = "lessons") -> list[str]:
    existing = {p.stem for p in Path(lessons_dir).glob("*.json")}
    out = []
    for t in topics:
        done = sum(lesson_id(t, p) in existing for p in t["parts"])
        out.append(f"{t['id']}: {done}/{len(t['parts'])} parts written")
    return out


def plan_duplicates(topics: list[dict]) -> list[str]:
    """A phrase planned twice in the curriculum is a repeated video, unless it is deliberately taught again."""
    import re as _re
    seen: dict[str, str] = {}
    out = []
    for t in topics:
        for part in t["parts"]:
            for seed in part["seeds"]:
                key = " ".join(_re.findall(r"\w+", seed.lower()))
                where = f"{t['id']} part {part['n']}"
                if key in seen:
                    out.append(f"'{seed}' is planned in {seen[key]} and again in {where}")
                else:
                    seen[key] = where
    return out


def taught_elsewhere(lesson: dict, lessons_dir: Path | str = "lessons") -> list[str]:
    """Phrases of this lesson that another lesson file already teaches."""
    import re as _re

    def norm(x):
        return " ".join(_re.findall(r"\w+", str(x).lower()))
    mine = {norm(p["target"]): p["target"] for p in lesson.get("phrases", [])}
    out = []
    for f in sorted(Path(lessons_dir).glob("*.json")):
        other = json.loads(f.read_text(encoding="utf-8"))
        if other.get("id") == lesson.get("id"):
            continue
        for p in other.get("phrases", []):
            if norm(p["target"]) in mine:
                out.append(f"'{p['target']}' is already taught in {other.get('id')}")
    return out


def known_phrases(lesson: dict, topics: list[dict], lessons_dir: Path | str = "lessons") -> set[str]:
    """Normalised phrases taught by lessons that come BEFORE this one in the curriculum (all others if it is not listed).
    A dialogue or quiz may only reuse what the viewer has already met."""
    import re as _re

    def norm(x):
        return " ".join(_re.findall(r"\w+", str(x).lower()))
    order = [lesson_id(t, p) for t in topics for p in t["parts"]]
    cur = lesson.get("id")
    before = set(order[:order.index(cur)]) if cur in order else set(order)
    out: set[str] = set()
    for f in sorted(Path(lessons_dir).glob("*.json")):
        other = json.loads(f.read_text(encoding="utf-8"))
        if other.get("id") in before and other.get("id") != cur:
            out |= {norm(p["target"]) for p in other.get("phrases", [])}
    return out
