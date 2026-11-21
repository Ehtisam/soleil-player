# Installing SoleilOS on a Pi

These are the steps for when the parts arrive. The setup script and the settings are ready, but **they have not been tried on a real Pi yet**. Places marked "DENENECEK" (to be tested) will be checked during the first install.

## 1. SD card
- Raspberry Pi Imager: **Raspberry Pi OS Lite (64-bit)**
- In the Imager settings: username and password, Wi-Fi, SSH on, time zone Istanbul

## 2. Copying the code to the Pi
From a computer (if the Pi is named `soleil.local`):
```
scp -r soleilos soleil@soleil.local:~/
```

## 3. Setup
On the Pi:
```
cd ~/soleilos
sudo bash pi/kurulum.sh
sudo reboot
```
The script installs the packages, adds the screen and audio settings to `config.txt` (keeping the old one as `config.txt.soleil-yedek`) and starts SoleilOS at boot.

## 4. Testing the parts one by one
Stop SoleilOS first:
```
sudo systemctl stop soleil
sudo /opt/soleil/venv/bin/python /opt/soleil/soleilos/tools/donanim_testi.py ekran
```
In order: `ekran` (screen), `tuslar` (buttons), `isik` (lights), `ses` (sound), `mikrofon` (microphone). When done, run `sudo systemctl start soleil`.

| Problem | Where to look |
|---|---|
| Screen does not turn on | `ls /dev/fb*`, `dmesg \| grep -i fb`; lower `speed` in `config.txt` |
| Image is sideways | `rotate=180` instead of `rotate=0` in `config.txt` (or 90/270, but it must be portrait) |
| Colors are swapped (red and blue) | the driver is BGR: to be fixed in code |
| Encoder turns the wrong way | `soleil/hw/pins.py`: `ENCODER_INVERT = True` |
| No sound | does `aplay -l` see the card; if not, `hifiberry-dac` in `config.txt` |
| Lights do not turn on | is the data pin GPIO13, are the strip's 5V and GND connected |

## Pin plan
In `soleil/hw/pins.py` (BCM numbers):

| Part | Pins |
|---|---|
| Screen (SPI0) | MOSI 10, SCLK 11, CE0 8, DC 24, RST 25 (22 if there is a backlight pin) |
| Reserved by the screen driver | 17, 22, 7, 9 (touch and backlight; not used for anything else) |
| Audio (I2S) | BCLK 18, LRCLK 19, microphone 20, DAC/amp 21 |
| Speaker amp shutdown | 14 |
| Light bars | data 13, LED power (MOSFET) 15 |
| Encoder | A 5, B 6, click 26 |
| Left 1 / 2 / 3 | 16, 23, 27 |
| Top 1 / 2 | 4, 12 |
| I2C: battery level and power manager | 2, 3 |

The buttons connect between the pin and GND, with no extra resistor needed.

This pin plan follows the earlier parts. The plan for the current parts is in [donanim](../../donanim/README.md).

## Shutting down
(This is the old power plan. The new plan has a power button on the logo and a power manager.) Before switching the power off, use **Sistem Ayarları > Cihazı Kapat** (System Settings > Shut Down, press twice). The SD card can get corrupted if power is cut while it is being written. The system will be made read-only later.

## Logs
```
journalctl -u soleil -f
```
