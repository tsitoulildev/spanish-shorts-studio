"""Command line interface: lesson | voice | qa | check | next | storyboard | upload."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def cmd_lesson(args) -> int:
    from .lessons import build_all

    res = build_all(args.lesson, args.out, size=args.size, preview=not args.no_preview)
    print(f"Lesson built: {res['dir']}")
    print(f"  cards: {res['cards']}  segments: {res['segments']}  est. length: {res['seconds']} s")
    if "preview" in res:
        print(f"  silent preview: {res['preview']}")
    print("  next: scriptstudio voice <folder>, then scriptstudio qa <folder>")
    print("  reminder: check every Spanish line (docs/LANGUAGE_REVIEW.md) and set review_status before publishing")
    return 0


def cmd_voice(args) -> int:
    from .tts import assemble, get_engine, synthesize

    from .voices import load_pools, pick_voices

    lesson_dir = Path(args.lesson_dir)
    manifest = json.loads((lesson_dir / "manifest.json").read_text(encoding="utf-8"))
    from .voices import load_voice_rules
    voices = pick_voices(manifest["lesson_id"], load_pools(args.engine), args.rotate, manifest.get("variety_code") or None,
                         load_voice_rules(), manifest.get("accent_sensitive", False))   # rotation from data/voices.json
    voices.update(dict(v.split("=", 1) for v in (args.voice or [])))                      # explicit --voice always wins
    (lesson_dir / "voices_used.json").write_text(json.dumps(voices, indent=2), encoding="utf-8")
    print(f"Voices for {manifest['lesson_id']}: {voices or 'engine defaults'}")
    from .voices import credits_for
    credit = credits_for(voices)
    if credit:
        (lesson_dir / "credits.txt").write_text(credit + "\n", encoding="utf-8")
    engine = get_engine(args.engine, voices, args.device)
    audio_dir = lesson_dir / f"audio_{args.engine}"
    synthesize(lesson_dir / "manifest.json", engine, audio_dir)
    res = assemble(lesson_dir, audio_dir, lesson_dir / f"lesson_{args.engine}.mp4", args.size, args.allow_long)
    print(f"Narrated video: {res['video']}  ({res['seconds']} s)")
    if args.engine == "tone":
        print("NOTE: 'tone' is a silent test engine. It produces NO speech: use it only to check timing.")
    return 0


def cmd_qa(args) -> int:
    from .qa import run_qa

    passed, report = run_qa(args.lesson_dir, args.engine, args.transcribe)
    print(report)
    (Path(args.lesson_dir) / "qa_report.txt").write_text(report + "\n", encoding="utf-8")
    return 0 if passed else 3


def cmd_check(args) -> int:
    from .lessons import load_lesson
    from .quality import quality_issues

    from .curriculum import known_phrases, load_topics, taught_elsewhere
    from .lessons import layout_problems

    try:
        lesson = load_lesson(args.lesson)
    except ValueError as exc:
        print(f"BLOCK {exc}")
        print("CHECK: BLOCK (not publishable yet)")
        return 4
    topics = load_topics()
    issues = quality_issues(lesson, topics, known_phrases(lesson, topics, Path(args.lesson).parent))
    issues += [("BLOCK", f"layout: {m}") for m in layout_problems(lesson)]
    if not lesson.get("reuse_ok"):
        issues += [("WARN", f"duplicate: {m} (set \"reuse_ok\": true if this is a deliberately different angle)")
                   for m in taught_elsewhere(lesson, Path(args.lesson).parent)]
    for lvl, msg in issues:
        print(f"{lvl} {msg}")
    blocked = any(l == "BLOCK" for l, _ in issues)
    publishable = not issues or all(l == "WARN" for l, _ in issues)
    print("CHECK: " + ("BLOCK" if blocked else "OK") + ("" if publishable else " (not publishable yet)"))
    return 4 if blocked else 0


def cmd_storyboard(args) -> int:
    from .lessons import load_lesson, storyboard

    print(storyboard(load_lesson(args.lesson)), end="")
    return 0


def cmd_upload(args) -> int:
    from .curriculum import known_phrases, load_topics
    from .lessons import load_lesson
    from .upload import UploadError, publish

    lesson = load_lesson(args.lesson)
    topics = load_topics()
    try:
        res = publish(lesson, Path(args.lesson_dir), args.engine, args.ledger, args.privacy, not args.not_synthetic,
                      args.dry_run, args.if_configured, topics, known_phrases(lesson, topics, Path(args.lesson).parent))
    except UploadError as exc:
        print(f"UPLOAD REFUSED: {exc}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS"):  # visible as an annotation on the run; the message never holds a credential
            print(f"::error title=Upload refused::{str(exc).replace(chr(10), ' ')[:900]}")
        return 5
    if res["status"] == "skipped":
        print(f"NOT UPLOADED ({res['reason']}). Metadata that would be sent:")
        print(json.dumps(res["metadata"], indent=2, ensure_ascii=False))
    elif res["status"] == "already-uploaded":
        print(f"already uploaded: {res['id']} -> https://youtu.be/{res['video_id']}")
    else:
        print(f"UPLOADED {res['id']} -> {res['url']} (privacy: {args.privacy})")
    return 0


def cmd_next(args) -> int:
    from .curriculum import brief, load_topics, next_part, status

    topics = load_topics()
    print("\n".join(status(topics, args.lessons_dir)) + "\n")
    pending = {x.strip() for x in (args.pending or "").split(",") if x.strip()}
    nxt = next_part(topics, args.lessons_dir, pending)
    if not nxt:
        print("All topics are written: add a new topic to data/curriculum.json.")
        return 0
    print(brief(*nxt))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scriptstudio", description="Automated Spanish lesson Shorts")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("lesson", help="build cards, narration manifest and silent preview from a lesson JSON")
    s.add_argument("lesson")
    s.add_argument("--out", default="output/lessons")
    s.add_argument("--size", choices=["short", "wide"], default="short")
    s.add_argument("--no-preview", action="store_true")
    s.set_defaults(fn=cmd_lesson)

    s = sub.add_parser("voice", help="generate voice for a built lesson and assemble the narrated video")
    s.add_argument("lesson_dir", help="folder created by the lesson command")
    s.add_argument("--engine", choices=["kokoro", "mixed", "chatterbox", "tone"], default="kokoro")
    s.add_argument("--voice", action="append", help="override voice per language, e.g. es=ef_dora")
    s.add_argument("--rotate", type=int, default=None, help="force the rotation number instead of the one in the lesson id")
    s.add_argument("--device", default="cuda", help="chatterbox only: cuda or cpu")
    s.add_argument("--size", choices=["short", "wide"], default="short")
    s.add_argument("--allow-long", action="store_true", help="skip the 40 s limit for Shorts")
    s.set_defaults(fn=cmd_voice)

    s = sub.add_parser("next", help="show topic progress and the ready-to-use brief for the next lesson to write")
    s.add_argument("--lessons-dir", default="lessons")
    s.add_argument("--pending", default="", help="comma-separated lesson ids already written on unapproved branches (skipped)")
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("upload", help="upload an approved, built lesson to YouTube after every gate passes (docs/UPLOAD.md)")
    s.add_argument("lesson_dir", help="folder created by the lesson command, after voice and qa")
    s.add_argument("--lesson", required=True, help="the lesson json")
    s.add_argument("--engine", choices=["kokoro", "mixed", "chatterbox", "tone"], default="mixed")
    s.add_argument("--ledger", default="ledger.json", help="json file recording what was uploaded (never upload twice)")
    s.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    s.add_argument("--not-synthetic", action="store_true", help="do NOT declare synthetic media (default: declared)")
    s.add_argument("--dry-run", action="store_true", help="run every gate and print the metadata, upload nothing")
    s.add_argument("--if-configured", action="store_true", help="skip quietly when the YouTube secrets are not set")
    s.set_defaults(fn=cmd_upload)

    s = sub.add_parser("storyboard", help="print the whole Short as a timeline (heard, shown, seconds) to judge its flow")
    s.add_argument("lesson")
    s.set_defaults(fn=cmd_storyboard)

    s = sub.add_parser("check", help="lesson quality rules before rendering (exit 4 on BLOCK)")
    s.add_argument("lesson")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("qa", help="automatic quality gate for a finished lesson video (exit 3 on FAIL)")
    s.add_argument("lesson_dir", help="folder created by the lesson command, after the voice command")
    s.add_argument("--engine", choices=["kokoro", "mixed", "chatterbox", "tone"], default="kokoro")
    s.add_argument("--transcribe", action="store_true", help="let Whisper check every spoken clip against the script (needs faster-whisper)")
    s.set_defaults(fn=cmd_qa)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (ValueError, RuntimeError, FileNotFoundError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
