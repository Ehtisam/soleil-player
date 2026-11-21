"""assets/ornek/gorsel içindeki örnek görselleri üretir (hepsi kodla çizilir).

  python tools/make_sample_images.py

- Gün Batımı: retro güneş, deniz yansımaları (yatay)
- Izgara: dağlar ve perspektif ızgara (yatay)
- Dalgalar: üst üste dalgalar (dikey)
- Renk Çizelgesi: renk şeritleri, tema filtresini denemek için (büyük JPEG)
- Dikey Fotoğraf: pikselleri yatay, EXIF'te "90° döndür" yazan JPEG;
  telefon fotoğraflarının yön düzeltmesini denemek için
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "ornek" / "gorsel"


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient(draw, box, top, bottom):
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        draw.line([(x0, y), (x1, y)], fill=lerp(top, bottom, (y - y0) / max(1, y1 - y0 - 1)))


def sunset() -> Image.Image:
    w, h = 960, 640
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    horizon = 400
    gradient(d, (0, 0, w, horizon), (40, 12, 60), (250, 120, 60))
    gradient(d, (0, horizon, w, h), (60, 20, 50), (15, 8, 25))
    # Retro güneş: alt yarısı yatay boşluklarla kesik
    cx, cy, r = w // 2, horizon - 40, 150
    for y in range(cy - r, horizon):
        half = math.sqrt(max(0, r * r - (y - cy) ** 2))
        k = (y - (cy - r)) / (2 * r)
        if y > cy and int((y - cy) / 14) % 2 == 1 and (y - cy) % 14 < 2 + (y - cy) // 14:
            continue
        d.line([(cx - half, y), (cx + half, y)], fill=lerp((255, 230, 120), (255, 80, 110), k))
    # Denizde yansıma
    for i in range(18):
        y = horizon + 8 + i * 13
        span = 160 - i * 7
        d.line([(cx - span, y), (cx + span, y)], fill=lerp((255, 150, 90), (90, 30, 70), i / 18), width=3)
    return img


def grid() -> Image.Image:
    w, h = 960, 600
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    horizon = 300
    gradient(d, (0, 0, w, horizon), (10, 5, 30), (90, 30, 110))
    d.rectangle([0, horizon, w, h], fill=(12, 4, 24))
    # Dağlar
    pts = [(0, horizon)]
    for i in range(0, w + 1, 40):
        pts.append((i, horizon - 40 - 70 * abs(math.sin(i * 0.011)) - 40 * abs(math.sin(i * 0.037))))
    pts.append((w, horizon))
    d.polygon(pts, fill=(40, 12, 60), outline=(200, 80, 220))
    # Perspektif ızgara
    color = (230, 70, 200)
    for i in range(-20, 21):
        d.line([(w / 2 + i * 12, horizon), (w / 2 + i * 120, h)], fill=color, width=2)
    y, step = horizon, 6
    while y < h:
        d.line([(0, y), (w, y)], fill=color, width=2)
        step *= 1.35
        y += step
    return img


def waves() -> Image.Image:
    w, h = 640, 960
    img = Image.new("RGB", (w, h), (8, 20, 40))
    d = ImageDraw.Draw(img)
    gradient(d, (0, 0, w, 360), (250, 200, 140), (120, 160, 200))
    d.ellipse([w // 2 - 70, 120, w // 2 + 70, 260], fill=(255, 240, 200))
    for layer in range(9):
        base = 360 + layer * 68
        color = lerp((60, 140, 190), (5, 25, 60), layer / 8)
        pts = [(0, h)]
        for x in range(0, w + 1, 8):
            pts.append((x, base + 18 * math.sin(x * 0.02 + layer * 1.3) + 8 * math.sin(x * 0.051 + layer)))
        pts.append((w, h))
        d.polygon(pts, fill=color)
    return img


def chart() -> Image.Image:
    w, h = 1600, 1200
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    colors = [(255, 255, 255), (255, 220, 0), (0, 220, 230), (0, 210, 60),
              (230, 0, 210), (230, 30, 30), (20, 40, 230), (0, 0, 0)]
    bw = w // len(colors)
    for i, c in enumerate(colors):
        d.rectangle([i * bw, 0, (i + 1) * bw, int(h * 0.66)], fill=c)
    for x in range(w):           # gri ton geçişi
        v = round(255 * x / (w - 1))
        d.line([(x, int(h * 0.66)), (x, h)], fill=(v, v, v))
    return img


def portrait_photo() -> tuple[Image.Image, Image.Exif]:
    # Telefon dik tutulmuş: dosyada yatay, EXIF yönü 6 (saat yönünde 90°)
    w, h = 1200, 900
    img = Image.new("RGB", (w, h), (30, 30, 40))
    d = ImageDraw.Draw(img)
    gradient(d, (0, 0, w, h), (40, 60, 90), (200, 140, 90))
    # Dik görünmesi gereken bir kule (dosyada yatık çizilir)
    d.rectangle([200, 380, 1000, 520], fill=(240, 220, 190))
    d.polygon([(200, 340), (50, 450), (200, 560)], fill=(200, 60, 50))   # çatı: dönünce üstte
    for i in range(6):
        d.rectangle([280 + i * 120, 420, 320 + i * 120, 480], fill=(60, 50, 60))
    exif = Image.Exif()
    exif[0x0112] = 6
    return img, exif


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sunset().save(OUT / "Gün Batımı.jpg", quality=88)
    grid().save(OUT / "Izgara.png", optimize=True)
    waves().save(OUT / "Dalgalar.jpg", quality=88)
    chart().save(OUT / "Renk Çizelgesi.jpg", quality=85)
    img, exif = portrait_photo()
    img.save(OUT / "Dikey Fotoğraf.jpg", quality=85, exif=exif)
    for p in sorted(OUT.iterdir()):
        print(f"{p.name}: {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
