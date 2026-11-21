"""Pin planı (BCM numaraları). ÖNERİ: donanım gelince değişebilir.

Pi Zero 2 W'nin 40 pinlik başlığında çakışmasın diye:

  Ekran (SPI0)        : MOSI 10, SCLK 11, CE0 8, DC 24, RST 25
  Ekran sürücüsünün ayırdıkları (piscreen overlay'i): 17 dokunmatik,
                        22 arka ışık, CE1 7 ve MISO 9 dokunmatik çipi
                        -> bunlar başka işe verilmez
  Ses (I2S)           : BCLK 18, LRCLK 19, mikrofon DIN 20, DAC/amfi DOUT 21
  Hoparlör amfisi     : MAX98357A SD (kapatma) 14
  Işık çubukları      : WS2812B veri 13 (PWM1; I2S ile çakışmasın diye 18 değil),
                        LED gücünü kesen MOSFET 15
  I2C                 : SDA 2, SCL 3 -> pil ölçümü (INA219) + güç yöneticisi (ATtiny85)
  Encoder             : A 5, B 6, tık 26
  Sol 1 / 2 / 3       : 16, 23, 27
  Üst 1 / 2           : 4, 12  (eskiden 22, 17: ekran sürücüsüyle çakışıyordu)

Tuşlar pinle GND arasına bağlanır (Pi'nin iç pull-up direnci kullanılır),
ek direnç gerekmez. Güç tuşu (logo) Pi'ye değil güç yöneticisine bağlı;
basışları Pi I2C'den okur.
"""

from __future__ import annotations

from ..input import Action

# Ekran (kernel sürücüsü kullanır; burada sadece belge için)
DISPLAY_DC = 24
DISPLAY_RST = 25
# Arka ışık: piscreen overlay'i 22'yi arka ışık olarak sürüyor
# (/sys/class/backlight). Modülde arka ışık pini yoksa (çoğu ILI9486) bağlanmaz.
DISPLAY_BACKLIGHT = 22

# Hoparlör amfisi: SD pini LOW = kapalı (kulaklık takılıyken, duraklatınca)
AMP_SHUTDOWN = 14

# Işık çubukları
LED_PIN = 13
LED_CHANNEL = 1               # GPIO13 -> PWM kanal 1
LED_POWER = 15                # LED'lerin 5V'unu kesen MOSFET (HIGH = açık)
LED_PER_BAR = 6               # her çubukta (144 LED/m şeritten ~4 cm)
LED_REVERSED_LEFT = True      # sol çubuk logodan dışa doğru dolsun

# I2C adresleri
I2C_BUS = 1
INA219_ADDR = 0x40            # pil ölçümü
RTC_ADDR = 0x68               # DS3231 saat modülü (kernel sürücüsü kullanır)
POWER_MANAGER_ADDR = 0x2A     # ATtiny85 güç yöneticisi (firmware'de aynı adres;
                              # 0x20-0x27 pin çoğaltıcılara kalsın diye)

# Encoder
ENCODER_A = 5
ENCODER_B = 6
ENCODER_BUTTON = 26
ENCODER_INVERT = False        # çevirme yönü ters gelirse True

# Tuşlar
BUTTONS = {
    16: Action.LEFT1,
    23: Action.LEFT2,
    27: Action.BACK,
    4: Action.TOP1,
    12: Action.TOP2,
}
