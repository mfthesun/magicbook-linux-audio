#!/usr/bin/env bash
# Выбор режима микрофона гарнитуры HONOR DRA-XX (параметр honor_dra_mic модуля Realtek HDA, DKMS honor-dra-fix >= 2.2).
#   0 = только пины (микрофон не работает, для сравнения)   1 = штатный headset mode + подстраховка по пину
#   2 = принудительно CTIA                                   3 = как фикс HONOR BRB-X
#   4 = штатный headset mode, авто CTIA/OMTP (по умолчанию, как в апстрим-патче)
# Использование: ./set-mic-mode.sh <0|1|2|3|4>   |   ./set-mic-mode.sh --status
# Вступает в силу после перезагрузки.
set -euo pipefail
CONF=/etc/modprobe.d/honor-dra-mic.conf
MOD=snd_hda_codec_alc269
modinfo "$MOD" >/dev/null 2>&1 || MOD=snd_hda_codec_realtek   # ядра < 6.17

status() {
  echo "модуль:            $MOD ($(modinfo -n "$MOD" 2>/dev/null))"
  echo "в конфиге:         $(cat "$CONF" 2>/dev/null || echo '(нет, действует значение по умолчанию = 4)')"
  echo "загружено сейчас:  honor_dra_mic=$(cat /sys/module/$MOD/parameters/honor_dra_mic 2>/dev/null || echo '? (модуль без параметра или не загружен)')"
}
case "${1:-}" in
  --status|"") status; [ -n "${1:-}" ] || echo "Использование: $0 <0|1|2|3|4> | --status"; exit 0;;
  0|1|2|3|4) ;;
  *) echo "Режим должен быть 0, 1, 2, 3 или 4"; exit 1;;
esac
modinfo -p "$MOD" 2>/dev/null | grep -q honor_dra_mic || {
  echo "Установленный модуль не имеет параметра honor_dra_mic. Выполните ./install.sh (нужна версия 2.2)."; exit 1; }
echo "options $MOD honor_dra_mic=$1" | sudo tee "$CONF" >/dev/null
KREL="$(uname -r)"
if command -v update-initramfs >/dev/null; then sudo update-initramfs -u -k "$KREL"
elif command -v dracut >/dev/null; then sudo dracut -f --kver "$KREL"
elif command -v make-initrd >/dev/null; then sudo make-initrd -k "$KREL"; fi
status
echo "Перезагрузитесь, чтобы режим $1 вступил в силу."
