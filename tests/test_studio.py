import json
import tempfile
import unittest
from pathlib import Path

from scriptstudio import cli

LESSON = Path(__file__).parent.parent / "lessons" / "es-a1-greetings-01.json"
HAS_FFMPEG = __import__("shutil").which("ffmpeg") is not None

class LessonTests(unittest.TestCase):
    def test_lesson_validation(self):
        from scriptstudio.lessons import LessonError, load_lesson, validate_lesson
        lesson = load_lesson(LESSON)
        self.assertEqual(validate_lesson(lesson), [])
        bad = dict(lesson, phrases=[{"target": "Hola.", "translation": ""}, {"target": "hola.", "translation": "x"}])
        problems = validate_lesson(bad)
        self.assertTrue(any("missing 'translation'" in p for p in problems))
        self.assertTrue(any("duplicate" in p for p in problems))
        self.assertTrue(any("between 3 and 20" in p for p in problems))
        with self.assertRaises(LessonError):
            from scriptstudio.lessons import load_lesson as ll
            with tempfile.TemporaryDirectory() as d:
                f = Path(d) / "x.json"
                f.write_text(json.dumps({"id": "x"}))
                ll(f)

    def test_manifest_structure(self):
        from scriptstudio.lessons import card_durations, load_lesson, plan
        lesson = load_lesson(LESSON)
        cards, segs = plan(lesson)
        n = len(lesson["phrases"])
        kinds = [c.kind for c in cards]
        self.assertEqual(kinds[:2], ["cold", "hook"])
        self.assertEqual(segs[0].lang, lesson["target_code"])   # the first thing heard is Spanish
        self.assertEqual(kinds[-1], "outro")
        self.assertEqual(kinds.count("phrase_q"), n)
        self.assertEqual(kinds.count("phrase_a"), n)
        self.assertEqual(kinds.count("dialogue"), len(lesson["dialogue"]))
        self.assertEqual(kinds.count("quiz_q"), len(lesson["quiz"]))
        self.assertEqual(kinds.count("quiz_a"), len(lesson["quiz"]))
        self.assertEqual(len({s.id for s in segs}), len(segs))
        self.assertEqual(len(card_durations(segs, len(cards))), len(cards))
        self.assertTrue(all(0 <= s.card < len(cards) for s in segs))
        first = [s for s in segs if s.id.startswith("p01")]
        self.assertEqual([s.speed for s in first], ["fast", "silent", "clear", "silent"])
        self.assertEqual(first[0].lang, "en")
        self.assertEqual(first[2].lang, "es")   # Spanish is spoken once per phrase, English only as the prompt
        self.assertLess(sum(g.est_seconds for g in segs), 46)   # a Short: max 40 s real, estimates run ~10% high
        self.assertEqual({s.voice for s in segs if s.id.startswith("d")}, {"A", "B"})  # two voices in the dialogue
        self.assertTrue(all(s.lang in ("en", "es", "-") for s in segs))

    def test_old_style_lesson_without_extras_still_builds(self):
        from scriptstudio.lessons import load_lesson, plan
        lesson = load_lesson(LESSON)
        for k in ("cold_open", "hook", "scene", "dialogue", "quiz", "outro"):
            lesson.pop(k, None)
        kinds = [c.kind for c in plan(lesson)[0]]
        self.assertEqual(kinds, ["hook"] + ["phrase_q", "phrase_a"] * len(lesson["phrases"]) + ["outro"])

    def test_dialogue_and_quiz_validation(self):
        from scriptstudio.lessons import load_lesson, validate_lesson
        lesson = load_lesson(LESSON)
        lesson["dialogue"] = [{"speaker": "C", "target": "x", "translation": ""}]
        lesson["quiz"] = [{"prompt": "q", "answer": "z", "choices": ["a", "b"]}]
        problems = " | ".join(validate_lesson(lesson))
        self.assertIn("speaker must be", problems)
        self.assertIn("missing 'translation'", problems)
        self.assertIn("must be one of", problems)

    def test_every_lesson_file_fits_a_short(self):
        from scriptstudio.lessons import MAX_SHORT_SECONDS, load_lesson, plan
        files = sorted((Path(__file__).parent.parent / "lessons").glob("*.json"))
        self.assertGreaterEqual(len(files), 2)
        for f in files:
            est = sum(g.est_seconds for g in plan(load_lesson(f))[1])   # load_lesson also validates
            self.assertLess(est, MAX_SHORT_SECONDS, f"{f.name} would likely be over the Short limit")

    def _long_lesson(self):
        from scriptstudio.lessons import load_lesson
        root = Path(__file__).parent.parent / "lessons"
        a, b = load_lesson(root / "es-a1-greetings-01.json"), load_lesson(root / "es-a1-greetings-02.json")
        return dict(a, id="es-long-test", phrases=a["phrases"] + b["phrases"], dialogue=a["dialogue"] + b["dialogue"],
                    quiz=a["quiz"] + b["quiz"])

    def test_too_long_lesson_is_rejected_unless_allowed(self):
        from scriptstudio.lessons import validate_lesson
        long = self._long_lesson()
        self.assertIn("too long for a Short", " | ".join(validate_lesson(long)))
        self.assertEqual(validate_lesson(dict(long, allow_long=True)), [])

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
    def test_assemble_refuses_video_over_40_seconds(self):
        from scriptstudio.lessons import LessonError, build_all
        from scriptstudio.tts import assemble, get_engine, synthesize
        with tempfile.TemporaryDirectory() as d:
            lf = Path(d) / "long.json"
            lf.write_text(json.dumps(dict(self._long_lesson(), allow_long=True)), encoding="utf-8")
            res = build_all(lf, d, preview=False)
            audio = res["dir"] / "audio"
            synthesize(res["dir"] / "manifest.json", get_engine("tone"), audio)
            with self.assertRaises(LessonError):
                assemble(res["dir"], audio, res["dir"] / "v.mp4")

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
    def test_build_and_voice_with_tone_engine(self):
        from scriptstudio.lessons import build_all
        from scriptstudio.tts import assemble, get_engine, synthesize, wav_seconds
        with tempfile.TemporaryDirectory() as d:
            res = build_all(LESSON, d, preview=False)
            lesson_dir = res["dir"]
            self.assertTrue((lesson_dir / "manifest.json").exists())
            self.assertTrue((lesson_dir / "narration.txt").read_text().startswith("[es/clear/A]"))
            audio = lesson_dir / "audio"
            wavs = synthesize(lesson_dir / "manifest.json", get_engine("tone"), audio)
            self.assertEqual(len(wavs), res["segments"] - sum(1 for g in json.loads((lesson_dir / "manifest.json").read_text())["segments"] if g["speed"] == "silent"))
            out = assemble(lesson_dir, audio, lesson_dir / "v.mp4")
            self.assertTrue(out["video"].exists() and out["video"].stat().st_size > 10000)
            self.assertGreater(out["seconds"], sum(wav_seconds(w) for w in wavs))  # pauses and silent cards added
            import subprocess
            vol = subprocess.run(["ffmpeg", "-i", str(out["video"]), "-af", "volumedetect", "-f", "null", "-"],
                                 capture_output=True, text=True).stderr
            self.assertIn("max_volume: -91", vol.replace("-inf", "-91") if "-inf" in vol else vol)  # test engine is silent

    def test_real_engines_fail_cleanly_without_install(self):
        from scriptstudio.tts import get_engine
        with self.assertRaises(ValueError):
            get_engine("nope")
        for name in ("kokoro", "chatterbox"):
            try:
                get_engine(name)
            except RuntimeError as exc:
                self.assertIn("not installed", str(exc))


class QaTests(unittest.TestCase):
    GOOD = {"duration": 33.0, "width": 1080, "height": 1920, "fps": 30.0, "has_audio": True, "lufs": -15.5,
            "peak": -1.4, "silence_total": 15.0, "silence_longest": 2.3, "black_total": 0.0}

    def test_good_video_passes(self):
        from scriptstudio.qa import evaluate
        self.assertEqual(evaluate(self.GOOD, planned_silence=14.0), [])

    def test_each_hard_failure_is_caught(self):
        from scriptstudio.qa import evaluate
        cases = {"duration": 41.0, "lufs": -25.0, "peak": 0.0, "silence_longest": 4.0, "black_total": 1.0, "width": 720}
        for key, bad in cases.items():
            res = evaluate(dict(self.GOOD, **{key: bad}), planned_silence=14.0)
            self.assertTrue(any(lvl == "FAIL" for lvl, _ in res), key)
        self.assertTrue(any("no audio" in msg for _, msg in evaluate(dict(self.GOOD, has_audio=False))))

    def test_dead_air_is_a_warning_not_a_failure(self):
        from scriptstudio.qa import evaluate
        res = evaluate(dict(self.GOOD, silence_total=21.0), planned_silence=12.6)
        self.assertEqual([lvl for lvl, _ in res], ["WARN"])

    def test_silent_engine_skips_audio_checks(self):
        from scriptstudio.qa import evaluate
        silent = dict(self.GOOD, lufs=-70.0, peak=-70.0, silence_total=33.0, silence_longest=33.0)
        self.assertEqual(evaluate(silent, audio_checks=False), [])

    def test_transcript_similarity_ignores_accents_case_and_punctuation(self):
        from scriptstudio.qa import similarity
        self.assertGreater(similarity("Buenos días.", "buenos dias"), 0.95)
        self.assertGreater(similarity("¿Cómo estás?", "Como estas"), 0.95)
        self.assertLess(similarity("Buenas noches.", "Buenos días"), 0.8)

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
    def test_measure_reads_a_real_file(self):
        import subprocess
        from scriptstudio.qa import measure
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "t.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x224466:s=1080x1920:r=30:d=2",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-pix_fmt", "yuv420p", str(v)], check=True)
            m = measure(v)
            self.assertEqual((m["width"], m["height"]), (1080, 1920))
            self.assertAlmostEqual(m["fps"], 30.0, places=1)
            self.assertTrue(m["has_audio"])
            self.assertAlmostEqual(m["duration"], 2.0, delta=0.2)
            self.assertGreater(m["lufs"], -40)


class VoiceRotationTests(unittest.TestCase):
    POOLS = {"es": {"A": ["f1", "f2", "f3"], "B": ["m1", "m2"]}, "en": {"A": ["n1"]}}

    def test_consecutive_lessons_never_share_a_voice(self):
        from scriptstudio.voices import pick_voices
        for n in range(1, 30):
            a, b = pick_voices(f"x-{n:02d}", self.POOLS), pick_voices(f"x-{n + 1:02d}", self.POOLS)
            self.assertNotEqual(a["es"], b["es"])
            self.assertNotEqual(a["es_b"], b["es_b"])

    def test_every_voice_in_the_pool_gets_used(self):
        from scriptstudio.voices import pick_voices
        used = {pick_voices(f"x-{n:02d}", self.POOLS)["es"] for n in range(1, 7)}
        self.assertEqual(used, {"f1", "f2", "f3"})

    def test_partner_is_never_the_same_voice_as_main(self):
        from scriptstudio.voices import pick_voices
        pools = {"es": {"A": ["v1", "v2"], "B": ["v1", "v2"]}}
        for n in range(1, 10):
            v = pick_voices(f"x-{n:02d}", pools)
            self.assertNotEqual(v["es"], v["es_b"])

    def test_single_voice_pool_and_missing_number_still_work(self):
        from scriptstudio.voices import pick_voices, rotation_index
        self.assertEqual(pick_voices("x-05", self.POOLS)["en"], "n1")
        self.assertEqual(rotation_index("no-number-here"), 0)
        self.assertEqual(pick_voices("x", {}), {})

    def test_shipped_pool_file_matches_the_engine_defaults(self):
        from scriptstudio.voices import load_pools, pick_voices
        v = pick_voices("es-a1-greetings-01", load_pools("kokoro"))
        self.assertEqual(v["es"], "ef_dora")
        self.assertIn("en", v)


class CliTests(unittest.TestCase):
    def test_check_and_next_commands(self):
        self.assertEqual(cli.main(["check", "lessons/es-a1-greetings-01.json"]), 0)
        self.assertEqual(cli.main(["next"]), 0)

    def test_check_blocks_a_lesson_that_is_not_in_the_plan(self):
        les = json.loads(Path("lessons/es-a1-greetings-01.json").read_text(encoding="utf-8"))
        les["id"] = "es-a1-unplanned-01"
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.json"
            f.write_text(json.dumps(les), encoding="utf-8")
            self.assertEqual(cli.main(["check", str(f)]), 4)

    def test_removed_sales_script_commands_are_gone(self):
        with self.assertRaises(SystemExit):
            cli.main(["generate", "x.json"])


class QualityRuleTests(unittest.TestCase):
    def _lesson(self, **kw):
        base = json.loads(Path("lessons/es-a1-greetings-01.json").read_text(encoding="utf-8"))
        base.update(kw)
        return base

    def test_shipped_lessons_have_no_blockers(self):
        from scriptstudio.quality import quality_issues
        for f in sorted(Path("lessons").glob("*.json")):
            lesson = json.loads(f.read_text(encoding="utf-8"))
            self.assertFalse([m for l, m in quality_issues(lesson) if l == "BLOCK"], f.name)

    def test_unreviewed_lesson_is_not_publishable(self):
        from scriptstudio.quality import quality_issues
        self.assertIn("PUBLISH", [l for l, _ in quality_issues(self._lesson(review_status="NOT reviewed"))])
        self.assertNotIn("PUBLISH", [l for l, _ in quality_issues(self._lesson(review_status="auto-reviewed: Claude"))])
        self.assertNotIn("PUBLISH", [l for l, _ in quality_issues(self._lesson(review_status="approved"))])

    def test_missing_teaching_point_hook_quiz_block(self):
        from scriptstudio.quality import quality_issues
        les = self._lesson(hook="", quiz=[])
        les["phrases"][0] = {"target": "Hola.", "translation": "Hello.", "pronunciation": "OH-lah"}
        msgs = [m for l, m in quality_issues(les) if l == "BLOCK"]
        self.assertEqual(len(msgs), 3)

    def test_look_changes_between_consecutive_lessons(self):
        from scriptstudio.lessons import look_index
        self.assertNotEqual(look_index("es-a1-greetings-01"), look_index("es-a1-greetings-02"))
        self.assertNotEqual(look_index("x-03"), look_index("x-04"))


class CurriculumTests(unittest.TestCase):
    def test_topic_finishes_before_next_starts(self):
        from scriptstudio.curriculum import load_topics, next_part
        topics = load_topics()
        with tempfile.TemporaryDirectory() as d:
            t, part = next_part(topics, d)
            self.assertEqual((t["id"], part["n"]), ("greetings", 1))
            (Path(d) / "es-a1-greetings-01.json").write_text("{}")
            self.assertEqual(next_part(topics, d)[1]["n"], 2)
            (Path(d) / "es-a1-greetings-02.json").write_text("{}")
            self.assertEqual(next_part(topics, d)[0]["id"], "introductions")

    def test_next_for_real_lessons_moves_on_when_a_topic_is_complete(self):
        from scriptstudio.curriculum import load_topics, next_part
        topics = load_topics()
        done = {t["id"] for t in topics if all((Path("lessons") / f"es-a1-{t['id']}-{p['n']:02d}.json").exists() for p in t["parts"])}
        self.assertIn("greetings", done)          # other topics depend on which lessons are already approved
        self.assertNotIn(next_part(topics)[0]["id"], done)

    def test_every_seed_phrase_is_short_enough_for_a_short(self):
        from scriptstudio.curriculum import load_topics
        for t in load_topics():
            self.assertLessEqual(len(t["parts"]), 4)
            for p in t["parts"]:
                self.assertTrue(3 <= len(p["seeds"]) <= 5)


class TopicGuardTests(unittest.TestCase):
    def test_shipped_lessons_stay_on_their_planned_topic(self):
        from scriptstudio.curriculum import load_topics
        from scriptstudio.quality import quality_issues
        for f in sorted(Path("lessons").glob("*.json")):
            lesson = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual([x for x in quality_issues(lesson, load_topics()) if x[0] in ("BLOCK", "WARN")], [], f.name)

    def test_unplanned_lesson_is_blocked_and_drifted_one_warned(self):
        from scriptstudio.curriculum import load_topics
        from scriptstudio.quality import quality_issues
        les = json.loads(Path("lessons/es-a1-greetings-01.json").read_text(encoding="utf-8"))
        les["id"] = "es-a1-random-01"
        self.assertTrue(any(l == "BLOCK" and "curriculum" in m for l, m in quality_issues(les, load_topics())))
        les["id"] = "es-a1-greetings-01"
        for p, w in zip(les["phrases"], ["Gato.", "Perro.", "Casa.", "Mesa."]):
            p["target"] = w
        self.assertTrue(any(l == "WARN" and "on topic" in m for l, m in quality_issues(les, load_topics())))


class ColdOpenTests(unittest.TestCase):
    def test_cold_open_phrase_is_never_the_quiz_answer(self):
        for f in sorted(Path("lessons").glob("*.json")):
            les = json.loads(f.read_text(encoding="utf-8"))
            lead = les["phrases"][les["cold_open"]["phrase"] - 1]["target"].strip().lower()
            answers = {q["answer"].strip().lower() for q in les.get("quiz", [])}
            self.assertNotIn(lead, answers, f"{f.name}: the opening phrase would spoil the quiz")

    def test_lesson_without_cold_open_is_blocked(self):
        from scriptstudio.quality import quality_issues
        les = json.loads(LESSON.read_text(encoding="utf-8"))
        les.pop("cold_open")
        self.assertTrue(any(l == "BLOCK" and "cold_open" in m for l, m in quality_issues(les)))

    def test_slow_first_sound_fails_qa(self):
        from scriptstudio.qa import evaluate
        good = {"duration": 33.0, "width": 1080, "height": 1920, "fps": 30.0, "has_audio": True, "lufs": -15.5,
                "peak": -1.4, "silence_total": 14.0, "silence_longest": 2.2, "black_total": 0.0}
        self.assertEqual(evaluate(dict(good, onset=0.2), 14.0), [])
        self.assertEqual([l for l, _ in evaluate(dict(good, onset=1.0), 14.0)], ["WARN"])
        self.assertEqual([l for l, _ in evaluate(dict(good, onset=2.5), 14.0)], ["FAIL"])


class PrinciplesTests(unittest.TestCase):
    def test_no_phrase_is_planned_twice_in_the_curriculum(self):
        from scriptstudio.curriculum import load_topics, plan_duplicates
        self.assertEqual(plan_duplicates(load_topics()), [])

    def test_duplicate_phrase_across_lessons_is_found(self):
        from scriptstudio.curriculum import taught_elsewhere
        les = json.loads(LESSON.read_text(encoding="utf-8"))
        les["id"] = "es-a1-copy-01"
        self.assertTrue(taught_elsewhere(les, "lessons"))
        self.assertEqual(taught_elsewhere(json.loads(LESSON.read_text(encoding="utf-8")), "lessons"), [])

    def test_shipped_lessons_keep_text_inside_the_safe_zone(self):
        from scriptstudio.lessons import layout_problems
        for f in sorted(Path("lessons").glob("*.json")):
            self.assertEqual(layout_problems(json.loads(f.read_text(encoding="utf-8"))), [], f.name)

    def test_layout_check_catches_overflow(self):
        from scriptstudio.lessons import layout_problems
        les = json.loads(LESSON.read_text(encoding="utf-8"))
        les["phrases"][0]["target"] = "Supercalifragilisticoespialidosoextraordinariamente"
        self.assertTrue(layout_problems(les))

    def test_shipped_lessons_name_their_spanish_variety(self):
        from scriptstudio.quality import quality_issues
        for f in sorted(Path("lessons").glob("*.json")):
            msgs = [m for l, m in quality_issues(json.loads(f.read_text(encoding="utf-8"))) if "variety" in m]
            self.assertEqual(msgs, [], f.name)


class MixedEngineTests(unittest.TestCase):
    class FakePiper:
        def __init__(self):
            self.calls = []

        def synth(self, voice, text, speed):
            self.calls.append((voice, text, speed))
            return [0.0] * 2400, 24000

    def test_spanish_main_voice_goes_to_piper_and_partner_to_kokoro(self):
        from scriptstudio.tts import MixedEngine
        eng = MixedEngine({"es": "piper:es_AR-daniela-high", "es_b": "kokoro:em_alex"}, piper=self.FakePiper())
        self.assertEqual(eng.spec("es", "A"), ("piper", "es_AR-daniela-high"))
        self.assertEqual(eng.spec("es", "B"), ("kokoro", "em_alex"))
        samples, sr = eng.synth("Hola.", "es", "clear", "A")
        self.assertEqual((len(samples), sr), (2400, 24000))
        self.assertEqual(eng.piper.calls, [("es_AR-daniela-high", "Hola.", "clear")])

    def test_bad_voice_spec_is_rejected(self):
        from scriptstudio.tts import MixedEngine
        with self.assertRaises(RuntimeError):
            MixedEngine({"es": "daniela"}, piper=self.FakePiper()).synth("Hola.", "es", "clear")

    def test_piper_paths_and_licence_credit(self):
        from scriptstudio.tts import piper_paths
        from scriptstudio.voices import credits_for
        self.assertEqual(piper_paths("es_AR-daniela-high")[0], "es/es_AR/daniela/high/es_AR-daniela-high.onnx")
        self.assertIn("CC BY-SA 4.0", credits_for({"es": "piper:es_AR-daniela-high", "en": "kokoro:af_heart"}))
        self.assertEqual(credits_for({"en": "kokoro:af_heart"}), "")

    def test_piper_voice_is_the_main_spanish_voice_in_the_mixed_pool(self):
        from scriptstudio.voices import load_pools, pick_voices
        v = pick_voices("es-a1-greetings-01", load_pools("mixed"))
        self.assertIn(v["es"], ("piper:es_AR-daniela-high", "piper:es_ES-sharvard-medium@1"))
        self.assertIn(v["es_b"], ("piper:es_AR-daniela-high", "piper:es_ES-sharvard-medium@1"))   # owner rule: female only


class LoudnessAndShortClipTests(unittest.TestCase):
    def test_parse_loudnorm_reads_the_measurement(self):
        from scriptstudio.tts import parse_loudnorm
        txt = 'x\n{\n "input_i" : "-24.1",\n "input_tp" : "-5.0",\n "input_lra" : "3.2",\n "input_thresh" : "-34.5",\n "output_i" : "-14",\n "target_offset" : "0.2"\n}\n'
        self.assertEqual(parse_loudnorm(txt)["input_i"], -24.1)
        self.assertIsNone(parse_loudnorm("no json here"))
        self.assertIsNone(parse_loudnorm(txt.replace("-24.1", "-inf")))

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
    def test_two_pass_reaches_the_target_better_than_one_pass(self):
        import subprocess
        from scriptstudio.qa import measure
        from scriptstudio.tts import loudnorm_two_pass
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src = d / "a.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=6", "-af",
                            "volume=-26dB,tremolo=f=3:d=0.9", str(src)], check=True)
            self.assertEqual(loudnorm_two_pass(src, d / "b.wav"), "two-pass")
            vid = d / "v.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=1080x1920:d=6:r=30",
                            "-i", str(d / "b.wav"), "-shortest", "-pix_fmt", "yuv420p", str(vid)], check=True)
            self.assertTrue(-16.0 <= measure(vid)["lufs"] <= -12.5, measure(vid)["lufs"])

    def test_one_and_two_word_clips_are_not_judged_by_whisper(self):
        import sys
        import types
        import scriptstudio.qa as qa

        class Seg:
            text = "Ve la"

        class Model:
            def __init__(self, *a, **k): pass
            def transcribe(self, *a, **k): return [Seg()], None
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = Model
        sys.modules["faster_whisper"] = fake
        try:
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / "p01_a.wav").write_bytes(b"x")
                man = {"segments": [{"id": "p01_a", "speed": "clear", "lang": "es", "text": "Hola."}]}
                res = qa.transcript_check(man, d)
        finally:
            del sys.modules["faster_whisper"]
        self.assertEqual([lvl for lvl, _ in res], ["INFO"])


class FemaleSpanishOnlyTests(unittest.TestCase):
    def test_no_male_voice_in_any_spanish_pool(self):
        import json as _json
        data = _json.loads(Path("data/voices.json").read_text(encoding="utf-8"))
        for engine, langs in data["engines"].items():
            for role, voices in langs.get("es", {}).items():
                for v in voices:
                    self.assertFalse(v.split(":")[-1].startswith("em_"), f"{engine}/es/{role}: {v} is a male voice")

    def test_speech_is_slower_than_before(self):
        from scriptstudio.tts import KOKORO_SPEED, PIPER_LENGTH
        self.assertGreaterEqual(PIPER_LENGTH["clear"], 1.2)      # Spanish teaching speed, flowing
        self.assertLessEqual(KOKORO_SPEED["fast"], 1.05)         # English prompts no longer rushed


class VarietyVoiceTests(unittest.TestCase):
    AR, ES = "piper:es_AR-daniela-high", "piper:es_ES-sharvard-medium@1"

    def setup(self):
        from scriptstudio.voices import load_pools, load_voice_rules
        return load_pools("mixed"), load_voice_rules()

    def test_voseo_lesson_is_never_read_by_the_spain_voice(self):
        from scriptstudio.voices import pick_voices
        pools, rules = self.setup()
        for n in range(1, 12):
            v = pick_voices(f"x-{n:02d}", pools, variety="argentine", rules=rules)
            self.assertEqual((v["es"], v["es_b"]), (self.AR, self.AR))

    def test_spain_voice_only_reads_plain_text(self):
        from scriptstudio.voices import pick_voices
        pools, rules = self.setup()
        for n in range(1, 12):
            v = pick_voices(f"x-{n:02d}", pools, variety="neutral", rules=rules, sensitive=True)
            self.assertEqual((v["es"], v["es_b"]), (self.AR, self.AR))

    def test_plain_neutral_lessons_rotate_and_partner_differs(self):
        from scriptstudio.voices import pick_voices
        pools, rules = self.setup()
        used = set()
        for n in range(1, 7):
            v = pick_voices(f"x-{n:02d}", pools, variety="neutral", rules=rules)
            used.add(v["es"])
            self.assertNotEqual(v["es"], v["es_b"])
        self.assertEqual(used, {self.AR, self.ES})

    def test_accent_sensitive_detection(self):
        from scriptstudio.voices import accent_sensitive
        self.assertTrue(accent_sensitive("Estoy bien, gracias."))
        self.assertTrue(accent_sensitive("Me llamo Ana."))
        self.assertFalse(accent_sensitive("Hola. Buenos días. Buenas tardes. Buenas noches."))

    def test_every_shipped_lesson_declares_its_variety_code(self):
        from scriptstudio.quality import quality_issues
        for f in sorted(Path("lessons").glob("*.json")):
            msgs = [m for _, m in quality_issues(json.loads(f.read_text(encoding="utf-8"))) if "variety_code" in m]
            self.assertEqual(msgs, [], f.name)

    def test_neutral_lessons_contain_no_voseo(self):
        for f in sorted(Path("lessons").glob("*.json")):
            les = json.loads(f.read_text(encoding="utf-8"))
            if les.get("variety_code") == "neutral":
                text = " ".join(p["target"] for p in les["phrases"]) + " " + " ".join(d["target"] for d in les.get("dialogue", []))
                self.assertNotRegex(text.lower(), r"\bvos\b|llamás|\bsos\b|\btenés\b", f.name)

    def test_speaker_id_is_parsed_and_credited(self):
        from scriptstudio.tts import piper_paths, split_speaker
        from scriptstudio.voices import credits_for
        self.assertEqual(split_speaker("es_ES-sharvard-medium@1"), ("es_ES-sharvard-medium", 1))
        self.assertEqual(split_speaker("es_AR-daniela-high"), ("es_AR-daniela-high", None))
        self.assertEqual(piper_paths("es_ES-sharvard-medium@1")[0], "es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx")
        self.assertIn("CC BY 3.0", credits_for({"es": self.ES}))


class FlowTests(unittest.TestCase):
    def test_opening_is_one_connected_beat(self):
        from scriptstudio.lessons import load_lesson, plan
        les = load_lesson(LESSON)
        cards, segs = plan(les)
        self.assertEqual([c.kind for c in cards[:2]], ["cold", "hook"])
        lead = les["phrases"][les["cold_open"]["phrase"] - 1]
        self.assertEqual(cards[1].data["phrase"], lead)       # the hook card keeps the opening phrase on screen
        self.assertEqual(segs[0].text, lead["target"])         # and the phrase is still the first thing heard

    def test_question_is_taught_before_its_answer(self):
        from scriptstudio.quality import flow_issues
        for f in sorted(Path("lessons").glob("*.json")):
            les = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(flow_issues(les), [], f.name)

    def test_flow_rule_catches_answer_before_question(self):
        from scriptstudio.quality import flow_issues
        les = {"phrases": [{"target": "Estoy bien."}, {"target": "¿Cómo estás?"}],
               "quiz": [{"prompt": "“¿Cómo estás?” How do you answer?", "answer": "Estoy bien."}]}
        self.assertTrue(any("flow" in m for _, m in flow_issues(les)))
        les["phrases"].reverse()
        self.assertEqual(flow_issues(les), [])

    def test_lessons_follow_a_real_conversation_order(self):
        les = json.loads(Path("lessons/es-a1-introductions-01.json").read_text(encoding="utf-8"))
        self.assertEqual([p["target"] for p in les["phrases"]][:2], ["¿Cómo te llamás?", "Me llamo Ana."])
        les = json.loads(Path("lessons/es-a1-greetings-02.json").read_text(encoding="utf-8"))
        self.assertEqual([p["target"] for p in les["phrases"]][1:3], ["¿Cómo estás?", "Estoy bien, gracias."])

    def test_opening_phrase_is_among_the_first_two_taught(self):
        for f in sorted(Path("lessons").glob("*.json")):
            les = json.loads(f.read_text(encoding="utf-8"))
            self.assertLessEqual(les["cold_open"]["phrase"], 2, f.name)


class AutomationToolsTests(unittest.TestCase):
    def test_dialogue_and_quiz_reuse_only_taught_phrases(self):
        from scriptstudio.curriculum import known_phrases, load_topics
        from scriptstudio.quality import flow_issues
        topics = load_topics()
        for f in sorted(Path("lessons").glob("*.json")):
            les = json.loads(f.read_text(encoding="utf-8"))
            self.assertEqual(flow_issues(les, known_phrases(les, topics)), [], f.name)

    def test_unknown_dialogue_sentence_is_flagged(self):
        from scriptstudio.quality import flow_issues
        les = {"phrases": [{"target": "Hola."}], "dialogue": [{"speaker": "A", "target": "Hola. Qué onda."}]}
        self.assertTrue(any("Qué onda" in m for _, m in flow_issues(les, set())))
        self.assertEqual(flow_issues(les, {"qué onda"}), [])

    def test_known_phrases_only_come_from_earlier_lessons(self):
        from scriptstudio.curriculum import known_phrases, load_topics
        les = json.loads(Path("lessons/es-a1-greetings-02.json").read_text(encoding="utf-8"))
        k = known_phrases(les, load_topics())
        self.assertIn("hola", k)                      # taught in greetings-01
        self.assertNotIn("cómo te llamás", k)         # taught later, in introductions-01

    def test_storyboard_lists_every_spoken_line_in_order(self):
        from scriptstudio.lessons import load_lesson, plan, storyboard
        les = load_lesson(LESSON)
        text = storyboard(les)
        spoken = [s.text for s in plan(les)[1] if s.speed != "silent"]
        body = text.split("\n\n", 1)[1]                 # skip the header line, which repeats the hook
        cursor = 0
        for line in spoken:                              # every spoken line appears, in the planned order
            at = body.find(line, cursor)
            self.assertGreaterEqual(at, 0, line)
            cursor = at + len(line)
        self.assertIn("estimated length", text)

    def test_build_writes_storyboard_and_card_sheet(self):
        import tempfile
        from scriptstudio.lessons import build_all
        with tempfile.TemporaryDirectory() as d:
            res = build_all(LESSON, d, preview=False)
            self.assertTrue((res["dir"] / "storyboard.txt").exists())
            self.assertTrue((res["dir"] / "cards_sheet.png").exists())

    def test_pending_lessons_are_not_written_twice(self):
        from scriptstudio.curriculum import load_topics, next_part
        topics = load_topics()
        first = next_part(topics)
        from scriptstudio.curriculum import lesson_id
        again = next_part(topics, pending={lesson_id(*first)})
        self.assertNotEqual(lesson_id(*first), lesson_id(*again))


class UploadTests(unittest.TestCase):
    class Resp:
        def __init__(self, status=200, body=None, headers=None, text=""):
            self.status_code, self._body, self.headers, self.text = status, body or {}, headers or {}, text

        def json(self):
            return self._body

    class Http:
        """Records calls; answers token, upload-session and upload-bytes requests."""
        def __init__(self, token_status=200):
            self.calls, self.token_status = [], token_status

        def post(self, url, **kw):
            self.calls.append(("post", url, kw))
            if "oauth2" in url:
                return UploadTests.Resp(self.token_status, {"access_token": "tok"} if self.token_status == 200 else {"error": "invalid_grant"})
            return UploadTests.Resp(200, headers={"Location": "https://upload.example/session"})

        def put(self, url, **kw):
            self.calls.append(("put", url, kw))
            return UploadTests.Resp(200, {"id": "VID123"})

    def _built(self, d, qa="QA: PASS"):
        les = json.loads(Path("lessons/es-a1-introductions-02.json").read_text(encoding="utf-8")) if Path("lessons/es-a1-introductions-02.json").exists() \
            else json.loads(Path("lessons/es-a1-greetings-01.json").read_text(encoding="utf-8"))
        folder = Path(d) / les["id"]
        folder.mkdir()
        (folder / "lesson_mixed.mp4").write_bytes(b"x" * 100)
        (folder / "qa_report.txt").write_text(qa + "\n", encoding="utf-8")
        return les, folder

    ENV = {"YT_CLIENT_ID": "a", "YT_CLIENT_SECRET": "b", "YT_REFRESH_TOKEN": "c"}

    def test_metadata_for_every_lesson_is_valid(self):
        from scriptstudio.upload import build_metadata, metadata_problems
        for f in sorted(Path("lessons").glob("*.json")):
            les = json.loads(f.read_text(encoding="utf-8"))
            meta = build_metadata(les, "Voice: x (CC BY-SA 4.0)")
            self.assertEqual(metadata_problems(meta), [], f.name)
            self.assertIn("#Shorts", meta["snippet"]["description"])
            self.assertTrue(meta["status"]["containsSyntheticMedia"])
            self.assertFalse(meta["status"]["selfDeclaredMadeForKids"])
            self.assertEqual(meta["status"]["privacyStatus"], "private")
            for p in les["phrases"]:
                self.assertIn(p["target"], meta["snippet"]["description"])

    def test_title_from_hook(self):
        from scriptstudio.upload import hook_title
        self.assertEqual(hook_title("Stop saying only “Hola”. Four greetings."), "Stop saying only “Hola” – four greetings")

    def test_upload_happy_path_records_ledger(self):
        import tempfile
        from scriptstudio.upload import load_ledger, publish
        with tempfile.TemporaryDirectory() as d:
            les, folder = self._built(d)
            http, ledger = self.Http(), Path(d) / "ledger.json"
            res = publish(les, folder, "mixed", ledger, http=http, env=self.ENV, seconds=30.0)
            self.assertEqual(res["video_id"], "VID123")
            self.assertEqual(load_ledger(ledger)[les["id"]]["video_id"], "VID123")
            self.assertEqual([c[0] for c in http.calls], ["post", "post", "put"])
            again = publish(les, folder, "mixed", ledger, http=self.Http(), env=self.ENV, seconds=30.0)
            self.assertEqual(again["status"], "already-uploaded")   # never twice

    def test_gates_block_the_upload(self):
        import tempfile
        from scriptstudio.upload import UploadError, publish
        with tempfile.TemporaryDirectory() as d:
            les, folder = self._built(d, qa="QA: FAIL")
            http = self.Http()
            with self.assertRaises(UploadError):
                publish(les, folder, "mixed", Path(d) / "l.json", http=http, env=self.ENV, seconds=30.0)
            (folder / "qa_report.txt").write_text("QA: PASS\n", encoding="utf-8")
            with self.assertRaises(UploadError):                      # too long
                publish(les, folder, "mixed", Path(d) / "l.json", http=http, env=self.ENV, seconds=41.0)
            les["review_status"] = "NOT reviewed"
            with self.assertRaises(UploadError):                      # Spanish not reviewed
                publish(les, folder, "mixed", Path(d) / "l.json", http=http, env=self.ENV, seconds=30.0)
            self.assertEqual(http.calls, [])                          # nothing reached the network

    def test_no_credentials_never_uploads(self):
        import tempfile
        from scriptstudio.upload import UploadError, publish
        with tempfile.TemporaryDirectory() as d:
            les, folder = self._built(d)
            http = self.Http()
            res = publish(les, folder, "mixed", Path(d) / "l.json", if_configured=True, http=http, env={}, seconds=30.0)
            self.assertEqual(res["status"], "skipped")
            with self.assertRaises(UploadError):
                publish(les, folder, "mixed", Path(d) / "l.json", http=http, env={}, seconds=30.0)
            dry = publish(les, folder, "mixed", Path(d) / "l.json", dry_run=True, http=http, env=self.ENV, seconds=30.0)
            self.assertEqual(dry["status"], "skipped")
            self.assertEqual(http.calls, [])

    def test_token_error_does_not_leak_secrets(self):
        import tempfile
        from scriptstudio.upload import UploadError, publish
        with tempfile.TemporaryDirectory() as d:
            les, folder = self._built(d)
            with self.assertRaises(UploadError) as cm:
                publish(les, folder, "mixed", Path(d) / "l.json", http=self.Http(token_status=400), env=self.ENV, seconds=30.0)
            for secret in ("a", "b", "c"):
                self.assertNotIn(f"={secret}", str(cm.exception))
            self.assertIn("invalid_grant", str(cm.exception))
