# Spanish Shorts Studio

Automated English-to-Spanish lesson **Shorts**. One lesson file (`lessons/<id>.json`) becomes a finished vertical video of at most 40 seconds: cards, narration with rotating voices, a quality gate, and (optionally) an upload to YouTube after a person approves it. Built to run on GitHub Actions; nothing needs a local machine.

The Spanish in this repository is **Argentine (Rioplatense, voseo)**. Every line is checked by an AI model and recorded in `docs/LANGUAGE_REVIEW.md`; no native speaker has reviewed it. Treat it as a learning aid, and corrections are welcome (open an issue).

## How a lesson becomes a video
`data/curriculum.json` (topics and parts) -> `next` (what to write next, with a ready brief) -> `lessons/<id>.json` -> `check` (quality rules before rendering) -> `lesson` (cards, storyboard, card sheet) -> `voice` (voices, ffmpeg) -> `qa` (measurements and Whisper read-back) -> a person approves (merge) -> upload.

What the gates enforce, in short: at most 40 s; a spoken opening phrase in the first second; one teaching point per phrase; a question is taught before its answer; dialogue and quiz reuse only phrases already taught; text inside the safe zone; loudness and silence limits; no off-topic lessons. Details: `docs/LESSON_SPEC.md`.

## Commands
```bash
export PYTHONPATH=src
python -m scriptstudio next                                   # progress and the brief for the next lesson
python -m scriptstudio check lessons/es-a1-greetings-01.json  # quality rules (exit 4 on BLOCK)
python -m scriptstudio storyboard lessons/es-a1-greetings-01.json
python -m scriptstudio lesson lessons/es-a1-greetings-01.json
python -m scriptstudio voice output/lessons/es-a1-greetings-01 --engine mixed
python -m scriptstudio qa output/lessons/es-a1-greetings-01 --engine mixed --transcribe
python -m scriptstudio upload output/lessons/es-a1-greetings-01 --lesson lessons/es-a1-greetings-01.json --dry-run
```
Voice engines: `mixed` (default: Piper and Kokoro voices from `data/voices.json`), `kokoro`, `tone` (silent timing check, needs no model). Tests: `PYTHONPATH=src python -m unittest discover -s tests` (about two minutes, ffmpeg is used).

## Workflows (`.github/workflows/`)
- `lessons.yml`: builds changed lessons, runs the QA gate, publishes videos and `report.txt` to the `renders` branch.
- `publish.yml`: when a lesson is merged into `main`, builds it again and uploads it to YouTube as a private video. It does a dry run until the three YouTube secrets exist. See `docs/UPLOAD.md`.
- `voices.yml`: voice audition samples.
- `next-brief.yml`: weekly issue with the brief for the next lesson.

Credentials are read only from GitHub Actions secrets (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`). Nothing is uploaded without a merged lesson, and YouTube forces API uploads from unverified projects to private, so a person makes each video public.

## Documentation
`docs/LESSON_SPEC.md` (what a good lesson is), `docs/AUTOMATION.md` (stages and guardrails), `docs/UPLOAD.md` (YouTube setup), `docs/DEPLOY.md` (running production), `docs/VOICES.md` (voices and their licences), `docs/LANGUAGE_REVIEW.md` (how the Spanish is checked).

## Licence and credits
Code and lesson files: MIT (`LICENSE`). Voices and third-party software have their own terms: read `NOTICE.md` before publishing videos. In particular, the legal position of the `es_AR-daniela-high` voice for monetised videos has **not** been fully checked.

Security: `SECURITY.md`.
