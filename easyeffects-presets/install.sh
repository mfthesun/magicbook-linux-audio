#!/usr/bin/env bash
# Копирует пресеты (output + input) в папки EasyEffects 8.x (нативный пакет и/или Flatpak).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
targets=()
command -v easyeffects >/dev/null 2>&1 && targets+=("${XDG_DATA_HOME:-$HOME/.local/share}/easyeffects")
flatpak info com.github.wwmm.easyeffects >/dev/null 2>&1 && targets+=("$HOME/.var/app/com.github.wwmm.easyeffects/data/easyeffects")
[ ${#targets[@]} -eq 0 ] && { echo "EasyEffects не найден. Установите его и запустите один раз."; exit 1; }
for t in "${targets[@]}"; do
  for kind in output input; do
    mkdir -p "$t/$kind"; cp -v "$HERE/$kind"/*.json "$t/$kind"/
  done
done
echo "Готово. Перезапустите EasyEffects."
