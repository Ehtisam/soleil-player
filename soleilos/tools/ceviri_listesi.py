"""Koddaki ekran yazılarını bir dilin çeviri tablosuna ekler.

  python tools/ceviri_listesi.py solainwen    assets/dil/solainwen/ceviri.md

Tablo Obsidian'da açılıp "Okunuş" sütunu doldurulur. Araç tekrar
çalıştırılınca yeni yazılar sona eklenir; doldurulmuş satırlara ve
sıraya dokunulmaz. Kodda artık olmayan yazılar silinmez, "Eski" başlığı
altına taşınır.

Hangi yazılar toplanır (soleil/ altındaki .py dosyalarından):
- _("...") ve N_("...") içindekiler
- app.text.draw / width / fit içindeki sabit yazılar
- ListItem, MenuItem, toast(...) içindekiler, title / TITLE / name değerleri
  (başlık yolları " / " ile parçalanır)
- (Action.X, "ETİKET") tuş ipuçları
- tamamı büyük harf olan sabit yazılar ("ÇALAN YOK", "AÇIK")
Tek harfler, sayılar, dosya yolları, iç anahtarlar, cihaz adresleri,
teknik kısaltmalar ve örnek şarkılar (sample_data.py) alınmaz. f-string
içindeki parçalar alınmaz (çeviride tutmaz); onlar kodda _("{n} şarkı")
biçiminde yazılır. Sadece f-string başlık yollarının sabit parçaları alınır.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from soleil.lang import FOLDER, key  # noqa: E402

SOURCES = ROOT / "soleil"
HEADER = "| Türkçe | Okunuş |\n|---|---|\n"
CALLS = {"_", "N_", "ListItem", "MenuItem", "toast", "Placeholder", "draw_back_row"}
TEXT_METHODS = {"draw", "width", "fit", "wrap"}
SKIP = re.compile(r"^[\W\d_]*$|^[a-z0-9_.\-/]+$|\.(png|ttf|json|md|txt|py)$|^#[0-9a-f]+$|^mid|^top|^bottom")
MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$")
# Çevrilmeyecek kısaltmalar ve adlar
TECH = {"PATH", "SSID", "RGB", "RGBA", "FLAC", "WAV", "APIC", "LRCLIB", "TR", "UNKNOWN", "KB", "MB",
        "GB", "TB", "TXT", "CPU", "RAM", "IP", "BT", "SOLEIL", "SOLSHUENSHIA ELECTRONIX", "512MB",
        "512 MB", "I2S DAC + AMFİ", "320 KBPS", "SPOTIFY", "Spotify",
        "LRC DOSYASI", "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ", "ABC", "AMBER", "SD KART", "[SD-CARD]",
        "[WI-FI]", "[BT]", "[ OK ]", "SEQUENTIA INITIALIS INCEPTIVA", "CAELUM PROPE.", "SYSTEMA PARATUM.",
        "CPU:", "// RAM:", "NOT-", "Sols", "System // Solshuenshia", "SOLSHUENSHIA // HOŞ GELDİN",
        "II", "III", "IV", "VI", "AS", "MA", "PA", "ZA", "LA", "KA"}   # Şeb ay numaraları ve kısaltmaları
SKIP_FILES = {"sample_data.py"}
UPPER_WORDS = re.compile(r"^[A-ZÇĞİÖŞÜ0-9 .,:!?%&/\-+'()\[\]…]*[A-ZÇĞİÖŞÜ]{2,}[A-ZÇĞİÖŞÜ0-9 .,:!?%&/\-+'()\[\]…]*$")
NOT_UI = {"YEREL", "DOSYA", "RADYO", "SPOTIFY"}       # iç kaynak adları da olabilir; yine de alınır


def useful(text: str) -> bool:
    text = text.strip()
    return (len(text) >= 2 and not SKIP.search(text) and not MAC.match(text)
            and text not in TECH and any(ch.isalpha() for ch in text))


def split_path(text: str) -> list[str]:
    return [p for p in text.split(" / ")] if " / " in text else [text]


class Collector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.found: list[str] = []
        self.in_fstring: set[int] = set()

    def add(self, node) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and useful(node.value):
            for part in split_path(node.value):
                if useful(part):
                    self.found.append(part.strip())

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name in CALLS:
            for arg in node.args[:2]:
                self.add(arg)
            for kw in node.keywords:
                if kw.arg in ("right", "label", "detail", "title"):
                    self.add(kw.value)
        elif name in TEXT_METHODS and isinstance(func, ast.Attribute) and \
                isinstance(func.value, ast.Attribute) and func.value.attr == "text":
            # app.text.draw(surf, "YAZI", ...) / app.text.width("YAZI", ...)
            for arg in node.args[:2]:
                self.add(arg)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
            if name in ("title", "TITLE", "name"):     # name: oyun ve araç adları
                self.add(node.value)
        self.generic_visit(node)

    def visit_Tuple(self, node: ast.Tuple) -> None:
        # (Action.LEFT1, "SİL")
        if len(node.elts) == 2 and isinstance(node.elts[0], ast.Attribute) and \
                isinstance(node.elts[0].value, ast.Name) and node.elts[0].value.id in ("Action", "A"):
            self.add(node.elts[1])
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        # Açıklama metinleri (docstring) alınmaz
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # f"{TITLE} / Albümler": yol parçaları alınır, diğer parçalar alınmaz
        for value in node.values:
            if isinstance(value, ast.Constant):
                self.in_fstring.add(id(value))
                if " / " in value.value:
                    for part in value.value.split(" / "):
                        if useful(part) and not part.strip().endswith(":"):
                            self.found.append(part.strip())
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if id(node) in self.in_fstring:
            return
        if isinstance(node.value, str) and UPPER_WORDS.match(node.value.strip()):
            self.add(node)


def collect() -> list[str]:
    seen, out = set(), []
    for path in sorted(SOURCES.rglob("*.py")):
        if path.name in SKIP_FILES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        c = Collector()
        c.visit(tree)
        for text in c.found:
            k = key(text)
            if k not in seen:
                seen.add(k)
                out.append(text)
    return out


def read_rows(path: Path) -> list[tuple[str, str]]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "Türkçe" or set(cells[0]) <= set("-: "):
            continue
        rows.append((cells[0], cells[1]))
    return rows


def write(code: str) -> tuple[int, int]:
    folder = FOLDER / code
    path = folder / "ceviri.md"
    old = read_rows(path)
    texts = collect()
    current = {key(t) for t in texts}
    known = {key(t) for t, _ in old}
    kept = [(t, r) for t, r in old if key(t) in current]
    gone = [(t, r) for t, r in old if key(t) not in current]
    new = [(t, "") for t in texts if key(t) not in known]

    def table(rows):
        lines = []
        for t, r in rows:
            t = t.replace("|", "\\|")
            lines.append(f"| {t} | {r} |\n")
        return HEADER + "".join(lines)

    body = (f"# Çeviri: {code}\n\n"
            "Sol sütun Türkçe yazı, sağ sütuna okunuşu Latin harfleriyle yaz. Boş bırakılan Türkçe görünür.\n"
            "Büyük/küçük harf fark etmez. `{n}` gibi yerler çeviride de aynen kalmalı.\n"
            "Yeni yazılar için: `python tools/ceviri_listesi.py " + code + "`\n\n"
            + table(kept + new))
    if gone:
        body += "\n## Eski\n\nKodda artık olmayan yazılar (silinebilir).\n\n" + table(gone)
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")
    return len(new), len(kept) + len(new)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    added, total = write(sys.argv[1])
    print(f"{added} yeni yazı eklendi, tabloda {total} yazı var.")
