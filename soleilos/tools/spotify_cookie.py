"""Spotify çerezini (sp_dc) kaydeder. Sadece Spotify'dan şarkı sözü almak için.

Çalıştırma:  python tools/spotify_cookie.py
Kopyaladığın çerezi yapıştırıp Enter'a bas. Yazdığın görünmez, bu normal.
Çerez ~/.soleil/secrets.json dosyasına yazılır (proje klasörünün dışı).
Silmek için aynı komutu çalıştırıp hiçbir şey yazmadan Enter'a bas.
"""

import getpass
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from soleil import config  # noqa: E402


def main() -> None:
    try:
        secrets = json.loads(config.SECRETS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        secrets = {}

    if sys.stdin.isatty():
        value = getpass.getpass("sp_dc çerezini yapıştır (görünmez) ve Enter'a bas: ")
    else:  # Git Bash gibi gizli girişi desteklemeyen terminaller
        value = input("sp_dc çerezini yapıştır ve Enter'a bas: ")
    value = value.strip()
    if value:
        secrets["spotify_sp_dc"] = value
    else:
        secrets.pop("spotify_sp_dc", None)

    config.SECRETS.parent.mkdir(parents=True, exist_ok=True)
    config.SECRETS.write_text(json.dumps(secrets, indent=2), encoding="utf-8")
    print(("Kaydedildi: " if value else "Çerez silindi: ") + str(config.SECRETS))


if __name__ == "__main__":
    main()
