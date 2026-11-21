#!/usr/bin/env bash
# SoleilOS'u Raspberry Pi OS Lite (64 bit, Bookworm) üzerine kurar.
#
#   sudo bash pi/kurulum.sh
#
# Ne yapar:
#   1. Gerekli paketleri kurar (pygame, mpv, gpiozero, ses...)
#   2. Python ortamını hazırlar (/opt/soleil/venv), LED kütüphanesini ekler
#   3. config.txt'ye ekran, ses ve SPI ayarlarını ekler (eskisini yedekler)
#   4. SoleilOS'u açılışta başlayan servis yapar
#
# Tekrar çalıştırmak zararsızdır. Gerçek Pi'de HENÜZ DENENMEDİ; ekran ve ses
# ayarları parçalar gelince doğrulanacak (bkz. pi/README.md).

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "root olarak çalıştır: sudo bash pi/kurulum.sh" >&2
    exit 1
fi

SRC="$(cd "$(dirname "$0")/.." && pwd)"          # soleilos klasörü
TARGET=/opt/soleil
USER_NAME="${SUDO_USER:-pi}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
CONFIG=/boot/firmware/config.txt
[[ -f $CONFIG ]] || CONFIG=/boot/config.txt

echo "== 1/4 paketler"
apt-get update
apt-get install -y \
    python3-venv python3-pip python3-pygame python3-numpy python3-pil \
    python3-mutagen python3-mpv libmpv2 python3-gpiozero python3-lgpio \
    python3-sounddevice libportaudio2 rfkill alsa-utils rsync \
    bluez bluez-alsa-utils i2c-tools
# Saat modülü (DS3231) var: sahte saat (son kapanış saatini hatırlayan) gereksiz
apt-get remove -y fake-hwclock || true

echo "== 2/4 python ortamı ve kod"
mkdir -p "$TARGET"
rsync -a --delete --exclude screenshots --exclude __pycache__ "$SRC/" "$TARGET/soleilos/"
if [[ ! -d $TARGET/venv ]]; then
    python3 -m venv --system-site-packages "$TARGET/venv"
fi
"$TARGET/venv/bin/pip" install --quiet rpi_ws281x

echo "== 3/4 config.txt ($CONFIG)"
if ! grep -q "# --- SoleilOS ---" "$CONFIG"; then
    cp "$CONFIG" "$CONFIG.soleil-yedek"
    cat "$SRC/pi/config.txt" >> "$CONFIG"
    echo "   eklendi (yedek: $CONFIG.soleil-yedek)"
else
    echo "   zaten var, dokunulmadı"
fi

echo "== 4/4 servis"
mkdir -p "$USER_HOME/.soleil/medya"
chown -R "$USER_NAME:$USER_NAME" "$USER_HOME/.soleil"
sed "s|__SOLEIL_HOME__|$USER_HOME/.soleil|" "$SRC/pi/soleil.service" > /etc/systemd/system/soleil.service
systemctl daemon-reload
systemctl enable soleil.service

echo
echo "Bitti. Yeniden başlat: sudo reboot"
echo "Kayıtları izlemek için: journalctl -u soleil -f"
