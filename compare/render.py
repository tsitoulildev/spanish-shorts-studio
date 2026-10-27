"""Country vs country comparison Short (1080x1920, ~34 s), bilingual English/Spanish.
python compare/render.py GRC TUR --seed 1 --out out.mp4 [--voices DIR]"""
from __future__ import annotations
import argparse, json, math, pathlib, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.io import wavfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import music  # noqa: E402

W, H, FPS = 1080, 1920, 30
A = HERE / "assets"
DATA = json.load(open(HERE / "data" / "worldbank.json", encoding="utf-8"))
F = {s: str(A / "fonts" / f"Poppins-{s}.ttf") for s in ("Bold", "Medium")}
_fc = {}


def font(sz, w="Bold"):
    k = (sz, w)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(F[w], sz)
    return _fc[k]


# indicator -> (English, Spanish, format, higher wins?)
CAT = {
    "SP.POP.TOTL": ("POPULATION", "Población", "count", True),
    "AG.SRF.TOTL.K2": ("AREA", "Superficie", "km2", True),
    "NY.GDP.MKTP.CD": ("ECONOMY (GDP)", "Economía (PIB)", "usd", True),
    "NY.GDP.PCAP.CD": ("GDP PER PERSON", "PIB por persona", "usd0", True),
    "SP.DYN.LE00.IN": ("LIFE EXPECTANCY", "Esperanza de vida", "years", True),
    "MS.MIL.XPND.CD": ("MILITARY SPENDING", "Gasto militar", "usd", True),
    "ST.INT.ARVL": ("TOURISTS PER YEAR", "Turistas al año", "count", True),
    "IT.NET.USER.ZS": ("INTERNET USERS", "Usuarios de internet", "pct", True),
    "SL.UEM.TOTL.ZS": ("UNEMPLOYMENT", "Desempleo", "pct", False),
    "FP.CPI.TOTL.ZG": ("INFLATION", "Inflación", "pct", False),
    "NE.EXP.GNFS.CD": ("EXPORTS", "Exportaciones", "usd", True),
    "SH.XPD.CHEX.PC.CD": ("HEALTH SPENDING PER PERSON", "Gasto en salud por persona", "usd0", True),
    "AG.LND.FRST.ZS": ("FOREST COVER", "Bosques", "pct", True),
    "EG.ELC.RNEW.ZS": ("RENEWABLE ELECTRICITY", "Electricidad renovable", "pct", True),
    "IS.AIR.PSGR": ("AIR PASSENGERS", "Pasajeros aéreos", "count", True),
}
CORE = ["SP.POP.TOTL", "NY.GDP.MKTP.CD", "MS.MIL.XPND.CD", "NY.GDP.PCAP.CD"]  # economy and military are the classic hooks of the genre
BLUE, RED, GREEN, GREY, GOLD = (59, 130, 246), (239, 68, 68), (34, 197, 94), (71, 85, 105), (250, 204, 21)


def fmt(v, kind):
    if kind == "pct":
        return f"{v:.1f}%"
    if kind == "years":
        return f"{v:.1f} yrs"
    if kind == "km2":
        return f"{v:,.0f} km²"
    if kind == "usd0":
        return f"${v:,.0f}"
    pre = "$" if kind == "usd" else ""
    for d, s in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= d:
            return f"{pre}{v / d:.1f}{s}"
    return f"{pre}{v:,.0f}"


def choose(a, b, seed, n=7):
    rng = np.random.default_rng(seed)
    ok = [k for k in CAT if a in DATA["values"].get(k, {}) and b in DATA["values"][k]
          and DATA["values"][k][a][0] != DATA["values"][k][b][0]]
    core = [k for k in CORE if k in ok]
    rest = [k for k in ok if k not in core]
    rng.shuffle(rest)
    cats = core + rest[: n - len(core)]
    rng.shuffle(cats)
    if "MS.MIL.XPND.CD" in cats:
        cats.remove("MS.MIL.XPND.CD"); cats.insert(0, "MS.MIL.XPND.CD")
    return cats


# ---------- graphics helpers ----------
def flag(iso2, w):
    im = Image.open(A / "flags" / f"{iso2}.png").convert("RGBA")
    return im.resize((w, int(w * im.height / im.width)), Image.LANCZOS)


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = im.copy(); out.putalpha(m)
    return out


def card(iso2, w):
    f = rounded(flag(iso2, w), 22)
    pad = 18
    sh = Image.new("RGBA", (f.width + pad * 2, f.height + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 8, pad + f.width, pad + f.height + 8), 22, fill=(0, 0, 0, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    sh.alpha_composite(f, (pad, pad))
    return sh


GEO = {f["id"]: f["geometry"] for f in json.load(open(A / "countries.geo.json"))["features"]}


def silhouette(iso3, iso2, box):
    g = GEO.get(iso3)
    if not g:
        return None
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    rings = [np.array(p[0]) for p in polys]

    def area(r):
        x, y = r[:, 0], r[:, 1]
        return abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))) / 2
    big_r = max(rings, key=area); big = area(big_r); c0 = big_r.mean(0)
    # keep the mainland and nearby islands; drop small far-away territories (French Guiana, Alaska, ...)
    rings = [r for r in rings if area(r) >= 0.02 * big and (np.hypot(*(r.mean(0) - c0)) < 15 or area(r) >= 0.5 * big)]
    lat0 = np.mean(np.concatenate(rings)[:, 1])
    pts = [np.c_[r[:, 0] * math.cos(math.radians(lat0)), -r[:, 1]] for r in rings]
    allp = np.concatenate(pts); mn, mx = allp.min(0), allp.max(0)
    s = min(box / (mx[0] - mn[0]), box / (mx[1] - mn[1]))
    size = (int((mx[0] - mn[0]) * s) + 8, int((mx[1] - mn[1]) * s) + 8)
    mask = Image.new("L", size, 0); d = ImageDraw.Draw(mask)
    for p in pts:
        d.polygon([tuple(v) for v in ((p - mn) * s + 4)], fill=255)
    fl = Image.open(A / "flags" / f"{iso2}.png").convert("RGBA")
    k = max(size[0] / fl.width, size[1] / fl.height)
    fl = fl.resize((int(fl.width * k) + 1, int(fl.height * k) + 1), Image.LANCZOS)
    ox, oy = (fl.width - size[0]) // 2, (fl.height - size[1]) // 2
    fl = fl.crop((ox, oy, ox + size[0], oy + size[1]))
    out = Image.new("RGBA", size, (0, 0, 0, 0)); out.paste(fl, (0, 0), mask)
    glow = Image.new("RGBA", size, (255, 255, 255, 0)); glow.putalpha(mask.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(4)))
    res = Image.new("RGBA", (size[0] + 40, size[1] + 40), (0, 0, 0, 0))
    res.alpha_composite(glow, (20, 20)); res.alpha_composite(out, (20, 20))
    return res


def background(t):
    """Deep navy gradient with two slow colour glows (one per side) and a faint grid."""
    global _BG
    if "_BG" not in globals():
        y = np.linspace(0, 1, H)[:, None]
        base = (np.array([10, 14, 32]) * (1 - y[..., None]) + np.array([4, 6, 16]) * y[..., None]) * np.ones((1, W, 1))
        g = Image.fromarray(base.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(g)
        for x in range(0, W, 90):
            d.line((x, 0, x, H), fill=(255, 255, 255, 10))
        for yy in range(0, H, 90):
            d.line((0, yy, W, yy), fill=(255, 255, 255, 10))
        blob = Image.new("L", (900, 900), 0); ImageDraw.Draw(blob).ellipse((150, 150, 750, 750), fill=110)
        blob = blob.filter(ImageFilter.GaussianBlur(120))
        _BG = (g, blob)
    g, blob = _BG
    im = g.copy()
    for col, cx, ph in ((BLUE, 180, 0.0), (RED, 900, 2.0)):
        layer = Image.new("RGBA", blob.size, col + (0,)); layer.putalpha(blob)
        im.alpha_composite(layer, (int(cx - 450 + 40 * math.sin(t * 0.6 + ph)), int(500 - 450 + 60 * math.cos(t * 0.4 + ph))))
    return im


def text_c(d, xy, s, f, fill, stroke=0):
    w = d.textlength(s, font=f)
    d.text((xy[0] - w / 2, xy[1]), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))


def fit(d, s, w, sz, weight="Bold"):
    while sz > 24 and d.textlength(s, font=font(sz, weight)) > w:
        sz -= 2
    return font(sz, weight)


ease = lambda x: 1 - (1 - min(max(x, 0), 1)) ** 3


# ---------- the video ----------
def build(a, b, seed, out, voices=None):
    ca, cb = DATA["countries"][a], DATA["countries"][b]
    cats = choose(a, b, seed)
    INTRO, ROUND, OUTRO = 3.6, 3.2, 3.4
    total = INTRO + ROUND * len(cats) + OUTRO
    cardA, cardB = card(ca["iso2"], 380), card(cb["iso2"], 380)
    silA, silB = silhouette(a, ca["iso2"], 430), silhouette(b, cb["iso2"], 430)
    results = []
    for k in cats:
        va, vb = DATA["values"][k][a][0], DATA["values"][k][b][0]
        hi = CAT[k][3]
        results.append(("A" if (va > vb) == hi else "B", va, vb))
    events = []  # (time, kind)
    tmp = pathlib.Path(tempfile.mkdtemp())
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", str(tmp / "v.mp4")], stdin=subprocess.PIPE)
    nframes = int(total * FPS)
    for fi in range(nframes):
        t = fi / FPS
        im = background(t)
        d = ImageDraw.Draw(im)
        if t < INTRO:
            u = ease(t / 0.6)
            for sil, cx, col in ((silA, 290, BLUE), (silB, 790, RED)):
                if sil:
                    sc = 0.6 + 0.4 * u
                    s2 = sil.resize((max(1, int(sil.width * sc * 0.9)), max(1, int(sil.height * sc * 0.9))))
                    im.alpha_composite(s2, (int(cx - s2.width / 2), int(820 - s2.height / 2)))
            d = ImageDraw.Draw(im)
            for i, line in enumerate(hook_lines(a, b)):
                text_c(d, (540, 250 + i * 92), line, fit(d, line, 980, 76), (255, 255, 255) if i == 0 else GOLD, 4)
            fA = fit(d, ca["en"].upper(), 460, 60); fB = fit(d, cb["en"].upper(), 460, 60)
            text_c(d, (290, 1130), ca["en"].upper(), fA, (255, 255, 255), 3)
            text_c(d, (790, 1130), cb["en"].upper(), fB, (255, 255, 255), 3)
            text_c(d, (290, 1205), ca["es"], fit(d, ca["es"], 460, 42, "Medium"), GOLD, 2)
            text_c(d, (790, 1205), cb["es"], fit(d, cb["es"], 460, 42, "Medium"), GOLD, 2)
            r = 70 + 6 * math.sin(t * 8)
            d.ellipse((540 - r, 820 - r, 540 + r, 820 + r), fill=(220, 38, 38), outline=(255, 255, 255), width=5)
            text_c(d, (540, 820 - 42), "VS", font(64), (255, 255, 255))
            if fi == 0:
                events.append((0.0, "whoosh"))
        else:
            # header: flags, names, score
            im.alpha_composite(cardA, (60 - 18, 230 - 18)); im.alpha_composite(cardB, (640 - 18, 230 - 18))
            d = ImageDraw.Draw(im)
            text_c(d, (250, 500), ca["en"].upper(), fit(d, ca["en"].upper(), 420, 46), (255, 255, 255), 2)
            text_c(d, (830, 500), cb["en"].upper(), fit(d, cb["en"].upper(), 420, 46), (255, 255, 255), 2)
            text_c(d, (250, 556), ca["es"], fit(d, ca["es"], 420, 32, "Medium"), GOLD)
            text_c(d, (830, 556), cb["es"], fit(d, cb["es"], 420, 32, "Medium"), GOLD)
            d.ellipse((540 - 52, 357 - 52, 540 + 52, 357 + 52), fill=(220, 38, 38), outline=(255, 255, 255), width=4)
            text_c(d, (540, 357 - 32), "VS", font(46), (255, 255, 255))
            ri = min(int((t - INTRO) // ROUND), len(cats) - 1)
            tr = t - INTRO - ri * ROUND
            done = [r for i, r in enumerate(results) if i < ri or (i == ri and tr >= 1.5)]
            sa, sb = sum(r[0] == "A" for r in done), sum(r[0] == "B" for r in done)
            for sc, cx, col in ((sa, 250, BLUE), (sb, 830, RED)):
                d.rounded_rectangle((cx - 60, 610, cx + 60, 700), 18, fill=col)
                text_c(d, (cx, 612), str(sc), font(62), (255, 255, 255))
            if t >= INTRO + ROUND * len(cats):  # outro
                to = t - INTRO - ROUND * len(cats)
                win = a if sa > sb else b if sb > sa else None
                if fi == int((INTRO + ROUND * len(cats)) * FPS):
                    events.append((t, "whoosh")); events.append((t + 0.3, "win")); events.append((t + 0.5, f"voice:{outro_line(a, b, seed)}"))
                u = ease(to / 0.5)
                if win:
                    cw = DATA["countries"][win]
                    big = card(cw["iso2"], int(520 * (0.7 + 0.3 * u)))
                    im.alpha_composite(big, (int(540 - big.width / 2), int(1060 - big.height / 2)))
                    d = ImageDraw.Draw(im)
                    # crown
                    cx, cy = 540, 1060 - big.height // 2 - 40
                    d.polygon([(cx - 90, cy + 50), (cx - 90, cy - 10), (cx - 45, cy + 20), (cx, cy - 40), (cx + 45, cy + 20), (cx + 90, cy - 10), (cx + 90, cy + 50)], fill=GOLD, outline=(120, 80, 0))
                    text_c(d, (540, 620), "WINNER", font(84), GOLD, 4)
                    text_c(d, (540, 1270), cw["en"].upper(), fit(d, cw["en"].upper(), 900, 72), (255, 255, 255), 3)
                    text_c(d, (540, 1355), f"¡Gana {cw['es']}!", font(50, "Medium"), GOLD, 2)
                else:
                    text_c(d, (540, 900), "IT'S A TIE!", font(96), GOLD, 4)
                    text_c(d, (540, 1020), "¡Empate!", font(60, "Medium"), (255, 255, 255), 2)
                text_c(d, (540, 1450), "Agree? Comment your country!", font(44), (255, 255, 255), 2)
                text_c(d, (540, 1510), "¡Comenta tu país!", font(40, "Medium"), GOLD, 2)
            else:
                k = cats[ri]; en, es, kind, hi = CAT[k]; who, va, vb = results[ri]
                if abs(tr) < 1 / FPS / 2 or (fi == int((INTRO + ri * ROUND) * FPS)):
                    events.append((t, "whoosh")); events.append((t + 0.25, f"voice:{say(k)}")); events.append((t + 1.5, "ding"))
                    for j in range(8):
                        events.append((t + 0.35 + j * 0.11, "tick"))
                slide = ease(tr / 0.35)
                x0 = int((1 - slide) * 300)
                text_c(d, (540 + x0, 760), en, fit(d, en, 960, 66), (255, 255, 255), 3)
                text_c(d, (540 + x0, 845), es, fit(d, es, 900, 48, "Medium"), GOLD, 2)
                yr = max(DATA["values"][k][a][1], DATA["values"][k][b][1])
                text_c(d, (540, 905), f"{yr} · World Bank", font(26, "Medium"), (148, 163, 184))
                g = ease((tr - 0.3) / 1.0)
                vmax = max(abs(va), abs(vb)) or 1
                base, top = 1480, 1060
                for v, cx, col, side in ((va, 290, BLUE, "A"), (vb, 790, RED, "B")):
                    hfrac = max(0.06, abs(v) / vmax)
                    hpx = int((base - top) * hfrac * g)
                    c = col
                    if tr >= 1.5:
                        c = GREEN if who == side else GREY
                    d.rounded_rectangle((cx - 130, base - hpx, cx + 130, base), 20, fill=c)
                    text_c(d, (cx, base - hpx - 78), fmt(v * g, kind), fit(d, fmt(v, kind), 380, 54), (255, 255, 255), 3)
                    if tr >= 1.5 and who == side:
                        pop = ease((tr - 1.5) / 0.25)
                        rr = int(40 * pop)
                        cy = base - hpx + 60 if hpx > 140 else base - hpx - 130  # inside the bar when it is tall enough
                        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=(21, 128, 61), outline=(255, 255, 255), width=4)
                        if pop > 0.6:
                            d.line((cx - 18, cy, cx - 4, cy + 14, cx + 20, cy - 16), fill=(255, 255, 255), width=8)
                        text_c(d, (cx, base + 10), "+1", font(44), GREEN, 2)
                # progress dots
                for i in range(len(cats)):
                    cxd = 540 - (len(cats) - 1) * 22 + i * 44
                    d.ellipse((cxd - 9, 1560, cxd + 9, 1578), fill=(255, 255, 255) if i <= ri else (71, 85, 105))
        p.stdin.write(np.asarray(im.convert("RGB")).tobytes())
    p.stdin.close(); p.wait()
    # ---------- audio ----------
    sr = music.SR
    mix = music.track(total, seed) * 0.55
    rng = np.random.default_rng(seed)
    voice_cache = {}
    vdir = pathlib.Path(voices) if voices else None
    vtrack = np.zeros(mix.shape[1])

    def add(arr, at, gain=1.0, stereo=True, target=None):
        i = int(at * sr)
        if i >= mix.shape[1]:
            return
        n = min(len(arr), mix.shape[1] - i)
        if target is not None:
            target[i:i + n] += arr[:n] * gain
        else:
            mix[:, i:i + n] += arr[:n] * gain
    for at, kind in events:
        if kind == "whoosh":
            add(music.whoosh(rng), at, 0.8)
        elif kind == "ding":
            add(music.ding(), at, 1.0)
        elif kind == "win":
            for j, m in enumerate((72, 76, 79, 84)):
                add(music.ding(m, 0.8), at + j * 0.12, 0.9)
        elif kind == "tick":
            add(music.tick(), at, 1.0)
        elif kind.startswith("voice:") and vdir:
            txt = kind[6:]
            f = vdir / (voice_name(txt) + ".wav")
            if f.exists():
                if txt not in voice_cache:
                    vsr, x = wavfile.read(str(f)); x = x.astype(float) / 32768
                    if x.ndim > 1:
                        x = x.mean(1)
                    if vsr != sr:
                        x = np.interp(np.arange(int(len(x) * sr / vsr)) / sr, np.arange(len(x)) / vsr, x)
                    voice_cache[txt] = x / (np.abs(x).max() + 1e-9) * 0.9
                add(voice_cache[txt], at, 1.0, target=vtrack)
    if vdir:
        intro_txt = intro_line(a, b)
        f = vdir / (voice_name(intro_txt) + ".wav")
        if f.exists():
            vsr, x = wavfile.read(str(f)); x = x.astype(float) / 32768
            x = np.interp(np.arange(int(len(x) * sr / vsr)) / sr, np.arange(len(x)) / vsr, x)
            add(x / (np.abs(x).max() + 1e-9) * 0.9, 0.3, 1.0, target=vtrack)
    # duck the music under the voice
    env = np.convolve(np.abs(vtrack), np.ones(4410) / 4410, mode="same")
    duck = 1 - 0.55 * np.clip(env / 0.05, 0, 1)
    mix = mix * duck + vtrack
    mix = mix / (np.abs(mix).max() + 1e-9) * 0.89
    wavfile.write(str(tmp / "a.wav"), sr, (mix.T * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp / "v.mp4"), "-i", str(tmp / "a.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", out], check=True)
    return {"a": a, "b": b, "cats": cats, "results": [r[0] for r in results], "seconds": total}


def hook_lines(a, b):
    """A surprising fact from the data as the opening line, then the question."""
    ca, cb = DATA["countries"][a], DATA["countries"][b]
    V = DATA["values"]
    pa, pb = V["SP.POP.TOTL"][a][0], V["SP.POP.TOTL"][b][0]
    big, small = (ca, cb) if pa > pb else (cb, ca)
    r = max(pa, pb) / min(pa, pb)
    if r >= 1.5:
        return [f"{big['en'].upper()} HAS {r:.1f}x MORE PEOPLE", "...BUT WHO WINS?"]
    ga, gb = V.get("NY.GDP.PCAP.CD", {}).get(a, [0])[0], V.get("NY.GDP.PCAP.CD", {}).get(b, [0])[0]
    if ga and gb and max(ga, gb) / min(ga, gb) >= 1.3:
        rich = ca if ga > gb else cb
        return [f"{rich['en'].upper()} IS RICHER PER PERSON", "...BUT WHO WINS?"]
    return ["ALMOST THE SAME SIZE...", "SO WHO WINS?"]


def voice_name(txt):
    import hashlib
    return hashlib.md5(txt.encode()).hexdigest()[:12]


def say(k):
    return CAT[k][0].capitalize().replace("gdp", "GDP").replace("Gdp", "GDP")


def outro_line(a, b, seed):
    res = [("A" if (DATA["values"][k][a][0] > DATA["values"][k][b][0]) == CAT[k][3] else "B") for k in choose(a, b, seed)]
    sa, sb = res.count("A"), res.count("B")
    if sa == sb:
        return "It's a tie!"
    return f"{DATA['countries'][a if sa > sb else b]['en']} wins!"


def intro_line(a, b):
    l1, l2 = hook_lines(a, b)
    l1 = l1.lower().replace("x more", " times more").rstrip(".")
    for c in (DATA["countries"][a]["en"], DATA["countries"][b]["en"]):
        l1 = l1.replace(c.lower(), c)
    return f"{DATA['countries'][a]['en']} versus {DATA['countries'][b]['en']}. {l1[0].upper() + l1[1:]}. {l2.replace('...', '').capitalize()}"


def voice_lines(a, b, seed):
    return [intro_line(a, b)] + [say(k) for k in choose(a, b, seed)] + [outro_line(a, b, seed)]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--voices")
    ap.add_argument("--lines", action="store_true", help="print the Spanish lines to synthesise, one per line")
    x = ap.parse_args()
    if x.lines:
        for l in voice_lines(x.a, x.b, x.seed):
            print(voice_name(l) + "\t" + l)
    else:
        print(json.dumps(build(x.a, x.b, x.seed, x.out, x.voices)))
