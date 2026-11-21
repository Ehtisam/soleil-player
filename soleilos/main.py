"""SoleilOS'u başlatır.

  python main.py              320x480, ekrana sığan en büyük katla büyütülmüş pencere
  python main.py --figma      320x380, Figma frame'leriyle aynı boyut
  python main.py --scale 3    pencereyi 3 kat büyütür
  python main.py --theme mor  amber, mor, kırmızı, mavi
  python main.py --no-boot    açılış sekansını atla
  python main.py --sade       pencerede ön yüzü (ışık çubukları) gösterme
  python main.py --cihaz pi   Pi'de SPI ekran, GPIO tuşlar, LED (Pi'de kendiliğinden seçilir)

Pencerede: T tema değiştirir, F12 ekran görüntüsü alır.
"""

import argparse

from soleil import config, hw
from soleil.app import App
from soleil.screens.boot import BootScreen
from soleil.screens.main_menu import MainMenu
from soleil.theme import THEMES


def main() -> None:
    parser = argparse.ArgumentParser(description="SoleilOS")
    parser.add_argument("--figma", action="store_true", help="320x380 çalış (Figma ile karşılaştırma için)")
    parser.add_argument("--scale", type=int, default=None, help="pencere büyütme katı (verilmezse ekrana sığan en büyük kat)")
    parser.add_argument("--no-boot", action="store_true", help="açılış sekansını atla")
    parser.add_argument("--theme", default=None, choices=list(THEMES),
                        help="kayıtlı tema yerine bunu kullan")
    parser.add_argument("--cihaz", default="auto", choices=["auto", "pc", "pi"],
                        help="pc: pencere ve klavye, pi: SPI ekran, GPIO, LED (auto: kendisi anlar)")
    parser.add_argument("--sade", action="store_true", help="PC penceresinde ön yüzü (ışık çubukları) gösterme")
    args = parser.parse_args()

    height = config.FIGMA_HEIGHT if args.figma else config.HEIGHT
    device = hw.detect() if args.cihaz == "auto" else args.cihaz
    app = App(height=height, theme=args.theme, scale=args.scale, device=device, face=not args.sade)
    if app.settings.boot_animation and not args.no_boot:
        app.push(BootScreen(app, lambda: MainMenu(app)))
    else:
        app.push(MainMenu(app))
    app.run()


if __name__ == "__main__":
    main()
