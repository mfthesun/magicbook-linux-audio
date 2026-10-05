#!/usr/bin/env bash
# ТЕСТ: включить/выключить привязку нижних динамиков (0x1b) к ЦАП 0x02 (DKMS honor-dra-fix >= 2.2, параметр honor_dra_share_dac).
#   1 = привязка есть (штатное поведение фикса, по умолчанию)
#   0 = без привязки: только описания пинов, как у фикса HONOR MRB-XXX и после апстрим-исправления 0003.
#   На звук не влияет: 0x1b и без привязки подключён к ЦАП 0x02 (проверено 03-05.10.2026).
# Использование: ./set-dac-share.sh <0|1>   |   ./set-dac-share.sh --status      Нужна перезагрузка.
# Откат: ./set-dac-share.sh 1 и перезагрузка.
set -euo pipefail
CONF=/etc/modprobe.d/honor-dra-dac.conf
MOD=snd_hda_codec_alc269
modinfo "$MOD" >/dev/null 2>&1 || MOD=snd_hda_codec_realtek
status() {
  echo "в конфиге:         $(cat "$CONF" 2>/dev/null || echo '(нет, по умолчанию 1)')"
  echo "загружено сейчас:  honor_dra_share_dac=$(cat /sys/module/$MOD/parameters/honor_dra_share_dac 2>/dev/null || echo '? (нет параметра)')"
}
case "${1:-}" in
  --status|"") status; exit 0;;
  0|1) ;;
  *) echo "Режим должен быть 0 или 1"; exit 1;;
esac
modinfo -p "$MOD" 2>/dev/null | grep -q honor_dra_share_dac || { echo "Модуль без параметра honor_dra_share_dac: выполните ./install.sh"; exit 1; }
if [ "$1" = 1 ]; then sudo rm -f "$CONF"; else echo "options $MOD honor_dra_share_dac=0" | sudo tee "$CONF" >/dev/null; fi
KREL="$(uname -r)"
if command -v update-initramfs >/dev/null; then sudo update-initramfs -u -k "$KREL"
elif command -v dracut >/dev/null; then sudo dracut -f --kver "$KREL"
elif command -v make-initrd >/dev/null; then sudo make-initrd -k "$KREL"; fi
status; echo "Перезагрузитесь."
