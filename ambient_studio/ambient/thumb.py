"""Thumbnail: the theme's hero frame, graded, with a short bold headline. python -m ambient.thumb '<plan json>' out.jpg"""
from __future__ import annotations
import json, pathlib, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from .themes import THEMES
from .build2 import ROOT, fetch

TEXT = {"rain": ("RAIN SOUNDS", "FOR SLEEP", (120, 200, 255)), "ocean": ("OCEAN WAVES", "TO RELAX", (90, 230, 235)),
        "river": ("RIVER SOUNDS", "FOR FOCUS", (130, 255, 190)), "storm": ("THUNDERSTORM", "DEEP SLEEP", (255, 220, 90)),
        "snow": ("SNOWFALL", "WINTER CALM", (170, 215, 255)), "autumn": ("AUTUMN RAIN", "COZY & CALM", (255, 175, 90))}
FONT = ROOT / "fonts" / "Poppins-Bold.ttf"


def frame(kind: str, out: pathlib.Path) -> None:
    src = fetch(THEMES[kind]["video"][0])
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], capture_output=True, text=True, check=True).stdout)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(min(d, 30) * 0.45), "-i", str(src), "-frames:v", "1", str(out)], check=True)


def outlined(dr, xy, text, font, fill, width=7):
    x, y = xy
    for dx in range(-width, width + 1, 2):
        for dy in range(-width, width + 1, 2):
            if dx * dx + dy * dy <= width * width:
                dr.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    dr.text(xy, text, font=font, fill=fill)


def make(plan: dict, out: str) -> None:
    kind = plan["kind"]; top, bottom, accent = TEXT[kind]
    with tempfile.TemporaryDirectory() as t:
        fr = pathlib.Path(t) / "f.png"; frame(kind, fr)
        im = Image.open(fr).convert("RGB")
    w, h = im.size; s = max(1280 / w, 720 / h)
    im = im.resize((int(w * s) + 1, int(h * s) + 1), Image.LANCZOS)
    im = im.crop(((im.width - 1280) // 2, (im.height - 720) // 2, (im.width - 1280) // 2 + 1280, (im.height - 720) // 2 + 720))
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.35)).enhance(1.12)
    # dark gradient from the left and bottom so the text is always readable
    shade = Image.new("L", (1280, 720), 0); px = shade.load()
    for x in range(1280):
        for y in range(720):
            px[x, y] = int(min(255, max(0, 190 * (1 - x / 900)) + max(0, 150 * (y - 450) / 270)))
    im = Image.composite(Image.new("RGB", (1280, 720), (0, 0, 0)), im, shade.filter(ImageFilter.GaussianBlur(30)))
    dr = ImageDraw.Draw(im)
    f1, f2, f3 = (ImageFont.truetype(str(FONT), n) for n in (118, 96, 52))
    outlined(dr, (60, 150), top, f1, (255, 255, 255))
    outlined(dr, (60, 290), bottom, f2, accent)
    mins = round(plan["hours"] * 60)
    label = f"{mins} MIN"
    tw = dr.textlength(label, font=f3)
    dr.rounded_rectangle((60, 560, 60 + tw + 50, 640), radius=14, fill=(0, 0, 0))
    dr.text((85, 565), label, font=f3, fill=(255, 255, 255))
    im.save(out, "JPEG", quality=92)


if __name__ == "__main__":
    make(json.loads(sys.argv[1]), sys.argv[2])
