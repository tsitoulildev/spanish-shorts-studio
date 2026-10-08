# Voices

Goal: a smooth, natural female Spanish voice, and several voices that rotate so two consecutive lessons do not sound the same. Pronunciation quality cannot be judged from text: a person has to listen.

## Rotation
`data/voices.json` holds pools per engine, language and role (A = main voice, B = dialogue partner). Lesson number n takes `pool[n % len]`; the partner comes from its own pool and never equals voice A when avoidable. `--voice es=<name>` overrides. Voices that need a credit write a `credits.txt` next to the video (paste it into the video description).

## Engines (audition samples: workflow `voices.yml`, output on the `renders` branch)
| Engine | Licence as found | Notes |
|---|---|---|
| Kokoro | Apache-2.0 code; weights licence not separately confirmed | CPU, light. English narrator `af_heart`. Spanish voices `ef_dora` (female), `em_alex`, `em_santa` (male, not used) |
| Piper | GPL-3.0 code (`piper-tts`); each voice has its own model card | CPU. Used through its command line as a separate program |
| Chatterbox Multilingual | MIT | Needs a GPU, adds an inaudible watermark: not usable on free runners |
| XTTS-v2 | CPML weights | Not recommended: commercial terms unclear |

## Voices in use (engine `mixed`)
- **es_AR-daniela-high** (Piper): Argentine accent. Licence on the model card: CC BY-SA 4.0, credit required. The card says the voice was adapted from a US English base ("lessac"). OPEN, NOT VERIFIED: whether the audio may be used in monetised videos, and whether ShareAlike reaches generated audio, are legal questions that have not been answered. Fallbacks to audition: `es_MX-claude-high` (Apache-2.0 as listed), `es_ES-davefx-medium` (CC0).
- **es_ES-sharvard-medium, speaker 1** (Piper, voice id `piper:es_ES-sharvard-medium@1`, passed as `--speaker 1`): Spain accent. Licence CC BY 3.0, credit required, commercial use allowed.
- **Kokoro `af_heart`**: English narrator.

## Rules for speech
- Spanish is spoken only by a female voice, the dialogue partner included. A test fails if a male Spanish voice enters a pool.
- Speech must not be fast: Piper length-scale for Spanish "clear" is 1.2 and "slow" 1.4; the English narrator "fast" is 1.05. QA fails any video over 40 s.
- Accent rules (`voice_rules` in `data/voices.json`): a voseo lesson (`variety_code: argentine`) is read only by Daniela. The Spain voice reads a lesson only if `variety_code` is `neutral` and the Spanish text has no accent-sensitive letters (z, ce, ci, ll, y+vowel: Spain says "gracias" with a th sound, Argentina with an s, so one respelling cannot fit both). This is detected automatically (`accent_sensitive`).
- Whisper reads every spoken clip back against the script. It sometimes mishears synthetic Spanish (for example "Hola"), so a mismatch is a hint, not a verdict; clips of one or two words are reported as INFO only.
