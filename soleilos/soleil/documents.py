"""Okunacak dosyalar (notlar ve e-kitaplar) ve nerede kalındığı.

Dosyalar düz metin (.txt, .md). "# " ile başlayan satır bölüm başlığıdır;
e-kitaplarda bölüm listesi bunlardan çıkar. Boş satır paragraf ayırır,
tek satır sonu da korunur (notlardaki listeler bozulmasın diye).

Dosyalar iki yerden toplanır: kullanıcının klasörü (~/.soleil/medya/...)
ve assets/ornek içindeki örnekler. Okuma yerleri ~/.soleil/okuma.json'da.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import config

EXTENSIONS = {".txt", ".md"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
AUDIO_EXTENSIONS = {".mp3", ".ogg", ".flac", ".wav", ".m4a", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
KINDS = {"metin": "TXT", "kitap": "E-Kitap"}
READING_PATH = config.DATA / "okuma.json"


@dataclass(frozen=True)
class Document:
    name: str      # dosya adı, uzantısız
    path: Path
    kind: str      # "metin", "kitap" ya da "gorsel"
    sample: bool   # assets/ornek içinden mi

    @property
    def key(self) -> str:
        """Okuma kaydındaki anahtar; örnekler kullanıcı dosyalarıyla karışmasın."""
        return f"{'ornek/' if self.sample else ''}{self.kind}/{self.path.name}"

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    def read(self) -> str:
        data = self.path.read_bytes()
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1254", errors="replace")   # eski Windows Türkçe
        return text.replace("\r\n", "\n").replace("\t", "    ")


def list_documents(kind: str, extensions=EXTENSIONS) -> list[Document]:
    """kind klasöründeki dosyalar (metin, kitap, gorsel); önce kullanıcınınkiler."""
    docs = []
    for folder, sample in ((config.MEDIA / kind, False), (config.SAMPLES / kind, True)):
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in extensions:
                docs.append(Document(path.stem, path, kind, sample))
    return sorted(docs, key=lambda d: (d.sample, d.name.casefold()))


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{round(size)}{unit}"
        size /= 1024
    return ""


# -- metni bloklara ayırma ---------------------------------------------------

@dataclass(frozen=True)
class Block:
    kind: str      # "heading", "line" ya da "gap" (paragraf arası)
    text: str
    offset: int    # metnin başından itibaren karakter konumu


def parse(text: str) -> list[Block]:
    blocks: list[Block] = []
    offset = 0
    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.startswith("# "):
            blocks.append(Block("heading", line[2:].strip(), offset))
        elif not line.strip():
            if blocks and blocks[-1].kind != "gap":
                blocks.append(Block("gap", "", offset))
        else:
            blocks.append(Block("line", line, offset))
        offset += len(raw) + 1
    while blocks and blocks[-1].kind == "gap":
        blocks.pop()
    return blocks


# -- nerede kalındı ----------------------------------------------------------

class ReadingLog:
    """Her dosya için en üstte görünen satırın konumu ve okunma yüzdesi.
    Okuyucu kapanınca diske yazılır."""

    def __init__(self, data: dict, enabled: bool) -> None:
        self.data = data
        self.enabled = enabled

    @classmethod
    def load(cls, enabled: bool = True) -> "ReadingLog":
        if not enabled:
            return cls({}, False)
        try:
            data = json.loads(READING_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        return cls(data if isinstance(data, dict) else {}, True)

    def get(self, doc: Document) -> tuple[int, float] | None:
        entry = self.data.get(doc.key)
        if not isinstance(entry, dict):
            return None
        return int(entry.get("offset", 0)), float(entry.get("progress", 0.0))

    def set(self, doc: Document, offset: int, progress: float) -> None:
        self.data[doc.key] = {"offset": offset, "progress": round(progress, 3)}

    def save(self) -> None:
        if not self.enabled:
            return
        try:
            READING_PATH.parent.mkdir(parents=True, exist_ok=True)
            READING_PATH.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"[okuma] kaydedilemedi: {e}")

    def label(self, doc: Document) -> str:
        """Listelerde sağdaki etiket: hiç açılmadıysa YENİ, yoksa yüzde."""
        entry = self.get(doc)
        if entry is None:
            return "[YENİ]"
        return f"[%{round(entry[1] * 100)}]"
