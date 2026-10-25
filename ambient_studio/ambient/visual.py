"""Procedural looping visuals (numpy -> raw frames -> ffmpeg). Fully periodic, so the clip loops seamlessly."""
from __future__ import annotations
import subprocess
import numpy as np
from scipy.ndimage import gaussian_filter

W, H, FPS = 1280, 720, 24


def _grad(top, bot):
    t = np.linspace(0, 1, H)[:, None, None]
    return (np.array(top) * (1 - t) + np.array(bot) * t) * np.ones((1, W, 1))


def frames(kind: str, seconds: int, seed: int):
    r = np.random.default_rng(seed)
    n = seconds * FPS
    if kind in ("rain", "storm", "rainfire"):
        base = _grad((8, 14, 24), (22, 34, 46))
        if kind == "rainfire":
            base = _grad((10, 8, 8), (40, 22, 12))
        # window glass: blurred bokeh lights
        bok = np.zeros((H, W, 3))
        for _ in range(26):
            y, x = r.integers(0, H), r.integers(0, W)
            col = np.array(r.choice([(255, 190, 110), (120, 170, 255), (255, 120, 90)])) * r.uniform(0.2, 0.55)
            bok[max(0, y - 6):y + 6, max(0, x - 6):x + 6] += col
        bok = gaussian_filter(bok, (14, 14, 0))
        layers = []
        for cycles, cnt, ln, br in ((6, 260, 22, 0.35), (9, 170, 38, 0.55), (14, 90, 60, 0.8)):
            xs = r.integers(0, W, cnt); ys0 = r.uniform(0, H, cnt)
            layers.append((xs, ys0, H * cycles / n, ln, br))
        flash = np.zeros(n)
        if kind == "storm":
            for f0 in r.choice(np.arange(FPS * 3, n - FPS * 3), 3, replace=False):
                for k, a in enumerate((1.0, 0.2, 0.7, 0.3, 0.1)):
                    if f0 + k * 2 < n:
                        flash[f0 + k * 2] = a
        for f in range(n):
            img = base + bok * (0.9 + 0.1 * np.sin(2 * np.pi * f / n))
            streak = np.zeros((H, W))
            for xs, ys0, step, ln, br in layers:
                ys = ((ys0 + step * f) % H).astype(int)
                for x, y in zip(xs, ys):
                    y2 = min(H, y + ln)
                    streak[y:y2, x] += br
            streak = gaussian_filter(streak, (0.8, 0.7))
            img = img + streak[..., None] * np.array([150, 170, 195])
            if flash[f]:
                img = img + flash[f] * np.array([110, 120, 150])
            yield np.clip(img, 0, 255).astype(np.uint8)
    elif kind == "fire":
        yy, xx = np.mgrid[0:H, 0:W]
        cx, cy = W * 0.5, H * 0.78
        ph = r.uniform(0, 2 * np.pi, 6)
        for f in range(n):
            t = 2 * np.pi * f / n
            flick = 1 + sum(0.08 * np.sin(k * t + ph[k - 1]) for k in range(1, 5))
            rad = np.sqrt(((xx - cx) / (W * 0.30 * flick)) ** 2 + ((yy - cy) / (H * 0.55 * flick)) ** 2)
            glow = np.exp(-rad ** 2 * 2.2)
            core = np.exp(-rad ** 2 * 9)
            sway = np.sin(t * 2 + yy / 60.0) * 0.5
            img = np.zeros((H, W, 3))
            img += glow[..., None] * np.array([210, 80, 18]) * (1 + 0.1 * sway[..., None])
            img += core[..., None] * np.array([255, 190, 80])
            img += np.array([6, 4, 4])
            yield np.clip(img, 0, 255).astype(np.uint8)
    else:
        raise ValueError(kind)


def render_loop(kind: str, seconds: int, seed: int, out: str) -> None:
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p", out],
                         stdin=subprocess.PIPE)
    for fr in frames(kind, seconds, seed):
        p.stdin.write(fr.tobytes())
    p.stdin.close(); p.wait()
