# Lesson specification: what a good Short is, written so a writer (human or agent) cannot drift

Every rule is either enforced by `scriptstudio check` (marked **[check]**) or by the reviewer checklist at the end.
Read the finished `scriptstudio storyboard <lesson>` output before calling a lesson done: it shows the whole Short in order.

## 1. One story, one promise
A Short is one small story: **promise, then keep it, then prove it**.
- Hook (max 14 words) promises one concrete result about THIS lesson's phrases, e.g. "Meet someone in Spanish. Four phrases." Never a generic greeting, never a channel intro. **[check: length]**
- The cold open (`cold_open.phrase`, phrase 1 or 2) is spoken first, before any English, and stays on screen under the hook. It must be one of the phrases that keeps the promise, and never the quiz answer. **[check]**
- Phrases (3 to 5, 4 is ideal) keep the promise, in the order a real conversation uses them: meet, ask, answer, return the question, leave. A question is always taught before its answer. **[check: question before answer]**
- Dialogue (two female voices A and B) is a real exchange that uses only phrases the viewer has met: this lesson's or earlier lessons'. No new words appear in the dialogue or the quiz. **[check: known phrases]**
- Quiz tests one phrase taught in this lesson; the wrong choices are also known phrases that are plausible but wrong. **[check]**
- Outro names the next step (the next part, or follow). **[check]**

## 2. Each phrase earns its place
- `target` max 7 words. `translation` natural English. `pronunciation` English-style respelling, capitals mark the stress. **[check]**
- `when` (or `note`): one teaching point beyond the translation: when to use it, a trap, a cultural note. A phrase without one is BLOCKED. **[check]**
- Prefer phrases a learner will use this week. No filler words, no textbook sentences nobody says.

## 3. Spanish
- Series variety: Argentine (Rioplatense), voseo (`¿Cómo te llamás?`, `¿De dónde sos?`, `vos`).
- `variety_code`: `neutral` if the phrase is identical in Argentina and Mexico (any female voice may read it), `argentine` if it uses voseo or Argentine-only usage (only the Argentine voice reads it). **[check]**
- Never present a regional phrase as universal. Fill `variety` honestly.
- Voices are always female. Pronunciation hints must describe the Argentine accent where it matters (`ll`, `y` as "sh").
- No song lyrics, book quotes or copied lines from other channels.
- Every Spanish line is checked by the writer and recorded in `docs/LANGUAGE_REVIEW.md` (no native reviewer, owner decision). `review_status` stays `NOT reviewed` until that record exists, then `auto-reviewed: ...`. **[check: PUBLISH flag]**

## 4. Time and look
- Estimated length stays under 40 s (the estimate is cautious: real videos are about 6 s shorter). The build refuses an over-long Short. **[check]**
- Text stays inside the safe zone (5 % sides, 80 % bottom) and is never smaller than 42 px. **[check: layout BLOCK]**
- A phrase is never taught in a second lesson by accident. **[check: duplicate WARN]** A deliberate repeat needs `"reuse_ok": true`.
- The lesson id must exist in `data/curriculum.json` (topic arcs finish before the next topic starts). **[check]**

## 5. Reviewer checklist (a second reading of the storyboard, one line per answer in the PR)
1. Does the hook promise exactly what the first taught phrase delivers?
2. Is there any moment where a viewer would ask "why is this here?"
3. Does every question come before its answer, and every dialogue line use only met phrases?
4. Would a beginner remember at least one phrase and know when to use it?
5. Is each Spanish line correct, natural, and right for the declared variety?
6. Are the 4 teaching points different from each other and from the previous part?
7. Is the outro a real next step?
Any "no" means rewrite, not publish.
