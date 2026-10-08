"""Upload an approved, built lesson to YouTube (Data API v3, resumable upload).

Design rules (docs/UPLOAD.md):
- Nothing is uploaded unless every gate passes: lesson quality check, QA gate PASS, length <= 40 s, reviewed Spanish.
- Credentials come only from environment variables (repo secrets in CI). They never touch a file or a log.
- An id in the ledger is never uploaded twice.
- Videos from an unverified API project are forced to private by YouTube: a human makes them public in Studio.
- The HTTP layer is injectable so the whole flow is tested without a network.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
MAX_SECONDS = 40.0
CATEGORY_EDUCATION = "27"
BASE_TAGS = ["learn spanish", "spanish for beginners", "argentine spanish", "spanish phrases", "shorts"]
HASHTAGS = "#Shorts #LearnSpanish #SpanishForBeginners #ArgentineSpanish"


class UploadError(RuntimeError):
    pass


def _clean(text: str) -> str:
    return str(text).replace("<", "").replace(">", "").strip()


def hook_title(hook: str) -> str:
    """'Stop saying only “Hola”. Four greetings.' -> 'Stop saying only “Hola” – four greetings'."""
    parts = [p.strip().rstrip(".") for p in re.split(r"(?<=[.!?])\s+", hook.strip()) if p.strip()]
    if not parts:
        return ""
    rest = [p[0].lower() + p[1:] if len(p) > 1 and not p.startswith("I ") else p for p in parts[1:]]
    return " – ".join([parts[0]] + rest)


def build_metadata(lesson: dict, credits: str = "", privacy: str = "private", synthetic: bool = True) -> dict:
    """Title, description, tags and status from the lesson file alone, so a video never needs hand-written text."""
    base = _clean(hook_title(lesson.get("hook") or lesson["topic"]))
    title = f"{base} | Spanish A1"
    if len(title) > 100:
        title = base[:100].rstrip()
    lines = [_clean(lesson.get("hook", "")), "", "In this Short:"]
    for p in lesson["phrases"]:
        pron = f" ({p['pronunciation']})" if p.get("pronunciation") else ""
        lines.append(f"• {p['target']} = {p['translation']}{pron}")
    lines += ["", "Argentine Spanish (Rioplatense). Spot a mistake or a better way to say it? Tell us in the comments.",
              "", "The voices in this video are synthetic (text-to-speech)."]
    if credits.strip():
        lines += ["", _clean(credits)]
    lines += ["", HASHTAGS]
    description = "\n".join(_clean(x) if x else "" for x in lines)
    tags = list(dict.fromkeys(BASE_TAGS + [_clean(lesson["topic"]).lower()]))
    while sum(len(t) + 1 for t in tags) > 480:
        tags.pop()
    return {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": CATEGORY_EDUCATION,
                    "defaultLanguage": "en", "defaultAudioLanguage": "en"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": bool(synthetic),
                   "embeddable": True},
    }


def metadata_problems(meta: dict) -> list[str]:
    s = meta["snippet"]
    out = []
    if not s["title"]:
        out.append("empty title")
    if len(s["title"]) > 100:
        out.append("title longer than 100 characters")
    if len(s["description"]) > 5000:
        out.append("description longer than 5000 characters")
    if "<" in s["title"] + s["description"] or ">" in s["title"] + s["description"]:
        out.append("title or description contains < or >, which YouTube rejects")
    if meta["status"]["privacyStatus"] not in ("private", "unlisted", "public"):
        out.append("privacyStatus must be private, unlisted or public")
    return out


def video_seconds(video: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, check=False)
    try:
        return float(r.stdout.strip())
    except ValueError as exc:
        raise UploadError(f"cannot read the length of {video}") from exc


def gate_problems(lesson: dict, lesson_dir: Path, engine: str, topics: list[dict] | None = None,
                  known: set[str] | None = None, seconds: float | None = None) -> list[str]:
    """Every reason this lesson must NOT be uploaded. Empty list = allowed."""
    from .quality import quality_issues

    out = [f"{lvl}: {msg}" for lvl, msg in quality_issues(lesson, topics, known) if lvl in ("BLOCK", "PUBLISH")]
    video = lesson_dir / f"lesson_{engine}.mp4"
    if not video.exists() or video.stat().st_size == 0:
        out.append(f"no built video at {video}")
    qa = lesson_dir / "qa_report.txt"
    if not qa.exists():
        out.append("no qa_report.txt: the QA gate has not run")
    elif "QA: PASS" not in qa.read_text(encoding="utf-8"):
        out.append("the QA gate did not pass")
    if video.exists():
        secs = seconds if seconds is not None else video_seconds(video)
        if secs > MAX_SECONDS:
            out.append(f"video is {secs:.1f} s, limit {MAX_SECONDS:.0f} s")
    return out


def load_ledger(path: Path | str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_ledger(path: Path | str, ledger: dict) -> None:
    Path(path).write_text(json.dumps(ledger, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def credentials_from_env(env: dict | None = None) -> tuple[str, str, str] | None:
    e = os.environ if env is None else env
    vals = tuple(e.get(k, "").strip() for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))
    return vals if all(vals) else None  # type: ignore[return-value]


def access_token(creds: tuple[str, str, str], http) -> str:
    cid, secret, refresh = creds
    r = http.post(TOKEN_URL, data={"client_id": cid, "client_secret": secret, "refresh_token": refresh,
                                   "grant_type": "refresh_token"}, timeout=60)
    if r.status_code != 200:
        # the response may echo parts of the request: report only the status and Google's error code
        code = ""
        try:
            code = r.json().get("error", "")
        except ValueError:
            pass
        raise UploadError(f"could not refresh the YouTube token (HTTP {r.status_code} {code}); see docs/UPLOAD.md")
    return r.json()["access_token"]


def upload_video(video: Path, meta: dict, token: str, http) -> dict:
    """Resumable upload: one request opens the session, one sends the bytes (a Short is a few MB)."""
    size = video.stat().st_size
    init = http.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, json=meta, timeout=60,
                     headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                              "X-Upload-Content-Length": str(size)})
    if init.status_code != 200 or not init.headers.get("Location"):
        raise UploadError(f"YouTube refused to start the upload (HTTP {init.status_code}): {init.text[:300]}")
    with video.open("rb") as fh:
        put = http.put(init.headers["Location"], data=fh, timeout=600,
                       headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    if put.status_code not in (200, 201):
        raise UploadError(f"YouTube upload failed (HTTP {put.status_code}): {put.text[:300]}")
    return put.json()


def publish(lesson: dict, lesson_dir: Path, engine: str, ledger_path: Path | str, privacy: str = "private",
            synthetic: bool = True, dry_run: bool = False, if_configured: bool = False, topics: list[dict] | None = None,
            known: set[str] | None = None, http=None, env: dict | None = None, seconds: float | None = None) -> dict:
    """Run every gate, then upload. Returns {'status': ..., ...}. Raises UploadError when something is wrong."""
    lid = lesson["id"]
    ledger = load_ledger(ledger_path)
    if lid in ledger:
        return {"status": "already-uploaded", "id": lid, "video_id": ledger[lid]["video_id"]}
    problems = gate_problems(lesson, lesson_dir, engine, topics, known, seconds)
    if problems:
        raise UploadError("not uploaded, gates failed: " + "; ".join(problems))
    credits_file = lesson_dir / "credits.txt"
    meta = build_metadata(lesson, credits_file.read_text(encoding="utf-8") if credits_file.exists() else "", privacy, synthetic)
    bad = metadata_problems(meta)
    if bad:
        raise UploadError("bad metadata: " + "; ".join(bad))
    creds = credentials_from_env(env)
    if dry_run or (creds is None and if_configured):
        why = "dry run" if dry_run else "YouTube credentials are not set (see docs/UPLOAD.md)"
        return {"status": "skipped", "reason": why, "id": lid, "metadata": meta}
    if creds is None:
        raise UploadError("YouTube credentials are not set: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (docs/UPLOAD.md)")
    if http is None:
        import requests
        http = requests
    token = access_token(creds, http)
    res = upload_video(lesson_dir / f"lesson_{engine}.mp4", meta, token, http)
    ledger[lid] = {"video_id": res["id"], "privacy": privacy}
    save_ledger(ledger_path, ledger)
    return {"status": "uploaded", "id": lid, "video_id": res["id"], "url": f"https://youtu.be/{res['id']}"}
