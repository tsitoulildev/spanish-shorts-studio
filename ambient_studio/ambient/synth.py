"""Procedural ambience: every sound is generated from random noise, so there is no third-party audio and no licence to track.
Each recipe takes a seed, so every video gets its own, unique mix. All loops are seamless (equal-power crossfade of the tail into the head)."""
from __future__ import annotations
import numpy as np
from scipy import signal

SR = 44100


def _rng(seed: int, salt: str) -> np.random.Generator:
    return np.random.default_rng([seed, *[ord(c) for c in salt]])


def _band(x: np.ndarray, lo: float | None, hi: float | None, order: int = 4) -> np.ndarray:
    if lo and hi:
        sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    elif hi:
        sos = signal.butter(order, hi, btype="low", fs=SR, output="sos")
    else:
        sos = signal.butter(order, lo, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _slow(rng, n: int, rate_hz: float, depth: float) -> np.ndarray:
    """Slow random gain wobble around 1.0 (e.g. gusts, intensity changes)."""
    pts = max(4, int(n / SR * rate_hz) + 2)
    ctrl = rng.normal(0, 1, pts)
    env = np.interp(np.linspace(0, pts - 1, n), np.arange(pts), ctrl)
    return 10 ** (depth * env / 20)


def _pink(rng, n: int) -> np.ndarray:
    f = np.fft.rfft(rng.normal(0, 1, n))
    k = np.arange(len(f)); k[0] = 1
    out = np.fft.irfft(f / np.sqrt(k), n)
    return out / (np.std(out) + 1e-9)


def _impulses(rng, n: int, rate: float, heavy: float = 1.0) -> np.ndarray:
    x = np.zeros(n)
    k = rng.poisson(rate * n / SR)
    pos = rng.integers(0, n, k)
    amp = rng.exponential(1.0, k) ** heavy * rng.choice([-1, 1], k)
    np.add.at(x, pos, amp)
    return x


def _ping(rng, n: int, rate: float, f_lo: float, f_hi: float, decay_ms: float) -> np.ndarray:
    """Short decaying sine blips: single drops hitting glass / a roof."""
    x = np.zeros(n)
    k = rng.poisson(rate * n / SR)
    L = int(SR * decay_ms * 4 / 1000)
    t = np.arange(L) / SR
    for p in rng.integers(0, max(1, n - L), k):
        f = rng.uniform(f_lo, f_hi)
        d = decay_ms / 1000 * rng.uniform(0.5, 1.5)
        x[p:p + L] += rng.exponential(0.5) * np.sin(2 * np.pi * f * t) * np.exp(-t / d)
    return x


def _loopify(x: np.ndarray, length: int, fade: int) -> np.ndarray:
    """x has length+fade samples (last axis). Blend the tail into the head so the end flows into the start."""
    a = np.linspace(0, 1, fade)
    head = x[..., :fade] * np.sin(a * np.pi / 2) + x[..., length:length + fade] * np.cos(a * np.pi / 2)
    out = x[..., :length].copy()
    out[..., :fade] = head
    return out


def rain(seconds: float, seed: int, intensity: float = 1.0, thunder: bool = False, roof: float = 0.5) -> np.ndarray:
    n = int(seconds * SR)
    chans = []
    for c in range(2):
        r = _rng(seed, f"rain{c}")
        bed = _band(_pink(r, n), 500, 11000) * _slow(r, n, 0.05, 1.5)
        hiss = _band(r.normal(0, 1, n), 4000, 12000) * 0.35 * _slow(r, n, 0.08, 1.5)
        drops = _band(_impulses(r, n, 350 * intensity, 1.3), 1500, 8000) * 0.6
        pings = _ping(r, n, 18 * intensity * (0.4 + roof), 900, 3800, 7) * 0.5
        rumble = _band(_pink(r, n), None, 160) * 0.5
        chans.append(1.0 * bed + hiss + drops + pings * (0.6 + roof) + rumble)
    out = np.stack(chans)
    if thunder:
        out = out + _thunder(n, seed)
    return out


def _thunder(n: int, seed: int, gap_s: float = 70.0) -> np.ndarray:
    r = _rng(seed, "thunder")
    out = np.zeros((2, n))
    t0 = r.uniform(10, gap_s)
    while t0 < n / SR - 12:
        L = int(SR * r.uniform(7, 12))
        t = np.arange(L) / SR
        base = _band(r.normal(0, 1, L), 25, r.uniform(90, 170), 3)
        env = (1 - np.exp(-t / 0.25)) * np.exp(-t / r.uniform(2.2, 3.8))
        # rolling re-swells of the rumble
        for _ in range(r.integers(1, 4)):
            s, w = r.uniform(0.5, 5), r.uniform(0.6, 1.6)
            env += 0.5 * np.exp(-((t - s) ** 2) / (2 * w * w))
        crack = _band(r.normal(0, 1, L), 600, 3500) * np.exp(-t / 0.05) * 0.35
        ev = (base * env * 2.2 + crack) * r.uniform(0.35, 0.8)
        pan = r.uniform(0.3, 0.7)
        p = int(t0 * SR)
        out[0, p:p + L] += ev * pan * 2
        out[1, p:p + L] += ev * (1 - pan) * 2
        t0 += r.uniform(gap_s * 0.6, gap_s * 1.6)
    return out


def fire(seconds: float, seed: int, crackle: float = 1.0) -> np.ndarray:
    n = int(seconds * SR)
    chans = []
    for c in range(2):
        r = _rng(seed, f"fire{c}")
        roar = _band(_pink(r, n), 60, 700) * _slow(r, n, 0.3, 3.0) * 0.9
        hiss = _band(r.normal(0, 1, n), 3500, 9000) * 0.12 * _slow(r, n, 0.7, 4.0)
        # pops: tiny noise bursts at a wandering rate
        rate = crackle * 14 * _slow(r, n, 0.1, 5)
        k = int(np.mean(rate) * n / SR * 1.3)
        pos = r.integers(0, n - 800, k)
        keep = r.random(k) < np.clip(rate[pos] / (rate.max() + 1e-9), 0.05, 1)
        pops = np.zeros(n)
        for p, amp in zip(pos[keep], r.exponential(1, keep.sum()) ** 1.6):
            L = int(SR * r.uniform(0.002, 0.012))
            burst = r.normal(0, 1, L) * np.exp(-np.arange(L) / (L / 3))
            pops[p:p + L] += burst * amp
        pops = _band(pops, 900, 6500) * 1.6
        snaps = _band(_impulses(r, n, 0.9 * crackle, 2.0), 300, 3000) * 3.0
        chans.append(roar + hiss + pops + snaps)
    return np.stack(chans)


def make_loop(kind: str, seconds: float, seed: int, **kw) -> np.ndarray:
    fade = int(SR * 8)
    n_total = seconds + 8
    if kind == "rain":
        x = rain(n_total, seed, **kw)
    elif kind == "storm":
        x = rain(n_total, seed, intensity=kw.get("intensity", 1.4), thunder=True, roof=kw.get("roof", 0.6))
    elif kind == "fire":
        x = fire(n_total, seed, **kw)
    elif kind == "wind":
        x = wind(n_total, seed)
    elif kind == "rainfire":
        x = rain(n_total, seed, intensity=0.7, roof=0.3) * 0.8 + fire(n_total, seed, 0.9) * 0.7
    else:
        raise ValueError(f"unknown kind {kind}")
    return _loopify(x, int(seconds * SR), fade)


def normalise(x: np.ndarray, target_rms_db: float = -26.0, peak_db: float = -3.0) -> np.ndarray:
    x = x - x.mean(axis=-1, keepdims=True)
    rms = np.sqrt(np.mean(x ** 2)) + 1e-12
    x = x * (10 ** (target_rms_db / 20) / rms)
    peak = 10 ** (peak_db / 20)
    return np.tanh(x / peak) * peak  # soft limit keeps sudden thunder/pops from clipping


def write_wav(path, x: np.ndarray) -> None:
    from scipy.io import wavfile
    wavfile.write(str(path), SR, (np.clip(x.T, -1, 1) * 32767).astype(np.int16))


def wind(seconds: float, seed: int) -> np.ndarray:
    """Soft wind for snow scenes: low/mid band noise with slow gusts (generated, no recording)."""
    n = int(seconds * SR)
    ch = []
    for c in range(2):
        r = _rng(seed, f"wind{c}")
        x = _band(_pink(r, n), 60, 1100, 2) * _slow(r, n, 0.06, 5.0)
        ch.append(x + 0.15 * _band(r.normal(0, 1, n), 1500, 4000, 2) * _slow(r, n, 0.09, 6.0))
    return np.stack(ch)
