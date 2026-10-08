# Automation: how a lesson goes from curriculum to approval, and who does what

Goal: the channel runs itself; a human only approves. Nothing here needs a paid service or a secret.

| # | Stage | Who | Tool | Gate before moving on |
|---|---|---|---|---|
| 1 | Pick the next lesson | automatic | `scriptstudio next` (topic arcs in `data/curriculum.json`) | none left -> open an issue and stop |
| 2 | Write the lesson file | Claude session (scheduled task, see below) | follows `docs/LESSON_SPEC.md` | `scriptstudio check` has no BLOCK and no WARN |
| 3 | Read the storyboard | same session | `scriptstudio storyboard` + reviewer checklist | every checklist answer is yes |
| 4 | Build and measure | automatic, GitHub Actions | `lessons.yml`: render, voices, QA gate, Whisper | QA PASS: 40 s, loudness, first sound, silence |
| 5 | Look at the result | same session | `renders` branch: `report.txt`, `<id>_storyboard.txt`, `<id>_cards.png` | no FAIL, WARNs explained |
| 6 | Ask for approval | same session | pull request into `main` | **a human merges (approves) or closes (rejects)** |
| 7 | Publish to YouTube | human, manually | not automated | maintainer decision, only on request |

## The writer run (what the scheduled task does, in order)
1. `git fetch`, start from the latest `main`. List the unapproved lessons: the branches from `git ls-remote --heads origin 'lesson/*'` whose id has NO `lessons/<id>.json` on `main` yet (check with `git cat-file -e origin/main:lessons/<id>.json`; a merged branch that was left behind does not count). If there are already 2 or more, stop: the human is the bottleneck, do not pile up lessons. Otherwise run `PYTHONPATH=src python -m scriptstudio next --pending <ids from those branch names, comma separated>`. If it says all topics are written, open an issue "Curriculum finished: add a new topic" and stop.
2. Create branch `lesson/<id>` (id from the brief).
3. Write `lessons/<id>.json` from the brief and `docs/LESSON_SPEC.md`. Add the matching section to `docs/LANGUAGE_REVIEW.md` (each Spanish line, variety, why it is correct). Only then set `review_status` to `auto-reviewed: ...`.
4. Run `check` until it prints `CHECK: OK` with no WARN; run `storyboard`, read it, answer the reviewer checklist honestly. Run the unit tests.
5. Commit only `lessons/<id>.json` and `docs/LANGUAGE_REVIEW.md`; push the branch. The push starts the build in GitHub Actions.
6. Read the result from the `renders` branch (`git fetch origin renders`): `latest/report.txt`, `latest/<id>_storyboard.txt`, `latest/<id>_cards.png`. Look at the picture. If QA FAILs or the flow is wrong, fix the lesson file and push again (at most 3 rounds), then stop and open an issue "Lesson <id> needs help" with what is wrong.
7. Open a pull request from `lesson/<id>` to `main`: body = storyboard, the QA lines, the checklist answers, and the paths of the video and card sheet on `renders`. Never merge it. `gh pr create` does not work in these sessions (GraphQL is blocked): write the title, head, base and body to a JSON file and run `gh api repos/OWNER/REPO/pulls --method POST --input file.json`.

## Guardrails (hard)
- The writer touches only `lessons/<id>.json` and `docs/LANGUAGE_REVIEW.md`. Any other changed file means the run is wrong: stop and report.
- Only branches named `lesson/*` are pushed. No force-push, no history rewrite, no deleting branches, no secrets, no tags.
- One lesson per run. No run publishes anything to YouTube.
- If a gate fails and it cannot be fixed within 3 rounds, an issue is opened. The run never lowers a rule to pass.

## What the human does
Watch the video (linked in the pull request), listen to the Spanish, then merge (approve) or close with a comment (reject). That is the whole job. The merged file is what gets published, manually.

## Known limits (said plainly)
- The QA gate measures sound and picture, not whether the story makes sense; the storyboard, card sheet and checklist exist for that, and the final judge is the human.
- The writer and the checklist reviewer are the same kind of model, so the review is a second reading, not an independent one. No native speaker reviews the Spanish (project decision); the Whisper check and the human ear are the safety net.
- Whisper mishears some synthetic Spanish; a mismatch is a hint, not a verdict.
- The scheduled task needs the repository and a way to push branches; if the session cannot push, it must report that and stop.

## Pause or change
Disable or delete the scheduled task from the Claude app to stop all automatic writing. Cadence and rules live in this file and in `docs/LESSON_SPEC.md`: improve them and the next run follows them.
