"""assets/ornek/muzik içine örnek müzik üretir: kısa, özgün chiptune parçalar.

  python tools/make_sample_music.py

Notalar kodla çalınır (kare/üçgen dalga), mpv ile ogg / mp3 / flac'a
kodlanır, mutagen ile etiketlenir. Farklı durumları denemek için:
- Gün Doğumu (ogg) ve Kadran (mp3): kapak dosyanın içinde
- Amber Işık (flac): kapak dosyanın içinde, mono ve kısa
- Kırmızı Tema (mp3): kapak yok, klasördeki cover.jpg kullanılır;
  yanında senkron söz dosyası (.lrc) var

mpv (libmpv) gerekir: soleil/audio.py'ye bak.
"""

from __future__ import annotations

import base64
import io
import shutil
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from soleil.audio import _import_mpv  # noqa: E402

OUT = ROOT / "assets" / "ornek" / "muzik"
SR = 32000

NOTES = {"C": -9, "C#": -8, "D": -7, "D#": -6, "E": -5, "F": -4, "F#": -3,
         "G": -2, "G#": -1, "A": 0, "A#": 1, "B": 2}


def freq(note: str) -> float:
    name, octave = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((NOTES[name] + (octave - 4) * 12) / 12)


def voice(notes: str, beat: float, wave_kind: str, volume: float, total: float) -> np.ndarray:
    """notes: "C4 E4 G4 - ..." (- = sus, . = önceki nota uzar)"""
    out = np.zeros(int(total * SR), dtype=np.float32)
    seq = notes.split()
    step = int(beat * SR)
    i = 0
    while i < len(seq) and i * step < len(out):
        n = seq[i]
        length = 1
        while i + length < len(seq) and seq[i + length] == ".":
            length += 1
        if n not in ("-", "."):
            t = np.arange(min(step * length, len(out) - i * step)) / SR
            f = freq(n)
            if wave_kind == "square":
                w = np.sign(np.sin(2 * np.pi * f * t)) * 0.6
            elif wave_kind == "triangle":
                w = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t))
            else:
                w = np.sin(2 * np.pi * f * t)
            env = np.minimum(1.0, t * 80) * np.exp(-t * 2.2)
            out[i * step:i * step + len(t)] += (w * env * volume).astype(np.float32)
        i += length
    return out


def song(parts, beat: float, repeats: int) -> np.ndarray:
    total = beat * max(len(p[0].split()) for p in parts) * repeats
    mix = np.zeros(int(total * SR), dtype=np.float32)
    for notes, kind, vol in parts:
        mix += voice(" ".join([notes] * repeats), beat, kind, vol, total)
    fade = int(SR * 1.5)
    mix[-fade:] *= np.linspace(1, 0, fade)
    return np.clip(mix, -1, 1)


def write_wav(path: Path, data: np.ndarray, channels: int = 2) -> None:
    pcm = (data * 30000).astype(np.int16)
    if channels == 2:
        pcm = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def encode(mpv, wav: Path, out: Path, codec: str, extra: dict) -> None:
    player = mpv.MPV(o=str(out), oac=codec, video=False, **extra)
    player.play(str(wav))
    player.wait_for_playback()
    player.terminate()


def cover(colors, label: str) -> bytes:
    """Kodla çizilmiş kare kapak (güneş + yazı yerine çizgiler)."""
    size = 300
    img = Image.new("RGB", (size, size), colors[0])
    d = ImageDraw.Draw(img)
    for y in range(size):
        k = y / size
        d.line([(0, y), (size, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(colors[0], colors[1])))
    d.ellipse([90, 70, 210, 190], fill=colors[2])
    for i in range(6):
        d.rectangle([90, 140 + i * 9, 210, 143 + i * 9], fill=colors[1])
    d.rectangle([30, 240, 270, 246], fill=colors[2])
    d.rectangle([30, 256, 30 + 20 * len(label), 260], fill=colors[2])
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def tag(path: Path, title, artist, album, track, year, art: bytes | None) -> None:
    from mutagen.flac import FLAC, Picture
    from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TRCK
    from mutagen.oggvorbis import OggVorbis

    ext = path.suffix.lower()
    if ext == ".mp3":
        tags = ID3()
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TPE1(encoding=3, text=artist))
        tags.add(TALB(encoding=3, text=album))
        tags.add(TRCK(encoding=3, text=str(track)))
        tags.add(TDRC(encoding=3, text=str(year)))
        if art:
            tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Kapak", data=art))
        tags.save(path)
        return
    audio = FLAC(path) if ext == ".flac" else OggVorbis(path)
    audio["title"], audio["artist"], audio["album"] = title, artist, album
    audio["tracknumber"], audio["date"] = str(track), str(year)
    if art:
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, "image/jpeg", art
        if ext == ".flac":
            audio.add_picture(pic)
        else:
            audio["metadata_block_picture"] = [base64.b64encode(pic.write()).decode("ascii")]
    audio.save()


SONGS = [
    # (klasör, dosya, başlık, sanatçı, albüm, sıra, yıl, codec, parçalar, vuruş, tekrar, kapak, kanal)
    ("Solshuenshia/Amber Kasetler", "01 Gün Doğumu.ogg", "Gün Doğumu", "Solshuenshia", "Amber Kasetler", 1, 2026,
     ("libvorbis", {}), [
         ("C5 E5 G5 C6 B4 D5 G5 B5 A4 C5 E5 A5 F4 A4 C5 F5", "square", 0.22),
         ("C3 . . . G2 . . . A2 . . . F2 . . .", "triangle", 0.5),
     ], 0.16, 6, ((40, 20, 70), (250, 140, 60), (255, 220, 120)), 2),
    ("Solshuenshia/Amber Kasetler", "02 Kadran.mp3", "Kadran", "Solshuenshia", "Amber Kasetler", 2, 2026,
     ("libmp3lame", {"oacopts": "b=128k"}), [
         ("E5 - E5 G5 - G5 A5 B5 A5 - G5 E5 D5 - E5 -", "square", 0.2),
         ("A2 . E3 . A2 . E3 . D3 . A2 . E2 . B2 .", "triangle", 0.55),
     ], 0.14, 7, None, 2),
    ("Solshuenshia/Amber Kasetler", "03 Amber Işık.flac", "Amber Işık", "Solshuenshia", "Amber Kasetler", 3, 2026,
     ("flac", {}), [
         ("G4 B4 D5 G5 F#5 D5 B4 A4 G4 - D5 - B4 - A4 -", "triangle", 0.35),
         ("G2 . . . D3 . . . E3 . . . C3 . . .", "sine", 0.45),
     ], 0.2, 3, None, 1),
    ("Sols/Gece Modu", "01 Kırmızı Tema.mp3", "Kırmızı Tema", "Sols", "Gece Modu", 1, 2025,
     ("libmp3lame", {"oacopts": "b=128k"}), [
         ("A4 C5 E5 A5 G5 E5 C5 E5 F4 A4 C5 F5 E5 C5 A4 C5", "square", 0.18),
         ("A2 . . . . . . . F2 . . . . . . .", "triangle", 0.55),
     ], 0.18, 5, None, 2),
]
ALBUM_COVERS = {
    "Amber Kasetler": ((40, 20, 70), (250, 140, 60), (255, 220, 120)),
    "Gece Modu": ((10, 5, 20), (160, 20, 40), (255, 90, 80)),
}
LRC = """[ti:Kırmızı Tema]
[ar:Sols]
[00:01.00]ekran kızıla döner
[00:04.00]gece yavaşça çöker
[00:07.00]ışıklar kısılır
[00:10.00]bir nota süzülür
[00:13.00]kadran döner durur
[00:16.00]sabaha az kalır
"""


def main() -> None:
    mpv = _import_mpv()
    if OUT.exists():
        shutil.rmtree(OUT)
    tmp = Path(tempfile.mkdtemp())
    for folder, name, title, artist, album, track, year, (codec, extra), parts, beat, rep, art, ch in SONGS:
        target = OUT / folder
        target.mkdir(parents=True, exist_ok=True)
        wav = tmp / "x.wav"
        write_wav(wav, song(parts, beat, rep), ch)
        encode(mpv, wav, target / name, codec, extra)
        embedded = cover(ALBUM_COVERS[album], title) if album == "Amber Kasetler" else None
        tag(target / name, title, artist, album, track, year, embedded)
    # Gece Modu: kapak klasörde, sözler .lrc dosyasında
    gece = OUT / "Sols/Gece Modu"
    (gece / "cover.jpg").write_bytes(cover(ALBUM_COVERS["Gece Modu"], "GECE"))
    (gece / "01 Kırmızı Tema.lrc").write_text(LRC, encoding="utf-8")
    shutil.rmtree(tmp)
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print(f"{p.relative_to(OUT)}: {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
