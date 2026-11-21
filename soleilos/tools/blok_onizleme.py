"""Okunuşu hece blokları halinde büyük çizer; her bloğun altında okunuşu.

  python tools/blok_onizleme.py "ego om cra va a maison" "spada de auru"
  python tools/blok_onizleme.py --dil solainwen --cikti screenshots/bloklar.png "maison"

Font yokken taslak (Latin harfler), font varsa alfabenin kendi harfleri.
Her satır ayrı bir argüman.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from soleil import script  # noqa: E402
from soleil.lang import FOLDER  # noqa: E402
from soleil.text import FONT_PATH  # noqa: E402

BG, FG, DIM = (20, 16, 14), (232, 160, 72), (130, 92, 50)
CELL, GAP = 56, 6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("satirlar", nargs="+")
    parser.add_argument("--dil", default="solainwen")
    parser.add_argument("--cikti", default=str(ROOT / "screenshots" / "bloklar.png"))
    args = parser.parse_args()

    pygame.init()
    sc = script.load(FOLDER / args.dil)
    if sc is None:
        sys.exit(f"{args.dil}: dil.json'da alfabe yok")
    small = pygame.font.Font(str(FONT_PATH), 13)
    rows = [sc.encode(line) for line in args.satirlar]
    width = max(len(r) for r in rows) * (CELL + GAP) + 40
    out = pygame.Surface((max(320, width), 30 + len(rows) * (CELL + 40)))
    out.fill(BG)
    for r, row in enumerate(rows):
        y = 20 + r * (CELL + 40)
        x = 20
        for ch in row:
            if script.is_block(ch):
                pygame.draw.rect(out, (40, 32, 28), (x - 2, y - 2, CELL + 4, CELL + 4), 1)
                out.blit(sc.render(ch, (CELL, CELL), FG, FONT_PATH), (x, y))
                label = small.render("".join(sc.decode(ch)), True, DIM)
                out.blit(label, label.get_rect(midtop=(x + CELL // 2, y + CELL + 6)))
                x += CELL + GAP
            else:
                if ch != " ":
                    img = pygame.font.Font(str(FONT_PATH), 28).render(ch, True, DIM)
                    out.blit(img, img.get_rect(center=(x + 10, y + CELL // 2)))
                x += 24
    Path(args.cikti).parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(out, args.cikti)
    print(args.cikti)


if __name__ == "__main__":
    main()
