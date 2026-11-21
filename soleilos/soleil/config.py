import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SCREENSHOTS = ROOT / "screenshots"

# Kullanıcı verisi proje klasörünün dışında: önbellek ve gizli bilgiler
# (ör. Spotify çerezi) Obsidian kasasına ya da paylaşılan yerlere düşmesin.
DATA = Path(os.environ.get("SOLEIL_HOME", Path.home() / ".soleil"))
CACHE = DATA / "cache"
SECRETS = DATA / "secrets.json"

# Kullanıcının dosyaları: medya/metin (notlar, .txt) ve medya/kitap (e-kitap).
# Pi'de SD kartta aynı yer. Örnek dosyalar assets/ornek içinde.
MEDIA = DATA / "medya"
SAMPLES = ASSETS / "ornek"

# 3.5" ekran, dikey
WIDTH = 320
HEIGHT = 480

# Figma frame'lerinin yüksekliği. --figma ile bu boyutta çalışıp
# tasarımla birebir karşılaştırma yapılabilir.
FIGMA_HEIGHT = 380

# Animasyon varken ve ekran sabitken kare hızı (işlemci ve pil için)
FPS_ACTIVE = 30
FPS_IDLE = 10
