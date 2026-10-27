"""Original background music and sound effects, generated from scratch (no samples, no licences, nothing for Content ID to match).
A driving 120 bpm electronic loop: four-on-the-floor kick, clap, hats, sub bass and a chord pad; the seed picks key and progression."""
from __future__ import annotations
import numpy as np
from scipy import signal

SR = 44100


def _env(n, a, d):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def kick(n=int(0.35 * SR)):
    t = np.arange(n) / SR
    f = 50 + 120 * np.exp(-t / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18) * 1.0


def clap(rng, n=int(0.25 * SR)):
    x = rng.normal(0, 1, n) * _env(n, 0.001, 0.07)
    sos = signal.butter(2, [900, 4000], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x) * 0.9


def hat(rng, n=int(0.06 * SR), open_=False):
    if open_:
        n = int(0.2 * SR)
    x = rng.normal(0, 1, n) * _env(n, 0.0005, 0.08 if open_ else 0.015)
    sos = signal.butter(2, 7000, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x) * 0.35


def saw(freq, n):
    t = np.arange(n) / SR
    return 2 * ((t * freq) % 1) - 1


def note(m):  # midi -> Hz
    return 440 * 2 ** ((m - 69) / 12)


def track(seconds: float, seed: int, bpm: int = 120) -> np.ndarray:
    rng = np.random.default_rng(seed)
    root = 45 + int(rng.integers(0, 7))  # A2..D#3
    progs = [[0, -4, 3, -2], [0, 3, -2, -4], [0, -2, -4, -5], [0, 5, 3, -2]]  # minor-key pop progressions (i VI III VII ...)
    prog = progs[int(rng.integers(0, len(progs)))]
    beat = 60 / bpm
    n = int(seconds * SR) + SR
    out = np.zeros((2, n))
    k, cl = kick(), clap(rng)
    bars = int(seconds / (4 * beat)) + 2
    for b in range(bars):
        chord_root = root + prog[b % 4]
        minor = prog[b % 4] in (0, 5, -5)
        triad = [chord_root, chord_root + (3 if minor else 4), chord_root + 7]
        bar0 = int(b * 4 * beat * SR)
        L = int(4 * beat * SR)
        if bar0 + L > n:
            break
        # pad: detuned saws, low-passed, slow attack, stereo spread
        pad = np.zeros(L)
        for m in triad:
            for det in (-0.08, 0.08):
                pad += saw(note(m + 12) * (1 + det / 100), L)
        pad = signal.sosfilt(signal.butter(2, 1400, fs=SR, output="sos"), pad) * _env(L, 0.15, 6) * 0.06
        out[0, bar0:bar0 + L] += pad
        out[1, bar0:bar0 + L] += np.roll(pad, 300)
        for s in range(8):  # eighth notes
            p = bar0 + int(s * beat / 2 * SR)
            # sub bass on offbeats-ish pattern
            if s in (0, 3, 4, 6):
                Lb = int(beat / 2 * SR * 0.9)
                t = np.arange(Lb) / SR
                bass = np.sin(2 * np.pi * note(chord_root - 12) * t) + 0.3 * np.sign(np.sin(2 * np.pi * note(chord_root - 12) * t))
                bass = signal.sosfilt(signal.butter(2, 400, fs=SR, output="sos"), bass) * _env(Lb, 0.005, 0.25) * 0.35
                out[:, p:p + Lb] += bass
            h = hat(rng, open_=(s % 2 == 1 and s == 7))
            out[:, p:p + len(h)] += h * (0.6 if s % 2 == 0 else 1.0)
        for q in range(4):
            p = bar0 + int(q * beat * SR)
            out[:, p:p + len(k)] += k * 0.9
            if q in (1, 3):
                out[:, p:p + len(cl)] += cl
        # pluck arpeggio on top for movement
        for s in range(8):
            p = bar0 + int(s * beat / 2 * SR)
            m = triad[[0, 1, 2, 1, 0, 2, 1, 2][s]] + 24
            Lp = int(0.3 * SR)
            pl = signal.sosfilt(signal.butter(2, 3000, fs=SR, output="sos"), saw(note(m), Lp)) * _env(Lp, 0.002, 0.12) * 0.07
            out[0, p:p + Lp] += pl * (0.6 if s % 2 else 1.0)
            out[1, p:p + Lp] += pl * (1.0 if s % 2 else 0.6)
    out = out[:, :int(seconds * SR)]
    fade = int(0.8 * SR)
    out[:, -fade:] *= np.linspace(1, 0, fade)
    return out


def whoosh(rng, secs=0.45):
    n = int(secs * SR)
    x = rng.normal(0, 1, n)
    f = np.linspace(400, 5000, n)
    y = np.zeros(n); zi = None
    # sweep a band-pass by chunks
    for i in range(0, n, 1024):
        sos = signal.butter(2, [f[i] * 0.7, f[i] * 1.3], btype="band", fs=SR, output="sos")
        y[i:i + 1024] = signal.sosfilt(sos, x[i:i + 1024])
    return y * np.sin(np.linspace(0, np.pi, n)) * 0.5


def ding(m=84, secs=0.6):
    n = int(secs * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * note(m) * t) + 0.4 * np.sin(2 * np.pi * note(m + 12) * t)) * np.exp(-t / 0.18) * 0.35


def tick(secs=0.03):
    n = int(secs * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * 2200 * t) * np.exp(-t / 0.006) * 0.25
