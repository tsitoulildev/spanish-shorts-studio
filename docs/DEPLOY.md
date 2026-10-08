# Running production

Lessons are built automatically on a GitHub-hosted runner; a person only reviews and approves. The same scripts also run on any Linux server.

## GitHub Actions
- `.github/workflows/lessons.yml` builds every `lessons/*.json` when a lesson file or the code changes, or on demand (Actions > Build lessons > Run workflow; choose the engine and optionally a lesson list).
- Output: the finished mp4, narration, storyboard, card sheet, manifest and log are attached to the run (kept 30 days). Every run also copies the videos and a `report.txt` (duration, loudness, silence, QA verdict per video) to the `renders` branch, folder `latest/`, so a build can be reviewed with `git fetch origin renders`. Each run adds a commit, and videos are binary, so keep runs purposeful.
- Builds are serialised (one at a time) because every run publishes to the same branch.
- No secrets are needed to build. The voice models download from Hugging Face on the runner and are cached.
- Free minutes depend on the account and on whether the repository is public or private: check the current GitHub pricing page.
- The upload workflow (`publish.yml`) is described in `docs/UPLOAD.md`.

## Any other Linux server (optional)
```bash
git clone <this repository>
cd <this repository>
bash scripts/setup_server.sh          # ffmpeg, espeak-ng, fonts, .venv, Kokoro
```
`SKIP_KOKORO=1 bash scripts/setup_server.sh` installs only the video tools.

## Run
```bash
bash scripts/make_lessons_server.sh                 # all lessons/*.json without a video yet
ENGINE=tone bash scripts/make_lessons_server.sh     # silent timing check, no voice model needed
LESSONS="lessons/es-a1-greetings-01.json" FORCE=1 bash scripts/make_lessons_server.sh
```
Output: `output/lessons/<name>/lesson_<engine>.mp4`. Logs: `logs/`. The exit code is non-zero if any lesson failed.

## Rules
- Never put keys or tokens in code or commits; use environment variables or GitHub Actions secrets.
- Every Spanish line is checked and recorded in `docs/LANGUAGE_REVIEW.md`. These scripts build videos; they do not publish.
- Run heavy steps one at a time on a small machine.
