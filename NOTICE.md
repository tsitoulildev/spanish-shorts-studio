# Notice and credits

This is a notice of the third-party material this project uses, not legal advice. Licences were taken from the sources named here and have not all been independently verified.

## Voices
| Voice | Used for | Licence as found | Credit |
|---|---|---|---|
| `es_AR-daniela-high` (Piper voices) | Spanish, Argentine accent | CC BY-SA 4.0 (model card) | Required. Line written to `credits.txt` and to the YouTube description: "Spanish voice: es_AR-daniela-high (Piper voices, CC BY-SA 4.0, https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_AR/daniela/high)" |
| `es_ES-sharvard-medium`, speaker 1 (Piper voices) | Spanish, Spain accent | CC BY 3.0 (model card) | Required. "Spanish voice: es_ES-sharvard-medium speaker 1 (Piper voices, CC BY 3.0, https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_ES/sharvard/medium)" |
| Kokoro `af_heart` | English narrator | Apache-2.0 as listed for Kokoro-82M; not independently verified | Recommended |

**Voice licensing caveat.** The model card for `es_AR-daniela-high` states that the voice was adapted from a US English base. Whether that voice may be used in monetised videos, and whether the ShareAlike term of CC BY-SA 4.0 reaches audio generated with it, is a legal question that has **not** been fully checked. Do not rely on this repository for that answer. Fallback voices to audition are listed in `docs/VOICES.md`. All videos are disclosed as containing synthetic voices.

## Software
| Component | Licence | How it is used |
|---|---|---|
| Piper (`piper-tts`) | GPL-3.0 | Called as a separate command-line program on the runner; not bundled or distributed here |
| Kokoro (`kokoro`) | Apache-2.0 | Python library installed on the runner |
| espeak-ng | GPL-3.0 | System package used by the speech engines |
| faster-whisper and Whisper models | MIT | Reads the spoken audio back to compare it with the script |
| FFmpeg | LGPL-2.1+ or GPL, depending on the build | System program for video and audio |
| Pillow | HPND | Draws the cards |
| DejaVu fonts | Bitstream Vera licence (free) | Card text on Linux |

## Images and text from other sources
No Wikipedia or Wikimedia Commons material, and no other third-party images, are used in this repository at present. The cards are drawn by code and the lesson text is original. If such material is added, list its author, licence and link here before publishing.

## YouTube
Uploads use the YouTube Data API v3 and are subject to the YouTube API Services Terms of Service and the platform's policies on synthetic content and on repetitive or templated content.
