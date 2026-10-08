#!/usr/bin/env bash
# Builds every lesson in lessons/*.json that has no finished video yet, on a Linux server. Safe to run on a schedule:
# lessons that are already built are skipped, a failed lesson does not stop the others, and the exit code is non-zero
# if anything failed.
#
# Environment variables (all optional):
#   ENGINE   kokoro (default) | tone (silent timing check) | chatterbox (needs a GPU)
#   LESSONS  space-separated lesson files; default: all lessons/*.json
#   OUT      output folder; default: output/lessons
#   FORCE=1  rebuild lessons that already have a video
#   QA_FLAGS extra flags for the quality gate, e.g. "--transcribe" (Whisper checks the spoken audio against the script)
set -uo pipefail
cd "$(dirname "$0")/.."

ENGINE="${ENGINE:-kokoro}"
OUT="${OUT:-output/lessons}"
LESSONS="${LESSONS:-$(ls lessons/*.json 2>/dev/null)}"

if [ ! -f .venv/bin/activate ]; then echo "No .venv found. Run: bash scripts/setup_server.sh" >&2; exit 1; fi
# shellcheck disable=SC1091
source .venv/bin/activate
export PYTHONUTF8=1

mkdir -p "$OUT" logs
LOG="logs/make_lessons_$(date -u +%Y%m%dT%H%M%SZ).log"
fail=0; built=0; skipped=0

on_exit() {   # diagnostics: if the script is killed silently (memory, signal), the log still says so
  rc=$?
  echo "script exit rc=$rc" | tee -a "$LOG"
  if [ "$rc" -ne 0 ]; then free -m 2>&1 | tee -a "$LOG"; dmesg 2>/dev/null | tail -5 | tee -a "$LOG"; fi
}
trap on_exit EXIT

for lesson in $LESSONS; do
  name="$(basename "$lesson" .json)"
  video="$OUT/$name/lesson_${ENGINE}.mp4"
  if [ -f "$video" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "skip   $name (already built)" | tee -a "$LOG"; skipped=$((skipped+1)); continue
  fi
  echo "build  $name  engine=$ENGINE" | tee -a "$LOG"
  chk="$(python -m scriptstudio check "$lesson" 2>&1)"; echo "$chk" | tee -a "$LOG"
  if [[ "$chk" == *"CHECK: OK"* ]] \
     && python -m scriptstudio lesson "$lesson" --out "$OUT" >>"$LOG" 2>&1 \
     && python -m scriptstudio voice "$OUT/$name" --engine "$ENGINE" --device cpu >>"$LOG" 2>&1 \
     && [ -s "$video" ] \
     && python -m scriptstudio qa "$OUT/$name" --engine "$ENGINE" ${QA_FLAGS:-} >>"$LOG" 2>&1; then
    echo "ok     $name -> $video" | tee -a "$LOG"; built=$((built+1))
  else
    echo "FAILED $name (see $LOG)" | tee -a "$LOG"; fail=1
    [ -f "$OUT/$name/qa_report.txt" ] && sed 's/^/       qa: /' "$OUT/$name/qa_report.txt" | tee -a "$LOG"
  fi
done

echo "done: built=$built skipped=$skipped failed=$fail  log=$LOG"
exit $fail
