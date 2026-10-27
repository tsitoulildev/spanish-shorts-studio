"""English narration with Kokoro (Apache-2.0), voice am_michael: python compare/voices_en.py A B SEED DIR"""
import pathlib, subprocess, sys
import numpy as np
from scipy.io import wavfile
from kokoro import KPipeline

a, b, seed, out = sys.argv[1], sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
lines = subprocess.run([sys.executable, str(pathlib.Path(__file__).parent / "render.py"), a, b, "--seed", seed, "--out", "x", "--lines"],
                       capture_output=True, text=True, check=True).stdout.strip().splitlines()
pipe = KPipeline(lang_code="a")
for row in lines:
    h, text = row.split("\t", 1)
    audio = np.concatenate([np.asarray(x[2]) for x in pipe(text, voice="am_michael", speed=1.05)])
    wavfile.write(str(out / f"{h}.wav"), 24000, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
    print("ok", text)
