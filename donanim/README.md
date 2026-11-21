# Hardware

The device has not been assembled yet. The parts are chosen, and the sizes of the small boards, which vary by seller, will be checked with calipers once the parts arrive.

## Parts

| Part | Choice |
|---|---|
| Computer | Raspberry Pi Zero 2 W |
| Screen | 3.5 inch, 320x480, ST7796S SPI module, no touch, adjustable backlight |
| Audio | WM8960 (headphone amp, 1 W speaker amp and microphone input on one board) |
| Microphone | A small electret capsule behind a hole in the front |
| Light bars | SK9822 / APA102 LED strip (2020 size, 4-5 mm) |
| Controls | Wheel encoder and 5 buttons |
| Battery | 4000 mAh |
| Charging and power | IP5306 charger board, ATtiny85 as the power manager |
| Battery level | MAX17048 |
| Clock | DS3231 |

The power manager is always powered from the battery and reads the power button. When the device is off, a press turns the charger board on. When it is on, presses are passed to the Pi. Holding the button for 20 seconds cuts the power without waiting for the Pi.

## Pin plan

BCM numbers:

| Part | Pins |
|---|---|
| Screen (SPI0) | MOSI 10, SCLK 11, CE0 8, DC 24, RST 25, backlight 12 (PWM) |
| Audio (I2S) | BCLK 18, LRCLK 19, microphone 20, DAC 21 |
| Light bars | data 13, clock 17, LED power (MOSFET) 15 |
| Encoder | A 5, B 6, click 26 |
| Left 1 / 2 / 3 | 16, 23, 27 |
| Top 1 / 2 | 4, 22 |
| I2C | SDA 2, SCL 3 (WM8960 0x1a, ATtiny85 0x2A, MAX17048 0x36, DS3231 0x68) |

The pin plan in SoleilOS (`soleilos/soleil/hw/pins.py`) still follows the earlier parts. It will be updated when the new parts arrive.

## Case

The case has two pieces: a front shell (the front face and the four side walls) and a back cover. All boards and parts mount to the front shell, and the back cover only closes it.

| | Size |
|---|---|
| Body | 70 x 126 x 22 mm |
| Wall thickness | 2 mm |
| Front corner radius | R4 |
| Edge rounding | R2 |

The screen is mounted upside down (180 degrees). This puts the board's connector pins at the top, so the cables do not have to run over the Pi. The image is flipped in software.

- [kasa-olculeri.svg](kasa-olculeri.svg): Case measurements
- [baglanti-semasi.svg](baglanti-semasi.svg): Wiring diagram
- [on-yuz-taslak.png](on-yuz-taslak.png): Front face sketch
- [boyut-karsilastirma.png](boyut-karsilastirma.png): Size comparison

## License

[CC BY-NC 4.0](LICENSE)
