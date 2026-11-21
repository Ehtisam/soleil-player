# SoleilOS

The interface of the Soleil music player, written with Pygame. The device's hardware is described in the [donanim](../donanim/README.md) folder.

The interface itself is in Turkish.

## Running

```
pip install -r requirements.txt
python main.py
```

Real sound needs mpv. Without it, playback still advances but no sound comes out.
- Windows: put `libmpv-2.dll` into `~/.soleil/lib/`
  (from `mpv-dev-x86_64-*.7z` at github.com/zhongfly/mpv-winbuild)
- Pi: `sudo apt install libmpv2`

| Command | What it does |
|---|---|
| `python main.py` | 320x480, window at 2x size |
| `python main.py --figma` | 320x380, the same size as the Figma frames |
| `python main.py --scale 3` | window at 3x size (without it, the largest size that fits the screen is picked) |
| `python main.py --theme mor` | overrides the saved theme: `amber`, `mor` (purple), `kırmızı` (red), `mavi` (blue) |
| `python main.py --no-boot` | skips the boot sequence |
| `python main.py --sade` | hides the front face (light bars) under the window |
| `python main.py --cihaz pi` | SPI screen, GPIO buttons and LEDs on a Pi (picked automatically on a Pi) |

## Tests

```
python -m tests
```

The tests cover the calculator, timers, text, the Pi screen output, GPIO buttons, lights, every screen (48 screens are opened and drawn), the notebook, games, voice recording and real playback through mpv (muted). They use a temporary folder and never touch `~/.soleil`. Plain `python -m unittest` does not work, because a lock prevents it.

## Keys

The hints on the buttons and on the screen use Old Turkic letters, and together the six of them spell SOLEİL (`soleil/ui/glyphs.py`, table: `screenshots/tus-isaretleri.png`).

| Keyboard | On the device | Mark |
|---|---|---|
| Up / Down, mouse wheel | turn the encoder | |
| Enter, Right arrow | click the encoder (hold for 0.5 s: long press) | L (thin) |
| 1 / 2 | Left 1 / Left 2 | S / O |
| 3, Esc, Backspace, Left arrow | Left 3 (back) | L (bold) |
| 4 / 5 | Top 1 / Top 2 | E / İ |
| T | change the theme (for development) | |
| F12 | screenshot (`screenshots/`) | |

4 (Top 1) opens the player from anywhere.

**Player:** Turning the encoder changes the volume, a click plays or pauses, and a long press opens the action menu (shuffle, repeat, seek). 1 / 2 go to the previous / next song, 4 shows the lyrics and 5 likes the song.

**Reader (notes, e-books):** Turning the encoder scrolls 2 lines, a click goes to the next page, and a long press opens the action menu (back to start, chapters, go to end, text size). 1 / 2 go to the previous / next page and 5 changes the text size.

**Notebook:** Turning the encoder picks a letter on the dial, a click types it, and a long press opens the menu (new line, move cursor, rename, delete note). 1 deletes, 2 adds a space, 5 switches the character set (abc / ABC / 123 / .,?) and 3 goes back. Notes are saved automatically.

**Tools:** In the stopwatch, a click starts or stops, 2 records a lap and 1 resets. In the timer, the encoder sets the time, a click starts or pauses and 1 resets. In the calculator, the encoder picks a digit or an operation, a click enters it, 2 shows the result, 1 deletes and a long press clears. In the screen light, the encoder changes the color.

**Image viewer:** The encoder goes to the previous / next image, a click shows it full screen, 2 starts a slideshow, 5 rotates and 1 toggles the filter (full color / theme color).

**Radio (player):** 1 / 2 go to the previous / next station and 5 adds a favorite. Seeking and lyrics are not available.

**Voice recorder:** A click starts, pauses or resumes, 2 finishes and saves, 1 deletes (press twice) and 5 opens the recordings. Recordings are saved as OGG in `~/.soleil/medya/ses`.

**Games:** A click starts or resumes, and a long press or 3 pauses (3 again while paused quits). In Breakout the encoder moves the paddle, and in Snake it turns left or right.

## User data

Cache and private data live outside the project folder, under `~/.soleil/` (this can be changed with the `SOLEIL_HOME` environment variable):

- `settings.json`: settings (theme, brightness, screen sleep, volume, reading text...)
- `okuma.json`: where you left off in notes and books
- `oyunlar.json`: high scores in the games
- `radyo.json`: favorite radio stations
- `begeniler.json`: liked songs
- `medya/metin/`, `medya/kitap/`: your own notes (the Notebook writes here) and books (`.txt`, `.md`). A line starting with `# ` becomes a chapter heading. Samples are in `assets/ornek/`
- `medya/muzik/`: the music library (subfolders included; mp3, flac, ogg, m4a, wav, opus). A `.lrc` file next to a song is used for its lyrics
- `medya/ses/`: the files listed under Media / Sound
- `medya/gorsel/`: images (png, jpg, gif, webp...). `medya/video/` is counted but there is no video player yet
- `lib/`: `libmpv-2.dll` on Windows
- `cache/lyrics/`: lyrics that were found
- `secrets.json`: an optional Spotify cookie: `{"spotify_sp_dc": "..."}`

## Tools

- `python tools/donanim_testi.py ekran|tuslar|isik|ses|mikrofon`: tests the parts one by one on a Pi (screen, buttons, lights, sound, microphone)
- `python tools/make_sample_music.py`: composes and encodes the sample music in `assets/ornek/muzik` (needs mpv)
- `python tools/make_sample_images.py`: redraws the sample images in `assets/ornek/gorsel`
- `python tools/spotify_cookie.py`: saves the Spotify cookie (`sp_dc`) to `~/.soleil/secrets.json`

## Structure

```
main.py                startup
soleil/
  app.py               main loop, screen stack, device state
  settings.py          saved settings
  playback.py          playback state: queue, shuffle/repeat (songs with files play through mpv)
  audio.py             audio engine (mpv); without it playback is simulated
  library.py           local music library: scanning, tags, covers
  radio.py             internet radio: Radio Browser lists, favorites
  bluetooth.py         Bluetooth: bluetoothctl on a Pi, fake devices on a PC
  likes.py             liked songs
  recorder.py          voice recording: microphone (sounddevice), level, WAV -> OGG
  lyrics.py            finding lyrics: cache, LRCLIB, Spotify (optional)
  documents.py         notes and e-books: finding files, chapters, reading position
  timers.py            stopwatch and timer (keep running in the background)
  calc.py              the calculator's math
  images.py            loading images in the background (Pillow, EXIF orientation)
  sample_data.py       sample playlists, songs and files
  config.py            resolution, frame rate, folders
  theme.py             color themes
  text.py              text in Share Tech Mono (missing Turkish letters are composed)
  icons.py             tinting icons with the theme color
  input.py             encoder and 5 buttons (keyboard on a PC)
  display.py           the PC window and the front face (light bars) preview under it
  hw/                  Pi hardware: pins.py (pin plan), framebuffer.py (SPI screen),
                       gpio_input.py (buttons, encoder), leds.py (light effects,
                       WS2812B), system.py (Wi-Fi/BT, shutdown, battery)
  ui/layout.py         layout measured from Figma
  ui/chrome.py         header, bottom bar, scrollbar
  ui/listview.py       numbered menu list
  ui/marquee.py        scrolling text that does not fit
  ui/glyphs.py         button marks (Old Turkic letters) and the hint line
  ui/dial.py           the dial strip (notebook, calculator)
  screens/             screens: main menu, submenus (menus.py), playlist,
                       player and lyrics (player.py), action menus, reader
                       (reader.py), notebook (notebook.py), tools (tools.py),
                       image viewer (gallery.py), games (games/), local music
                       and media/sound (local_music.py), radio (radio.py),
                       bluetooth (bluetooth.py), voice recorder (recorder.py),
                       settings, system info, boot sequence (boot.py), placeholder
assets/
  fonts/               Share Tech Mono and its license (OFL)
  icons/               icon masks taken from Figma
  ornek/               sample notes (metin/), books (kitap/), images (gorsel/) and music (muzik/)
tools/                 sample generation, hardware test, Spotify cookie
pi/                    Pi setup: kurulum.sh, config.txt additions, service, README
```
