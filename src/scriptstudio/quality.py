"""Lesson-level quality checks, run BEFORE any rendering.

Cheap, deterministic rules that encode the viewer promise: every phrase teaches something beyond the
translation, the hook and quiz exist, and the lesson is marked reviewed before it may be published.
BLOCK = do not render. PUBLISH = renders fine but must not be published yet. WARN = look at it.
"""
from __future__ import annotations

import re

MAX_HOOK_WORDS = 14
APPROVED = {"approved", "reviewed by a native speaker"}   # or any status starting with "auto-reviewed" (owner's decision: no human reviewer)


MAX_PHRASE_WORDS = 7      # A1 phrases: longer ones are not "say it back" material
MIN_SEED_OVERLAP = 0.5    # share of the planned phrases the lesson must keep, otherwise it drifted off its topic


def _norm(t: str) -> str:
    return " ".join(re.findall(r"\w+", str(t).lower()))


def topic_issues(lesson: dict, topics: list[dict]) -> list[tuple[str, str]]:
    """Is this lesson part of the plan, and does it stay on the topic planned for it?"""
    from .curriculum import lesson_id

    for t in topics:
        for part in t["parts"]:
            if lesson_id(t, part) == lesson.get("id"):
                seeds = {_norm(x) for x in part["seeds"]}
                have = {_norm(p.get("target", "")) for p in lesson.get("phrases") or []}
                overlap = len(seeds & have) / len(seeds)
                if overlap < MIN_SEED_OVERLAP:
                    return [("WARN", f"only {overlap:.0%} of the planned phrases for '{t['title']}' part {part['n']} "
                                     f"are kept: is the lesson still on topic?")]
                return []
    return [("BLOCK", f"lesson id '{lesson.get('id')}' is not in data/curriculum.json: add it to a topic first, "
                      f"so nothing off-topic is produced")]


def flow_issues(lesson: dict, known: set[str] | None = None) -> list[tuple[str, str]]:
    """The lesson must read as one story: a question is taught before its answer and the quiz tests
    something this lesson taught."""
    r: list[tuple[str, str]] = []
    phrases = lesson.get("phrases") or []
    order = {_norm(p.get("target", "")): i for i, p in enumerate(phrases)}
    for q in lesson.get("quiz") or []:
        ans = order.get(_norm(q.get("answer", "")))
        asked = [i for t, i in order.items() if t and t in _norm(q.get("prompt", ""))]
        if ans is None:
            r.append(("WARN", f"quiz answer '{q.get('answer', '')}' is not one of this lesson's phrases"))
        elif asked and min(asked) > ans:
            r.append(("WARN", "flow: the quiz question phrase is taught after its answer; teach the question first"))
    if known is not None:
        allowed = known | set(order)
        used = [(x.get("target", ""), "dialogue") for x in lesson.get("dialogue") or []]
        for q in lesson.get("quiz") or []:
            used += [(c, "quiz choice") for c in q.get("choices") or []] + [(q.get("answer", ""), "quiz answer")]
        for text, where in used:
            for sent in re.split(r"(?<=[.?!])\s+", str(text).strip()):
                if sent and _norm(sent) not in allowed:
                    r.append(("WARN", f"flow: {where} uses '{sent}', which this lesson and the earlier ones never teach"))
    cold = lesson.get("cold_open") or {}
    if cold and int(cold.get("phrase", 1) or 1) > 2:
        r.append(("WARN", "flow: the opening phrase should be phrase 1 or 2 so the promise is kept at once"))
    return r


def quality_issues(lesson: dict, topics: list[dict] | None = None, known: set[str] | None = None) -> list[tuple[str, str]]:
    r: list[tuple[str, str]] = []
    if topics is not None:
        r += topic_issues(lesson, topics)
    phrases = lesson.get("phrases") or []
    if not 3 <= len(phrases) <= 5:
        r.append(("WARN", f"{len(phrases)} phrases: a 40 s Short teaches 3 to 5"))
    for i, p in enumerate(phrases, 1):
        if not str(p.get("when") or p.get("note") or "").strip():
            r.append(("BLOCK", f"phrase {i} '{p.get('target', '')}': no 'when' or 'note' (teaching point beyond the translation)"))
        if len(re.findall(r"\w+", str(p.get("target", "")))) > MAX_PHRASE_WORDS:
            r.append(("WARN", f"phrase {i} has more than {MAX_PHRASE_WORDS} words: too long to repeat at A1"))
        if not str(p.get("pronunciation", "")).strip():
            r.append(("WARN", f"phrase {i}: no pronunciation hint"))
    cold = lesson.get("cold_open")
    if not cold or not 1 <= int(cold.get("phrase", 0) or 0) <= len(phrases):
        r.append(("BLOCK", "no valid 'cold_open': the Short must open with a useful Spanish phrase in the first second"))
    hook = str(lesson.get("hook", "")).strip()
    if not hook:
        r.append(("BLOCK", "no hook: the first 2 s must promise a concrete result"))
    elif len(re.findall(r"\w+", hook)) > MAX_HOOK_WORDS:
        r.append(("WARN", f"hook is longer than {MAX_HOOK_WORDS} words"))
    if not lesson.get("quiz"):
        r.append(("BLOCK", "no quiz: the viewer needs one active recall task"))
    r += flow_issues(lesson, known)
    if not lesson.get("outro"):
        r.append(("WARN", "no outro line (next step for the viewer)"))
    if lesson.get("variety_code") not in ("neutral", "argentine"):
        r.append(("WARN", "variety_code must be 'neutral' (same in every country, any voice) or 'argentine' (voseo, Argentine voice only)"))
    if not str(lesson.get("variety", "")).strip():
        r.append(("WARN", "no 'variety' (e.g. 'Latin American, understood everywhere'): never present a regional phrase as universal"))
    status = str(lesson.get("review_status", "")).strip().lower()
    if status not in APPROVED and not status.startswith("auto-reviewed"):
        r.append(("PUBLISH", f"review_status is '{lesson.get('review_status', '')}': set it to 'approved' or 'auto-reviewed: ...' after the Spanish has been checked (docs/LANGUAGE_REVIEW.md)"))
    return r
